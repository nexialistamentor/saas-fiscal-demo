"""RED: a mounted route publishing an alternative MEI producer must be reachable."""

from __future__ import annotations


def test_mounted_route_to_alternative_mei_producer_is_reachable_publication_red(
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
    (app_root / "imposto_service.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "def calcular_imposto_simples():\n"
        "    das = calcular_das_mei(1621, 'servicos')\n"
        "    return {'imposto': das}\n",
        encoding="utf-8",
    )
    (app_root / "public_router.py").write_text(
        "from app.imposto_service import calcular_imposto_simples\n"
        "\n"
        "router = APIRouter()\n"
        "\n"
        "@router.post('/mei-publico')\n"
        "def publicar_mei():\n"
        "    return calcular_imposto_simples()\n",
        encoding="utf-8",
    )
    (app_root / "main.py").write_text(
        "from app.public_router import router as public_router\n"
        "\n"
        "app.include_router(public_router, prefix='/api')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)

    census = census_module.build_census()
    matches = [
        item
        for item in census.get("paths", [])
        if item.get("entrypoint") == "/api/mei-publico"
    ]

    assert len(matches) == 1
    path = matches[0]
    assert path["mei_reachability"] == "REACHABLE_MEI"
    assert path["blocked_before_producer"] is False
    assert "PUBLICATION" in path["sink_kinds"]
    assert census_module.PRODUCER_ID in path["producer_ids"]
    assert "app.imposto_service.calcular_imposto_simples" in path["trace"]
    assert census_module.PRODUCER_ID in path["trace"]
