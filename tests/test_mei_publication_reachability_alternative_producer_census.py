"""RED attack: the final census must publish proven alternative MEI producers."""

from __future__ import annotations


def test_build_census_publishes_real_alternative_mei_producer_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()

    assert census["alternative_producers"][
        "app.services.imposto_service.calcular_imposto_simples"
    ] == [census_module.PRODUCER_ID]
