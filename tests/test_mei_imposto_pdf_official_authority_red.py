"""RED causal: PDF fiscal MEI nao pode nascer sem autoridade oficial."""

from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.routes.relatorio_router as relatorio_router
from app.main import app
from app.security import get_usuario_atual


def test_post_imposto_pdf_mei_bloqueia_sem_autoridade_oficial(monkeypatch):
    chamadas_calculo = []
    chamadas_pdf = []

    def calcular_imposto_simples_sentinela(**dados):
        chamadas_calculo.append(dados)
        return {"das": 987_654.32, "origem": "FORMULA_INTERNA_SENTINELA"}

    def gerar_pdf_imposto_espiado(resultado):
        chamadas_pdf.append(resultado)
        return BytesIO(b"%PDF-1.4\n% sentinela fiscal interna\n")

    monkeypatch.setattr(
        relatorio_router, "calcular_imposto_simples", calcular_imposto_simples_sentinela
    )
    monkeypatch.setattr(relatorio_router, "gerar_pdf_imposto", gerar_pdf_imposto_espiado)
    app.dependency_overrides[get_usuario_atual] = lambda: SimpleNamespace(id=17)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/relatorio/imposto-pdf",
                json={
                    "faturamento_mensal": 5_000.0,
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
    assert chamadas_calculo == []
    assert chamadas_pdf == []
    assert response.headers.get("content-type") != "application/pdf"
    assert not response.content.startswith(b"%PDF-")
