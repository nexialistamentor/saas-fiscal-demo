"""
Garante que o path Redis de LoginThrottle (sem fallback em memória) se comporta
como o esperado: 5 falhas consecutivas activam lockout, tempo restante, limpar.
Emulação via fakeredis (mesma API que redis-py).
"""
import pytest

import fakeredis

from app.rate_limit import LoginThrottle


def test_redis_path_cinco_falhas_lockout_tempo_restante_limpar():
    t = LoginThrottle()
    t._redis = fakeredis.FakeRedis()
    email = "teste@exemplo.com"

    assert t.esta_bloqueado(email) is False
    for i in range(4):
        assert t.registrar_falha(email) is False, f"após {i+1} falha(s) não deve lockout"
    assert t.registrar_falha(email) is True
    assert t.esta_bloqueado(email) is True
    assert t.tempo_restante(email) > 0
    t.limpar(email)
    assert t.esta_bloqueado(email) is False
