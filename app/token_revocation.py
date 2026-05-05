"""
Registo de JWTs revogados (logout). Redis em produção; fallback em memória.
A verificação integra-se em app.security.verificar_token via jti.
"""

import threading
import time
import logging
from datetime import datetime

from app.redis_connection import get_redis_connection

logger = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "auth:revoked_jti:"


def _exp_para_unix_seconds(exp) -> float:
    if exp is None:
        return time.time() + 900.0
    if isinstance(exp, (int, float)):
        return float(exp)
    if isinstance(exp, datetime):
        return exp.timestamp()
    return float(exp)


class RevogacaoJti:
    def __init__(self) -> None:
        client, redis_url, err = get_redis_connection()
        self._redis = client
        if self._redis:
            logger.info("RevogacaoJti: Redis activo")
        elif redis_url:
            logger.warning(
                "RevogacaoJti: Redis indisponível (%s) — fallback em memória",
                err,
            )
        self._mem: dict[str, float] = {}
        self._lock = threading.Lock()

    def _k(self, jti: str) -> str:
        return _REDIS_KEY_PREFIX + jti

    def esta_revogado(self, jti: str) -> bool:
        if not jti:
            return False
        if self._redis:
            try:
                return self._redis.exists(self._k(jti)) > 0
            except Exception as exc:
                logger.warning("RevogacaoJti.esta_revogado: Redis (%s) — memória", exc)
        with self._lock:
            exp_at = self._mem.get(jti)
            if exp_at is None:
                return False
            if time.time() > exp_at:
                del self._mem[jti]
                return False
            return True

    def registrar(self, jti: str, exp) -> None:
        exp_unix = _exp_para_unix_seconds(exp)
        ttl = int(exp_unix - time.time()) + 2
        if ttl < 1:
            ttl = 1
        if self._redis:
            try:
                self._redis.setex(self._k(jti), ttl, "1")
                return
            except Exception as exc:
                logger.warning("RevogacaoJti.registrar: Redis (%s) — memória", exc)
        with self._lock:
            self._mem[jti] = exp_unix


revogacao_jti = RevogacaoJti()
