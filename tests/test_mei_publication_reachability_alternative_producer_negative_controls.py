"""Negative controls after alternative-producer route publication wiring."""

from __future__ import annotations


def _entry(census: dict, entrypoint: str) -> dict:
    matches = [
        item
        for item in census.get("paths", [])
        if item.get("entrypoint") == entrypoint
    ]
    assert len(matches) == 1, (
        f"expected exactly one census path for {entrypoint!r}; "
        f"found {len(matches)}"
    )
    return matches[0]


def test_real_relatorio_mei_tax_remains_blocked_before_alternative_producer():
    import app.scripts.mei_publication_reachability_census as census_module

    path = _entry(census_module.build_census(), "/relatorio/mei_tax")

    assert path["mei_reachability"] == "BLOCKED_MEI"
    assert path["blocked_before_producer"] is True
    assert path["blocker_code"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert path["producer_ids"] == []
    assert path["sink_kinds"] == []
    assert "app.services.imposto_service.calcular_imposto_simples" not in path["trace"]


def test_real_relatorio_imposto_pdf_remains_blocked_before_alternative_producer():
    import app.scripts.mei_publication_reachability_census as census_module

    path = _entry(census_module.build_census(), "/relatorio/imposto-pdf")

    assert path["mei_reachability"] == "BLOCKED_MEI"
    assert path["blocked_before_producer"] is True
    assert path["blocker_code"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert path["producer_ids"] == []
    assert path["sink_kinds"] == []
    assert "app.services.imposto_service.calcular_imposto_simples" not in path["trace"]


def test_real_cpf_engine_wrapper_call_is_not_promoted_to_mei_public_root():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    callers = census_module._static_function_callers(
        modules,
        function_id="app.services.imposto_service.calcular_imposto_simples",
    )
    cpf_function_id = "app.services.tax_engines.cpf_engine.CPFEngine.execute"

    assert cpf_function_id in callers

    census = census_module.build_census()
    assert all(item.get("function_id") != cpf_function_id for item in census["paths"])
    assert all(cpf_function_id not in item.get("trace", []) for item in census["paths"])
