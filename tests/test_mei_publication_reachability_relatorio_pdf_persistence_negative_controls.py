import ast

from app.scripts import mei_publication_reachability_census as census_module


ENTRYPOINT = "/relatorio/relatorio-pdf"
ROUTE_ID = "app.routes.relatorio_router.relatorio_pdf"
SERVICE_ID = (
    "app.services.registro_analise_service."
    "executar_e_registrar_analise_xml"
)


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


def test_relatorio_pdf_without_empresa_id_forwarding_must_fail_closed(
    monkeypatch,
):
    modules = census_module._parse_app()
    _, route = census_module._function_node(modules, ROUTE_ID)

    calls = [
        node
        for node in ast.walk(route)
        if (
            isinstance(node, ast.Call)
            and census_module._call_name(node)
            == "executar_e_registrar_analise_xml"
        )
    ]
    assert len(calls) == 1
    call = calls[0]

    assert len(call.args) >= 4
    assert isinstance(call.args[3], ast.Name)
    assert call.args[3].id == "empresa_id"

    call.args[3] = ast.Constant(value=None)
    ast.fix_missing_locations(route)

    _assert_not_reachable(modules, monkeypatch)


def test_relatorio_pdf_without_empresa_branch_must_fail_closed(
    monkeypatch,
):
    modules = census_module._parse_app()
    _, service = census_module._function_node(modules, SERVICE_ID)

    branches = [
        node
        for node in ast.walk(service)
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "empresa_id"
            and any(
                isinstance(item, ast.Call)
                and census_module._call_name(item)
                == "engine.gerar_insights_empresa"
                for item in ast.walk(node)
            )
        )
    ]
    assert len(branches) == 1

    branches[0].test = ast.Constant(value=False)
    ast.fix_missing_locations(service)

    _assert_not_reachable(modules, monkeypatch)


def test_relatorio_pdf_without_insightengine_execution_must_fail_closed(
    monkeypatch,
):
    modules = census_module._parse_app()
    _, service = census_module._function_node(modules, SERVICE_ID)

    calls = [
        node
        for node in ast.walk(service)
        if (
            isinstance(node, ast.Call)
            and census_module._call_name(node)
            == "engine.gerar_insights_empresa"
        )
    ]
    assert len(calls) == 1

    call = calls[0]
    call.func = ast.Name(id="dict", ctx=ast.Load())
    call.args = []
    call.keywords = []
    ast.fix_missing_locations(service)

    _assert_not_reachable(modules, monkeypatch)
