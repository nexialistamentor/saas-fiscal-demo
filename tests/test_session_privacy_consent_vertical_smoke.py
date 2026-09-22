import uuid
from contextlib import contextmanager

from app.constants import (
    FINALIDADE_SIMULACAO,
    VERSAO_POLITICA_PRIVACIDADE,
)
from app.database import get_db
from app.models import ConsentimentoLGPD, User


@contextmanager
def _db_session():
    generator = get_db()
    db = next(generator)
    try:
        yield db
    finally:
        try:
            next(generator)
        except StopIteration:
            pass


def test_consentimento_privacidade_persiste_e_libera_estado_real(client):
    email = f"mei_consent_smoke_{uuid.uuid4().hex}@example.com"
    password = "SenhaSegura123!"

    registered = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "nome": "MEI consent smoke",
            "tipo_usuario": "mei",
            "mei_intent": "opening",
            "documento": None,
        },
    )
    assert registered.status_code in (200, 201), registered.text

    logged_in = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text

    headers = {
        "Authorization": f"Bearer {logged_in.json()['access_token']}"
    }

    accepted = client.post("/auth/accept-terms", headers=headers)
    assert accepted.status_code == 200, accepted.text

    terms_state = client.get("/auth/has-accepted-terms", headers=headers)
    assert terms_state.status_code == 200
    assert terms_state.json()["accepted"] is True

    consent_before = client.get("/auth/has-consented", headers=headers)
    assert consent_before.status_code == 200
    assert consent_before.json()["consented"] is False

    with _db_session() as db:
        user = db.query(User).filter(User.email == email).one()
        before = (
            db.query(ConsentimentoLGPD)
            .filter(ConsentimentoLGPD.user_id == user.id)
            .all()
        )
        assert before == []

    consent = client.post("/auth/consent", headers=headers)
    assert consent.status_code == 200, consent.text
    assert consent.json()["versao_politica"] == VERSAO_POLITICA_PRIVACIDADE

    consent_after = client.get("/auth/has-consented", headers=headers)
    assert consent_after.status_code == 200
    assert consent_after.json()["consented"] is True

    with _db_session() as db:
        user = db.query(User).filter(User.email == email).one()
        rows = (
            db.query(ConsentimentoLGPD)
            .filter(
                ConsentimentoLGPD.user_id == user.id,
                ConsentimentoLGPD.versao_politica == VERSAO_POLITICA_PRIVACIDADE,
                ConsentimentoLGPD.finalidade == FINALIDADE_SIMULACAO,
                ConsentimentoLGPD.consentiu.is_(True),
            )
            .all()
        )

        assert len(rows) == 1
