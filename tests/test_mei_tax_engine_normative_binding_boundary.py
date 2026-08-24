"""RED: MEI engine must not produce DAS without authoritative normative bindings."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace


def test_mei_tax_engine_blocks_missing_normative_bindings_before_calcular_das(
    monkeypatch,
):
    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    monkeypatch.setattr(
        mei_tax_engine,
        "verificar",
        lambda request: SimpleNamespace(
            permitido=True,
            fonte_id=request.fonte_id,
            motivo="autoridade operacional controlada exclusivamente pelo teste",
        ),
    )

    producer_calls: list[tuple[tuple, dict]] = []

    def _forbidden_producer(*args, **kwargs):
        producer_calls.append((args, kwargs))
        return 999.99

    monkeypatch.setattr(
        mei_tax_engine,
        "calcular_das_mei",
        _forbidden_producer,
    )

    caught: Exception | None = None
    result = None

    try:
        result = mei_tax_engine.MEITaxEngine().execute(
            {
                "data_referencia": date(2026, 1, 15),
                "faturamento": 1000.00,
                "atividade": "servicos",
            }
        )
    except Exception as exc:
        caught = exc

    assert producer_calls == [], (
        "calcular_das_mei was reached without authoritative normative "
        "binding validation"
    )
    assert result is None, (
        "MEITaxEngine returned a definitive MEI result without "
        "authoritative normative bindings"
    )
    assert caught is not None, (
        "MEITaxEngine did not fail closed when authoritative normative "
        "bindings were unavailable"
    )
