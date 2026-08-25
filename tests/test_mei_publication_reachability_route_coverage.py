"""Route coverage: real coverage must close; any synthetic gap must fail closed."""

from __future__ import annotations


def test_current_mounted_routes_are_fully_classified():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()

    assert census["unclassified_entrypoints"] == []
    assert census["route_coverage_complete"] is True


def test_unclassified_route_coverage_keeps_gate_a_unresolved(monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    original = census_module._route_coverage_inventory

    def synthetic_gap(*, mounted_entrypoints, paths):
        inventory = original(
            mounted_entrypoints=mounted_entrypoints,
            paths=paths,
        )

        return {
            **inventory,
            "unclassified_entrypoints": [
                *inventory["unclassified_entrypoints"],
                "/__synthetic_unclassified_route__",
            ],
            "route_coverage_complete": False,
        }

    monkeypatch.setattr(
        census_module,
        "_route_coverage_inventory",
        synthetic_gap,
    )

    census = census_module.build_census()

    assert (
        "/__synthetic_unclassified_route__"
        in census["unclassified_entrypoints"]
    )
    assert census["route_coverage_complete"] is False
    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
