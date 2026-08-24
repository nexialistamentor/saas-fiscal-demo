from decimal import Decimal

import pytest

from app.services import regime_engine
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


class _CanonicalBoundaryDenied(RuntimeError):
    pass


def test_comparar_regimes_mei_must_cross_canonical_authority_boundary(monkeypatch):
    """RED: regime comparison must not calculate MEI outside MEITaxEngine.

    The canonical boundary is forced to deny execution. If comparar_regimes()
    bypasses MEITaxEngine and calls calcular_das_mei() directly, no exception is
    observed and this contract stays RED.
    """

    def _deny(self, context):
        raise _CanonicalBoundaryDenied("canonical MEI authority boundary reached")

    monkeypatch.setattr(MEITaxEngine, "execute", _deny)

    with pytest.raises(
        _CanonicalBoundaryDenied,
        match="canonical MEI authority boundary reached",
    ):
        regime_engine.comparar_regimes(
            faturamento_anual=Decimal("12000.00"),
            atividade="servicos",
            regimes_permitidos=["mei"],
            ano_referencia=2026,
        )


def test_comparar_regimes_mei_delegates_exact_annual_semantics(monkeypatch):
    """RED: annual comparison input must reach MEITaxEngine as monthly revenue."""
    captured = {}

    def _canonical(self, context):
        captured["context"] = dict(context)
        return {
            "regime": "mei",
            "tributos": {"das": 73.45},
            "bases_calculo": {
                "faturamento_mensal": 1000.0,
                "faturamento_anual": 12000.0,
                "atividade": "servicos",
            },
            "alertas": ["canonical-engine-result"],
            "_ano_referencia": 2026,
            "_estado_temporal": "resolvido",
        }

    monkeypatch.setattr(MEITaxEngine, "execute", _canonical)

    faturamento_anual = Decimal("12000.00")
    resultado = regime_engine.comparar_regimes(
        faturamento_anual=faturamento_anual,
        atividade="servicos",
        regimes_permitidos=["mei"],
        ano_referencia=2026,
    )

    context = captured["context"]
    assert Decimal(str(context["faturamento"])) * Decimal("12") == faturamento_anual
    assert context["atividade"] == "servicos"
    assert context["ano_referencia"] == 2026

    mei = resultado.resultados["mei"]
    assert mei.carga_mensal == Decimal("73.45")
    assert mei.carga_anual == Decimal("881.40")
    assert "canonical-engine-result" in mei.alertas
