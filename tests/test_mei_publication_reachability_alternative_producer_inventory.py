"""Guard: imposto_service must not remain an alternative MEI producer."""

from __future__ import annotations


def test_real_calcular_imposto_simples_is_not_alternative_mei_producer():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    inventory = census_module._alternative_producer_inventory(
        modules,
        canonical_producer_id=census_module.PRODUCER_ID,
    )

    assert (
        "app.services.imposto_service.calcular_imposto_simples"
        not in inventory
    )
