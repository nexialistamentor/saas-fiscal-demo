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
