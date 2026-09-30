import uuid
from contextlib import contextmanager

from app.database import get_db
from app.models import Empresa, Plano, User
from app.security import hash_senha


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


def _email(label: str) -> str:
    return f"mei_smoke_{label}_{uuid.uuid4().hex}@example.com"


def test_existing_sem_cnpj_falha_sem_criar_usuario(client):
    email = _email("existing_sem_cnpj")

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SenhaSegura123!",
            "nome": "MEI existente sem CNPJ",
            "tipo_usuario": "mei",
            "mei_intent": "existing",
            "documento": None,
        },
    )

    assert response.status_code == 422

    with _db_session() as db:
        assert db.query(User).filter(User.email == email).first() is None


def test_mei_sem_intent_falha_sem_criar_usuario(client):
    email = _email("sem_intent")

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SenhaSegura123!",
            "nome": "MEI sem intenção",
            "tipo_usuario": "mei",
            "documento": None,
        },
    )

    assert response.status_code == 422

    with _db_session() as db:
        assert db.query(User).filter(User.email == email).first() is None


def test_existing_com_cnpj_persiste_identidade_e_owner(client):
    email = _email("existing_cnpj")

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SenhaSegura123!",
            "nome": "MEI existente smoke",
            "tipo_usuario": "mei",
            "mei_intent": "existing",
            "documento": "12.345.678/0001-95",
        },
    )

    assert response.status_code in (200, 201), response.text

    body = response.json()
    assert isinstance(body["empresa_id"], int)
    assert body["empresa_id"] > 0

    with _db_session() as db:
        user = db.query(User).filter(User.email == email).one()
        empresa = db.query(Empresa).filter(Empresa.id == body["empresa_id"]).one()

        assert empresa.user_id == user.id
        assert empresa.cnpj == "12345678000195"
        assert empresa.regime_tributario == "mei"


def test_opening_sem_cnpj_falha_sem_persistencia(client):
    email = _email("opening_bloqueado")
    nome = "MEI release " + uuid.uuid4().hex

    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "SenhaSegura123!",
            "nome": nome,
            "tipo_usuario": "mei",
            "mei_intent": "opening",
            "documento": None,
        },
    )

    assert response.status_code == 409, response.text

    with _db_session() as db:
        assert db.query(User).filter(User.email == email).first() is None
        assert (
            db.query(Empresa)
            .filter(Empresa.razao_social == nome)
            .first()
            is None
        )


def test_opening_real_fica_bloqueado_antes_de_serpro(client, monkeypatch):
    import app.routes.imposto_router as imposto_router

    email = _email("opening_das_block")
    password = "SenhaSegura123!"

    # Conta anterior ao fechamento do cadastro publico.
    with _db_session() as db:
        plano = db.query(Plano).filter(Plano.nome == "Basico").one()

        owner = User(
            email=email,
            hashed_password=hash_senha(password),
            plano_id=plano.id,
            consulta_paga=False,
        )
        db.add(owner)
        db.flush()

        empresa_legada = Empresa(
            razao_social="MEI abertura bloqueio DAS",
            regime_tributario="mei",
            cnpj=None,
            user_id=owner.id,
            status_empresa="em_abertura",
        )
        db.add(empresa_legada)
        db.commit()

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

    empresas = client.get("/empresas/", headers=headers)
    assert empresas.status_code == 200, empresas.text

    lista = empresas.json()
    assert len(lista) == 1
    empresa = lista[0]

    assert empresa["status_empresa"] == "em_abertura"
    assert empresa["cnpj"] is None

    efeitos = []

    def compose():
        efeitos.append("SERPRO_COMPOSED")
        raise AssertionError("SERPRO n?o pode ser composto para MEI em abertura")

    monkeypatch.setattr(imposto_router, "compose_serpro_pgmei", compose)
    imposto_router._get_serpro_pgmei_client.cache_clear()

    response = client.post(
        f"/imposto/mei/{empresa['id']}/das",
        headers=headers,
        json={
            "periodo_apuracao": "202609",
            "formato": "pdf",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["tipo_bloqueio"] == "EMPRESA_MEI_INATIVA"
    assert efeitos == []

    imposto_router._get_serpro_pgmei_client.cache_clear()
