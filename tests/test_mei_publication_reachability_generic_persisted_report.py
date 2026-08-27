"""RED: generic persisted report publication may expose MEI results."""

from __future__ import annotations


def test_generic_persisted_report_publication_has_no_canonical_mei_producer_red():
    from app.scripts.mei_publication_reachability_census import build_census

    census = build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["function_id"] == "app.routes.relatorio_router.obter_relatorio"
    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["blocked_before_producer"] is False
    assert path["blocker_code"] is None
    assert path["producer_ids"] == []
    assert "PUBLICATION" in path["sink_kinds"]
    assert path["persistence_source"] == {
        "model": "app.models.RelatorioAnalise",
        "analysis_type_filter": None,
        "may_include_analysis_type": "mei_tax",
        "field": "resultado_json",
        "lineage_proven": True,
    }


def test_generic_persisted_reader_degrades_on_unknown_relatorio_constructor(
    monkeypatch,
):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app

    def parse_app_with_unknown_constructor():
        modules = original_parse_app()
        route = modules["app.routes.relatorio_router"]
        node = route.functions["obter_relatorio"]

        synthetic_constructor = ast.parse(
            "RelatorioAnalise()"
        ).body[0]
        node.body.append(synthetic_constructor)

        return modules

    monkeypatch.setattr(
        census_module,
        "_parse_app",
        parse_app_with_unknown_constructor,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["persistence_source"]["lineage_proven"] is False


def test_generic_persisted_reader_degrades_on_dynamic_creator_analysis_type(
    monkeypatch,
):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app
    creator_id = (
        "app.services.registro_analise_service."
        "criar_registro_analise"
    )

    def parse_app_with_dynamic_creator_analysis_type():
        modules = original_parse_app()
        mutated_calls = 0

        for module in modules.values():
            if mutated_calls:
                break
            for function_node in module.functions.values():
                if mutated_calls:
                    break
                for item in ast.walk(function_node):
                    if not isinstance(item, ast.Call):
                        continue

                    call_name = census_module._call_name(item)
                    if (
                        call_name is None
                        or census_module._resolve_name(module, call_name)
                        != creator_id
                    ):
                        continue

                    analysis_keywords = [
                        keyword
                        for keyword in item.keywords
                        if keyword.arg == "analysis_type"
                    ]

                    if len(analysis_keywords) == 1:
                        analysis_keywords[0].value = ast.Name(
                            id="dynamic_analysis_type",
                            ctx=ast.Load(),
                        )
                    elif not analysis_keywords and len(item.args) > 2:
                        item.args[2] = ast.Name(
                            id="dynamic_analysis_type",
                            ctx=ast.Load(),
                        )
                    else:
                        continue

                    mutated_calls += 1
                    break

        assert mutated_calls == 1
        return modules

    monkeypatch.setattr(
        census_module,
        "_parse_app",
        parse_app_with_dynamic_creator_analysis_type,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["persistence_source"]["lineage_proven"] is False


def test_generic_persisted_reader_degrades_on_changed_insight_fingerprint_topology(
    monkeypatch,
):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app

    def parse_app_with_changed_insight_fingerprint_topology():
        modules = original_parse_app()
        insights = modules["app.services.insights_engine"]
        node = insights.functions["InsightEngine.gerar_insights_empresa"]

        constructors = [
            item
            for item in ast.walk(node)
            if (
                isinstance(item, ast.Call)
                and census_module._call_name(item)
                == "RelatorioAnalise"
            )
        ]

        assert len(constructors) == 1
        constructor = constructors[0]
        assert all(
            keyword.arg != "fingerprint"
            for keyword in constructor.keywords
        )

        constructor.keywords.append(
            ast.keyword(
                arg="fingerprint",
                value=ast.Constant(value="0" * 64),
            )
        )

        return modules

    monkeypatch.setattr(
        census_module,
        "_parse_app",
        parse_app_with_changed_insight_fingerprint_topology,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["persistence_source"]["lineage_proven"] is False


def test_generic_persisted_reader_degrades_when_verifier_is_bypassed(
    monkeypatch,
):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app

    def parse_app_with_bypassed_generic_verifier():
        modules = original_parse_app()
        route = modules["app.routes.relatorio_router"]
        node = route.functions["obter_relatorio"]

        mutated_calls = 0
        for item in ast.walk(node):
            if (
                isinstance(item, ast.Call)
                and census_module._call_name(item)
                == "verificar_resultado_persistido"
            ):
                item.func = ast.Name(
                    id="verifier_bypassed",
                    ctx=ast.Load(),
                )
                mutated_calls += 1

        assert mutated_calls == 1
        return modules

    monkeypatch.setattr(
        census_module,
        "_parse_app",
        parse_app_with_bypassed_generic_verifier,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/{relatorio_id:int}"
    ]

    assert len(matches) == 1
    assert matches[0]["mei_reachability"] == "UNRESOLVED_MEI"
