"""
Parser PDF da Portaria SAIF 062/2025 — extrai PMPF dos anexos (pdfplumber).

Opção A (2026-04): NCM fixo por anexo com dicionário `ANEXO_NCM_MG` codificado
e documentado em `doc/mg_pmpf_mapping.md`. As tabelas da portaria não trazem
coluna NCM — o NCM inequivoco por produto vem do mapeamento anexo → NCM.

Primeiro entregável: apenas **Anexo I** (refrigerantes → 22021000).
Demais anexos reconhecidos mas ignorados até extensão do mapeamento.

Campos opcionais em `RegraNormativa`: `pmpf_reais`, `marca_produto`,
`embalagem_ml`, `observacao`; ver `app/services/pipeline_normativo.py`.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import date
from typing import Any

from app.services.parsers.base_parser import (
    BaseParser,
    DiagnosticoHTTP,
    ResultadoParser,
    fetch_com_diagnostico,
)
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

_URL_PDF_ANEXOS = (
    "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/"
    "portarias/2025/port_saif062_2025_anexos.pdf"
)

_FONTE_LEGAL_BASE = "Portaria SAIF 062/2025"
_IMPORTADO_POR = "sefaz_mg_pdf_parser_v1"
_VIGENCIA_INICIO = date(2026, 1, 1)
_VIGENCIA_FIM = date(2026, 6, 30)

# Alíquota interna ICMS MG na ausência de coluna específica na portaria (RICMS).
_ALIQUOTA_PADRAO_MG = 0.18

_TIMEOUT_PDF = 30.0

# Mapeamento anexo romano → NCM (8 dígitos, sem pontos). Estender quando novos
# anexos forem importados — consultar doc/mg_pmpf_mapping.md e legislação.
ANEXO_NCM_MG: dict[str, str] = {
    "I": "22021000",
    # II: bebidas hidroeletrolíticas — rever NCM se política de ST divergir
    "II": "22021000",
    "III": "22021000",
}

_PADRAO_ANEXO = re.compile(
    r"ANEXO\s+([IVXLCDM]+)\b",
    re.IGNORECASE,
)
_PADRAO_VOLUME = re.compile(r"(\d{2,5})\s*ml", re.IGNORECASE)
_PADRAO_VALOR = re.compile(r"R?\$?\s*(\d{1,4}[,\.]\d{2})")


class SefazMGPdfParser(BaseParser):
    """
    Extrai PMPF do PDF anexo da SAIF 062/2025 (Anexo I — refrigerantes).

    Layouts suportados no PDF oficial:
    - **Largo** (Anexo I): colunas ITEM duplicadas / mesclas — detectado por
      linha com ≥2 células «ITEM» e largura da linha.
    - **Compacto** (Anexos II e III): ITEM | EMBALAGEM | MARCA | CÓDIGO | PMPF.
    """

    nome = "SEFAZ-MG-PDF"
    url_base = _URL_PDF_ANEXOS

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        diagnosticos: list[DiagnosticoHTTP] = []

        resp, diag = fetch_com_diagnostico(_URL_PDF_ANEXOS, timeout=_TIMEOUT_PDF)
        diagnosticos.append(diag)

        if resp is None:
            erros.append(
                f"SEFAZ-MG-PDF: GET falhou — {diag.erro or 'sem detalhe'} "
                f"(url={_URL_PDF_ANEXOS})"
            )
            return _resultado(regras, erros, diagnosticos)

        if resp.status_code != 200:
            erros.append(
                f"SEFAZ-MG-PDF: GET retornou status={resp.status_code} "
                f"bytes={diag.bytes_recebidos} (url={_URL_PDF_ANEXOS})"
            )
            return _resultado(regras, erros, diagnosticos)

        if not _parece_pdf(resp.content or b""):
            erros.append(
                "SEFAZ-MG-PDF: resposta não começa com '%PDF-' — content-type="
                f"{diag.content_type or '?'} bytes={diag.bytes_recebidos}. "
                "Servidor pode ter devolvido página HTML de erro/redirect."
            )
            return _resultado(regras, erros, diagnosticos)

        regras_extraidas, erros_pdf = extrair_regras_mg_pdf_de_bytes(resp.content)
        regras.extend(regras_extraidas)
        erros.extend(erros_pdf)

        if not regras_extraidas:
            erros.append(
                "SEFAZ-MG-PDF: PDF aberto mas nenhuma linha PMPF reconhecida "
                "(Anexo I). Verificar doc/mg_pmpf_mapping.md e layout do PDF."
            )

        return _resultado(regras, erros, diagnosticos)


def extrair_regras_mg_pdf_de_bytes(
    conteudo: bytes,
    *,
    apenas_anexos: frozenset[str] | None = None,
) -> tuple[list[RegraNormativa], list[str]]:
    """
    Extrai regras a partir dos bytes do PDF SAIF 062/2025.

    `apenas_anexos`: por defeito só romano ``I`` (refrigerantes).
    """
    if apenas_anexos is None:
        apenas_anexos = frozenset({"I"})
    return _extrair_regras_do_pdf_bytes(conteudo, apenas_anexos=apenas_anexos)


def _resultado(
    regras: list[RegraNormativa],
    erros: list[str],
    diagnosticos: list[DiagnosticoHTTP],
) -> ResultadoParser:
    return ResultadoParser(
        regras=regras,
        erros=erros,
        fonte=_FONTE_LEGAL_BASE + " — Anexo I (PDF)",
        url_consultada=_URL_PDF_ANEXOS,
        data_consulta=date.today().isoformat(),
        diagnostico=diagnosticos,
    )


def _parece_pdf(conteudo: bytes) -> bool:
    return conteudo[:5] == b"%PDF-"


def _extrair_regras_do_pdf_bytes(
    conteudo: bytes,
    *,
    apenas_anexos: frozenset[str],
) -> tuple[list[RegraNormativa], list[str]]:
    erros: list[str] = []
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except Exception as exc:
        erros.append(
            f"SEFAZ-MG-PDF: pdfplumber indisponível — {exc}. "
            "Instalar dependência `pdfplumber`."
        )
        return [], erros

    regras: list[RegraNormativa] = []
    preview_logged = 0
    anexo_ctx: str | None = None

    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            logger.info(
                "SEFAZ-MG-PDF: PDF aberto — %d página(s), %d bytes",
                len(pdf.pages),
                len(conteudo),
            )
            for idx_pagina, page in enumerate(pdf.pages, start=1):
                texto_pag = page.extract_text() or ""
                ax_txt = _ultimo_anexo_no_texto(texto_pag)
                if ax_txt:
                    anexo_ctx = ax_txt

                try:
                    tabelas = page.extract_tables() or []
                except Exception as exc:
                    erros.append(
                        f"SEFAZ-MG-PDF: extract_tables falhou na página "
                        f"{idx_pagina}: {exc}"
                    )
                    continue

                for idx_tabela, tabela in enumerate(tabelas, start=1):
                    if not tabela:
                        continue
                    ax_tab = _detectar_anexo_na_tabela(tabela)
                    anexo = ax_tab or anexo_ctx
                    if ax_tab:
                        anexo_ctx = ax_tab

                    if preview_logged < 3:
                        for linha in tabela[:3]:
                            preview_logged += 1
                            logger.info(
                                "SEFAZ-MG-PDF preview pag=%d tab=%d: %s",
                                idx_pagina,
                                idx_tabela,
                                linha,
                            )
                            if preview_logged >= 3:
                                break

                    if not anexo:
                        continue
                    if anexo not in apenas_anexos:
                        continue
                    if anexo not in ANEXO_NCM_MG:
                        erros.append(
                            f"SEFAZ-MG-PDF: anexo «{anexo}» sem entrada em "
                            "ANEXO_NCM_MG — ignorado."
                        )
                        continue

                    ncm_fixo = ANEXO_NCM_MG[anexo]
                    extraidas = _extrair_regras_de_tabela(tabela, anexo_romano=anexo, ncm_fixo=ncm_fixo)
                    regras.extend(extraidas)

    except Exception as exc:
        erros.append(f"SEFAZ-MG-PDF: pdfplumber.open falhou: {exc}")
        return regras, erros

    return regras, erros


def _ultimo_anexo_no_texto(texto: str) -> str | None:
    ultimo: str | None = None
    for m in _PADRAO_ANEXO.finditer(texto):
        ultimo = m.group(1).upper()
    return ultimo


def _detectar_anexo_na_tabela(tabela: list[list[str | None]]) -> str | None:
    for ri in range(min(4, len(tabela))):
        linha = tabela[ri]
        for cel in linha:
            if not cel:
                continue
            m = _PADRAO_ANEXO.search(str(cel).replace("–", "-").replace("—", "-"))
            if m:
                return m.group(1).upper()
    return None


def _extrair_regras_de_tabela(
    tabela: list[list[str | None]],
    *,
    anexo_romano: str,
    ncm_fixo: str,
) -> list[RegraNormativa]:
    mapeamento = _mapear_colunas_saif(tabela)
    if mapeamento is None:
        return []

    cols, primeira_linha, _fmt = mapeamento
    regras: list[RegraNormativa] = []
    vistos: set[tuple[str, float, str, int | None]] = set()

    for linha in tabela[primeira_linha:]:
        regra = _extrair_regra_da_linha(
            linha,
            cols,
            anexo_romano=anexo_romano,
            ncm_fixo=ncm_fixo,
        )
        if regra is None:
            continue
        emb = regra.embalagem_ml
        chave = (regra.ncm, float(regra.pmpf_reais or 0), (regra.marca_produto or ""), emb)
        if chave in vistos:
            continue
        vistos.add(chave)
        regras.append(regra)

    return regras


def _mapear_colunas_saif(
    tabela: list[list[str | None]],
) -> tuple[dict[str, int], int, str] | None:
    """
    Devolve (cols, primeira_linha_dados, formato) com formato «compacto» ou «largo».
    """
    for i in range(min(6, len(tabela))):
        linha = tabela[i]
        if not linha:
            continue
        linha_str = [_normalizar(c) for c in linha]
        item_dup = sum(1 for t in linha_str if t == "item")
        largura = len(linha)
        if (
            largura >= 10
            and item_dup >= 2
            and any("marca" == t for t in linha_str)
            and any("pmpf" in t for t in linha_str)
        ):
            cols = _cols_layout_largo(linha)
            if cols:
                pri = i + 1
                if pri < len(tabela) and _linha_e_subtitulo_fabricante(tabela[pri]):
                    pri += 1
                return cols, pri, "largo"

        if (
            _normalizar(_celula(linha, 0)) == "item"
            and largura <= 8
            and any("embalagem" in t for t in linha_str)
            and any("pmpf" in t for t in linha_str)
        ):
            cols = {
                "item": 0,
                "embalagem": 1,
                "marca": 2,
                "pmpf": min(len(linha) - 1, 4),
            }
            return cols, i + 1, "compacto"

    return None


def _cols_layout_largo(linha: list[str | None]) -> dict[str, int] | None:
    """
    Cabeçalho tipo Anexo I — colunas deslocadas vs linha de dados.
    """
    item_idxs = [ci for ci, c in enumerate(linha) if _normalizar(c) == "item"]
    if not item_idxs:
        return None
    item_col = max(item_idxs)

    emb_col = marca_col = pmpf_col = None
    for ci, c in enumerate(linha):
        n = _normalizar(c)
        if "embalagem" in n:
            emb_col = ci + 1
        elif n == "marca":
            marca_col = ci + 1
        elif "pmpf" in n:
            pmpf_col = ci

    if emb_col is None or marca_col is None or pmpf_col is None:
        return None

    pmpf_idxs = [ci for ci, c in enumerate(linha) if "pmpf" in (_normalizar(c) or "")]
    if pmpf_idxs:
        pmpf_col = max(pmpf_idxs)

    return {
        "item": item_col,
        "embalagem": emb_col,
        "marca": marca_col,
        "pmpf": pmpf_col,
    }


def _linha_e_subtitulo_fabricante(linha: list[str | None]) -> bool:
    return any("fabricante" in (_normalizar(c) or "") for c in linha)


def _extrair_regra_da_linha(
    linha: list[str | None],
    cols: dict[str, int],
    *,
    anexo_romano: str,
    ncm_fixo: str,
) -> RegraNormativa | None:
    item_cel = _celula(linha, cols["item"])
    if not item_cel.isdigit():
        return None

    pmpf_cel = _celula(linha, cols["pmpf"])
    pmpf = _parse_valor(pmpf_cel)
    if pmpf is None or pmpf <= 0:
        return None

    marca_cel = _celula(linha, cols["marca"])
    emb_cel = _celula(linha, cols["embalagem"])

    emb_ml = _parse_volume(emb_cel) or _parse_volume(marca_cel) or 0
    marca = _limpar_marca(marca_cel)

    obs = (
        f"Mapeamento anexo {anexo_romano} → NCM {ncm_fixo} (fixo por anexo; "
        "ver doc/mg_pmpf_mapping.md)."
    )
    fonte = (
        f"{_FONTE_LEGAL_BASE}, Anexo {anexo_romano} | map→{ncm_fixo} | "
        f"{marca} | {emb_cel} | R${pmpf:.2f}"
    )

    return RegraNormativa(
        estado="MG",
        ncm=ncm_fixo,
        mva=0.0,
        aliquota_interna=_ALIQUOTA_PADRAO_MG,
        vigencia_inicio=_VIGENCIA_INICIO,
        vigencia_fim=_VIGENCIA_FIM,
        fonte_legal=fonte,
        url_fonte=_URL_PDF_ANEXOS,
        nivel_confianca="candidata_oficial",
        importado_por=_IMPORTADO_POR,
        observacao=obs,
        pmpf_reais=pmpf,
        marca_produto=marca or "—",
        embalagem_ml=emb_ml if emb_ml > 0 else None,
    )


def _celula(linha: list[str | None], idx: int | None) -> str:
    if idx is None or idx < 0 or idx >= len(linha):
        return ""
    return (linha[idx] or "").strip()


def _normalizar(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def _parse_valor(s: str) -> float | None:
    if not s:
        return None
    m = _PADRAO_VALOR.search(s)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _parse_volume(s: str) -> int | None:
    if not s:
        return None
    m = _PADRAO_VOLUME.search(s)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _limpar_marca(s: str) -> str:
    if not s:
        return ""
    sem_volume = _PADRAO_VOLUME.sub("", s)
    sem_valor = _PADRAO_VALOR.sub("", sem_volume)
    limpo = re.sub(r"\s+", " ", sem_valor).strip(" -|\t\n")
    return limpo

