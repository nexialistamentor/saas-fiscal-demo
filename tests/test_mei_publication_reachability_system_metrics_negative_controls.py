import ast

from app.scripts import mei_publication_reachability_census as census_module


ENTRYPOINT = "/system/metrics"
ORCHESTRATOR = "app.services.analysis_orchestrator"


def _assert_not_no_canonical(modules, monkeypatch):
    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == ENTRYPOINT
    )
    assert path["mei_reachability"] != "NO_CANONICAL_MEI_PRODUCER"


def _module_assignment(module, name):
    matches = [
        node
        for node in module.tree.body
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        )
    ]
    assert len(matches) == 1
    return matches[0]


def test_system_metrics_non_get_operation_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    metrics = modules["app.routes.metrics_router"]

    status = metrics.functions["_status_engines"]
    calls = [
        node
        for node in ast.walk(status)
        if (
            isinstance(node, ast.Call)
            and census_module._call_name(node) == "engine_failures.get"
        )
    ]
    assert len(calls) == 1

    calls[0].func.attr = "pop"
    ast.fix_missing_locations(status)

    _assert_not_no_canonical(modules, monkeypatch)


def test_system_metrics_non_literal_mapping_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    orchestrator = modules[ORCHESTRATOR]

    assignment = _module_assignment(orchestrator, "engine_versions")
    assert isinstance(assignment.value, ast.Dict)

    assignment.value = ast.Call(
        func=ast.Name(id="dict", ctx=ast.Load()),
        args=[],
        keywords=[],
    )
    ast.fix_missing_locations(orchestrator.tree)

    _assert_not_no_canonical(modules, monkeypatch)


def test_system_metrics_mapping_rebinding_must_fail_closed(monkeypatch):
    modules = census_module._parse_app()
    orchestrator = modules[ORCHESTRATOR]

    assignment = _module_assignment(orchestrator, "engine_failures")

    rebinding = ast.Assign(
        targets=[ast.Name(id="engine_failures", ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="object", ctx=ast.Load()),
            args=[],
            keywords=[],
        ),
    )
    rebinding.lineno = assignment.lineno + 1
    rebinding.col_offset = 0
    orchestrator.tree.body.append(rebinding)
    ast.fix_missing_locations(orchestrator.tree)

    _assert_not_no_canonical(modules, monkeypatch)
