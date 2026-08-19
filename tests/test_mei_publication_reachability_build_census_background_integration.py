"""build_census must integrate the real disabled scheduler inventory."""

from __future__ import annotations


def test_build_census_integrates_real_disabled_scheduler_as_inventory_only_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    roots = {
        item["function_id"]: item
        for item in census["background_roots"]
    }

    assert roots["app.agents.agent_scheduler.AgentScheduler.iniciar_loop"] == {
        "function_id": "app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
        "present": True,
        "registration_ids": [],
        "is_root": False,
        "reachability": "INVENTORY_ONLY",
    }
