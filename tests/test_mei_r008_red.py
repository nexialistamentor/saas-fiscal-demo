"""MEI-R008: faturamento material ausente deve falhar explicitamente."""

import pytest

from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_mei_com_faturamento_ausente_falha_sem_produzir_resultado_fiscal():
    with pytest.raises((KeyError, TypeError, ValueError), match="(?i)faturamento"):
        MEITaxEngine().execute(
            {
                "atividade": "servicos",
                "ano_referencia": 2026,
            }
        )
