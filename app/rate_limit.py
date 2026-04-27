"""
Protecção anti-brute-force em duas camadas:
  1. Rate limit por IP (slowapi) — partilhado com toda a app
  2. Lockout por conta — bloqueia temporariamente após N falhas consecutivas
     Armazenamento: Redis (produção) com fallback para memória (se Redis indisponível)
"""

import os
import time
import threading
import logging
from collections import defaultdict

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# ── Camada 1: Rate limit global por IP (slowapi) ──────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute"],
)

# ── Camada 2: Lockout por conta ───────────────────────────────────────
_MAX_TENTATIVAS = 5
_JANELA_SEGUNDOS = 900  # 15 min — janela de contagem
_LOCKOUT_SEGUNDOS = 900  # 15 min — duração do bloqueio

# ── Prefixos Redis ────────────────────────────────────────────────────
_REDIS_PREFIX_TENTATIVAS = "throttle:tentativas:"
_REDIS_PREFIX_PRIMEIRO = "throttle:primeiro_erro:"
_REDIS_PREFIX_BLOQUEADO = "throttle:bloqueado_ate:"


class _ContadorFalhas:
    __slots__ = ("tentativas", "primeiro_erro", "bloqueado_ate")

    def __init__(self) -> None:
        self.tentativas: int = 0
        self.primeiro_erro: float = 0.0
        self.bloqueado_ate: float = 0.0


class LoginThrottle:
    """
    Rastreio de falhas de login por email.
    Usa Redis quando disponível; fallback thread-safe em memória.
    """

    def __init__(
        self,
        max_tentativas: int = _MAX_TENTATIVAS,
        janela: int = _JANELA_SEGUNDOS,
        lockout: int = _LOCKOUT_SEGUNDOS,
    ) -> None:
        self._max = max_tentativas
        self._janela = janela
        self._lockout = lockout

        # Tentativa de conexão Redis
        self._redis = None
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            try:
                import redis as redis_lib

                client = redis_lib.from_url(redis_url, socket_connect_timeout=2)
                client.ping()
                self._redis = client
                logger.info("LoginThrottle: usando Redis (%s)", redis_url)
            except Exception as exc:
                logger.warning(
                    "LoginThrottle: Redis indisponível (%s) — fallback para memória", exc
                )
        else:
            logger.warning(
                "LoginThrottle: REDIS_URL não definida — fallback para memória "
                "(throttle não sobrevive a restart ou múltiplos workers)"
            )

        # Fallback em memória
        self._store: dict[str, _ContadorFalhas] = defaultdict(_ContadorFalhas)
        self._lock = threading.Lock()

    # ── Helpers Redis ─────────────────────────────────────────────────

    def _r_esta_bloqueado(self, email: str) -> bool:
        val = self._redis.get(_REDIS_PREFIX_BLOQUEADO + email)
        if val is None:
            return False
        bloqueado_ate = float(val)
        if time.time() < bloqueado_ate:
            return True
        # Expirou — limpar (TTL devia ter apagado, mas garante consistência)
        self._r_limpar(email)
        return False

    def _r_registrar_falha(self, email: str) -> bool:
        agora = time.time()
        pipe = self._redis.pipeline()

        k_tent = _REDIS_PREFIX_TENTATIVAS + email
        k_prim = _REDIS_PREFIX_PRIMEIRO + email
        k_bloq = _REDIS_PREFIX_BLOQUEADO + email

        # Lê estado actual
        tentativas_raw = self._redis.get(k_tent)
        primeiro_raw = self._redis.get(k_prim)

        tentativas = int(tentativas_raw) if tentativas_raw else 0
        primeiro_erro = float(primeiro_raw) if primeiro_raw else 0.0

        # Janela expirada — reset
        if primeiro_erro and (agora - primeiro_erro) > self._janela:
            tentativas = 0
            primeiro_erro = 0.0

        if tentativas == 0:
            primeiro_erro = agora

        tentativas += 1

        # Persiste
        pipe.set(k_tent, tentativas, ex=self._lockout * 2)
        pipe.set(k_prim, primeiro_erro, ex=self._lockout * 2)

        if tentativas >= self._max:
            bloqueado_ate = agora + self._lockout
            pipe.set(k_bloq, bloqueado_ate, ex=self._lockout)
            pipe.execute()
            logger.warning(
                "Conta %s bloqueada por %ds após %d tentativas falhadas",
                email,
                self._lockout,
                tentativas,
            )
            return True

        pipe.execute()
        return False

    def _r_limpar(self, email: str) -> None:
        self._redis.delete(
            _REDIS_PREFIX_TENTATIVAS + email,
            _REDIS_PREFIX_PRIMEIRO + email,
            _REDIS_PREFIX_BLOQUEADO + email,
        )

    def _r_tempo_restante(self, email: str) -> int:
        val = self._redis.get(_REDIS_PREFIX_BLOQUEADO + email)
        if val is None:
            return 0
        restante = float(val) - time.time()
        return int(restante) if restante > 0 else 0

    # ── Interface pública ─────────────────────────────────────────────

    def esta_bloqueado(self, email: str) -> bool:
        email = email.lower().strip()
        if self._redis:
            try:
                return self._r_esta_bloqueado(email)
            except Exception as exc:
                logger.warning("LoginThrottle.esta_bloqueado: Redis falhou (%s), usando memória", exc)

        with self._lock:
            c = self._store.get(email)
            if c is None:
                return False
            agora = time.time()
            if c.bloqueado_ate and agora < c.bloqueado_ate:
                return True
            if c.bloqueado_ate and agora >= c.bloqueado_ate:
                self._store.pop(email, None)
            return False

    def registrar_falha(self, email: str) -> bool:
        email = email.lower().strip()
        if self._redis:
            try:
                return self._r_registrar_falha(email)
            except Exception as exc:
                logger.warning("LoginThrottle.registrar_falha: Redis falhou (%s), usando memória", exc)

        agora = time.time()
        with self._lock:
            c = self._store[email]
            if c.primeiro_erro and (agora - c.primeiro_erro) > self._janela:
                c.tentativas = 0
                c.primeiro_erro = 0.0
            if c.tentativas == 0:
                c.primeiro_erro = agora
            c.tentativas += 1
            if c.tentativas >= self._max:
                c.bloqueado_ate = agora + self._lockout
                logger.warning(
                    "Conta %s bloqueada por %ds após %d tentativas falhadas",
                    email,
                    self._lockout,
                    c.tentativas,
                )
                return True
        return False

    def limpar(self, email: str) -> None:
        email = email.lower().strip()
        if self._redis:
            try:
                self._r_limpar(email)
                return
            except Exception as exc:
                logger.warning("LoginThrottle.limpar: Redis falhou (%s), usando memória", exc)

        with self._lock:
            self._store.pop(email, None)

    def tempo_restante(self, email: str) -> int:
        email = email.lower().strip()
        if self._redis:
            try:
                return self._r_tempo_restante(email)
            except Exception as exc:
                logger.warning("LoginThrottle.tempo_restante: Redis falhou (%s), usando memória", exc)

        with self._lock:
            c = self._store.get(email)
            if c is None:
                return 0
            agora = time.time()
            if c.bloqueado_ate and agora < c.bloqueado_ate:
                return int(c.bloqueado_ate - agora)
        return 0


login_throttle = LoginThrottle()
