"""
Protecção anti-brute-force em duas camadas:
  1. Rate limit por IP (slowapi) — partilhado com toda a app
  2. Lockout por conta — bloqueia temporariamente após N falhas consecutivas
"""

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
_JANELA_SEGUNDOS = 900      # 15 min — janela de contagem
_LOCKOUT_SEGUNDOS = 900     # 15 min — duração do bloqueio


class _ContadorFalhas:
    __slots__ = ("tentativas", "primeiro_erro", "bloqueado_ate")

    def __init__(self) -> None:
        self.tentativas: int = 0
        self.primeiro_erro: float = 0.0
        self.bloqueado_ate: float = 0.0


class LoginThrottle:
    """Rastreio thread-safe de falhas de login por email (in-memory)."""

    def __init__(
        self,
        max_tentativas: int = _MAX_TENTATIVAS,
        janela: int = _JANELA_SEGUNDOS,
        lockout: int = _LOCKOUT_SEGUNDOS,
    ) -> None:
        self._max = max_tentativas
        self._janela = janela
        self._lockout = lockout
        self._store: dict[str, _ContadorFalhas] = defaultdict(_ContadorFalhas)
        self._lock = threading.Lock()

    def esta_bloqueado(self, email: str) -> bool:
        """Retorna True se a conta está em lockout."""
        email = email.lower().strip()
        with self._lock:
            c = self._store.get(email)
            if c is None:
                return False
            agora = time.monotonic()
            if c.bloqueado_ate and agora < c.bloqueado_ate:
                return True
            if c.bloqueado_ate and agora >= c.bloqueado_ate:
                self._store.pop(email, None)
            return False

    def registrar_falha(self, email: str) -> bool:
        """Registra tentativa falhada. Retorna True se entrou em lockout."""
        email = email.lower().strip()
        agora = time.monotonic()
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
                    email, self._lockout, c.tentativas,
                )
                return True
        return False

    def limpar(self, email: str) -> None:
        """Limpa registo de falhas (chamar após login bem-sucedido)."""
        email = email.lower().strip()
        with self._lock:
            self._store.pop(email, None)

    def tempo_restante(self, email: str) -> int:
        """Segundos restantes de lockout (0 se não bloqueado)."""
        email = email.lower().strip()
        with self._lock:
            c = self._store.get(email)
            if c is None:
                return 0
            agora = time.monotonic()
            if c.bloqueado_ate and agora < c.bloqueado_ate:
                return int(c.bloqueado_ate - agora)
        return 0


login_throttle = LoginThrottle()
