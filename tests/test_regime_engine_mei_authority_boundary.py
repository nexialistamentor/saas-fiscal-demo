from decimal import Decimal

import pytest

from app.services import regime_engine
from app.services.tax_engines.mei_tax_engine import (
    AutoridadeFiscalIndisponivelError,
    AutoridadeNormativaMEIIndisponivelError,
    MEITaxEngine,
)


def _resultado_simples_stub() -> regime_engine.ResultadoRegime:
    return regime_engine.ResultadoRegime(
        regime="simples",
        carga_anual=Decimal("1200.00"),
        carga_mensal=Decimal("100.00"),
        aliquota_efetiva_pct=10.0,
        anexo_simples="III",
        fator_r=None,
        alertas=[],
        detalhes={"stub": True},
    )


@pytest.mark.parametrize(
    ("erro_autoridade", "codigo", "motivo"),
    [
        (
            AutoridadeNormativaMEIIndisponivelError(motivo="BINDING_MISSING"),
            AutoridadeNormativaMEIIndisponivelError.codigo,
            "BINDING_MISSING",
        ),
        (
            AutoridadeFiscalIndisponivelError(
                fonte_id="PGMEI-001",
                motivo="FONTE_INDISPONIVEL",
            ),
            AutoridadeFiscalIndisponivelError.codigo,
            "FONTE_INDISPONIVEL",
        ),
    ],
)
def test_comparar_regimes_mei_authority_denial_is_non_evaluated_without_aborting_others(
    monkeypatch,
    erro_autoridade,
    codigo,
    motivo,
):
    """RED: authority denial must fail closed for MEI without aborting composition."""

    def _deny(self, context):
        raise erro_autoridade

    monkeypatch.setattr(MEITaxEngine, "execute", _deny)
    monkeypatch.setattr(
        regime_engine,
        "calcular_simples",
        lambda *args, **kwargs: _resultado_simples_stub(),
    )

    resultado = regime_engine.comparar_regimes(
        faturamento_anual=Decimal("12000.00"),
        folha_anual=Decimal("0"),
        secao_cnae="J",
        atividade="servicos",
        regimes_permitidos=["mei", "simples"],
        ano_referencia=2026,
    )

    assert resultado.regime_recomendado == "simples"
    assert "simples" in resultado.resultados
    assert "mei" not in resultado.resultados
    assert "mei" not in resultado.regimes_inelegiveis

    estado_mei = resultado.regimes_nao_avaliados["mei"]
    assert estado_mei["estado"] == "autoridade_indisponivel"
    assert estado_mei["codigo"] == codigo
    assert estado_mei["motivo"] == motivo


def test_comparar_regimes_mei_preserves_exact_annual_fact_at_canonical_boundary(monkeypatch):
    """RED: exact annual fact must cross the canonical boundary without float reconstruction."""
    captured = {}

    def _canonical(self, context):
        captured["context"] = dict(context)
        return {
            "regime": "mei",
            "tributos": {"das": 86.05},
            "bases_calculo": {
                "faturamento_mensal": context["faturamento"],
                "faturamento_anual": context["faturamento_anual"],
                "atividade": "servicos",
            },
            "alertas": [],
            "_ano_referencia": 2026,
            "_estado_temporal": "resolvido",
        }

    monkeypatch.setattr(MEITaxEngine, "execute", _canonical)

    faturamento_anual = Decimal("80000.01")
    resultado = regime_engine.comparar_regimes(
        faturamento_anual=faturamento_anual,
        atividade="servicos",
        regimes_permitidos=["mei"],
        ano_referencia=2026,
    )

    context = captured["context"]
    assert context["faturamento_anual"] == faturamento_anual
    assert isinstance(context["faturamento_anual"], Decimal)
    assert isinstance(context["faturamento"], Decimal)

    mei = resultado.resultados["mei"]
    assert mei.carga_mensal == Decimal("86.05")
    assert mei.carga_anual == Decimal("1032.60")
