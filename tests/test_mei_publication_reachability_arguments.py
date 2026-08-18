"""RED attack: MEI value provenance must survive a function argument edge."""

from __future__ import annotations


def test_mei_value_provenance_survives_function_argument_and_return_red(
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
        "def identidade(valor):\n"
        "    return valor\n"
        "\n"
        "def publicar():\n"
        "    das = calcular_das_mei(1621, 'servicos')\n"
        "    saida = identidade(das)\n"
        "    return saida\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    provenance = census_module._argument_provenance_trace(
        modules,
        producer_id=census_module.PRODUCER_ID,
        caller_function_id="app.bridge.publicar",
        callee_function_id="app.bridge.identidade",
    )

    assert provenance == [
        "app.services.tax_engines.mei_constants.calcular_das_mei",
        "app.bridge.publicar:das",
        "app.bridge.identidade:valor",
        "app.bridge.identidade:return",
        "app.bridge.publicar:saida",
        "app.bridge.publicar:return",
    ]
