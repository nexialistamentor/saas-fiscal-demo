"""
Parser PDF da Portaria SAIF 062/2025 — extrai tabela PMPF dos anexos.

Contexto (2026-04-28):
- A SAIF 062/2025 publica o preâmbulo legal em HTML (parser HTML em
  `sefaz_mg_parser.py`) mas a tabela PMPF de refrigerantes reside
  exclusivamente no PDF anexo `port_saif062_2025_anexos.pdf`. Tentar
  regex sobre o HTML é inviável.
- Este parser baixa o PDF em memória (httpx + BytesIO), abre com
  pdfplumber e itera `extract_tables()` em todas as páginas.
- O reconhecimento da tabela PMPF é heurístico: identifica o header
  procurando células com NCM, marca/descrição/produto, embalagem/
  volume/ml e PMPF/preço/R$ (case-insensitive). Sem header reconhecível,
  a tabela é ignorada.
- Cada linha de dados produz uma `RegraNormativa` para tabela_pmpf
  (mva=0.0, valor real registado em fonte_legal — mesma convenção do
  parser HTML).
- Vigência: 2026-01-01 → 2026-06-30 (ciclo semestral SAIF 062/2025).
- Nivel de confiança: `candidata_oficial` (AG-VALIDACAO promove a
  `oficial` após validação cruzada).

Auditoria operacional: as primeiras 3 linhas extraídas são logadas em
INFO para inspecção rápida em produção sem precisar de debugger.
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
_FONTE_LEGAL = (
    "Portaria SAIF 062/2025 (anexo PDF) — SEFAZ-MG"
)
_IMPORTADO_POR = "sefaz_mg_pdf_parser.py v1.0"
_VIGENCIA_INICIO = date(2026, 1, 1)
_VIGENCIA_FIM = date(2026, 6, 30)
_ALIQUOTA_MG = 0.18  # RICMS-MG alíquota modal

_TIMEOUT_PDF = 30.0  # PDF é maior que HTML — timeout generoso

# Tokens reconhecidos no header da tabela PMPF (case-insensitive).
# Cada chave do dicionário mapeia uma intenção semântica para os tokens
# que o cabeçalho pode usar — a SEFAZ-MG não normaliza nomes de coluna
# entre revisões da portaria, então toleramos sinónimos.
_HEADER_TOKENS: dict[str, tuple[str, ...]] = {
    "ncm": ("ncm",),
    "marca": ("marca", "descricao", "descrição", "produto"),
    "volume": ("embalagem", "volume", "ml", "capacidade"),
    "pmpf": ("pmpf", "preço", "preco", "r$"),
}

_PADRAO_NCM = re.compile(r"(\d{4})\.?(\d{2})\.?(\d{2})")
_PADRAO_VOLUME = re.compile(r"(\d{2,5})\s*ml", re.IGNORECASE)
_PADRAO_VALOR = re.compile(r"R?\$?\s*(\d{1,4}[,\.]\d{2})")


class SefazMGPdfParser(BaseParser):
    """
    Extrai PMPF do PDF anexo da SAIF 062/2025.

    Fluxo:
    1. GET ao PDF (httpx via fetch_com_diagnostico — timeout 30s).
    2. Abre o PDF em memória (BytesIO) — nunca grava em disco.
    3. Itera todas as páginas e para cada uma chama extract_tables().
    4. Reconhece tabelas com header NCM/marca/volume/PMPF e extrai as
       linhas de dados.
    5. Devolve list[RegraNormativa] com vigência semestral explícita.
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

        regras_extraidas, erros_pdf = _extrair_regras_do_pdf_bytes(resp.content)
        regras.extend(regras_extraidas)
        erros.extend(erros_pdf)

        if not regras_extraidas:
            erros.append(
                "SEFAZ-MG-PDF: PDF aberto mas nenhuma linha PMPF reconhecida. "
                "Verificar layout das tabelas (header esperado: NCM, marca/"
                "descrição, embalagem/volume, PMPF/R$)."
            )

        return _resultado(regras, erros, diagnosticos)


def _resultado(
    regras: list[RegraNormativa],
    erros: list[str],
    diagnosticos: list[DiagnosticoHTTP],
) -> ResultadoParser:
    return ResultadoParser(
        regras=regras,
        erros=erros,
        fonte=_FONTE_LEGAL,
        url_consultada=_URL_PDF_ANEXOS,
        data_consulta=date.today().isoformat(),
        diagnostico=diagnosticos,
    )


def _parece_pdf(conteudo: bytes) -> bool:
    """PDFs válidos começam pelos magic bytes `%PDF-`."""
    return conteudo[:5] == b"%PDF-"


def _extrair_regras_do_pdf_bytes(
    conteudo: bytes,
) -> tuple[list[RegraNormativa], list[str]]:
    """
    Abre `conteudo` (bytes do PDF) e extrai todas as RegraNormativa
    reconhecidas. Retorna (regras, erros).

    Importa pdfplumber lazy para que falhas de import não bloqueiem
    o resto do pipeline em ambientes mínimos (a dependência está em
    `requirements.txt` mas algum cenário CI pode pular instalação).
    """
    erros: list[str] = []
    try:
        import pdfplumber  # type: ignore[import-not-found]
    except Exception as exc:
        erros.append(
            f"SEFAZ-MG-PDF: pdfplumber indisponível — {exc}. "
            "Adicionar `pdfplumber` ao requirements.txt e reinstalar."
        )
        return [], erros

    regras: list[RegraNormativa] = []
    preview_logged = 0  # primeiras 3 linhas de qualquer tabela

    try:
        with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
            num_paginas = len(pdf.pages)
            logger.info(
                "SEFAZ-MG-PDF: PDF aberto — %d página(s), %d bytes",
                num_paginas,
                len(conteudo),
            )
            for idx_pagina, page in enumerate(pdf.pages, start=1):
                try:
                    tabelas = page.extract_tables() or []
                except Exception as exc:
                    erros.append(
                        f"SEFAZ-MG-PDF: extract_tables falhou na página "
                        f"{idx_pagina}: {exc}"
                    )
                    continue
                for idx_tabela, tabela in enumerate(tabelas, start=1):
                    if preview_logged < 3:
                        for linha in tabela[:3]:
                            preview_logged += 1
                            logger.info(
                                "SEFAZ-MG-PDF preview pag=%d tabela=%d: %s",
                                idx_pagina,
                                idx_tabela,
                                linha,
                            )
                            if preview_logged >= 3:
                                break
                    regras.extend(_extrair_regras_de_tabela(tabela))
    except Exception as exc:
        erros.append(f"SEFAZ-MG-PDF: pdfplumber.open falhou: {exc}")
        return regras, erros

    return regras, erros


def _extrair_regras_de_tabela(
    tabela: list[list[str | None]],
) -> list[RegraNormativa]:
    """
    Extrai RegraNormativa de uma única tabela (list[list[str|None]]).

    Estratégia:
    1. Procura o header em qualquer das 5 primeiras linhas — algumas
       portarias colocam título da tabela na linha 0 antes do header.
    2. Mapeia colunas para {ncm, marca, volume, pmpf}. Sem coluna NCM
       e PMPF, descarta a tabela inteira (não é tabela PMPF).
    3. Para cada linha de dados subsequente, extrai NCM, marca, volume
       e PMPF; descarta linhas com NCM ou PMPF inválidos (heurística
       para ignorar separadores/notas).
    """
    if not tabela:
        return []

    cols: dict[str, int] | None = None
    primeira_linha_dados = 0
    for idx in range(min(5, len(tabela))):
        candidato = _identificar_header(tabela[idx])
        if candidato and "ncm" in candidato and "pmpf" in candidato:
            cols = candidato
            primeira_linha_dados = idx + 1
            break

    if cols is None:
        return []

    regras: list[RegraNormativa] = []
    vistos: set[tuple[str, float, str]] = set()

    for linha in tabela[primeira_linha_dados:]:
        regra = _extrair_regra_da_linha(linha, cols)
        if regra is None:
            continue
        chave = (regra.ncm, _extrair_pmpf_do_fonte_legal(regra.fonte_legal), _extrair_marca_do_fonte_legal(regra.fonte_legal))
        if chave in vistos:
            continue
        vistos.add(chave)
        regras.append(regra)

    return regras


def _identificar_header(linha: list[str | None]) -> dict[str, int] | None:
    """
    Devolve mapa {ncm,marca,volume,pmpf} → índice da coluna, ou None
    se a linha não parece um header (sem NCM identificável).
    """
    if not linha:
        return None
    cols: dict[str, int] = {}
    for idx, cel in enumerate(linha):
        token = _normalizar(cel)
        if not token:
            continue
        for nome, alvos in _HEADER_TOKENS.items():
            if nome in cols:
                continue
            if any(alvo in token for alvo in alvos):
                cols[nome] = idx
                break
    if "ncm" in cols:
        return cols
    return None


def _extrair_regra_da_linha(
    linha: list[str | None], cols: dict[str, int]
) -> RegraNormativa | None:
    if not linha:
        return None

    ncm_cel = _celula(linha, cols.get("ncm"))
    pmpf_cel = _celula(linha, cols.get("pmpf"))
    marca_cel = _celula(linha, cols.get("marca"))
    volume_cel = _celula(linha, cols.get("volume"))

    ncm = _parse_ncm(ncm_cel)
    if ncm is None:
        return None

    pmpf = _parse_valor(pmpf_cel)
    if pmpf is None or pmpf <= 0:
        return None

    volume_ml = _parse_volume(volume_cel) or _parse_volume(marca_cel) or 0
    marca = _limpar_marca(marca_cel)

    return _construir_regra(ncm, pmpf, marca, volume_ml)


def _celula(linha: list[str | None], idx: int | None) -> str:
    if idx is None or idx < 0 or idx >= len(linha):
        return ""
    return (linha[idx] or "").strip()


def _normalizar(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip().lower()


def _parse_ncm(s: str) -> str | None:
    if not s:
        return None
    m = _PADRAO_NCM.search(s)
    if not m:
        return None
    return f"{m.group(1)}{m.group(2)}{m.group(3)}"


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
    """
    Remove sufixos típicos da célula marca (volume em ml e valor em R$),
    mantendo só o nome do produto. Devolve "" se a célula ficar vazia.
    """
    if not s:
        return ""
    sem_volume = _PADRAO_VOLUME.sub("", s)
    sem_valor = _PADRAO_VALOR.sub("", sem_volume)
    limpo = re.sub(r"\s+", " ", sem_valor).strip(" -|\t\n")
    return limpo


def _construir_regra(
    ncm_sem_ponto: str, pmpf: float, marca: str, embalagem_ml: int
) -> RegraNormativa:
    detalhe: list[str] = []
    if marca:
        detalhe.append(marca)
    if embalagem_ml:
        detalhe.append(f"{embalagem_ml}ml")
    detalhe.append(f"R${pmpf:.2f}")
    sufixo = " | PMPF " + " ".join(detalhe)
    return RegraNormativa(
        estado="MG",
        ncm=ncm_sem_ponto,
        mva=0.0,  # MG usa PMPF — valor real registado em fonte_legal
        aliquota_interna=_ALIQUOTA_MG,
        vigencia_inicio=_VIGENCIA_INICIO,
        vigencia_fim=_VIGENCIA_FIM,
        fonte_legal=f"{_FONTE_LEGAL}{sufixo}",
        url_fonte=_URL_PDF_ANEXOS,
        nivel_confianca="candidata_oficial",
        importado_por=_IMPORTADO_POR,
    )


def _extrair_pmpf_do_fonte_legal(fonte: str) -> float:
    """Auxilia deduplicação: extrai o R$ XX,XX do sufixo de fonte_legal."""
    m = _PADRAO_VALOR.search(fonte)
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def _extrair_marca_do_fonte_legal(fonte: str) -> str:
    """Auxilia deduplicação: marca = tudo entre 'PMPF ' e o primeiro número."""
    marcador = "PMPF "
    idx = fonte.find(marcador)
    if idx < 0:
        return ""
    cauda = fonte[idx + len(marcador) :]
    m_vol = _PADRAO_VOLUME.search(cauda)
    m_val = _PADRAO_VALOR.search(cauda)
    corte = min(
        (m.start() for m in (m_vol, m_val) if m is not None),
        default=len(cauda),
    )
    return cauda[:corte].strip()
