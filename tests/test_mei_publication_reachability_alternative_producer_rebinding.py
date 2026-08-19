"""RED attack: a rebound local must not remain producer-derived."""

from __future__ import annotations


def test_rebound_local_does_not_promote_alternative_producer_red(
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
    (app_root / "wrapper.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def falso_wrapper():\n"
        "    das = calcular_das_mei(1621, 'servicos')\n"
        "    das = 0\n"
        "    return {'imposto': das}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    inventory = census_module._alternative_producer_inventory(
        modules,
        canonical_producer_id=census_module.PRODUCER_ID,
    )

    assert "app.wrapper.falso_wrapper" not in inventory
