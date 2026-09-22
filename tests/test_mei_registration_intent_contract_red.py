import pytest
from pydantic import ValidationError

from app.schemas.user_schema import UserCreate


def test_mei_existing_sem_cnpj_deve_falhar_fechado():
    with pytest.raises(ValidationError):
        UserCreate(
            email="existing-mei@example.com",
            password="SenhaSegura123!",
            nome="MEI existente",
            tipo_usuario="mei",
            mei_intent="existing",
            documento=None,
        )


def test_mei_opening_pode_iniciar_sem_cnpj():
    payload = UserCreate(
        email="opening-mei@example.com",
        password="SenhaSegura123!",
        nome="MEI em abertura",
        tipo_usuario="mei",
        mei_intent="opening",
        documento=None,
    )

    assert payload.tipo_usuario == "mei"
    assert payload.documento is None


def test_mei_existing_com_cnpj_preserva_documento_canonico():
    payload = UserCreate(
        email="existing-mei-cnpj@example.com",
        password="SenhaSegura123!",
        nome="MEI existente",
        tipo_usuario="mei",
        mei_intent="existing",
        documento="12.345.678/0001-90",
    )

    assert payload.documento == "12345678000190"

def test_mei_sem_intencao_deve_falhar_fechado():
    with pytest.raises(ValidationError):
        UserCreate(
            email="mei-sem-intencao@example.com",
            password="SenhaSegura123!",
            nome="MEI sem intenção",
            tipo_usuario="mei",
            documento=None,
        )

def test_mei_opening_preserva_intencao_no_contrato():
    payload = UserCreate(
        email="opening-intent@example.com",
        password="SenhaSegura123!",
        nome="MEI em abertura",
        tipo_usuario="mei",
        mei_intent="opening",
        documento=None,
    )

    assert payload.mei_intent == "opening"


def test_mei_existing_preserva_intencao_no_contrato():
    payload = UserCreate(
        email="existing-intent@example.com",
        password="SenhaSegura123!",
        nome="MEI existente",
        tipo_usuario="mei",
        mei_intent="existing",
        documento="12.345.678/0001-90",
    )

    assert payload.mei_intent == "existing"
