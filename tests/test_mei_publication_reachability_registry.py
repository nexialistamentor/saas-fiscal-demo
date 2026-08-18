"""RED attack: registry indirection must not be replaced by a hardcoded MEI edge."""

from __future__ import annotations


def test_assistant_trace_fails_closed_when_registry_does_not_select_mei_engine_red(
    tmp_path,
    monkeypatch,
):
    import pytest
    import app.scripts.mei_publication_reachability_census as census_module

    app_root = tmp_path / "app"
    routers_root = app_root / "routers"
    services_root = app_root / "services"
    tax_engines_root = services_root / "tax_engines"
    routers_root.mkdir(parents=True)
    tax_engines_root.mkdir(parents=True)

    (routers_root / "assistente_router.py").write_text(
        "from app.services.assistente_service import responder_pergunta\n"
        "\n"
        "def perguntar():\n"
        "    return responder_pergunta()\n",
        encoding="utf-8",
    )
    (services_root / "assistente_service.py").write_text(
        "from app.services.analysis_orchestrator import executar_analise\n"
        "\n"
        "def responder_pergunta():\n"
        "    return _resposta_assistente_mei()\n"
        "\n"
        "def _resposta_assistente_mei():\n"
        "    return executar_analise('mei_tax', {})\n",
        encoding="utf-8",
    )
    (services_root / "analysis_orchestrator.py").write_text(
        "from app.services.engine_registry import ENGINE_REGISTRY\n"
        "\n"
        "def executar_analise(tipo, dados):\n"
        "    engine = ENGINE_REGISTRY[tipo]['v1']\n"
        "    return engine(dados)\n",
        encoding="utf-8",
    )
    (services_root / "fake_engine.py").write_text(
        "def fake_engine(dados):\n"
        "    return {'fake': True}\n",
        encoding="utf-8",
    )
    (services_root / "engine_registry.py").write_text(
        "from app.services.fake_engine import fake_engine\n"
        "\n"
        "ENGINE_REGISTRY = {'mei_tax': {'v1': fake_engine}}\n",
        encoding="utf-8",
    )
    (tax_engines_root / "mei_constants.py").write_text(
        "def calcular_das_mei(salario, atividade):\n"
        "    return salario\n",
        encoding="utf-8",
    )
    (tax_engines_root / "mei_tax_engine.py").write_text(
        "from app.services.tax_engines.mei_constants import calcular_das_mei\n"
        "\n"
        "class MEITaxEngine:\n"
        "    def execute(self, dados):\n"
        "        return calcular_das_mei(1621, 'servicos')\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(census_module, "ROOT", tmp_path)
    modules = census_module._parse_app()

    with pytest.raises(RuntimeError, match="MEI_REACHABILITY_UNRESOLVED_REGISTRY"):
        census_module._assistant_trace(
            modules,
            "app.routers.assistente_router.perguntar",
        )
