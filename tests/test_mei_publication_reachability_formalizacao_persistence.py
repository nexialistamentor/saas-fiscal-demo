"""RED: formalizacao MEI decision paths must prove absence of ORM persistence."""

from __future__ import annotations


def test_formalizacao_paths_carry_qualified_persistence_inventory_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()

    for entrypoint in (
        "/formalizacao/comparar-regimes",
        "/formalizacao/simular-empresa",
    ):
        path = next(
            item for item in census["paths"] if item["entrypoint"] == entrypoint
        )
        persistence = path["persistence_inventory"]

        assert persistence["qualified_trace"] == path["trace"]
        assert census_module.PRODUCER_ID in persistence["qualified_trace"]
        assert persistence["sink_operations"] == {}
        assert persistence["unresolved_app_callees"] == []
        assert persistence["scan_complete"] is True
        assert "PERSISTENCE" not in path["sink_kinds"]
