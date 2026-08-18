"""RED attack: the real imposto_service MEI wrapper must be inventoried as an alternative producer."""

from __future__ import annotations


def test_real_calcular_imposto_simples_is_alternative_mei_producer_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    inventory = census_module._alternative_producer_inventory(
        modules,
        canonical_producer_id=census_module.PRODUCER_ID,
    )

    assert inventory[
        "app.services.imposto_service.calcular_imposto_simples"
    ] == [census_module.PRODUCER_ID]
