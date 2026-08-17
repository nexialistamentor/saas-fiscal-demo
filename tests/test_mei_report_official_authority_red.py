"""RED causal: calculo MEI interno nao e autoridade fiscal operacional oficial."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.database import get_db
from app.main import app
from app.security import get_usuario_atual


def test_mei_interno_nao_pode_ser_persistido_como_relatorio_oficial_sem_autoridade(
    monkeypatch,
):
    estado = SimpleNamespace(calculos=0, added=[], committed=False)

    class DBFake:
        def add(self, relatorio):
            estado.added.append(relatorio)
            relatorio.id = 731

        def commit(self):
            estado.committed = True

        def refresh(self, _relatorio):
            pass

    def override_db():
        yield DBFake()

    def calcular_imposto_simples_nao_autorizado(**_dados):
        estado.calculos += 1
        return {"das": 987654.32}

    monkeypatch.setattr(
        relatorio_router,
        "calcular_imposto_simples",
        calcular_imposto_simples_nao_autorizado,
    )
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(
        id=17,
        consulta_paga=True,
    )
    app.dependency_overrides[get_db] = override_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/relatorio/mei_tax",
                json={
                    "faturamento_mensal": 5000.0,
                    "despesas": 0.0,
                    "tipo_usuario": "MEI",
                    "atividade": "comercio",
                    "ano_referencia": 2026,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert (
        response.json()["detail"]["tipo_bloqueio"]
        == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    )
    assert estado.calculos == 0
    assert estado.added == []
    assert estado.committed is False
