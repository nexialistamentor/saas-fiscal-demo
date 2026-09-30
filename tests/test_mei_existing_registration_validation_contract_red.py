from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.user_schema import UserCreate


APP = (
    Path(__file__).resolve().parents[1]
    / "frontend-dashboard/src/App.jsx"
).read_text(encoding="utf-8")


def input_jsx(field_id):
    position = APP.index(f'id="{field_id}"')
    start = APP.rfind("<input", 0, position)
    end = APP.index("/>", position)
    return APP[start:end + 2]


def existing_mei(**overrides):
    values = {
        "email": "mei-contract@example.com",
        "password": "SenhaSegura123!",
        "nome": "MEI de teste",
        "tipo_usuario": "mei",
        "mei_intent": "existing",
        "documento": "12.345.678/0001-95",
    }
    values.update(overrides)
    return UserCreate(**values)


@pytest.mark.parametrize(
    "field_id",
    [
        "solveris-register-name",
        "solveris-register-email",
        "solveris-register-password",
    ],
)
def test_existing_mei_frontend_requires_all_fields(field_id):
    assert (
        'required={isMeiPublicJourney && meiPublicIntent === "existing"}'
        in input_jsx(field_id)
    )


def test_existing_mei_frontend_enforces_password_length():
    assert "minLength={8}" in input_jsx("solveris-register-password")


def test_existing_mei_email_has_accessible_blur_feedback():
    email_input = input_jsx("solveris-register-email")
    section = APP[
        APP.index('id="solveris-register-email"'):
        APP.index('htmlFor="solveris-register-password"')
    ]
    assert "onBlur=" in email_input
    assert "aria-invalid=" in email_input
    assert 'role="alert"' in section


@pytest.mark.parametrize("name", [None, "", "   "])
def test_existing_mei_rejects_empty_name(name):
    with pytest.raises(ValidationError):
        existing_mei(nome=name)


@pytest.mark.parametrize(
    "cnpj",
    ["12.345.678/0001-90", "00.000.000/0000-00"],
)
def test_existing_mei_rejects_invalid_cnpj_digits(cnpj):
    with pytest.raises(ValidationError):
        existing_mei(documento=cnpj)


def test_existing_mei_accepts_valid_cnpj_and_canonicalizes():
    assert existing_mei().documento == "12345678000195"


def test_other_registration_contract_remains_unchanged():
    legacy = UserCreate(
        email="legacy-contract@example.com",
        password="SenhaSegura123!",
        nome=None,
        tipo_usuario="empresa",
        documento="12.345.678/0001-90",
    )
    assert legacy.nome is None
    assert legacy.documento == "12345678000190"
