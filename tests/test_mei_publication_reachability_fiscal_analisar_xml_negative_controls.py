import ast

from app.scripts import mei_publication_reachability_census as census_module


ENTRYPOINT = "/fiscal/analisar-xml"
HELPER_ID = "app.routes.fiscal_router._enqueue_or_run_sync"


def _assert_not_reachable(modules, monkeypatch):
    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == ENTRYPOINT
    )
    assert path["mei_reachability"] != "REACHABLE_MEI"


def test_fiscal_analisar_xml_wrong_rq_target_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _, helper = census_module._function_node(modules, HELPER_ID)

    enqueue_calls = [
        node
        for node in ast.walk(helper)
        if (
            isinstance(node, ast.Call)
            and census_module._call_name(node)
            == "analysis_queue.enqueue"
        )
    ]
    assert len(enqueue_calls) == 1
    call = enqueue_calls[0]
    assert call.args
    assert isinstance(call.args[0], ast.Name)
    assert call.args[0].id == "processar_xml_job"

    call.args[0] = ast.Name(
        id="executar_analise_xml",
        ctx=ast.Load(),
    )
    ast.fix_missing_locations(helper)

    _assert_not_reachable(modules, monkeypatch)


def test_fiscal_analisar_xml_sync_fallback_drift_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    _, helper = census_module._function_node(modules, HELPER_ID)

    job_calls = [
        node
        for node in ast.walk(helper)
        if (
            isinstance(node, ast.Call)
            and census_module._call_name(node)
            == "processar_xml_job"
        )
    ]

    # Current topology: inline path + exception fallback.
    assert len(job_calls) == 2

    job_calls[-1].func = ast.Name(
        id="executar_analise_xml",
        ctx=ast.Load(),
    )
    ast.fix_missing_locations(helper)

    _assert_not_reachable(modules, monkeypatch)


def test_fiscal_analisar_xml_unproven_queue_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    queue_module = modules["app.queue.redis_queue"]

    assignments = [
        node
        for node in queue_module.tree.body
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "analysis_queue"
        )
    ]
    assert len(assignments) == 1

    assignments[0].value = ast.Call(
        func=ast.Name(id="object", ctx=ast.Load()),
        args=[],
        keywords=[],
    )
    ast.fix_missing_locations(queue_module.tree)

    _assert_not_reachable(modules, monkeypatch)
