"""RED: canonical MEI engine must enforce PGMEI authority before DAS production."""

from __future__ import annotations

from app.schemas.source_authority_schema import SourceAuthorityRequest
from app.services.source_authority_guard import verificar


def test_mei_tax_engine_blocks_pgmei_denial_before_calcular_das(monkeypatch):
    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    authority = verificar(
        SourceAuthorityRequest(
            fonte_id="PGMEI-001",
            uso_pretendido="validar_fato_operacional",
        )
    )
    assert authority.permitido is False

    producer_calls: list[tuple[tuple, dict]] = []

    def _forbidden_producer(*args, **kwargs):
        producer_calls.append((args, kwargs))
        return 999.99

    monkeypatch.setattr(mei_tax_engine, "calcular_das_mei", _forbidden_producer)

    caught: Exception | None = None
    try:
        mei_tax_engine.MEITaxEngine().execute(
            {
                "ano_referencia": 2026,
                "faturamento": 1000.00,
                "atividade": "servicos",
                "modo": "decisao_definitiva",
            }
        )
    except Exception as exc:  # exact domain type is asserted below
        caught = exc

    assert producer_calls == [], (
        "calcular_das_mei was reached before PGMEI-001 authority denial blocked the engine"
    )
    assert caught is not None, "MEITaxEngine returned despite denied PGMEI-001 authority"
    assert caught.__class__.__name__ == "AutoridadeFiscalIndisponivelError"
    assert getattr(caught, "codigo", None) == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert getattr(caught, "fonte_id", None) == "PGMEI-001"


def test_mei_tax_engine_sem_modo_consulta_pgmei_antes_das(monkeypatch):
    from types import SimpleNamespace

    import app.services.tax_engines.mei_tax_engine as mei_tax_engine

    requests = []
    forbidden_calls = []

    def _deny_pgmei(request):
        requests.append(request)
        return SimpleNamespace(
            permitido=False,
            fonte_id=request.fonte_id,
            motivo="autoridade operacional negada pelo teste",
        )

    def _forbidden(stage):
        def _record(*args, **kwargs):
            forbidden_calls.append((stage, args, kwargs))
            raise AssertionError(f"{stage} foi alcançado após a negação do PGMEI")

        return _record

    monkeypatch.setattr(mei_tax_engine, "verificar", _deny_pgmei)
    monkeypatch.setattr(
        mei_tax_engine,
        "_exigir_autoridade_normativa_mei",
        _forbidden("autoridade normativa"),
    )
    monkeypatch.setattr(
        mei_tax_engine,
        "obter_salario_minimo",
        _forbidden("salário"),
    )
    monkeypatch.setattr(
        mei_tax_engine,
        "calcular_das_mei",
        _forbidden("cálculo"),
    )

    caught = None
    try:
        mei_tax_engine.MEITaxEngine().execute(
            {
                "ano_referencia": 2026,
                "faturamento": 1000.00,
                "atividade": "servicos",
            }
        )
    except Exception as exc:
        caught = exc

    assert caught is not None
    assert caught.__class__.__name__ == "AutoridadeFiscalIndisponivelError"
    assert getattr(caught, "fonte_id", None) == "PGMEI-001"
    assert len(requests) == 1
    assert requests[0].fonte_id == "PGMEI-001"
    assert requests[0].uso_pretendido == "validar_fato_operacional"
    assert forbidden_calls == []
