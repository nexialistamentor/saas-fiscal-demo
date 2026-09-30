"""Invalid existing-MEI identities must never reach the registration writer."""

import pytest
from pydantic import ValidationError

from app.database import get_db
from app.main import app
from app.schemas.user_schema import UserCreate


@pytest.mark.parametrize(
    "overrides",
    [
        {"nome": None},
        {"nome": "   "},
        {"nome": "\u200b"},
        {"documento": None},
        {"documento": "12.345.678/0001-90"},
        {"documento": "11.111.111/1111-11"},
        {"documento": "¹²³⁴⁵⁶⁷⁸⁰⁰⁰¹⁹⁵"},
        {"email": "invalid-email"},
        {"password": "short"},
    ],
)
def test_invalid_existing_mei_never_reaches_database(client, monkeypatch, overrides):
    class ForbiddenDatabase:
        def __getattr__(self, name):
            raise AssertionError(f"Invalid registration reached database: {name}")

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: ForbiddenDatabase())
    payload = {
        "email": "no-write@example.com",
        "password": "SenhaSegura123!",
        "nome": "MEI sintético",
        "tipo_usuario": "mei",
        "mei_intent": "existing",
        "documento": "12.345.678/0001-95",
    }
    payload.update(overrides)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("tipo_usuario", ["cpf", "empresa"])
def test_legacy_registration_keeps_optional_name(tipo_usuario):
    documento = "12345678901" if tipo_usuario == "cpf" else "12345678000190"
    payload = UserCreate(
        email="legacy@example.com", password="SenhaSegura123!",
        tipo_usuario=tipo_usuario, documento=documento,
    )
    assert payload.nome is None
    assert payload.documento == documento


def test_opening_keeps_optional_name_and_document():
    payload = UserCreate(
        email="opening@example.com", password="SenhaSegura123!",
        tipo_usuario="mei", mei_intent="opening",
    )
    assert payload.nome is None
    assert payload.documento is None


def test_existing_rejects_missing_email_and_password():
    with pytest.raises(ValidationError):
        UserCreate(nome="MEI sintético", tipo_usuario="mei", mei_intent="existing",
                   documento="12345678000195")
