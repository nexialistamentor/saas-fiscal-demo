"""8B regression: explicit from-import aliases preserve canonical MEI reachability."""

from __future__ import annotations


def test_from_import_alias_resolves_to_canonical_mei_producer(tmp_path, monkeypatch):
    import app.scripts.mei_publication_reachability_census as census_module

    producer_path = tmp_path / "app/services/tax_engines/mei_constants.py"
    producer_path.parent.mkdir(parents=True)
    producer_path.write_text(
        "def calcular_das_mei():\n"
        "    return 1\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app/routes/alias_router.py"
    consumer_path.parent.mkdir(parents=True)
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei as produtor\n"
        "\n"
        "def publicar():\n"
        "    return produtor()\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    module = modules["app.routes.alias_router"]
    node = module.functions["publicar"]

    assert census_module.PRODUCER_ID in census_module._direct_callees(module, node)
