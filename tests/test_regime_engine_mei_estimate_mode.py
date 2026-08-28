from decimal import Decimal

from app.services import regime_engine
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_comparar_regimes_envia_contexto_mei_em_modo_estimativa(monkeypatch):
    captured = {}

    def _capture(self, context):
        captured["context"] = dict(context)
        return {
            "regime": "mei",
            "tributos": {"das": 86.05},
            "bases_calculo": {},
            "alertas": [],
        }

    monkeypatch.setattr(MEITaxEngine, "execute", _capture)

    faturamento_anual = Decimal("60000.12")
    regime_engine.comparar_regimes(
        faturamento_anual=faturamento_anual,
        atividade="comercio",
        regimes_permitidos=["mei"],
        ano_referencia=2026,
    )

    assert captured["context"] == {
        "modo": "estimativa",
        "faturamento": faturamento_anual / Decimal("12"),
        "faturamento_anual": faturamento_anual,
        "atividade": "comercio",
        "ano_referencia": 2026,
    }
