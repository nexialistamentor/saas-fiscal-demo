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


def test_reexport_chain_to_mei_producer_is_resolved_red(tmp_path, monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    services_root = app_root / "services" / "tax_engines"
    services_root.mkdir(parents=True)

    (services_root / "mei_constants.py").write_text(
        "def calcular_das_mei(salario, atividade):\n"
        "    return salario\n",
        encoding="utf-8",
    )
    (app_root / "bridge.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n",
        encoding="utf-8",
    )
    (app_root / "consumer.py").write_text(
        "from app.bridge import calcular_das_mei\n"
        "\n"
        "def executar():\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    module = modules["app.consumer"]
    node = module.functions["executar"]
    callees = census_module._direct_callees(module, node)

    assert census_module.PRODUCER_ID in callees


def test_imported_mei_producer_rebinding_fails_closed_red(tmp_path, monkeypatch):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "consumer.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def substituto(salario, atividade):\n"
        "    return 0\n"
        "\n"
        "calcular_das_mei = substituto\n"
        "\n"
        "def executar():\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="MEI_REACHABILITY_REBINDING"):
        census_module._parse_app()


def test_dynamic_getattr_on_mei_module_fails_closed_red(tmp_path, monkeypatch):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "consumer.py").write_text(
        "import app.services.tax_engines.mei_constants as mc\n"
        "\n"
        "def executar():\n"
        "    produtor = getattr(mc, 'calcular_das_mei')\n"
        "    return produtor(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="MEI_REACHABILITY_DYNAMIC_ACCESS"):
        census_module._parse_app()


def test_dynamic_import_of_mei_module_fails_closed_red(tmp_path, monkeypatch):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "consumer.py").write_text(
        "import importlib\n"
        "\n"
        "def executar():\n"
        "    mc = importlib.import_module('app.services.tax_engines.mei_constants')\n"
        "    return mc.calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="MEI_REACHABILITY_DYNAMIC_IMPORT"):
        census_module._parse_app()


def test_local_homonym_is_not_canonical_mei_producer(tmp_path, monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "consumer.py").write_text(
        "def calcular_das_mei(salario, atividade):\n"
        "    return 0\n"
        "\n"
        "def executar():\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    module = modules["app.consumer"]
    node = module.functions["executar"]
    callees = census_module._direct_callees(module, node)

    assert "app.consumer.calcular_das_mei" in callees
    assert census_module.PRODUCER_ID not in callees


def test_only_main_mounted_router_is_public_root(tmp_path, monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / "main.py").write_text(
        "from app.mounted import router as mounted_router\n"
        "from app.orphan import router as orphan_router\n"
        "\n"
        "app.include_router(mounted_router, prefix='/api')\n",
        encoding="utf-8",
    )
    (app_root / "mounted.py").write_text("router = object()\n", encoding="utf-8")
    (app_root / "orphan.py").write_text("router = object()\n", encoding="utf-8")

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    mounted = census_module._mounted_routers(modules)

    assert mounted == {"app.mounted": ("router", "/api")}
    assert "app.orphan" not in mounted
