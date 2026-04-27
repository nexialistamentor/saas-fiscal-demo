"""AG3 — NormativeWatchdogAgent: testes de vigência, cobertura e fontes."""

import pytest
from unittest.mock import patch

from app.agents.normative_watchdog_agent import NormativeWatchdogAgent


@pytest.fixture
def agent():
    return NormativeWatchdogAgent()


@pytest.fixture
def tabela_base():
    return [
        {
            "estado": "PA",
            "ncm": "22021000",
            "mva": 40.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": "2018-01-01",
            "vigencia_fim": None,
            "nivel_confianca_fonte": "oficial",
            "fonte_legal": "Portaria SEFAZ/PA 058/2023",
            "importado_por": "seed_mva.py",
        },
    ]


@pytest.mark.asyncio
async def test_base_ausente_alerta_critico(agent):
    resultado = await agent.run({})
    assert resultado["total_alertas"] == 1
    assert resultado["alertas"][0]["tipo"] == "BASE_NORMATIVA_AUSENTE"


@pytest.mark.asyncio
async def test_ufs_sem_cobertura_detectadas(agent, tabela_base):
    with patch("app.agents.normative_watchdog_agent._consultar_dou", return_value=[]):
        resultado = await agent.run({"tabela_normativa": tabela_base})
    ufs = resultado.get("ufs_sem_cobertura", [])
    assert "SP" in ufs
    assert "PA" not in ufs


@pytest.mark.asyncio
async def test_vigencia_expirada_sem_substituto(agent):
    tabela = [
        {
            "estado": "MG",
            "ncm": "22021000",
            "mva": 40.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": "2018-01-01",
            "vigencia_fim": "2020-01-01",
            "nivel_confianca_fonte": "convenio_base",
            "fonte_legal": "Convênio 142/2018",
            "importado_por": "import_mva.py",
        },
    ]
    with patch("app.agents.normative_watchdog_agent._consultar_dou", return_value=[]):
        resultado = await agent.run({"tabela_normativa": tabela})
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "VIGENCIA_EXPIRADA_SEM_SUBSTITUTO" in tipos


@pytest.mark.asyncio
async def test_sem_fonte_legal_alerta_alto(agent):
    tabela = [
        {
            "estado": "PA",
            "ncm": "22021000",
            "mva": 40.0,
            "aliquota_interna": 0.18,
            "vigencia_inicio": "2018-01-01",
            "vigencia_fim": None,
            "nivel_confianca_fonte": "oficial",
            "fonte_legal": None,
            "importado_por": None,
        },
    ]
    with patch("app.agents.normative_watchdog_agent._consultar_dou", return_value=[]):
        resultado = await agent.run({"tabela_normativa": tabela})
    tipos = [a["tipo"] for a in resultado["alertas"]]
    assert "REGRAS_SEM_FONTE_LEGAL" in tipos
