import ast

from app.scripts import mei_publication_reachability_census as census_module


def test_insights_call_without_return_must_not_be_promoted_to_publication(monkeypatch):
    modules = census_module._parse_app()

    _, route = census_module._function_node(
        modules,
        "app.routers.insights_router.obter_insights",
    )

    returns = [
        (index, statement)
        for index, statement in enumerate(route.body)
        if isinstance(statement, ast.Return)
        and isinstance(statement.value, ast.Call)
    ]
    assert len(returns) == 1

    index, returned = returns[0]
    route.body[index] = ast.Expr(value=returned.value)
    ast.fix_missing_locations(route)

    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/insights/{empresa_id}"
    )

    assert path["mei_reachability"] != "REACHABLE_MEI"


def test_insights_flag_transform_must_fail_closed_if_shape_changes(monkeypatch):
    modules = census_module._parse_app()

    _, helper = census_module._function_node(
        modules,
        "app.services.context_flags_service.anexar_flags_nos_resultados_engines",
    )
    helper.body = [
        ast.Return(
            value=ast.Dict(keys=[], values=[]),
        )
    ]
    ast.fix_missing_locations(helper)

    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/insights/{empresa_id}"
    )
    assert path["mei_reachability"] != "REACHABLE_MEI"


def test_insights_mei_result_must_be_causally_added_to_session(monkeypatch):
    modules = census_module._parse_app()

    _, method = census_module._function_node(
        modules,
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa",
    )

    replaced = 0
    for parent in ast.walk(method):
        if not isinstance(parent, ast.Expr):
            continue
        call = parent.value
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "add"
            and isinstance(call.func.value, ast.Attribute)
            and isinstance(call.func.value.value, ast.Name)
            and call.func.value.value.id == "self"
            and call.func.value.attr == "db"
            and len(call.args) == 1
            and isinstance(call.args[0], ast.Name)
            and call.args[0].id == "registro"
        ):
            continue

        parent.value = ast.Constant(value=None)
        replaced += 1

    assert replaced == 1
    ast.fix_missing_locations(method)

    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    try:
        census = census_module.build_census()
    except RuntimeError:
        return

    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/insights/{empresa_id}"
    )
    assert path["mei_reachability"] != "REACHABLE_MEI"
