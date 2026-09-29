import uuid
from contextlib import contextmanager

import pytest

from app.database import get_db
from app.models import Empresa, User


@contextmanager
def db_session():
    generator = get_db()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


@pytest.mark.parametrize("with_document", [False, True])
def test_public_register_rejects_opening_without_persistence(
    client, with_document
):
    marker = "mei_release_" + uuid.uuid4().hex
    email = marker + "@example.com"
    documento = (
        f"{uuid.uuid4().int % 10**14:014d}"
        if with_document else None
    )

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SenhaSegura123!",
            "nome": marker,
            "tipo_usuario": "mei",
            "mei_intent": "opening",
            "documento": documento,
        },
    )

    assert response.status_code == 409, response.text

    with db_session() as db:
        assert db.query(User).filter(User.email == email).first() is None
        assert (
            db.query(Empresa)
            .filter(Empresa.razao_social == marker)
            .first()
            is None
        )
