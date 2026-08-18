"""RED attack: background job/agent presence alone must not create a reachability root."""

from __future__ import annotations


def test_background_function_without_registration_is_inventory_only_red(
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
    (app_root / "jobs.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def executar_mei_job():\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    result = census_module._background_root_inventory(
        modules,
        function_id="app.jobs.executar_mei_job",
    )

    assert result == {
        "function_id": "app.jobs.executar_mei_job",
        "present": True,
        "registration_ids": [],
        "is_root": False,
        "reachability": "INVENTORY_ONLY",
    }
