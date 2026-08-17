from types import SimpleNamespace

from app.services.analysis_orchestrator import executar_analise


def test_empresa_tax_mei_converge_para_autoridade_canonica():
    resultado = executar_analise(
        "empresa_tax",
        {
            "faturamento": 5_000.0,
            "atividade": "servicos",
            "ano_referencia": 2026,
        },
        empresa=SimpleNamespace(regime_tributario="mei"),
    )

    assert resultado.get("analysis_type") == "mei_tax"
