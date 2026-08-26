from types import SimpleNamespace

import pytest

from app.routes import relatorio_router
from app.routes.imposto_router import DadosImposto
from app.services.analysis_types import ANALYSIS_TYPE_CPF_TAX


class _FakeDB:
    def __init__(self):
        self.added = None

    def add(self, obj):
        self.added = obj

    def commit(self):
        pass

    def refresh(self, obj):
        pass


@pytest.mark.asyncio
async def test_cpf_report_must_not_be_persisted_as_mei_tax(monkeypatch):
    db = _FakeDB()
    usuario = SimpleNamespace(
        id=123,
        consulta_paga=True,
    )
    dados = DadosImposto(
        tipo_usuario="CPF",
        faturamento_mensal=1000,
        despesas=100,
    )

    monkeypatch.setattr(
        relatorio_router,
        "calcular_imposto_simples",
        lambda **kwargs: {
            "tipo": "CPF",
            "imposto": 10.0,
        },
    )

    await relatorio_router.gerar_relatorio_mei_tax(
        dados=dados,
        usuario_atual=usuario,
        db=db,
    )

    assert db.added is not None
    assert db.added.analysis_type == ANALYSIS_TYPE_CPF_TAX
