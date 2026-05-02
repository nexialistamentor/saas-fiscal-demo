"""
Parser DOU via Portal de Dados Abertos (Imprensa Nacional).

Fonte de documentação e entrada humana:
https://in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados

Sem autenticação. A página confirma a convenção *Ano → Mês → arquivo.zip* e um
nomenclatura alinhada às secções do DOU; o HTML inicial não lista URL absolutas
dos ficheiros (UI Liferay/JS). O prefixo HTTP(S) onde os ZIPs estão hospedados
deve ser configurado em DOU_DADOS_ABERTOS_ZIP_BASE.

Padrão de caminho (mesmo estilo de nome INLABS, conforme especificação do produto):
  {base_url}/{YYYY}/{MM}/{YYYY}_{MM}_{DD}-{SEC}.zip
Exemplo relativo: /2025/03/2025_03_01-DO1.zip

Latência típica: pacotes mensais (mês anterior) na política de publicação da IN;
para o dia seguinte continua a ser necessário INLABS ou outro canal.

Saída: RegraNormativa com nivel_confianca=\"candidata_oficial\" (como dou_parser).
"""
from __future__ import annotations

import logging
import os
import urllib.parse
import zipfile
from datetime import date, timedelta

from app.services.parsers.base_parser import (
    BaseParser,
    DiagnosticoHTTP,
    ResultadoParser,
    fetch_com_diagnostico,
)
from app.services.parsers.dou_parser import (
    _TERMOS_MVA,
    _extrair_uf_do_titulo,
)
from app.services.parsers import inlabs_official as inlabs
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

URL_PORTAL_DADOS_ABERTOS = (
    "https://in.gov.br/acesso-a-informacao/dados-abertos/base-de-dados"
)

_ENV_ZIP_BASE = "DOU_DADOS_ABERTOS_ZIP_BASE"
_ENV_MAX_DIAS = "DOU_DADOS_ABERTOS_MAX_DIAS"
_ENV_SECOES = "DOU_DADOS_ABERTOS_SECOES"

_IMPORTADO_POR = "dou_dados_abertos_parser.py v1.0"


def montar_url_zip_publico(prefixo: str, data: date, secao: str) -> str:
    """
    Monta URL do ZIP no padrão {base}/{ano}/{mês}/{YYYY_MM_DD}-{secao}.zip
    com secao em maiúsculas (ex.: DO1).
    """
    p = prefixo.rstrip("/")
    y = data.year
    m = f"{data.month:02d}"
    stem = data.strftime("%Y_%m_%d")
    sec = secao.strip().upper()
    return f"{p}/{y}/{m}/{stem}-{sec}.zip"


class DOUDadosAbertosParser(BaseParser):
    """
    Obtém XML do DOU via ZIPs públicos (prefixo configurável), filtra por
    termos MVA/ST (mesmo conjunto que dou_parser / INLABS).
    """

    nome = "DOU (Dados Abertos)"
    url_base = URL_PORTAL_DADOS_ABERTOS

    def __init__(self, dias_atras: int = 30):
        self.dias_atras = dias_atras

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        diagnosticos: list[DiagnosticoHTTP] = []

        zip_base = (os.environ.get(_ENV_ZIP_BASE) or "").strip()
        resp_portal, diag_portal = fetch_com_diagnostico(
            URL_PORTAL_DADOS_ABERTOS,
            timeout=25.0,
        )
        diagnosticos.append(diag_portal)
        if resp_portal is None:
            erros.append(
                f"DOU Dados Abertos: portal inacessível ({diag_portal.erro})"
            )
        elif resp_portal.status_code != 200:
            erros.append(
                "DOU Dados Abertos: portal retornou "
                f"{resp_portal.status_code}"
            )

        if not zip_base:
            erros.append(
                f"DOU Dados Abertos: defina a variável de ambiente {_ENV_ZIP_BASE} "
                "com o prefixo HTTPS público onde os ZIPs seguem o caminho "
                "`/{ano}/{mês}/{YYYY_MM_DD}-DO1.zip` (documentação em "
                f"{URL_PORTAL_DADOS_ABERTOS})."
            )
            return ResultadoParser(
                regras=regras,
                erros=erros,
                fonte=self.nome,
                url_consultada=URL_PORTAL_DADOS_ABERTOS,
                data_consulta=date.today().isoformat(),
                diagnostico=diagnosticos,
            )

        max_dias = self._max_dias_efectivo()
        secoes = self._secoes()
        hoje = date.today()
        vistos: set[tuple[str, str]] = set()
        downloads_debug = 0

        for offset in range(max_dias):
            d = hoje - timedelta(days=offset)
            for secao in secoes:
                url_zip = montar_url_zip_publico(zip_base, d, secao)
                resp, diag = fetch_com_diagnostico(url_zip, timeout=120.0)
                diagnosticos.append(diag)
                if resp is None:
                    if downloads_debug < 3:
                        erros.append(
                            f"DOU Dados Abertos: rede ao obter {url_zip}: {diag.erro}"
                        )
                        downloads_debug += 1
                    continue
                blob = resp.content or b""
                if resp.status_code != 200 or len(blob) < 64:
                    continue
                if blob[:2] != b"PK":
                    continue
                try:
                    pares = inlabs.iter_xml_de_zip(blob)
                except (zipfile.BadZipFile, OSError) as exc:
                    erros.append(f"DOU Dados Abertos ZIP inválido {url_zip}: {exc}")
                    continue

                for _nome_arq, xml_txt in pares:
                    if not inlabs.texto_coincide_termos(xml_txt, list(_TERMOS_MVA)):
                        continue
                    titulo = inlabs.extrair_identifica_xml(xml_txt)
                    uf = _extrair_uf_do_titulo(titulo) or _extrair_uf_do_titulo(
                        xml_txt[:8000]
                    )
                    if not uf:
                        continue
                    chave = (uf, titulo[:160])
                    if chave in vistos:
                        continue
                    vistos.add(chave)
                    q = urllib.parse.quote(titulo[:120])
                    busca = "https://www.in.gov.br/consulta/-/buscar/dou"
                    regras.append(
                        RegraNormativa(
                            estado=uf,
                            ncm="",
                            mva=0.0,
                            aliquota_interna=0.0,
                            vigencia_inicio=d,
                            vigencia_fim=None,
                            fonte_legal=f"DOU (Dados Abertos XML): {titulo[:200]}",
                            url_fonte=f"{busca}?q={q}",
                            nivel_confianca="candidata_oficial",
                            importado_por=_IMPORTADO_POR,
                        )
                    )

        if not regras and zip_base:
            erros.append(
                "DOU Dados Abertos: nenhuma publicação casou termos MVA "
                f"no intervalo de {max_dias} dia(s) e secções "
                f"{' '.join(secoes)} (prefixo configurado)."
            )

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte=self.nome,
            url_consultada=URL_PORTAL_DADOS_ABERTOS,
            data_consulta=date.today().isoformat(),
            diagnostico=diagnosticos,
        )

    def _max_dias_efectivo(self) -> int:
        raw = (os.environ.get(_ENV_MAX_DIAS) or "").strip()
        limite = self.dias_atras
        if raw:
            try:
                return max(1, min(int(raw), limite))
            except ValueError:
                pass
        return max(1, min(14, limite))

    def _secoes(self) -> tuple[str, ...]:
        raw = (os.environ.get(_ENV_SECOES) or "").strip()
        if raw:
            return tuple(s.strip().upper() for s in raw.split() if s.strip())
        return ("DO1", "DO2", "DO3", "DO1E", "DO2E", "DO3E")
