"""MEI-R008: preservar ausencia de faturamento ate ao MEITaxEngine."""

import uuid

from app.database import get_db
from app.models import Empresa, User
from app.services.analysis_types import ANALYSIS_TYPE_MEI_TAX
from app.services.engine_registry import ENGINES


def test_insights_mei_sem_faturamento_entrega_ausencia_ao_mei_tax_engine(
    client, auth_headers, test_user, monkeypatch
):
    assert client.post("/auth/accept-terms", headers=auth_headers).status_code == 200

    db_gen = get_db()
    db = next(db_gen)
    try:
        user = db.query(User).filter(User.email == test_user["email"]).one()
        empresa = Empresa(
            user_id=user.id,
            razao_social="Empresa MEI sem faturamento MEI-R008",
            cnpj=f"{uuid.uuid4().int % 10**14:014d}",
            regime_tributario="mei",
        )
        db.add(empresa)
        db.commit()
        db.refresh(empresa)
        empresa_id = empresa.id
    finally:
        db.close()

    contextos_recebidos = []

    def capturar_contexto(_self, context):
        contextos_recebidos.append(dict(context))
        return {}

    monkeypatch.setattr(ENGINES[ANALYSIS_TYPE_MEI_TAX], "execute", capturar_contexto)

    response = client.post(f"/insights/{empresa_id}", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert len(contextos_recebidos) == 1
    assert contextos_recebidos[0]["faturamento"] is None, (
        "MEI-R008: ausencia real de faturamento foi convertida antes do "
        f"MEITaxEngine; valor recebido={contextos_recebidos[0]['faturamento']!r}"
    )
