"""
Cliente Redis a partir de REDIS_URL: from_url + socket_connect_timeout=2 + ping.
"""

from __future__ import annotations

import os
from typing import Any, Tuple


def criar_cliente_redis() -> Any:
    """
    Cliente Redis via REDIS_URL (from_url + ping), para filas e workers.
    Falha explicitamente se REDIS_URL ausente ou inválida.

    Para throttle/revogação com fallback em memória, usar get_redis_connection().
    """
    client, redis_url, err = get_redis_connection()
    if client is not None:
        return client
    if redis_url is None:
        raise RuntimeError("REDIS_URL não definida.")
    raise RuntimeError(f"Redis indisponível em {redis_url!r}: {err}") from err


def get_redis_connection() -> Tuple[Any | None, str | None, Exception | None]:
    """
    Devolve (cliente, url, erro).
    - Sem REDIS_URL: (None, None, None).
    - Com URL e sucesso: (cliente, url, None).
    - Com URL e falha: (None, url, excepção).
    """
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None, None, None
    try:
        import redis as redis_lib

        client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
        client.ping()
        return client, redis_url, None
    except Exception as exc:
        return None, redis_url, exc
