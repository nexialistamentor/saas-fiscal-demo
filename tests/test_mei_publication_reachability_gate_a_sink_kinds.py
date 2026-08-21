"""RED: Gate A must block every qualified MEI sink kind."""

from __future__ import annotations


def test_gate_a_blocks_publication_decision_cache_and_persistence_red():
    import app.scripts.mei_publication_reachability_census as census_module

    for sink_kind in ("PUBLICATION", "DECISION", "CACHE", "PERSISTENCE"):
        paths = [
            {
                "mei_reachability": "REACHABLE_MEI",
                "producer_ids": [census_module.PRODUCER_ID],
                "sink_kinds": [sink_kind],
            }
        ]
        assert census_module._gate_a_blocked_by_paths(paths) is True

    assert census_module._gate_a_blocked_by_paths(
        [
            {
                "mei_reachability": "REACHABLE_MEI",
                "producer_ids": [],
                "sink_kinds": ["PERSISTENCE"],
            }
        ]
    ) is False
