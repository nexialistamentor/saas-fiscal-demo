"""RED contract for MEI publication/reachability census.

These tests intentionally define the observable contract before the scanner
exists. They exercise the real repository surface, not synthetic business
rules: the Assistant is currently a reachable MEI publication path, while the
two imposto endpoints below must be proven blocked before any MEI producer is
reached.
"""

from __future__ import annotations


def _build_census() -> dict:
    # Imported inside the helper so pytest collects this RED file and reports
    # the missing scanner as a test failure rather than hiding the contract in
    # a collection error.
    from app.scripts.mei_publication_reachability_census import build_census

    return build_census()


def _entry(census: dict, entrypoint: str) -> dict:
    matches = [
        item
        for item in census.get("paths", [])
        if item.get("entrypoint") == entrypoint
    ]
    assert len(matches) == 1, (
        f"expected exactly one census path for {entrypoint!r}; "
        f"found {len(matches)}"
    )
    return matches[0]


def test_real_assistant_mei_path_is_reachable_publication_red():
    census = _build_census()

    assert census["schema_version"] == "MEI_PUBLICATION_REACHABILITY_CENSUS_V1"
    assert census["scan_complete"] is True
    assert census["status"] == "BLOCKED"

    path = _entry(census, "/perguntar")

    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert "PUBLICATION" in path["sink_kinds"]
    assert (
        "app.services.tax_engines.mei_constants.calcular_das_mei"
        in path["producer_ids"]
    )

    trace = path["trace"]
    assert "app.routers.assistente_router.perguntar" in trace
    assert "app.services.assistente_service.responder_pergunta" in trace
    assert "app.services.assistente_service._resposta_assistente_mei" in trace
    assert "app.services.analysis_orchestrator.executar_analise" in trace
    assert "app.services.tax_engines.mei_tax_engine.MEITaxEngine.execute" in trace
    assert "app.services.tax_engines.mei_constants.calcular_das_mei" in trace


def test_real_imposto_calcular_mei_is_blocked_before_producer_red():
    census = _build_census()

    path = _entry(census, "/imposto/calcular")

    assert path["mei_reachability"] == "BLOCKED_MEI"
    assert path["blocked_before_producer"] is True
    assert path["blocker_code"] == "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"
    assert path["producer_ids"] == []


def test_real_simular_ano_mei_is_blocked_despite_later_service_call_red():
    census = _build_census()

    path = _entry(census, "/imposto/simular-ano")

    assert path["mei_reachability"] == "BLOCKED_MEI"
    assert path["blocked_before_producer"] is True
    assert path["blocker_code"] == "APLICABILIDADE_MEI_INSUFICIENTE"
    assert path["producer_ids"] == []

    # Critical anti-false-RED invariant: the function contains a generic call
    # to calcular_imposto_simples later in its body, but MEI execution raises
    # before that call. A call-graph-only census would classify this wrongly.
    assert "app.services.imposto_service.calcular_imposto_simples" not in path["trace"]


def test_module_alias_call_to_mei_producer_is_resolved_red(tmp_path, monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    consumer = app_root / "consumer.py"
    consumer.write_text(
        "import app.services.tax_engines.mei_constants as mc\n"
        "\n"
        "def executar():\n"
        "    return mc.calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    module = modules["app.consumer"]
    node = module.functions["executar"]
    callees = census_module._direct_callees(module, node)

    assert census_module.PRODUCER_ID in callees
