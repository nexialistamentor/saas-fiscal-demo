"""RED attack: MEI value provenance must survive a static persistence call."""

from __future__ import annotations


def test_mei_value_provenance_reaches_persistence_call_red(
    tmp_path,
    monkeypatch,
):
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
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def persistir_mei(valor):\n"
        "    return valor\n"
        "\n"
        "def produzir():\n"
        "    das = calcular_das_mei(1621, 'servicos')\n"
        "    return das\n"
        "\n"
        "def guardar():\n"
        "    valor = produzir()\n"
        "    persisted = persistir_mei(valor)\n"
        "    return persisted\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    provenance = census_module._value_provenance_trace(
        modules,
        producer_id=census_module.PRODUCER_ID,
        source_function_id="app.bridge.produzir",
        sink_function_id="app.bridge.guardar",
    )

    assert provenance == [
        "app.services.tax_engines.mei_constants.calcular_das_mei",
        "app.bridge.produzir:das",
        "app.bridge.produzir:return",
        "app.bridge.guardar:valor",
        "app.bridge.guardar:persistir_mei:persistence",
        "app.bridge.guardar:persisted",
        "app.bridge.guardar:return",
    ]
