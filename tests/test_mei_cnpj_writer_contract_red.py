import uuid
from contextlib import contextmanager

from app.database import get_db
from app.models import Empresa, User


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


def _cnpj_unico() -> str:
    return f"{uuid.uuid4().int % 10**14:014d}"


def _registrar_mei_abertura(client):
    email = f"mei_cnpj_writer_{uuid.uuid4().hex}@example.com"
    password = "SenhaSegura123!"

    # Preparacao isolada de conta legada; nao reabre cadastro publico.
    from app.models import Plano
    from app.security import hash_senha

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

        empresa = Empresa(
            razao_social="MEI legado writer",
            regime_tributario="mei",
            cnpj=None,
            user_id=owner.id,
            status_empresa="em_abertura",
        )
        db.add(empresa)
        db.commit()
        empresa_id = empresa.id

        # Preserva o estado usado pelos contratos originais do writer.
        empresa.status_empresa = "ativa"
        empresa.optante_mei = False
        db.commit()

    login = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text

    headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }

    terms = client.post("/auth/accept-terms", headers=headers)
    assert terms.status_code == 200, terms.text

    return {
        "empresa_id": empresa_id,
        "headers": headers,
    }


def test_owner_pode_completar_cnpj_ausente_sem_mudar_autoridades(client):
    ctx = _registrar_mei_abertura(client)
    cnpj = _cnpj_unico()

    response = client.patch(
        f"/empresas/{ctx['empresa_id']}/cnpj",
        headers=ctx["headers"],
        json={"cnpj": cnpj},
    )

    assert response.status_code == 200, response.text

    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == ctx["empresa_id"]).one()
        assert empresa.cnpj == cnpj
        assert empresa.status_empresa == "ativa"
        assert empresa.optante_mei is False


def test_writer_cnpj_nao_permite_overwrite_silencioso(client):
    ctx = _registrar_mei_abertura(client)
    cnpj_original = _cnpj_unico()
    cnpj_novo = _cnpj_unico()

    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == ctx["empresa_id"]).one()
        empresa.cnpj = cnpj_original
        db.commit()

    response = client.patch(
        f"/empresas/{ctx['empresa_id']}/cnpj",
        headers=ctx["headers"],
        json={"cnpj": cnpj_novo},
    )

    assert response.status_code == 409

    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == ctx["empresa_id"]).one()
        assert empresa.cnpj == cnpj_original


def test_outro_tenant_nao_pode_definir_cnpj(client):
    titular = _registrar_mei_abertura(client)
    outro = _registrar_mei_abertura(client)

    response = client.patch(
        f"/empresas/{titular['empresa_id']}/cnpj",
        headers=outro["headers"],
        json={"cnpj": _cnpj_unico()},
    )

    assert response.status_code == 403

    with _db_session() as db:
        empresa = db.query(Empresa).filter(Empresa.id == titular["empresa_id"]).one()
        assert empresa.cnpj is None


def test_writer_cnpj_bloqueia_cnpj_ja_vinculado_a_outra_empresa(client):
    titular = _registrar_mei_abertura(client)
    outra = _registrar_mei_abertura(client)
    cnpj = _cnpj_unico()

    with _db_session() as db:
        empresa_outra = db.query(Empresa).filter(
            Empresa.id == outra["empresa_id"]
        ).one()
        empresa_outra.cnpj = cnpj
        db.commit()

    response = client.patch(
        f"/empresas/{titular['empresa_id']}/cnpj",
        headers=titular["headers"],
        json={"cnpj": cnpj},
    )

    assert response.status_code == 409

    with _db_session() as db:
        empresa = db.query(Empresa).filter(
            Empresa.id == titular["empresa_id"]
        ).one()
        assert empresa.cnpj is None


def test_writer_cnpj_bloqueia_empresa_nao_mei(client):
    ctx = _registrar_mei_abertura(client)

    with _db_session() as db:
        empresa = db.query(Empresa).filter(
            Empresa.id == ctx["empresa_id"]
        ).one()
        empresa.regime_tributario = "simples"
        db.commit()

    response = client.patch(
        f"/empresas/{ctx['empresa_id']}/cnpj",
        headers=ctx["headers"],
        json={"cnpj": _cnpj_unico()},
    )

    assert response.status_code == 422

    with _db_session() as db:
        empresa = db.query(Empresa).filter(
            Empresa.id == ctx["empresa_id"]
        ).one()
        assert empresa.cnpj is None
