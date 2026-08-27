from datetime import date

import pytest

from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
from app.services.tax_engines.mei_temporal import (
    TempoNormativoMEIAmbiguoError,
    TempoNormativoMEIInvalidoError,
    resolver_data_referencia_mei,
)


def test_mei_2026_year_resolves_to_full_year_vigencia_start():
    assert resolver_data_referencia_mei({"ano_referencia": 2026}) == date(2026, 1, 1)


def test_mei_preserves_exact_reference_date():
    assert resolver_data_referencia_mei(
        {"data_referencia": "2023-06-01"}
    ) == date(2023, 6, 1)


def test_mei_2023_year_only_fails_closed_as_temporally_ambiguous():
    with pytest.raises(TempoNormativoMEIAmbiguoError, match="data_referencia exata"):
        resolver_data_referencia_mei({"ano_referencia": 2023})


def test_mei_conflicting_year_and_date_fail_closed():
    with pytest.raises(TempoNormativoMEIInvalidoError, match="divergem"):
        resolver_data_referencia_mei(
            {"ano_referencia": 2026, "data_referencia": "2025-12-31"}
        )


@pytest.mark.parametrize(
    "context",
    ({}, {"data_referencia": "2026"}, {"ano_referencia": True}),
)
def test_mei_missing_or_malformed_temporal_context_fails_closed(context):
    with pytest.raises((TempoNormativoAusenteError, TempoNormativoMEIInvalidoError)):
        resolver_data_referencia_mei(context)


def test_canonical_mei_engine_reaches_strict_temporal_resolver_before_authority(
    monkeypatch,
):
    import app.services.tax_engines.mei_tax_engine as engine_module

    calls = []

    def resolver(context):
        calls.append(dict(context))
        return date(2026, 1, 1)

    monkeypatch.setattr(engine_module, "resolver_data_referencia_mei", resolver)

    with pytest.raises(engine_module.AutoridadeFiscalIndisponivelError):
        engine_module.MEITaxEngine().execute(
            {
                "ano_referencia": 2026,
                "faturamento": 1000.0,
                "atividade": "servicos",
            }
        )

    assert calls == [
        {
            "ano_referencia": 2026,
            "faturamento": 1000.0,
            "atividade": "servicos",
        }
    ]
