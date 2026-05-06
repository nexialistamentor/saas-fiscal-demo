"""Fixtures partilhados pelos testes HTTP."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


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


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def test_user(client):
    email = f"terms_{uuid.uuid4().hex}@example.com"
    password = f"p{uuid.uuid4().hex}"
    res = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "tipo_usuario": "cpf",
            "documento": _cpf_unico_valido(),
        },
    )
    assert res.status_code in (200, 201), res.text
    return {"email": email, "password": password}


@pytest.fixture
def auth_headers(client, test_user):
    t = client.post(
        "/auth/login",
        data={"username": test_user["email"], "password": test_user["password"]},
    )
    assert t.status_code == 200, t.text
    token = t.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
