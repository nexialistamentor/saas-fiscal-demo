"""
Parser DOU — extrai publicações relevantes do Diário Oficial da União.

Fontes (tentadas em ordem):
1. INLABS (https://inlabs.in.gov.br) — XML estruturado via fluxo oficial
   (`logar.php` + ZIP em `index.php?p=`), credenciais em INLABS_USER /
   INLABS_PASS. O módulo `inlabs_official.py` replica o script publicado em
   https://github.com/Imprensa-Nacional/inlabs em `public/python/inlabs-auto-download-xml.py`.
2. Scraping HTML de https://www.in.gov.br/consulta/-/buscar/dou — público,
   sem autenticação. Atenção: o buscador é uma SPA — o HTML inicial não
   contém os resultados, eles são preenchidos por JavaScript após o load.
   Quando detectamos a shell SPA (ver `_eh_shell_spa_sem_resultados`)
   abortamos a extracção e devolvemos regras=[] em vez de produzir falsos
   positivos a partir de links de menu.

Publicações identificadas geram RegraNormativa com nivel_confianca="candidata_oficial"
para revisão pelo AG-VALIDACAO antes de promover a "oficial".
"""
from __future__ import annotations

import logging
import os
import urllib.parse
import zipfile
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

from app.services.parsers.base_parser import (
    BaseParser,
    DiagnosticoHTTP,
    ResultadoParser,
    fetch_com_diagnostico,
)
from app.services.parsers import inlabs_official as inlabs
from app.services.pipeline_normativo import RegraNormativa

logger = logging.getLogger(__name__)

_DOU_BUSCA_URL = "https://www.in.gov.br/consulta/-/buscar/dou"

_TERMOS_MVA = [
    "MVA substituição tributária ICMS",
    "margem valor agregado ICMS-ST",
    "IVA-ST refrigerantes",
    "PMPF bebidas substituição tributária",
    "Convênio ICMS alíquota substituição",
]
_IMPORTADO_POR = "dou_parser.py v1.3"

# Headers extra para sinalizar preferência por JSON. O endpoint `/consulta/`
# do in.gov.br não tem API pública estruturada — é uma SPA — mas o header
# Accept fica registado para auditoria e para o caso de algum dia
# negociarem content-type.
_DOU_EXTRA_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/html;q=0.8",
    "X-Requested-With": "XMLHttpRequest",
}


class DOUParser(BaseParser):
    """
    Consulta o DOU e tenta extrair regras normativas estruturadas.

    Estratégia:
    - Se INLABS_USER/INLABS_PASS estão presentes, tenta XML estruturado.
    - Caso contrário, faz scraping HTML do buscador público — com detecção
      de SPA shell para abortar quando o HTML não contiver resultados.

    Publicações detectadas → nivel_confianca_fonte="candidata_oficial"
    (AG-VALIDACAO promove a "oficial" depois de validação cruzada).
    """
    nome = "DOU"
    url_base = _DOU_BUSCA_URL

    def __init__(self, dias_atras: int = 30):
        self.dias_atras = dias_atras

    def extrair(self) -> ResultadoParser:
        regras: list[RegraNormativa] = []
        erros: list[str] = []
        diagnosticos: list[DiagnosticoHTTP] = []

        usuario_inlabs = os.environ.get("INLABS_USER")
        senha_inlabs = os.environ.get("INLABS_PASS")
        if usuario_inlabs and senha_inlabs:
            inlabs_regras, inlabs_erros, inlabs_diag = _tentar_inlabs(
                usuario_inlabs, senha_inlabs, self.dias_atras
            )
            regras.extend(inlabs_regras)
            erros.extend(inlabs_erros)
            diagnosticos.extend(inlabs_diag)
        else:
            erros.append(
                "INLABS_USER/INLABS_PASS ausentes — INLABS desactivado, "
                "usando apenas scraping HTML público (SPA, alto risco de 0 resultados)"
            )

        html_regras, html_erros, html_diag = _consultar_html(
            self.dias_atras, _TERMOS_MVA
        )
        regras.extend(html_regras)
        erros.extend(html_erros)
        diagnosticos.extend(html_diag)

        return ResultadoParser(
            regras=regras,
            erros=erros,
            fonte="DOU",
            url_consultada=_DOU_BUSCA_URL,
            data_consulta=date.today().isoformat(),
            diagnostico=diagnosticos,
        )


def _consultar_html(
    dias_atras: int, termos: list[str]
) -> tuple[list[RegraNormativa], list[str], list[DiagnosticoHTTP]]:
    """
    Faz scraping HTML do buscador público https://www.in.gov.br/consulta/-/buscar/dou.

    O endpoint é uma SPA: o HTML inicial é só o shell da aplicação, e os
    resultados são preenchidos por JS após o load. Por isso:

    - Pedimos `Accept: application/json` (caso o servidor algum dia
      negocie content-type — hoje devolve sempre HTML).
    - Detectamos a shell SPA (`<!DOCTYPE` sem `resultado-busca-item`) e
      abortamos a extracção desse termo, registando DiagnosticoHTTP e
      uma mensagem em `erros`. Não tentamos parsing fallback de <a> em
      shell SPA porque produz só falsos positivos (links do menu).
    """
    regras: list[RegraNormativa] = []
    erros: list[str] = []
    diagnosticos: list[DiagnosticoHTTP] = []

    data_inicio = (date.today() - timedelta(days=dias_atras)).strftime("%d/%m/%Y")
    data_fim = date.today().strftime("%d/%m/%Y")

    for termo in termos:
        params = {
            "q": termo,
            "exactDate": "personalizado",
            "publishFrom": data_inicio,
            "publishTo": data_fim,
            "delta": "20",
        }
        resp, diagnostico = fetch_com_diagnostico(
            _DOU_BUSCA_URL,
            params=params,
            timeout=15,
            extra_headers=_DOU_EXTRA_HEADERS,
        )
        diagnosticos.append(diagnostico)

        if resp is None:
            erros.append(f"DOU HTML falhou para termo '{termo}': {diagnostico.erro}")
            continue
        if resp.status_code != 200:
            erros.append(
                f"DOU HTML retornou {resp.status_code} para termo '{termo}'"
            )
            continue

        # SPA shell: corpo é HTML do app shell, sem resultados estruturados.
        # Abortamos antes de tentar regex/BS4 — produziria apenas falsos
        # positivos (ex.: links do menu de navegação).
        if _eh_shell_spa_sem_resultados(resp.text):
            erros.append(
                f"DOU: termo '{termo}' devolveu shell SPA "
                f"(JS-rendered, sem resultado-busca-item) — scraping HTML "
                f"inviável. Configure INLABS_USER/INLABS_PASS para acesso XML "
                f"estruturado. (bytes={diagnostico.bytes_recebidos}, "
                f"status={diagnostico.status_code})"
            )
            continue

        publicacoes = _extrair_publicacoes_html(resp.text)
        for pub in publicacoes:
            uf = _extrair_uf_do_titulo(pub["titulo"])
            if not uf:
                continue
            regras.append(
                RegraNormativa(
                    estado=uf,
                    ncm="",
                    mva=0.0,
                    aliquota_interna=0.0,
                    vigencia_inicio=date.today(),
                    vigencia_fim=None,
                    fonte_legal=f"DOU: {pub['titulo'][:200]}",
                    url_fonte=pub["url"] or _DOU_BUSCA_URL,
                    nivel_confianca="candidata_oficial",
                    importado_por=_IMPORTADO_POR,
                )
            )

    return regras, erros, diagnosticos


def _eh_shell_spa_sem_resultados(html: str) -> bool:
    """
    Detecta resposta HTML quando esperávamos JSON estruturado.

    O buscador `/consulta/-/buscar/dou` é uma SPA — o HTML inicial é só o
    shell da aplicação e os resultados são preenchidos por JS após o load.
    Como pedimos `Accept: application/json` mas o servidor devolve sempre
    HTML, o critério é simples: se o body começa por `<!DOCTYPE` ou `<html>`
    a resposta é inútil para extracção fiável e abortamos.

    Para podermos validar HTML real (ex.: testes unitários ou snapshot
    futuro server-side rendered) checamos primeiro se o documento contém
    pelo menos um container `div.resultado-busca-item` com filhos — nesse
    caso o HTML é tratado como válido.
    """
    head = html.lstrip()[:200].lower()
    if not (head.startswith("<!doctype") or head.startswith("<html")):
        return False
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    selectores_resultados = (
        "div.resultado-busca-item",
        "div.resultado",
        "li.resultado-busca-item",
        "article.resultado",
    )
    for sel in selectores_resultados:
        elementos = soup.select(sel)
        for el in elementos:
            if el.find("a", href=True) or el.get_text(strip=True):
                return False
    return True


def _extrair_publicacoes_html(html: str) -> list[dict]:
    """
    Faz parse do HTML do buscador DOU e devolve lista de publicações.

    A estrutura típica é uma <div class="resultado"> contendo <h5> com
    o título e <a href> para o detalhe. Quando a estrutura muda, o método
    cai num plano B baseado em <a> com href apontando para /web/dou/.

    Esta função NÃO faz detecção de shell SPA — assume que o caller
    já filtrou via `_eh_shell_spa_sem_resultados`. Está exposta para os
    testes unitários poderem injectar HTML controlado.
    """
    publicacoes: list[dict] = []
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "div.resultado-busca-item",
        "div.resultado",
        "li.resultado-busca-item",
        "article.resultado",
    ]
    items = []
    for sel in selectors:
        items = soup.select(sel)
        if items:
            break

    for it in items:
        link = it.find("a", href=True)
        titulo_el = it.find(["h5", "h4", "h3", "strong"]) or link
        if not link or not titulo_el:
            continue
        titulo = titulo_el.get_text(" ", strip=True)
        href = link["href"]
        if href.startswith("/"):
            href = f"https://www.in.gov.br{href}"
        if titulo:
            publicacoes.append({"titulo": titulo, "url": href})

    if not publicacoes:
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "/web/dou/" not in href and "/dou/" not in href:
                continue
            titulo = link.get_text(" ", strip=True)
            if not titulo or len(titulo) < 20:
                continue
            if href.startswith("/"):
                href = f"https://www.in.gov.br{href}"
            publicacoes.append({"titulo": titulo, "url": href})

    return publicacoes[:10]


def _tentar_inlabs(
    usuario: str, senha: str, dias_atras: int
) -> tuple[list[RegraNormativa], list[str], list[DiagnosticoHTTP]]:
    """
    Login INLABS (POST logar.php + cookie) e varredura de ZIPs XML oficiais
    nos últimos N dias à procura dos termos em `_TERMOS_MVA`.

    Usa `requests` e o mesmo contrato de cabeçalhos do script oficial da
    Imprensa Nacional — não depende de cookies copiados do browser.

    Limite de dias: `INLABS_MAX_DIAS_XML` ou min(dias_atras, 14) por defeito
    para não sobrecarregar o serviço.
    """
    regras: list[RegraNormativa] = []
    erros: list[str] = []
    diagnosticos: list[DiagnosticoHTTP] = []
    cfg = inlabs.config_from_env()

    max_dias_raw = os.getenv("INLABS_MAX_DIAS_XML", "").strip()
    if max_dias_raw:
        max_dias = max(1, min(int(max_dias_raw), dias_atras))
    else:
        max_dias = max(1, min(14, dias_atras))

    try:
        session, resp_login = inlabs.login_com_resposta(usuario, senha, cfg)
        diagnosticos.append(inlabs.resposta_para_diagnostico(resp_login))
    except requests.HTTPError as exc:
        if exc.response is not None:
            diagnosticos.append(inlabs.resposta_para_diagnostico(exc.response))
        else:
            diagnosticos.append(
                DiagnosticoHTTP(
                    url=inlabs.URL_LOGIN,
                    status_code=None,
                    bytes_recebidos=0,
                    content_type="",
                    preview="",
                    erro=str(exc),
                )
            )
        erros.append(f"INLABS login HTTP falhou: {exc}")
        return [], erros, diagnosticos
    except inlabs.InlabsAuthError as exc:
        erros.append(f"INLABS: {exc}")
        return [], erros, diagnosticos
    except requests.RequestException as exc:
        erros.append(f"INLABS login rede: {exc}")
        diagnosticos.append(
            DiagnosticoHTTP(
                url=inlabs.URL_LOGIN,
                status_code=None,
                bytes_recebidos=0,
                content_type="",
                preview="",
                erro=str(exc),
            )
        )
        return [], erros, diagnosticos

    vistos: set[tuple[str, str]] = set()
    downloads_nao_ok = 0
    hoje = date.today()

    for offset in range(max_dias):
        d = hoje - timedelta(days=offset)
        for secao in cfg.secoes_xml:
            try:
                zbytes, resp_zip = inlabs.descarregar_zip(
                    session, d, secao, cfg=cfg
                )
            except requests.RequestException as exc:
                erros.append(f"INLABS ZIP {d.isoformat()} {secao}: {exc}")
                continue

            if resp_zip.status_code != 200 or not zbytes:
                if downloads_nao_ok < 20:
                    diagnosticos.append(inlabs.resposta_para_diagnostico(resp_zip))
                    downloads_nao_ok += 1
                continue

            try:
                pares_xml = inlabs.iter_xml_de_zip(zbytes)
            except (zipfile.BadZipFile, OSError) as exc:
                erros.append(
                    f"INLABS ZIP inválido {d.isoformat()} {secao}: {exc}"
                )
                continue

            for nome_arq, xml_txt in pares_xml:
                if not inlabs.texto_coincide_termos(xml_txt, _TERMOS_MVA):
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
                url_fonte = f"{_DOU_BUSCA_URL}?q={q}"
                regras.append(
                    RegraNormativa(
                        estado=uf,
                        ncm="",
                        mva=0.0,
                        aliquota_interna=0.0,
                        vigencia_inicio=d,
                        vigencia_fim=None,
                        fonte_legal=f"DOU (INLABS XML): {titulo[:200]}",
                        url_fonte=url_fonte,
                        nivel_confianca="candidata_oficial",
                        importado_por=_IMPORTADO_POR,
                    )
                )

    if not regras:
        erros.append(
            "INLABS: login OK mas nenhuma publicação casou termos MVA "
            f"no período de {max_dias} dia(s) (secções: "
            f"{' '.join(cfg.secoes_xml)})."
        )

    return regras, erros, diagnosticos


def _extrair_uf_do_titulo(titulo: str) -> str | None:
    """Heurística: detecta UF mencionada no título da publicação."""
    _UFS = [
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
        "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    ]
    titulo_upper = titulo.upper()
    for uf in _UFS:
        if f" {uf} " in titulo_upper or f"/{uf}" in titulo_upper or titulo_upper.startswith(uf):
            return uf
    return None
