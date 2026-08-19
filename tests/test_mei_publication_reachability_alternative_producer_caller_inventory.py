"""Attack: statically inventory all direct callers of the alternative MEI producer."""

from __future__ import annotations


def test_real_alternative_mei_producer_has_only_expected_static_caller():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    callers = census_module._static_function_callers(
        modules,
        function_id="app.services.imposto_service.calcular_imposto_simples",
    )

    assert callers == ["app.routes.imposto_router.simular_ano"]
