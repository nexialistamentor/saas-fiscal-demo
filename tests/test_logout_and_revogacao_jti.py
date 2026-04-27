"""
RA6: /auth/logout + revogação de JTI: após logout o token deixa de validar.
"""
import uuid

import fakeredis
from fastapi.testclient import TestClient

from app.main import app
from app.token_revocation import revogacao_jti


def _cpf_unico_valido() -> str:
    """11 dígitos com DV válido; base aleatória evita conflito UNIQUE (cpf) no CI."""
    base = f"{uuid.uuid4().int % 10**9:09d}"
    s = 0
    for i, d in enumerate(base):
        s += int(d) * (10 - i)
    r = s % 11
    d1 = 0 if r < 2 else 11 - r
    s = sum(int(base[i]) * (11 - i) for i in range(9)) + d1 * 2
    r2 = s % 11
    d2 = 0 if r2 < 2 else 11 - r2
    return base + f"{d1}{d2}"


def test_logout_idempotente_apos_revoq_cheio_memoria():
    """Sem Redis: revoga, /me falha, segundo logout com o mesmo token responde 200."""
    r_store = revogacao_jti
    prev_redis = r_store._redis
    try:
        r_store._redis = None
        r_store._mem.clear()
        with TestClient(app) as c:
            email = f"u{uuid.uuid4().hex}@example.com"
            p = f"x{uuid.uuid4().hex}8"
            res = c.post(
                "/auth/register",
                json={
                    "email": email,
                    "password": p,
                    "tipo_usuario": "cpf",
                    "documento": _cpf_unico_valido(),
                },
            )
            assert res.status_code in (200, 201)
            t = c.post(
                "/auth/login",
                data={"username": email, "password": p},
            )
            assert t.status_code == 200, t.text
            token = t.json()["access_token"]
            h = {"Authorization": f"Bearer {token}"}
            assert c.get("/auth/me", headers=h).status_code == 200
            assert c.post("/auth/logout", headers=h).status_code == 200
            assert c.get("/auth/me", headers=h).status_code == 401
            assert c.post("/auth/logout", headers=h).status_code == 200
    finally:
        r_store._redis = prev_redis
        r_store._mem.clear()


def test_revoq_jti_path_redis_fakeredis():
    r = revogacao_jti
    prev = r._redis
    try:
        r._redis = fakeredis.FakeRedis()
        r._mem.clear()
        jti = "jti-" + uuid.uuid4().hex
        assert r.esta_revogado(jti) is False
        r.registrar(jti, int(__import__("time").time()) + 120)
        assert r.esta_revogado(jti) is True
    finally:
        r._redis = prev
        r._mem.clear()
