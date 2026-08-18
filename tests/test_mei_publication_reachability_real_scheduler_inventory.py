"""Contract: the real AgentScheduler loop is inventory-only while startup calls remain commented."""

from __future__ import annotations


def test_real_agent_scheduler_loop_is_not_an_operational_root_while_disabled():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    result = census_module._background_root_inventory(
        modules,
        function_id="app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
    )

    assert result == {
        "function_id": "app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
        "present": True,
        "registration_ids": [],
        "is_root": False,
        "reachability": "INVENTORY_ONLY",
    }
