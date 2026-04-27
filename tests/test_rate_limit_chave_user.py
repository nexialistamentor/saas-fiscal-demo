"""
Chave de rate limit: JWT válido => user:email; caso contrário => IP.
"""
from unittest.mock import MagicMock

from starlette.datastructures import Headers

from app.rate_limit import obter_chave_rate_limit
from app.security import criar_token


def test_chave_por_bearer_valido_é_utilizador():
    token = criar_token({"sub": "Util@Exemplo.com"})
    request = MagicMock()
    request.headers = Headers(
        raw=[
            (
                b"authorization",
                f"Bearer {token}".encode("utf-8"),
            )
        ]
    )
    request.client = MagicMock()
    request.client.host = "203.0.113.1"
    assert obter_chave_rate_limit(request) == "user:util@exemplo.com"


def test_sem_authorization_usa_ip():
    request = MagicMock()
    request.headers = Headers()
    request.client = MagicMock()
    request.client.host = "10.0.0.2"
    assert obter_chave_rate_limit(request) == "10.0.0.2"


def test_bearer_inválido_usa_ip():
    request = MagicMock()
    request.headers = Headers(
        raw=[(b"authorization", b"Bearer nao-um-jwt")]
    )
    request.client = MagicMock()
    request.client.host = "10.0.0.3"
    assert obter_chave_rate_limit(request) == "10.0.0.3"


def test_cabeçalho_authorization_dict_chave_maiúscula():
    """Headers a partir de mapping: chave 'Authorization' é normalizada."""
    token = criar_token({"sub": "a@b.pt"})
    request = MagicMock()
    request.headers = Headers(headers={"Authorization": f"Bearer {token}"})
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    assert obter_chave_rate_limit(request) == "user:a@b.pt"
