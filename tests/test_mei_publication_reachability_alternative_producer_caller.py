"""RED attack: prove the real static caller of the alternative MEI producer."""

from __future__ import annotations


def test_real_simular_ano_is_static_caller_of_alternative_mei_producer_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    callers = census_module._static_function_callers(
        modules,
        function_id="app.services.imposto_service.calcular_imposto_simples",
    )

    assert "app.routes.imposto_router.simular_ano" in callers
