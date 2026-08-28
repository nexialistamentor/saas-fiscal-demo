"""Fail-closed controls for the generic persisted-report writer closure."""

from __future__ import annotations

import ast

import pytest

from app.scripts import mei_publication_reachability_census as census_module


def _call(node: ast.AST, name: str) -> ast.Call:
    matches = [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and census_module._call_name(item) == name
    ]
    assert len(matches) == 1
    return matches[0]


def _insights(modules):
    return modules["app.services.insights_engine"].functions[
        "InsightEngine.gerar_insights_empresa"
    ]


def _cpf(modules):
    return modules["app.services.assistente_service"].functions[
        "responder_pergunta"
    ]


def _bypass_insight_sealing(modules):
    call = _call(_insights(modules), "selar_resultado_nao_mei")
    call.func = ast.Name(id="bypass_selagem", ctx=ast.Load())


def _fingerprint_other_object(modules):
    call = _call(_insights(modules), "fingerprint_resultado_json")
    call.args[0] = ast.Name(id="resultado_persistido", ctx=ast.Load())


def _change_insight_producer(modules):
    call = _call(_insights(modules), "selar_resultado_nao_mei")
    producer = next(
        keyword for keyword in call.keywords if keyword.arg == "producer_id"
    )
    producer.value = ast.Constant(value="app.services.insights_engine.alterado")


def _deliver_raw_cpf_payload(modules):
    call = _call(_cpf(modules), "finalizar_registro_analise")
    result = next(
        keyword for keyword in call.keywords if keyword.arg == "resultado_json"
    )
    result.value = ast.Subscript(
        value=ast.Name(id="cpf_resultado", ctx=ast.Load()),
        slice=ast.Constant(value="payload"),
        ctx=ast.Load(),
    )


def _make_cpf_local_import_ambiguous(modules):
    node = _cpf(modules)
    node.body.append(
        ast.ImportFrom(
            module="app.services.outro_registro_service",
            names=[
                ast.alias(
                    name="finalizar_registro_analise",
                    asname=None,
                )
            ],
            level=0,
        )
    )


def _payload_dict(modules):
    assignments = [
        item
        for item in ast.walk(_insights(modules))
        if isinstance(item, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "resultado_persistido"
            for target in item.targets
        )
    ]
    assert len(assignments) == 1
    assert isinstance(assignments[0].value, ast.Dict)
    return assignments[0].value


def _add_payload_unpacking(modules):
    payload = _payload_dict(modules)
    payload.keys.append(None)
    payload.values.append(ast.Name(id="extra", ctx=ast.Load()))


def _duplicate_payload_key(modules):
    payload = _payload_dict(modules)
    payload.keys[-1] = ast.Constant(value="empresa_id")


def _move_seal_to_wrong_branch(modules):
    node = _insights(modules)
    call = _call(node, "selar_resultado_nao_mei")
    assignment = next(
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Assign) and item.value is call
    )
    branch = next(
        item
        for item in ast.walk(node)
        if isinstance(item, ast.If)
        and isinstance(item.test, ast.Name)
        and item.test.id == "relatorio"
    )
    branch.body.remove(assignment)
    branch.orelse.append(assignment)


def _bind_alternate_relatorio(modules):
    _insights(modules).body.insert(
        1,
        ast.Expr(
            value=ast.NamedExpr(
                target=ast.Name(id="relatorio", ctx=ast.Store()),
                value=ast.Name(id="alternativo", ctx=ast.Load()),
            )
        ),
    )


def _add_seal_argument(modules):
    _call(_insights(modules), "selar_resultado_nao_mei").keywords.append(
        ast.keyword(arg="extra", value=ast.Constant(value=True))
    )


def _add_fingerprint_argument(modules):
    _call(_insights(modules), "fingerprint_resultado_json").keywords.append(
        ast.keyword(arg="extra", value=ast.Constant(value=True))
    )


def _seal_other_cpf_object(modules):
    _call(_cpf(modules), "selar_resultado_nao_mei").args[0] = ast.Name(
        id="cpf_resultado", ctx=ast.Load()
    )


def _shadow_cpf_finalizer_with_walrus(modules):
    _cpf(modules).body.append(
        ast.Expr(
            value=ast.NamedExpr(
                target=ast.Name(
                    id="finalizar_registro_analise", ctx=ast.Store()
                ),
                value=ast.Name(id="substituto", ctx=ast.Load()),
            )
        )
    )


def _shadow_cpf_finalizer_with_function(modules):
    _cpf(modules).body.append(
        ast.FunctionDef(
            name="finalizar_registro_analise",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                kwonlyargs=[],
                kw_defaults=[],
                defaults=[],
            ),
            body=[ast.Pass()],
            decorator_list=[],
        )
    )


def _shadow_cpf_finalizer_with_relative_import(modules):
    _cpf(modules).body.append(
        ast.ImportFrom(
            module="registro_analise_service",
            names=[ast.alias(name="finalizar_registro_analise")],
            level=1,
        )
    )


def _shadow_cpf_finalizer_with_match_capture(modules):
    _cpf(modules).body.append(
        ast.Match(
            subject=ast.Name(id="objeto", ctx=ast.Load()),
            cases=[
                ast.match_case(
                    pattern=ast.MatchAs(
                        pattern=None,
                        name="finalizar_registro_analise",
                    ),
                    guard=None,
                    body=[ast.Pass()],
                )
            ],
        )
    )


def _delete_relatorio(modules):
    _insights(modules).body.append(
        ast.Delete(targets=[ast.Name(id="relatorio", ctx=ast.Del())])
    )


def _declare_global_relatorio(modules):
    _insights(modules).body.append(ast.Global(names=["relatorio"]))


def _declare_nonlocal_relatorio(modules):
    _insights(modules).body.append(ast.Nonlocal(names=["relatorio"]))


def _capture_relatorio_with_match(modules):
    _insights(modules).body.append(
        ast.Match(
            subject=ast.Name(id="objeto", ctx=ast.Load()),
            cases=[
                ast.match_case(
                    pattern=ast.MatchMapping(
                        keys=[],
                        patterns=[],
                        rest="relatorio",
                    ),
                    guard=None,
                    body=[ast.Pass()],
                )
            ],
        )
    )


@pytest.mark.parametrize(
    "mutate",
    [
        _bypass_insight_sealing,
        _fingerprint_other_object,
        _change_insight_producer,
        _deliver_raw_cpf_payload,
        _make_cpf_local_import_ambiguous,
        _add_payload_unpacking,
        _duplicate_payload_key,
        _move_seal_to_wrong_branch,
        _bind_alternate_relatorio,
        _add_seal_argument,
        _add_fingerprint_argument,
        _seal_other_cpf_object,
        _shadow_cpf_finalizer_with_walrus,
        _shadow_cpf_finalizer_with_function,
        _shadow_cpf_finalizer_with_relative_import,
        _shadow_cpf_finalizer_with_match_capture,
        _delete_relatorio,
        _declare_global_relatorio,
        _declare_nonlocal_relatorio,
        _capture_relatorio_with_match,
    ],
    ids=[
        "insight-sealing-bypass",
        "fingerprint-other-object",
        "insight-producer-changed",
        "cpf-raw-payload",
        "cpf-local-import-ambiguous",
        "payload-dict-unpacking",
        "payload-duplicate-key",
        "seal-wrong-branch",
        "alternate-relatorio-binding",
        "seal-extra-argument",
        "fingerprint-extra-argument",
        "cpf-seals-other-object",
        "cpf-finalizer-walrus-shadow",
        "cpf-finalizer-function-shadow",
        "cpf-finalizer-relative-import-shadow",
        "cpf-finalizer-match-capture-shadow",
        "relatorio-delete",
        "relatorio-global",
        "relatorio-nonlocal",
        "relatorio-match-capture",
    ],
)
def test_generic_writer_mutations_degrade_to_unresolved(monkeypatch, mutate):
    modules = census_module._parse_app()
    mutate(modules)
    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    if mutate in {
        _make_cpf_local_import_ambiguous,
        _shadow_cpf_finalizer_with_walrus,
        _shadow_cpf_finalizer_with_function,
        _shadow_cpf_finalizer_with_relative_import,
        _shadow_cpf_finalizer_with_match_capture,
    }:
        route = modules["app.routes.relatorio_router"]
        source = census_module._persisted_mei_report_publication_source(
            modules,
            route.functions["obter_relatorio"],
        )
        assert source is not None
        assert source["lineage_proven"] is False
        mei_reachability = (
            "NO_CANONICAL_MEI_PRODUCER"
            if source["lineage_proven"]
            else "UNRESOLVED_MEI"
        )
        assert mei_reachability == "UNRESOLVED_MEI"
        return

    census = census_module.build_census()
    paths = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(paths) == 1
    assert paths[0]["mei_reachability"] == "UNRESOLVED_MEI"
    assert paths[0]["persistence_source"]["lineage_proven"] is False


def test_additional_result_bearing_finalizer_caller_preserves_topology_error(
    monkeypatch,
):
    modules = census_module._parse_app()
    registro = modules["app.services.registro_analise_service"]
    extra_caller = registro.functions["contar_alertas_empresa"]
    extra_caller.body.append(
        ast.Expr(
            value=ast.Call(
                func=ast.Name(id="finalizar_registro_analise", ctx=ast.Load()),
                args=[],
                keywords=[
                    ast.keyword(
                        arg="resultado_json",
                        value=ast.Name(id="resultado_extra", ctx=ast.Load()),
                    )
                ],
            )
        )
    )
    monkeypatch.setattr(census_module, "_parse_app", lambda: modules)

    with pytest.raises(
        RuntimeError,
        match=(
            r"^UNEXPECTED_WRITER_TOPOLOGY:"
            r"app\.services\.registro_analise_service\.contar_alertas_empresa$"
        ),
    ):
        census_module.build_census()
