"""Catraca comercial externa, read-only e fail-closed para o MEI.

Reutiliza o contrato HTTP dos smokes MEI; nunca faz cadastro, cria intencao,
abre uma nova ordem, efetua pagamento ou chama endpoints fiscais.

Exige uma conta sintetica JA EXISTENTE, exclusiva e previamente autorizada.
Para comprovar o checkout sem escrita, exige uma tentativa sintetica pendente
preexistente e recuperavel. Ausencia de prova bloqueia a campanha.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


_OPENER = build_opener(_NoRedirect)


def _get(url: str, token: str | None = None) -> tuple[int, bytes]:
    headers = {"User-Agent": "SOLVERIS-commercial-gate/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _send(Request(url, headers=headers))


def _login(url: str, email: str, password: str) -> tuple[int, bytes]:
    data = urlencode({"username": email, "password": password}).encode("utf-8")
    return _send(Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "SOLVERIS-commercial-gate/1.0",
    }))


def _post_json(url: str, token: str, key: str, payload: dict) -> tuple[int, bytes]:
    return _send(Request(url, data=json.dumps(payload).encode("utf-8"), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}",
        "Idempotency-Key": key, "User-Agent": "SOLVERIS-commercial-gate/1.0",
    }))


def _send(request: Request) -> tuple[int, bytes]:
    try:
        with _OPENER.open(request, timeout=12) as response:
            return response.status, response.read(262145)
    except HTTPError as exc:
        # Nunca imprimir corpo de erro, URL ou cabecalhos: podem conter segredos.
        return exc.code, b""
    except (URLError, TimeoutError, OSError, ValueError):
        return 0, b""


def _json(data: bytes):
    if len(data) > 262144:
        return None
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None


def _valid_base(url: str) -> bool:
    try:
        parts = urlsplit(url)
        if parts.username or parts.password or parts.query or parts.fragment:
            return False
        return (parts.scheme == "https" and bool(parts.hostname)) or (
            parts.scheme == "http" and parts.hostname in {"127.0.0.1", "localhost"}
        )
    except ValueError:
        return False


def _valid_checkout_url(url: object) -> bool:
    if not isinstance(url, str) or not url or any(c.isspace() for c in url):
        return False
    try:
        parts = urlsplit(url)
        return (
            parts.scheme == "https" and bool(parts.hostname)
            and parts.username is None and parts.password is None
            and not parts.fragment and (parts.port is None or parts.port > 0)
        )
    except ValueError:
        return False


def _check(results: list, name: str, ok: bool, status: int | None = None,
           reason: str = "") -> None:
    item = {"teste": name, "resultado": "APROVADO" if ok else "BLOQUEADO"}
    if status is not None:
        item["http"] = status
    if not ok and reason:
        item["motivo"] = reason
    results.append(item)


def evaluate(config: dict, get=_get, login=_login, post_json=_post_json) -> dict:
    """Injecao de transporte permite testar a catraca sem tocar em producao."""
    results: list[dict] = []
    landing = config.get("landing", "")
    api = config.get("api", "").rstrip("/")
    expected_title = config.get("landing_text", "SOLVERIS | MEI")
    if not _valid_base(landing) or not _valid_base(api):
        for name in ("landing", "backend", "login_sintetico", "checkout"):
            _check(results, name, False, reason="URL_INVALIDA")
        return _receipt(config, results)

    status, html = get(landing)
    page_ok = status == 200 and expected_title.encode("utf-8") in html and b"<div id=\"root\"" in html
    _check(results, "landing", page_ok, status, "PAGINA_INACESSIVEL_OU_INCORRETA")

    status, health_body = get(api + "/health")
    backend_ok = status == 200 and _json(health_body) == {"status": "ok"}
    _check(results, "backend", backend_ok, status, "HEALTH_INDISPONIVEL")

    email = config.get("email", "")
    password = config.get("password", "")
    empresa_id = config.get("empresa_id", "")
    competencia = config.get("competencia", "")
    if (not config.get("exclusive_test_account") or not email or not password
            or not isinstance(empresa_id, int) or empresa_id <= 0
            or not re.fullmatch(r"\d{4}(0[1-9]|1[0-2])", competencia)):
        _check(results, "login_sintetico", False, reason="CONTA_SINTETICA_NAO_CERTIFICADA")
        _check(results, "checkout", False, reason="LOGIN_NAO_COMPROVADO")
        return _receipt(config, results)

    status, body = login(api + "/auth/login", email, password)
    payload = _json(body)
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if status != 200 or not isinstance(token, str) or not token:
        _check(results, "login_sintetico", False, status, "AUTENTICACAO_FALHOU")
        _check(results, "checkout", False, reason="LOGIN_NAO_COMPROVADO")
        return _receipt(config, results)

    status, body = get(api + "/auth/me", token)
    identity = _json(body)
    identity_ok = (status == 200 and isinstance(identity, dict)
                   and identity.get("email") == email)
    _check(results, "login_sintetico", identity_ok, status, "IDENTIDADE_NAO_CONFIRMADA")
    if not identity_ok:
        _check(results, "checkout", False, reason="LOGIN_NAO_COMPROVADO")
        return _receipt(config, results)

    status, body = get(api + "/empresas/", token)
    companies = _json(body)
    owner_ok = (status == 200 and isinstance(companies, list)
                and any(isinstance(c, dict) and c.get("id") == empresa_id
                        and c.get("regime_tributario") == "mei" for c in companies))
    if not owner_ok:
        _check(results, "checkout", False, status, "EMPRESA_SINTETICA_NAO_CONFIRMADA")
        return _receipt(config, results)

    status, body = get(api + "/checkout/offers", token)
    offers = _json(body)
    matched = [o for o in offers if isinstance(o, dict)
               and o.get("offer_code") == "mei-das-one-time-company"] if isinstance(offers, list) else []
    expected = {"preco": "39.90", "moeda": "BRL", "vertical": "tax",
                "commercial_model": "one_time", "subject_type": "company",
                "usage_unit": "competence", "usage_limit": 1,
                "checkout_mode": "automatic"}
    offer_ok = (status == 200 and len(matched) == 1
                and all(matched[0].get(k) == v for k, v in expected.items()))
    if not offer_ok:
        _check(results, "checkout", False, status, "OFERTA_MEI_NAO_DISPONIVEL")
        return _receipt(config, results)

    phase = config.get("phase", "preflight")
    checkout_url_created = None
    if phase == "preflight":
        key = config.get("synthetic_idempotency_key", "")
        if (not config.get("approved_test_write") or not isinstance(key, str)
                or re.fullmatch(r"[\x21-\x7e]{1,255}", key) is None):
            _check(results, "checkout", False, reason="CRIACAO_SINTETICA_SEM_AUTORIZACAO")
            return _receipt(config, results)
        status, _ = post_json(api + f"/imposto/mei/{empresa_id}/checkout-intents", token, key,
                              {"competencia": competencia, "offer_code": "mei-das-one-time-company"})
        if status != 204:
            _check(results, "checkout", False, status, "INTENCAO_SINTETICA_FALHOU")
            return _receipt(config, results)
        status, body = post_json(api + "/checkout/one-time", token, key,
                                 {"empresa_id": empresa_id, "offer_code": "mei-das-one-time-company"})
        created = _json(body)
        checkout_url_created = created.get("checkout_url") if isinstance(created, dict) else None
        if status != 200 or not _valid_checkout_url(checkout_url_created):
            _check(results, "checkout", False, status, "CRIACAO_CHECKOUT_SINTETICO_FALHOU")
            return _receipt(config, results)
    elif phase != "during":
        _check(results, "checkout", False, reason="FASE_DE_MONITORAMENTO_INVALIDA")
        return _receipt(config, results)

    path = f"/imposto/mei/{empresa_id}/checkout-recovery?competencia={competencia}"
    status, body = get(api + path, token)
    recovery = _json(body)
    checkout_ok = (status == 200 and isinstance(recovery, dict)
                   and recovery.get("estado") == "pending"
                   and recovery.get("competencia") == competencia
                   and recovery.get("autorizado") is False
                   and isinstance(recovery.get("checkout_idempotency_key"), str)
                   and bool(recovery["checkout_idempotency_key"])
                   and _valid_checkout_url(recovery.get("checkout_url"))
                   and (checkout_url_created is None or
                        recovery.get("checkout_url") == checkout_url_created))
    if checkout_ok:
        # Apenas GET sem token no destino da preferencia. Nunca submete pagamento.
        status, checkout_html = get(recovery["checkout_url"])
        checkout_ok = status == 200 and b"<html" in checkout_html.lower()
    _check(results, "checkout", checkout_ok, status, "CHECKOUT_PENDENTE_NAO_RECUPERAVEL")
    return _receipt(config, results)


def _receipt(config: dict, results: list[dict]) -> dict:
    apta = all(row["resultado"] == "APROVADO" for row in results) and len(results) == 4
    verified = datetime.now(timezone.utc)
    return {
        "produto": "MEI", "verificado_em": verified.isoformat(),
        "valido_ate": (verified + timedelta(minutes=90)).isoformat() if apta else None,
        "resultado": "CAMPANHA_APTA" if apta else "CAMPANHA_BLOQUEADA",
        "testes": results,
        "fase": config.get("phase", "preflight"),
        "limites": "Nao paga, nao cria obrigacoes fiscais; during reutiliza ordem sintetica.",
    }


def main() -> int:
    raw_empresa_id = os.getenv("SOLVERIS_SYNTHETIC_EMPRESA_ID", "")
    empresa_id = int(raw_empresa_id) if raw_empresa_id.isdecimal() else 0
    config = {
        "landing": os.getenv("SOLVERIS_LANDING_URL", "https://solveris.ia.br/mei"),
        "api": os.getenv("SOLVERIS_API_URL", "https://saas-fiscal-demo-production.up.railway.app"),
        "landing_text": os.getenv("SOLVERIS_LANDING_TEXT", "SOLVERIS | MEI"),
        "email": os.getenv("SOLVERIS_SYNTHETIC_EMAIL", ""),
        "password": os.getenv("SOLVERIS_SYNTHETIC_PASSWORD", ""),
        "empresa_id": empresa_id,
        "competencia": os.getenv("SOLVERIS_SYNTHETIC_COMPETENCIA", ""),
        "exclusive_test_account": os.getenv("SOLVERIS_EXCLUSIVE_TEST_ACCOUNT") == "YES",
        "phase": os.getenv("SOLVERIS_GATE_PHASE", "preflight"),
        "approved_test_write": os.getenv("SOLVERIS_APPROVED_SYNTHETIC_CHECKOUT_WRITE") == "YES",
        "synthetic_idempotency_key": os.getenv("SOLVERIS_SYNTHETIC_IDEMPOTENCY_KEY", ""),
    }
    receipt = evaluate(config)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    if receipt["resultado"] != "CAMPANHA_APTA":
        print("::error title=SOLVERIS P0::CAMPANHA_BLOQUEADA", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
