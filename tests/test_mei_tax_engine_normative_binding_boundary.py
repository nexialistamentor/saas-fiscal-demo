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


def test_estimativa_binding_negado_bloqueia_salario_e_calculo(monkeypatch):
    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    calls = []
    monkeypatch.setattr(
        mei_tax_engine,
        "validar_bindings_normativos",
        lambda payload: SimpleNamespace(
            autorizado_fundamentar_decisao=False,
            bindings_validados=3,
        ),
    )
    monkeypatch.setattr(
        mei_tax_engine, "obter_salario_minimo", lambda ano: calls.append("salario")
    )
    monkeypatch.setattr(
        mei_tax_engine, "calcular_das_mei", lambda *args: calls.append("calculo")
    )

    try:
        mei_tax_engine.MEITaxEngine().execute(
            {
                "ano_referencia": 2026,
                "faturamento": 1000.0,
                "atividade": "servicos",
                "modo": "estimativa",
            }
        )
    except mei_tax_engine.AutoridadeNormativaMEIIndisponivelError:
        pass
    else:
        raise AssertionError("binding negado nao bloqueou a estimativa")

    assert calls == []


def test_estimativa_2026_autorizada_calcula_sem_pgmei(monkeypatch):
    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    monkeypatch.setattr(
        mei_tax_engine,
        "verificar",
        lambda request: (_ for _ in ()).throw(AssertionError("PGMEI consultado")),
    )

    result = mei_tax_engine.MEITaxEngine().execute(
        {
            "ano_referencia": 2026,
            "faturamento": 1000.0,
            "atividade": "servicos",
            "modo": "estimativa",
        }
    )

    assert result["modo"] == "estimativa"


def test_binding_2026_nao_e_reutilizado_fora_de_2026(monkeypatch):
    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    calls = []
    monkeypatch.setattr(
        mei_tax_engine, "obter_salario_minimo", lambda ano: calls.append("salario")
    )
    monkeypatch.setattr(
        mei_tax_engine, "calcular_das_mei", lambda *args: calls.append("calculo")
    )

    try:
        mei_tax_engine.MEITaxEngine().execute(
            {
                "data_referencia": date(2025, 1, 15),
                "faturamento": 1000.0,
                "atividade": "servicos",
                "modo": "estimativa",
            }
        )
    except mei_tax_engine.AutoridadeNormativaMEIIndisponivelError:
        pass
    else:
        raise AssertionError("binding de 2026 foi reutilizado em 2025")

    assert calls == []
