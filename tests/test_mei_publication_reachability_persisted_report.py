"""RED: persisted MEI report publication must recognize fail-closed provenance."""

from __future__ import annotations


def test_persisted_mei_report_publication_has_no_canonical_mei_producer_red():
    from app.scripts.mei_publication_reachability_census import build_census

    census = build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/mei_tax/{relatorio_id}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["function_id"] == (
        "app.routes.relatorio_router.buscar_relatorio_mei_tax"
    )
    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["blocked_before_producer"] is False
    assert path["producer_ids"] == []
    assert "PUBLICATION" in path["sink_kinds"]
    assert path["persistence_source"] == {
        "model": "app.models.RelatorioAnalise",
        "analysis_type": "mei_tax",
        "field": "resultado_json",
        "lineage_proven": True,
    }



def test_persisted_mei_none_authority_guard_fails_closed_on_mutated_semantics():
    import ast
    from types import SimpleNamespace

    from app.scripts.mei_publication_reachability_census import (
        _persisted_mei_none_authority_guard,
    )

    def modules_for(authority_expression: str):
        source = f"""
def verificar_resultado_persistido(relatorio):
    provenance = {{}}

    if (
        getattr(relatorio, "analysis_type", None) == "mei_tax"
        and provenance.get("mei_authority") == {authority_expression}
    ):
        raise ResultadoProvenanceError("blocked")

    payload = {{}}
"""
        node = ast.parse(source).body[0]
        return {
            "app.services.resultado_provenance_service": SimpleNamespace(
                functions={"verificar_resultado_persistido": node}
            )
        }

    # Controle de sensibilidade: a topologia exata deve ser reconhecida.
    assert (
        _persisted_mei_none_authority_guard(
            modules_for("_MEI_AUTHORITY_NONE")
        )
        is True
    )

    # Mesmo uma substitui??o aparentemente equivalente por literal deve
    # degradar fail-closed: o binding can?nico deixou de estar provado.
    assert (
        _persisted_mei_none_authority_guard(
            modules_for('"NONE"')
        )
        is False
    )


def test_persisted_mei_reader_degrades_when_none_authority_guard_is_unproven(
    monkeypatch,
):
    import app.scripts.mei_publication_reachability_census as census_module

    monkeypatch.setattr(
        census_module,
        "_persisted_mei_none_authority_guard",
        lambda modules: False,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/mei_tax/{relatorio_id}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["persistence_source"]["lineage_proven"] is False


def test_persisted_mei_reader_degrades_when_verifier_is_bypassed(monkeypatch):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app

    def parse_app_with_bypassed_verifier():
        modules = original_parse_app()
        route = modules["app.routes.relatorio_router"]
        node = route.functions["buscar_relatorio_mei_tax"]

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
        parse_app_with_bypassed_verifier,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/mei_tax/{relatorio_id}"
    ]

    assert len(matches) == 1
    assert matches[0]["mei_reachability"] == "UNRESOLVED_MEI"


def test_persisted_mei_reader_degrades_on_mutated_analysis_type_guard(
    monkeypatch,
):
    import ast

    import app.scripts.mei_publication_reachability_census as census_module

    original_parse_app = census_module._parse_app

    def parse_app_with_mutated_analysis_type_guard():
        modules = original_parse_app()
        service = modules["app.services.resultado_provenance_service"]
        node = service.functions["verificar_resultado_persistido"]

        mutated_constants = 0
        for item in ast.walk(node):
            if isinstance(item, ast.Constant) and item.value == "mei_tax":
                item.value = "cpf_tax"
                mutated_constants += 1

        assert mutated_constants == 1
        return modules

    monkeypatch.setattr(
        census_module,
        "_parse_app",
        parse_app_with_mutated_analysis_type_guard,
    )

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/relatorio/mei_tax/{relatorio_id}"
    ]

    assert len(matches) == 1
    path = matches[0]

    assert path["mei_reachability"] == "UNRESOLVED_MEI"
    assert path["persistence_source"]["lineage_proven"] is False
