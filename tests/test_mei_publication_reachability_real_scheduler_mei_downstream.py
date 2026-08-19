"""Real scheduler control: MEI-capable downstream must not promote a disabled root."""

from __future__ import annotations


def test_disabled_real_scheduler_is_not_promoted_by_mei_capable_downstream():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    root = census_module._background_root_inventory(
        modules,
        function_id="app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
    )
    assert root == {
        "function_id": "app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
        "present": True,
        "registration_ids": [],
        "is_root": False,
        "reachability": "INVENTORY_ONLY",
    }

    insights = census_module._function_node(
        modules,
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa",
    )
    assert insights is not None
    insights_module, insights_node = insights
    assert (
        "app.services.insights_engine.executar_engines"
        in census_module._direct_callees(insights_module, insights_node)
    )
    assert census_module._resolve_mei_registry_engine(modules) == census_module.MEI_ENGINE_EXECUTE_ID

    census = census_module.build_census()
    forbidden = {
        "app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
        "app.agents.agent_scheduler.AgentScheduler.executar_ciclo",
        "app.agents.agent_scheduler.AgentScheduler.executar_ciclo_multi_tenant",
        "app.agents.agent_scheduler.AgentScheduler._executar_agents_uma_empresa",
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa",
        "app.services.insights_engine.executar_engines",
    }
    assert all(
        not forbidden.intersection(item.get("trace", []))
        for item in census["paths"]
    )
