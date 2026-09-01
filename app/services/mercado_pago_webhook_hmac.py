"""Validação do HMAC oficial de webhooks do Mercado Pago."""

import hashlib
import hmac


def _decimal_ascii_canonico_positivo(valor):
    return (
        type(valor) is str
        and bool(valor)
        and valor.isascii()
        and valor.isdecimal()
        and valor[0] != "0"
    )


def _contem_whitespace_ou_controle(valor):
    return any(
        caractere.isspace()
        or ord(caractere) < 0x20
        or 0x7F <= ord(caractere) <= 0x9F
        for caractere in valor
    )


def validar_mercado_pago_webhook_hmac(
    *,
    x_signature,
    x_request_id,
    data_id,
    secret,
):
    """Valida uma assinatura HMAC-SHA256 sem normalizar as entradas."""
    if (
        type(x_signature) is not str
        or type(x_request_id) is not str
        or not x_request_id
        or type(secret) is not str
        or not secret
        or not _decimal_ascii_canonico_positivo(data_id)
        or _contem_whitespace_ou_controle(x_signature)
        or _contem_whitespace_ou_controle(x_request_id)
    ):
        return False

    componentes = x_signature.split(",")
    if len(componentes) != 2:
        return False

    campos = {}
    for componente in componentes:
        if not componente or componente.count("=") != 1:
            return False
        chave, valor = componente.split("=", 1)
        if not chave or not valor or chave not in {"ts", "v1"} or chave in campos:
            return False
        campos[chave] = valor

    if set(campos) != {"ts", "v1"}:
        return False

    timestamp = campos["ts"]
    received_digest = campos["v1"]
    if (
        not _decimal_ascii_canonico_positivo(timestamp)
        or len(received_digest) != 64
        or not received_digest.isascii()
        or any(
            caractere not in "0123456789abcdef"
            for caractere in received_digest
        )
    ):
        return False

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{timestamp};"
    try:
        secret_bytes = secret.encode("utf-8")
        manifest_bytes = manifest.encode("utf-8")
    except UnicodeEncodeError:
        return False

    computed_digest = hmac.new(
        secret_bytes,
        manifest_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(computed_digest, received_digest)
