from app.scripts.mei_normative_census import build_census


def test_mei_normative_census_discovers_all_physical_constants():
    census = build_census()

    assert census["schema_version"] == "MEI_NORMATIVE_CENSUS_V1"
    assert census["status"] == "BLOCKED"
    assert census["constants_total"] == 9

    assert {
        item["constante_id"]
        for item in census["constants"]
    } == {
        "ATIVIDADE_MEI_NORMALIZADA_POR_ALIAS",
        "MEI_ATIVIDADE_COMERCIO_INDUSTRIA",
        "MEI_ATIVIDADE_SERVICOS",
        "MEI_DAS_FATOR_SALARIO_MINIMO",
        "MEI_DAS_VALOR_FIXO_ICMS",
        "MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE",
        "MEI_LIMITE_ANUAL_FATURAMENTO",
        "PARCELA_FIXA_POR_ATIVIDADE",
        "SALARIO_MINIMO_POR_ANO",
    }

    assert all(
        item["arquivo_definicao"]
        == "app/services/tax_engines/mei_constants.py"
        for item in census["constants"]
    )



def test_mei_normative_census_fails_closed_on_unparseable_python(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_TEST_CONSTANT = 1\n",
        encoding="utf-8",
    )

    broken_path = tmp_path / "app" / "broken_module.py"
    broken_path.write_text(
        "def broken(:\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente Python impossivel de analisar"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_SCAN_FAILED:"
    )
    assert "app/broken_module.py" in message
    assert "SyntaxError" in message



def test_mei_normative_census_does_not_confuse_local_homonym_with_canonical_constant(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    unrelated_path = tmp_path / "app" / "unrelated.py"
    unrelated_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 123\n"
        "resultado = MEI_LIMITE_ANUAL_FATURAMENTO + 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    records = census_module.discover_mei_constants()
    record = next(
        item
        for item in records
        if item.constante_id == "MEI_LIMITE_ANUAL_FATURAMENTO"
    )

    assert record.call_sites == ()



def test_mei_normative_census_fails_closed_on_dynamic_canonical_access(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "import app.services.tax_engines.mei_constants as mc\n"
        'valor = getattr(mc, "MEI_LIMITE_ANUAL_FATURAMENTO")\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo ignorou silenciosamente acesso dinamico "
            "a constante canonica"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS:"
    )
    assert "app/consumer.py:2" in message



def test_mei_normative_census_fails_closed_when_canonical_import_is_rebound(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "MEI_LIMITE_ANUAL_FATURAMENTO = 123\n"
        "valor = MEI_LIMITE_ANUAL_FATURAMENTO\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente rebinding "
            "de import canonico"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_REBINDING:"
    )
    assert "app/consumer.py:2" in message
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message



def test_mei_normative_census_tracks_canonical_direct_import_alias(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO as limite_mei\n"
        "valor = limite_mei + 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    records = census_module.discover_mei_constants()
    record = next(
        item
        for item in records
        if item.constante_id == "MEI_LIMITE_ANUAL_FATURAMENTO"
    )

    assert len(record.call_sites) == 1
    assert record.call_sites[0].arquivo == "app/consumer.py"
    assert record.call_sites[0].linha == 2



def test_mei_normative_census_tracks_canonical_module_alias(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "import app.services.tax_engines.mei_constants as mc\n"
        "valor = mc.MEI_LIMITE_ANUAL_FATURAMENTO + 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    records = census_module.discover_mei_constants()
    record = next(
        item
        for item in records
        if item.constante_id == "MEI_LIMITE_ANUAL_FATURAMENTO"
    )

    assert len(record.call_sites) == 1
    assert record.call_sites[0].arquivo == "app/consumer.py"
    assert record.call_sites[0].linha == 2



def test_mei_normative_census_fails_closed_on_canonical_reexport(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    bridge_path = tmp_path / "app" / "bridge.py"
    bridge_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.bridge import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "valor = MEI_LIMITE_ANUAL_FATURAMENTO + 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente reexportacao "
            "de constante canonica"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_REEXPORT:"
    )
    assert "app/bridge.py" in message
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message



def test_mei_normative_census_fails_closed_on_duplicate_canonical_definition(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n"
        "MEI_LIMITE_ANUAL_FATURAMENTO = 90000\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente definicao "
            "canonica duplicada"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_DUPLICATE_DEFINITION:"
    )
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message



def test_mei_normative_census_fails_closed_on_dynamic_canonical_import(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "import importlib\n"
        'mc = importlib.import_module('
        '"app.services.tax_engines.mei_constants")\n'
        "valor = mc.MEI_LIMITE_ANUAL_FATURAMENTO\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo ignorou silenciosamente importacao "
            "dinamica do modulo canonico"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT:"
    )
    assert "app/consumer.py:2" in message



def test_mei_normative_census_fails_closed_on_local_alias_propagation(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "limite = MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "resultado = limite + 1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente propagacao "
            "por alias local"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS:"
    )
    assert "app/consumer.py:2" in message
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message
    assert "limite" in message



def test_mei_normative_census_fails_closed_when_canonical_value_escapes_by_return(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "\n"
        "def obter_limite():\n"
        "    return MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "\n"
        "valor = obter_limite()\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente valor canonico "
            "escapando por return"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_VALUE_ESCAPE:"
    )
    assert "app/consumer.py:4" in message
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message
    assert "RETURN" in message



def test_mei_normative_census_fails_closed_when_canonical_value_crosses_call_boundary(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app" / "consumer.py"
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "\n"
        "def calcular(valor):\n"
        "    return valor + 1\n"
        "\n"
        "resultado = calcular(MEI_LIMITE_ANUAL_FATURAMENTO)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    try:
        census_module.discover_mei_constants()
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError(
            "censo aceitou silenciosamente valor canonico "
            "atravessando fronteira de chamada"
        )

    assert message.startswith(
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_CALL_BOUNDARY:"
    )
    assert "app/consumer.py:6" in message
    assert "MEI_LIMITE_ANUAL_FATURAMENTO" in message



def test_mei_normative_census_accumulates_multiple_findings_in_one_scan(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    dynamic_path = tmp_path / "app" / "dynamic_consumer.py"
    dynamic_path.write_text(
        "import importlib\n"
        'mc = importlib.import_module('
        '"app.services.tax_engines.mei_constants")\n',
        encoding="utf-8",
    )

    alias_path = tmp_path / "app" / "alias_consumer.py"
    alias_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "limite = MEI_LIMITE_ANUAL_FATURAMENTO\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    report = census_module._scan_call_sites_report(
        {"MEI_LIMITE_ANUAL_FATURAMENTO"}
    )

    codes = {
        finding.code
        for finding in report.findings
    }

    assert (
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT"
        in codes
    )
    assert (
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS"
        in codes
    )

    assert len(report.findings) >= 2
    assert report.files_discovered == 3
    assert report.files_parsed == 3
    assert report.scan_complete is True



def test_build_census_returns_blocked_with_all_findings_instead_of_aborting(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_normative_census as census_module

    constants_path = (
        tmp_path
        / "app"
        / "services"
        / "tax_engines"
        / "mei_constants.py"
    )
    constants_path.parent.mkdir(parents=True)
    constants_path.write_text(
        "MEI_LIMITE_ANUAL_FATURAMENTO = 81000\n",
        encoding="utf-8",
    )

    dynamic_path = tmp_path / "app" / "dynamic_consumer.py"
    dynamic_path.write_text(
        "import importlib\n"
        'mc = importlib.import_module('
        '"app.services.tax_engines.mei_constants")\n',
        encoding="utf-8",
    )

    alias_path = tmp_path / "app" / "alias_consumer.py"
    alias_path.write_text(
        "from app.services.tax_engines.mei_constants "
        "import MEI_LIMITE_ANUAL_FATURAMENTO\n"
        "limite = MEI_LIMITE_ANUAL_FATURAMENTO\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    monkeypatch.setattr(
        census_module,
        "CONSTANTS_PATH",
        constants_path,
    )

    census = census_module.build_census()

    assert census["status"] == "BLOCKED"
    assert census["scan_complete"] is True
    assert census["files_discovered"] == 3
    assert census["files_parsed"] == 3
    assert census["constants_total"] == 1
    assert census["findings_total"] >= 2

    codes = {
        item["code"]
        for item in census["findings"]
    }

    assert (
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT"
        in codes
    )
    assert (
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS"
        in codes
    )



def test_real_repository_call_site_scan_is_complete_and_has_no_structural_findings():
    import app.scripts.mei_normative_census as census_module

    definitions = census_module._discover_constant_definitions()
    constant_names = {
        name
        for name, _ in definitions
    }

    report = census_module._scan_call_sites_report(
        constant_names
    )

    assert report.scan_complete is True
    assert report.files_discovered > 0
    assert report.files_parsed == report.files_discovered
    assert report.findings == ()
    assert len(constant_names) == 9



def test_mei_normative_census_classifies_direct_usage_contexts_deterministically():
    import ast
    import app.scripts.mei_normative_census as census_module

    source = """
MEI_TEST = 81000

if faturamento > MEI_TEST:
    bloqueado = True

valor = MEI_TEST * 2

mensagem = f"Limite: {MEI_TEST}"

EXPORTS = {"limite": MEI_TEST}
"""

    tree = ast.parse(source)

    usages = census_module._classify_constant_usages_in_tree(
        tree=tree,
        constant_names={"MEI_TEST"},
        arquivo="app/test_fixture.py",
    )

    observed = {
        (item.linha, item.categoria)
        for item in usages
    }

    assert observed == {
        (4, "DECISION"),
        (7, "CALCULATION"),
        (9, "PRESENTATION"),
        (11, "INFRASTRUCTURE"),
    }


def _normative_case(census_module, *, usages, bindings=None, sources=None, reference_date=None):
    record = census_module.ConstantRecord("MEI_TEST", "app/constants.py", 1, ())
    return census_module._evaluate_constant(
        record=record, usages=tuple(usages), bindings=bindings or [],
        sources=sources or {}, reference_date=reference_date,
    )


def _usage(census_module, category, line=2):
    return census_module.UsageRecord("MEI_TEST", "app/use.py", line, category, "fixture")


def _binding():
    return {"constante_id": "MEI_TEST", "fonte_id": "SYNTH-001", "versao_fonte": "1.0.0",
            "vigencia_inicio": "2025-01-01", "vigencia_fim": None,
            "jurisdicao_codigo": "BR", "risco": "alto", "invariantes": ["INV_001"]}


def _source(*, decisory=True, target="MEI_TEST"):
    source = _canonical_source()
    source["pode_fundamentar_decisao"] = decisory
    source["alvos_normativos_autorizados"] = [{"tipo": "constante", "id": target}]
    return source


def test_census_blocks_reachable_constant_without_binding_and_zero_structural_findings(tmp_path, monkeypatch):
    import json
    import app.scripts.mei_normative_census as module
    constants = tmp_path / "app/services/tax_engines/mei_constants.py"
    constants.parent.mkdir(parents=True)
    constants.write_text("MEI_TEST=1\n", encoding="utf-8")
    (tmp_path / "app/consumer.py").write_text(
        "from app.services.tax_engines.mei_constants import MEI_TEST\nif value > MEI_TEST:\n    pass\n",
        encoding="utf-8",
    )
    data = tmp_path / "data"
    data.mkdir()
    (data / "fontes_tributarias_manifest.json").write_text(json.dumps({"fontes": []}), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "CONSTANTS_PATH", constants)
    structural = module._scan_call_sites_report({"MEI_TEST"})
    result = module.build_census()
    assert structural.scan_complete is True and structural.findings == ()
    assert result["constants"][0]["final_status"] == "BLOCKED"
    assert result["constants"][0]["reasons"] == ["BINDING_MISSING"]


def test_census_blocks_binding_without_decisory_source_and_outside_target(monkeypatch):
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard
    usage = [_usage(module, "CALCULATION")]
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": _source(decisory=False)})
    no_authority = _normative_case(module, usages=usage, bindings=[_binding()], reference_date=date(2025, 6, 1))
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": _source(target="OTHER")})
    wrong_target = _normative_case(module, usages=usage, bindings=[_binding()], reference_date=date(2025, 6, 1))
    assert "FONTE_NAO_AUTORIZADA" in no_authority["reasons"]
    assert "ALVO_FORA_DO_ESCOPO_DA_FONTE" in wrong_target["reasons"]


def test_census_temporality_is_fail_closed_without_or_outside_reference_date(monkeypatch):
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": _source()})
    kwargs = {"usages": [_usage(module, "DECISION")], "bindings": [_binding()]}
    absent = _normative_case(module, **kwargs)
    outside = _normative_case(module, **kwargs, reference_date=__import__("datetime").date(2024, 12, 31))
    assert absent["reasons"] == ["UNRESOLVED_TEMPORAL"]
    assert "FORA_DA_VIGENCIA" in outside["reasons"]


def test_census_preserves_presentation_and_decision_and_unresolved_usage():
    import ast
    import app.scripts.mei_normative_census as module
    tree = ast.parse('MEI_TEST=1\nif value > MEI_TEST:\n    pass\ntext=f"{MEI_TEST}"\nlookup=table[MEI_TEST]\n')
    usages = module._classify_constant_usages_in_tree(
        tree=tree, constant_names={"MEI_TEST"}, arquivo="fixture.py"
    )
    result = _normative_case(module, usages=usages)
    assert result["categorias"] == ["DECISION", "PRESENTATION", "UNRESOLVED"]
    assert result["final_status"] == "UNRESOLVED"


def test_census_reports_multiple_problems_and_non_normative_explicitly(monkeypatch):
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": _source()})
    ambiguous = _normative_case(module, usages=[_usage(module, "DECISION")], bindings=[_binding(), dict(_binding())], reference_date=date(2025, 6, 1))
    infrastructure = _normative_case(module, usages=[_usage(module, "INFRASTRUCTURE")])
    assert "BINDING_DUPLICADO" in ambiguous["reasons"]
    assert infrastructure["final_status"] == "NON_NORMATIVE"


def test_census_does_not_infer_non_normative_from_absence_of_usages():
    import app.scripts.mei_normative_census as module
    result = _normative_case(module, usages=[])
    assert result["final_status"] == "UNRESOLVED"
    assert result["reasons"] == ["NO_USAGE_EVIDENCE"]


def test_census_accumulates_binding_ambiguity_and_source_authority_problems(monkeypatch):
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": _source(decisory=False)})
    result = _normative_case(
        module,
        usages=[_usage(module, "DECISION")],
        bindings=[_binding(), dict(_binding())],
        reference_date=date(2025, 6, 1),
    )
    assert result["final_status"] == "UNRESOLVED"
    assert result["reasons"] == ["BINDING_DUPLICADO"]


def test_census_evaluation_is_order_independent_and_repeatable(tmp_path, monkeypatch):
    import json
    import app.scripts.mei_normative_census as module

    def materialize(root, order):
        constants = root / "app/services/tax_engines/mei_constants.py"
        constants.parent.mkdir(parents=True)
        constants.write_text("MEI_A=1\nMEI_B=2\n", encoding="utf-8")
        contents = {
            "a.py": "from app.services.tax_engines.mei_constants import MEI_A\nif x > MEI_A:\n    pass\n",
            "b.py": "from app.services.tax_engines.mei_constants import MEI_B\ny=MEI_B*2\n",
        }
        for name in order:
            (root / "app" / name).write_text(contents[name], encoding="utf-8")
        data = root / "data"
        data.mkdir()
        (data / "fontes_tributarias_manifest.json").write_text(json.dumps({"fontes": []}), encoding="utf-8")
        return constants

    roots = [tmp_path / "one", tmp_path / "two"]
    constants = [materialize(roots[0], ["a.py", "b.py"]), materialize(roots[1], ["b.py", "a.py"])]
    outputs = []
    for root, path in zip(roots, constants):
        monkeypatch.setattr(module, "ROOT", root)
        monkeypatch.setattr(module, "CONSTANTS_PATH", path)
        outputs.append(module.build_census())
    assert outputs[0] == outputs[1]
    assert outputs[1] == module.build_census()

    from datetime import date
    import app.services.source_authority_guard as guard
    source = _canonical_source()
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": source})
    binding_a = _binding()
    binding_b = dict(_binding())
    binding_b["versao_fonte"] = "2.0.0"
    binding_b["invariantes"] = ["INV_002"]
    record = module.ConstantRecord("MEI_TEST", "fixture.py", 1, ())
    usages = (module.UsageRecord("MEI_TEST", "fixture.py", 2, "DECISION", "Compare"),)
    binding_outputs = []
    for bindings in ([binding_a, binding_b], [binding_b, binding_a]):
        result = module._evaluate_constant(
            record=record, usages=usages, bindings=list(bindings),
            sources={"SYNTH-001": source}, reference_date=date(2025, 6, 1),
        )
        binding_outputs.append(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    assert binding_outputs[0] == binding_outputs[1]


def test_incomplete_scan_cannot_produce_authorized(monkeypatch):
    import app.scripts.mei_normative_census as module
    monkeypatch.setattr(module, "_discover_constant_definitions", lambda: (("MEI_TEST", 1),))
    monkeypatch.setattr(module, "_scan_call_sites_report", lambda names: module.CallSiteScanReport({"MEI_TEST": ()}, (), 2, 1, False))
    monkeypatch.setattr(module, "_discover_usage_records", lambda names: ())
    monkeypatch.setattr(module, "_load_local_normative_evidence", lambda: module.BindingDiscoveryReport((), {}, ()))
    monkeypatch.setattr(module, "CONSTANTS_PATH", module.ROOT / "app/constants.py")
    assert module.build_census()["status"] == "BLOCKED"


def _canonical_source(*, version="1.0.0", end=None):
    return {
        "id": "SYNTH-001", "tipo": "normativa_oficial", "nome": "Sintetica",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": version, "vigencia_inicio": "2025-01-01",
        "vigencia_fim": end, "jurisdicao": "federal",
        "jurisdicao_codigo": "BR", "risco_se_desatualizada": "alto",
        "hash_referencia": "A" * 64,
        "alvos_normativos_autorizados": [
            {"tipo": "constante", "id": "MEI_TEST"}
        ],
    }


def test_census_cannot_authorize_when_canonical_guard_rejects(monkeypatch):
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard

    binding = _binding()
    binding["fonte_id"] = "SYNTH-001"
    binding["versao_fonte"] = "WRONG"
    binding["invariantes"] = ["INV_001"]
    source = _canonical_source(version="RIGHT")
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": source})

    canonical = guard.validar_bindings_normativos({
        "contexto": {"data_referencia": "2025-06-01", "jurisdicao_codigo": "BR", "uso_solicitado": "decisao_definitiva"},
        "bindings": [binding],
    })
    census = _normative_case(
        module, usages=[_usage(module, "DECISION")], bindings=[binding],
        sources={"SYNTH-001": source}, reference_date=date(2025, 6, 1),
    )
    assert canonical.autorizado_fundamentar_decisao is False
    assert census["final_status"] != "AUTHORIZED"
    assert "VERSAO_FONTE_INCOMPATIVEL" in census["reasons"]


def test_usage_inside_if_body_is_not_contaminated_by_branch():
    import ast
    import app.scripts.mei_normative_census as module
    tree = ast.parse('MEI_TEST=1\nif condicao:\n    texto=f"{MEI_TEST}"\n    valor=MEI_TEST*2\n')
    usages = module._classify_constant_usages_in_tree(
        tree=tree, constant_names={"MEI_TEST"}, arquivo="fixture.py"
    )
    assert [(item.linha, item.categoria) for item in usages] == [
        (3, "PRESENTATION"), (4, "CALCULATION")
    ]


def test_transformations_preserve_lineage_fail_closed():
    import ast
    import app.scripts.mei_normative_census as module
    sources = (
        'MEI_TEST=1\nx=str(MEI_TEST)\nif x:\n    pass\n',
        'MEI_TEST=1\nx=Decimal(str(MEI_TEST))\nif x > 0:\n    pass\n',
        'MEI_TEST=1\nx=f"{MEI_TEST}"\ndef expose():\n    return x\n',
    )
    for source in sources:
        usages = module._classify_constant_usages_in_tree(
            tree=ast.parse(source), constant_names={"MEI_TEST"}, arquivo="fixture.py"
        )
        assert len(usages) == 1
        assert usages[0].categoria == "UNRESOLVED"
        assert usages[0].evidencia.startswith("UNRESOLVED_LINEAGE:")


def test_canonical_temporality_closed_open_invalid_and_authorized(monkeypatch):
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard

    source = _canonical_source(end="2025-12-31")
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": source})
    closed = _binding()
    closed["vigencia_fim"] = "2025-12-31"
    common = {"usages": [_usage(module, "DECISION")], "bindings": [closed], "sources": {"SYNTH-001": source}}
    before = _normative_case(module, **common, reference_date=date(2024, 12, 31))
    after = _normative_case(module, **common, reference_date=date(2026, 1, 1))
    valid = _normative_case(module, **common, reference_date=date(2025, 6, 1))
    invalid = _normative_case(module, **common, reference_date="2025-02-30")
    assert "FORA_DA_VIGENCIA" in before["reasons"]
    assert "FORA_DA_VIGENCIA" in after["reasons"]
    assert valid["final_status"] == "AUTHORIZED"
    assert invalid["final_status"] != "AUTHORIZED"

    open_source = _canonical_source(end=None)
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": open_source})
    opened = _normative_case(
        module, usages=[_usage(module, "DECISION")], bindings=[_binding()],
        sources={"SYNTH-001": open_source}, reference_date=date(2030, 1, 1),
    )
    assert opened["final_status"] == "AUTHORIZED"


def test_census_authorized_implies_canonical_guard_authorized(monkeypatch):
    from copy import deepcopy
    from datetime import date
    import app.scripts.mei_normative_census as module
    import app.services.source_authority_guard as guard

    source = _canonical_source()
    monkeypatch.setattr(guard, "_carregar_manifest", lambda: {"SYNTH-001": source})
    variants = []
    valid = _binding()
    variants.append(valid)
    for field, value in (
        ("versao_fonte", "WRONG"),
        ("jurisdicao_codigo", "PT"),
        ("risco", "baixo"),
        ("constante_id", "OTHER"),
        ("vigencia_inicio", "2030-01-01"),
    ):
        item = deepcopy(valid)
        item[field] = value
        variants.append(item)

    for binding in variants:
        payload = {
            "contexto": {"data_referencia": "2025-06-01", "jurisdicao_codigo": binding["jurisdicao_codigo"], "uso_solicitado": "decisao_definitiva"},
            "bindings": [binding],
        }
        canonical = guard.validar_bindings_normativos(payload)
        census = _normative_case(
            module, usages=[_usage(module, "DECISION")], bindings=[binding],
            sources={"SYNTH-001": source}, reference_date=date(2025, 6, 1),
        )
        assert census["final_status"] != "AUTHORIZED" or canonical.autorizado_fundamentar_decisao


def test_binding_discovery_accepts_only_canonical_batch_envelope(tmp_path, monkeypatch):
    import json
    import app.scripts.mei_normative_census as module
    data = tmp_path / "data"
    data.mkdir()
    (data / "fontes_tributarias_manifest.json").write_text(
        json.dumps({"fontes": []}), encoding="utf-8"
    )
    payload = {
        "contexto": {"data_referencia": "2025-06-01", "jurisdicao_codigo": "BR", "uso_solicitado": "decisao_definitiva"},
        "bindings": [_binding()],
    }
    (data / "canonical.json").write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    report = module._load_local_normative_evidence()
    assert len(report.bindings) == 1
    assert report.bindings[0]["constante_id"] == "MEI_TEST"
    assert report.findings == ()


def test_binding_discovery_fails_closed_for_target_outside_canonical_batch(tmp_path, monkeypatch):
    import json
    import app.scripts.mei_normative_census as module
    data = tmp_path / "data"
    data.mkdir()
    (data / "nested.json").write_text(
        json.dumps({"records": [{"constante_id": "MEI_TEST", "fonte_id": "SYNTH-001"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    report = module._load_local_normative_evidence()
    assert report.bindings == ()
    assert [item.code for item in report.findings] == [
        "MEI_NORMATIVE_CENSUS_BINDING_DISCOVERY_UNRESOLVED"
    ]


def test_reconciliation_detects_unaccounted_orphan_and_duplicate_identities(tmp_path, monkeypatch):
    import app.scripts.mei_normative_census as module
    constants = tmp_path / "app/services/tax_engines/mei_constants.py"
    constants.parent.mkdir(parents=True)
    constants.write_text("MEI_TEST=1\n", encoding="utf-8")
    (tmp_path / "app/consumer.py").write_text(
        "from app.services.tax_engines.mei_constants import MEI_TEST\nif value > MEI_TEST:\n    pass\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "CONSTANTS_PATH", constants)
    structural = module._scan_call_sites_report({"MEI_TEST"}).call_sites
    semantic = module._discover_usage_records({"MEI_TEST"})

    exact = module._reconcile_call_sites_and_usages(structural, semantic)
    assert (exact.structural_total, exact.semantic_total) == (1, 1)
    assert exact.unaccounted == exact.orphan == exact.duplicates == ()

    missing_semantic = module._reconcile_call_sites_and_usages(structural, ())
    assert len(missing_semantic.unaccounted) == 1

    missing_structural = module._reconcile_call_sites_and_usages({"MEI_TEST": ()}, semantic)
    assert len(missing_structural.orphan) == 1

    duplicated = module._reconcile_call_sites_and_usages(structural, semantic + semantic)
    assert len(duplicated.duplicates) == 1

    original_scan = module._scan_call_sites_report
    original_usages = module._discover_usage_records
    base_scan = original_scan({"MEI_TEST"})

    monkeypatch.setattr(
        module, "_scan_call_sites_report",
        lambda names: module.CallSiteScanReport(
            {"MEI_TEST": ()}, base_scan.findings,
            base_scan.files_discovered, base_scan.files_parsed, True,
        ),
    )
    orphan_census = module.build_census()
    assert orphan_census["status"] == "BLOCKED"
    assert "MEI_NORMATIVE_CENSUS_RECONCILIATION_ORPHAN" in {
        item["code"] for item in orphan_census["findings"]
    }

    monkeypatch.setattr(module, "_scan_call_sites_report", original_scan)
    monkeypatch.setattr(module, "_discover_usage_records", lambda names: ())
    unaccounted_census = module.build_census()
    assert "MEI_NORMATIVE_CENSUS_RECONCILIATION_UNACCOUNTED" in {
        item["code"] for item in unaccounted_census["findings"]
    }

    monkeypatch.setattr(module, "_discover_usage_records", lambda names: semantic + semantic)
    duplicate_census = module.build_census()
    assert "MEI_NORMATIVE_CENSUS_RECONCILIATION_DUPLICATE" in {
        item["code"] for item in duplicate_census["findings"]
    }
