import ast

from app.scripts import mei_publication_reachability_census as census_module


ROUTE_ID = "app.routes.relatorio_router.obter_relatorio_por_tipo"
ENTRYPOINT = "/relatorio/{analysis_type}"


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


def _engine_result_assignment_and_following_return(route):
    for node in ast.walk(route):
        if not isinstance(node, ast.If):
            continue

        body = node.body
        for index, statement in enumerate(body):
            if not (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "resultado"
                and isinstance(statement.value, ast.Call)
                and census_module._call_name(statement.value)
                == "engine.gerar_insights_empresa"
            ):
                continue

            returns = [
                item
                for item in body[index + 1 :]
                if isinstance(item, ast.Return)
            ]
            assert len(returns) == 1
            return statement, returns[0]

    raise AssertionError("InsightEngine result branch not found")


def test_relatorio_insightengine_call_without_publication_must_fail_closed(
    monkeypatch,
):
    modules = census_module._parse_app()
    _, route = census_module._function_node(modules, ROUTE_ID)

    _, returned = _engine_result_assignment_and_following_return(route)

    assert isinstance(returned.value, ast.Dict)
    relatorio_indexes = [
        index
        for index, key in enumerate(returned.value.keys)
        if census_module._literal_string(key) == "relatorio"
    ]
    assert relatorio_indexes == [1]

    returned.value.values[1] = ast.Constant(value=None)
    ast.fix_missing_locations(route)

    _assert_not_reachable(modules, monkeypatch)


def test_relatorio_insightengine_result_source_must_fail_closed_if_removed(
    monkeypatch,
):
    modules = census_module._parse_app()
    _, route = census_module._function_node(modules, ROUTE_ID)

    assignment, _ = _engine_result_assignment_and_following_return(route)
    assignment.value = ast.Dict(keys=[], values=[])
    ast.fix_missing_locations(route)

    _assert_not_reachable(modules, monkeypatch)


def test_relatorio_tax_recovery_branch_must_be_in_allowed_domain(
    monkeypatch,
):
    modules = census_module._parse_app()
    analysis_types = modules["app.services.analysis_types"]

    assignments = [
        statement
        for statement in analysis_types.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "ANALYSIS_TYPES_RELATORIO_GET"
            and isinstance(statement.value, ast.Tuple)
        )
    ]
    assert len(assignments) == 1

    tuple_node = assignments[0].value
    original = list(tuple_node.elts)

    kept = [
        element
        for element in original
        if not (
            isinstance(element, ast.Name)
            and element.id == "ANALYSIS_TYPE_TAX_RECOVERY"
        )
    ]

    assert len(original) - len(kept) == 1
    tuple_node.elts = kept
    ast.fix_missing_locations(analysis_types.tree)

    _assert_not_reachable(modules, monkeypatch)
