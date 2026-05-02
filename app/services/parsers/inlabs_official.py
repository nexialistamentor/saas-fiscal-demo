"""
Cliente INLABS baseado no script oficial da Imprensa Nacional.

O código segue o fluxo de `public/python/inlabs-auto-download-xml.py` em
https://github.com/Imprensa-Nacional/inlabs (o caminho antigo
`public/python3/inlabs.py` já não existe no repositório).

Credenciais: variáveis de ambiente INLABS_USER e INLABS_PASS (o exemplo
oficial usa email/senha em variáveis `login`/`senha` no próprio ficheiro).
"""
from __future__ import annotations

import io
import logging
import os
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import BinaryIO

import requests
from bs4 import BeautifulSoup

from app.services.parsers.base_parser import DiagnosticoHTTP

logger = logging.getLogger(__name__)

URL_LOGIN = "https://inlabs.in.gov.br/logar.php"
URL_DOWNLOAD_BASE = "https://inlabs.in.gov.br/index.php?p="

# Cabeçalho exigido pelo INLABS (mesmo valor do script oficial: "script" em hex).
_HEADER_ORIGEM = "736372697074"

_DEFAULT_LOGIN_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class InlabsAuthError(RuntimeError):
    """Sessão INLABS sem `PHPSESSID` após POST em logar.php."""


@dataclass
class InlabsConfig:
    """Parâmetros de descarga (sobreponíveis via ambiente)."""

    timeout: float = 120.0
    secoes_xml: tuple[str, ...] = ("DO1", "DO2", "DO3", "DO1E", "DO2E", "DO3E")
    user_agent: str = "INLABS-Official-Flow/1.0 (+python requests; saas-fiscal-demo)"


def config_from_env(timeout: float | None = None) -> InlabsConfig:
    sec = os.getenv("INLABS_SECOES_XML", "").strip()
    secoes: tuple[str, ...]
    if sec:
        secoes = tuple(s.upper() for s in sec.split() if s.strip())
    else:
        secoes = InlabsConfig.secoes_xml
    t = timeout if timeout is not None else float(os.getenv("INLABS_TIMEOUT", "120"))
    ua = os.getenv("INLABS_USER_AGENT", InlabsConfig.user_agent)
    return InlabsConfig(timeout=t, secoes_xml=secoes, user_agent=ua)


def criar_sessao_apos_login(
    email: str,
    password: str,
    cfg: InlabsConfig | None = None,
) -> requests.Session:
    """
    POST em logar.php como no script oficial; devolve sessão com cookies.
    Lança InlabsAuthError se não houver PHPSESSID.
    """
    session, _resp = login_com_resposta(email, password, cfg)
    return session


def login_com_resposta(
    email: str,
    password: str,
    cfg: InlabsConfig | None = None,
) -> tuple[requests.Session, requests.Response]:
    """POST logar.php; devolve (sessão, resposta). Lança InlabsAuthError se sem cookie."""
    cfg = cfg or config_from_env()
    session = requests.Session()
    session.headers.update({"User-Agent": cfg.user_agent})
    payload = {"email": email.strip(), "password": password}
    resp = session.post(
        URL_LOGIN,
        data=payload,
        headers=_DEFAULT_LOGIN_HEADERS,
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    if not session.cookies.get("PHPSESSID"):
        logger.warning(
            "INLABS login sem cookie (status=%s, len=%s)",
            resp.status_code,
            len(resp.content or b""),
        )
        raise InlabsAuthError(
            "Resposta de logar.php sem PHPSESSID — credenciais ou bloqueio WAF."
        )
    return session, resp


def resposta_para_diagnostico(resp: requests.Response, preview_len: int = 500) -> DiagnosticoHTTP:
    """Converte resposta `requests` em DiagnosticoHTTP."""
    body = resp.text or ""
    return DiagnosticoHTTP(
        url=str(resp.url),
        status_code=resp.status_code,
        bytes_recebidos=len(resp.content or b""),
        content_type=resp.headers.get("content-type", ""),
        preview=body[:preview_len],
        erro=None,
    )


def extrair_identifica_xml(xml_texto: str) -> str:
    """Tenta obter texto do nó Identifica do XML do DOU; senão primeiros caracteres."""
    try:
        soup = BeautifulSoup(xml_texto, "lxml-xml")
    except Exception:
        soup = BeautifulSoup(xml_texto, "xml")
    el = soup.find("Identifica") or soup.find("identifica")
    if el:
        t = el.get_text(" ", strip=True)
        if t and len(t) >= 8:
            return t[:500]
    linha = " ".join(xml_texto.split())[:400]
    return linha if linha else "DOU XML"


def url_download_zip(data: date, secao: str) -> str:
    d_hifen = data.strftime("%Y-%m-%d")  # parâmetro p=
    d_underscore = data.strftime("%Y_%m_%d")  # nome do ficheiro dl=
    fn = f"{d_underscore}-{secao}.zip"
    return f"{URL_DOWNLOAD_BASE}{d_hifen}&dl={fn}"


def descarregar_zip(
    session: requests.Session,
    data: date,
    secao: str,
    *,
    cfg: InlabsConfig | None = None,
) -> tuple[bytes | None, requests.Response]:
    """
    GET do ZIP XML de uma secção e data. Devolve (conteúdo ou None, response).
    Usa o mesmo cabeçalho Cookie + origem do script oficial.
    """
    cfg = cfg or config_from_env()
    phpsessid = session.cookies.get("PHPSESSID")
    ts_cookie = next(
        (f"{k}={v}" for k, v in session.cookies.items() if k.startswith("TS")),
        None,
    )
    if not phpsessid:
        raise InlabsAuthError("Sessão sem PHPSESSID")
    cookie_header = f"PHPSESSID={phpsessid}"
    if ts_cookie:
        cookie_header += f"; {ts_cookie}"
    url = url_download_zip(data, secao)
    cab = {
        "Cookie": cookie_header,
        "origem": _HEADER_ORIGEM,
    }
    r = session.get(url, headers=cab, timeout=cfg.timeout)
    if r.status_code == 200 and r.content:
        return r.content, r
    return None, r


def iter_xml_de_zip(zip_bytes: bytes) -> list[tuple[str, str]]:
    """Abre o ZIP em memória e devolve [(nome_ficheiro, texto_xml), ...]."""
    out: list[tuple[str, str]] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename
            if not name.lower().endswith(".xml"):
                continue
            with zf.open(info, "r") as f:
                raw = _read_textio(f)
            out.append((name, raw))
    return out


def _read_textio(stream: BinaryIO) -> str:
    data = stream.read()
    if isinstance(data, str):
        return data
    for enc in ("utf-8", "iso-8859-1", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def texto_coincide_termos(texto: str, termos: list[str]) -> bool:
    tl = texto.lower()
    return any(t.lower() in tl for t in termos if t.strip())
