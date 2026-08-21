"""RED: negated MEI conditions must not hide a reachable canonical producer."""

from __future__ import annotations


def test_negated_mei_condition_does_not_hide_fallthrough_producer_red(
    tmp_path,
    monkeypatch,
):
    import app.scripts.mei_publication_reachability_census as census_module

    producer_path = tmp_path / "app/services/tax_engines/mei_constants.py"
    producer_path.parent.mkdir(parents=True)
    producer_path.write_text(
        "def calcular_das_mei(salario, atividade):\n"
        "    return salario\n",
        encoding="utf-8",
    )

    consumer_path = tmp_path / "app/services/dispatcher.py"
    consumer_path.parent.mkdir(parents=True, exist_ok=True)
    consumer_path.write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def executar(regime):\n"
        "    if not (regime == 'mei'):\n"
        "        return 0\n"
        "    return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    modules = census_module._parse_app()
    module = modules["app.services.dispatcher"]
    node = module.functions["executar"]

    assert census_module.PRODUCER_ID in census_module._direct_callees(module, node)
