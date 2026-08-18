"""Attack contract: MEI argument provenance must survive a static cross-file edge."""

from __future__ import annotations


def test_mei_argument_provenance_survives_cross_file_import(
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
    (app_root / "helpers.py").write_text(
        "def identidade(valor):\n"
        "    return valor\n",
        encoding="utf-8",
    )
    (app_root / "publisher.py").write_text(
        "from app.helpers import identidade\n"
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
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
        caller_function_id="app.publisher.publicar",
        callee_function_id="app.helpers.identidade",
    )

    assert provenance == [
        "app.services.tax_engines.mei_constants.calcular_das_mei",
        "app.publisher.publicar:das",
        "app.helpers.identidade:valor",
        "app.helpers.identidade:return",
        "app.publisher.publicar:saida",
        "app.publisher.publicar:return",
    ]
