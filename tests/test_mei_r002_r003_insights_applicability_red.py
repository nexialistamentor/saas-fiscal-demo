"""RED causal: empresa nao-MEI nunca deve executar MEITaxEngine via insights."""

import uuid

from app.database import get_db
from app.models import Empresa, User
from app.services.analysis_types import ANALYSIS_TYPE_MEI_TAX
from app.services.engine_registry import ENGINES


def test_insights_nao_executa_mei_tax_engine_para_simples_nacional(
    client, auth_headers, test_user, monkeypatch
):
    assert client.post("/auth/accept-terms", headers=auth_headers).status_code == 200

    db_gen = get_db()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.email == test_user["email"]).one()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa nao-MEI MEI-R002-R003",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
            regime_tributario="simples_nacional",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    finally:
        db.close()

    chamadas = []

    def detectar_execucao_mei(_self, context):
        chamadas.append(
            {
                "empresa_id": context.get("empresa_id"),
                "regime": context.get("regime"),
            }
        )
        return {}

    monkeypatch.setattr(
        ENGINES[ANALYSIS_TYPE_MEI_TAX], "execute", detectar_execucao_mei
    )

    response = client.post(f"/insights/{empresa_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert chamadas == [], (
        "MEI-R002/R003: MEITaxEngine.execute foi chamado para empresa nao-MEI "
        f"pelo caminho publico POST /insights/{{empresa_id}}: {chamadas}"
    )


def test_insights_executa_mei_tax_engine_para_empresa_mei(
    client, auth_headers, test_user, monkeypatch
):
    assert client.post("/auth/accept-terms", headers=auth_headers).status_code == 200

    db_gen = get_db()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.email == test_user["email"]).one()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa MEI MEI-R002-R003",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
            regime_tributario="mei",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    finally:
        db.close()

    chamadas = []

    def detectar_execucao_mei(_self, context):
        chamadas.append(
            {
                "empresa_id": context.get("empresa_id"),
                "regime": context.get("regime"),
            }
        )
        return {}

    monkeypatch.setattr(
        ENGINES[ANALYSIS_TYPE_MEI_TAX], "execute", detectar_execucao_mei
    )

    response = client.post(f"/insights/{empresa_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert chamadas == [{"empresa_id": empresa_id, "regime": "mei"}]
