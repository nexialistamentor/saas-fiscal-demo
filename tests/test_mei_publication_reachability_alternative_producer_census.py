"""Guard: final census must not publish imposto_service as alternative MEI producer."""

from __future__ import annotations


def test_build_census_does_not_publish_imposto_service_as_alternative_producer():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()

    assert (
        "app.services.imposto_service.calcular_imposto_simples"
        not in census["alternative_producers"]
    )
