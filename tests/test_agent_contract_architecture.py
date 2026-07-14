"""
Testes arquitecturais dos contratos soberanos L3 — ADR-008 B14.0/B14.1.

Prova, por análise estática do código-fonte:
- contratos não importam ORM, HTTP ou providers;
- agentes operacionais não importam/chamam outros agentes;
- produção não cria AgentMission directamente fora da MissionFactory;
- agentes não importam SDKs ou adaptadores directos de providers LLM;
- run_all() não integra o fluxo B14;
- o scheduler permanece sem activação no lifespan da API.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
AGENTS_DIR = APP_DIR / "agents"
CONTRACTS_DIR = AGENTS_DIR / "contracts"
MISSION_FACTORY = AGENTS_DIR / "mission_factory.py"
MAIN_MODULE = APP_DIR / "main.py"

COORDINATION_MODULES = {
    "__init__.py",
    "agent_executor.py",
    "agent_registry.py",
    "agent_scheduler.py",
    "mission_factory.py",
}

FORBIDDEN_CONTRACT_IMPORT_PREFIXES = (
    "sqlalchemy",
    "fastapi",
    "starlette",
    "requests",
    "httpx",
    "aiohttp",
    "openai",
    "anthropic",
    "groq",
    "ollama",
    "litellm",
    "mistralai",
    "cohere",
    "google.generativeai",
    "google.genai",
    "app.database",
    "app.db",
    "app.models",
    "app.routers",
    "app.providers",
    "app.services.llm_router",
)

FORBIDDEN_PROVIDER_IMPORT_PREFIXES = (
    "openai",
    "anthropic",
    "groq",
    "ollama",
    "litellm",
    "mistralai",
    "cohere",
    "google.generativeai",
    "google.genai",
    "app.providers",
    "app.services.providers",
    "app.services.llm_providers",
    "app.services.deepseek",
    "app.services.kimi",
    "app.services.openai",
    "app.services.anthropic",
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(
        path.read_text(encoding="utf-8"),
        filename=str(path),
    )


def _imports(path: Path) -> set[str]:
    tree = _parse(path)
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)

    return modules


def _is_prefixed_by(
    module: str,
    prefixes: tuple[str, ...],
) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in prefixes
    )


def _calls_named(path: Path, name: str) -> list[int]:
    tree = _parse(path)
    lines: list[int] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr
        else:
            continue

        if called_name == name:
            lines.append(node.lineno)

    return lines


def _operational_agent_modules() -> list[Path]:
    return sorted(
        path
        for path in AGENTS_DIR.glob("*.py")
        if path.name not in COORDINATION_MODULES
    )


@pytest.mark.parametrize(
    "contract_path",
    sorted(CONTRACTS_DIR.glob("*.py")),
    ids=lambda path: path.name,
)
def test_contracts_do_not_import_orm_http_or_providers(
    contract_path: Path,
) -> None:
    forbidden = sorted(
        module
        for module in _imports(contract_path)
        if _is_prefixed_by(
            module,
            FORBIDDEN_CONTRACT_IMPORT_PREFIXES,
        )
    )

    assert forbidden == [], (
        f"{contract_path.relative_to(ROOT)} importa dependências "
        f"proibidas para contrato puro: {forbidden}"
    )


@pytest.mark.parametrize(
    "agent_path",
    _operational_agent_modules(),
    ids=lambda path: path.name,
)
def test_operational_agents_do_not_import_other_agents(
    agent_path: Path,
) -> None:
    internal_agent_imports = sorted(
        module
        for module in _imports(agent_path)
        if (
            module == "app.agents"
            or module.startswith("app.agents.")
        )
    )

    assert internal_agent_imports == [], (
        f"{agent_path.relative_to(ROOT)} importa outro módulo de agente: "
        f"{internal_agent_imports}. Comunicação agente→agente é proibida."
    )


def test_production_creates_agent_mission_only_in_factory() -> None:
    creation_sites: list[str] = []

    for path in sorted(APP_DIR.rglob("*.py")):
        for line in _calls_named(path, "AgentMission"):
            creation_sites.append(
                f"{path.relative_to(ROOT)}:{line}"
            )

    assert creation_sites == [
        f"{MISSION_FACTORY.relative_to(ROOT)}:206"
    ], (
        "AgentMission deve ser criada operacionalmente apenas pela "
        f"MissionFactory. Ocorrências encontradas: {creation_sites}"
    )


@pytest.mark.parametrize(
    "agent_path",
    sorted(AGENTS_DIR.glob("*.py")),
    ids=lambda path: path.name,
)
def test_agents_do_not_import_provider_sdks_or_direct_adapters(
    agent_path: Path,
) -> None:
    direct_provider_imports = sorted(
        module
        for module in _imports(agent_path)
        if _is_prefixed_by(
            module,
            FORBIDDEN_PROVIDER_IMPORT_PREFIXES,
        )
    )

    assert direct_provider_imports == [], (
        f"{agent_path.relative_to(ROOT)} acede directamente a provider "
        f"LLM: {direct_provider_imports}. Deve usar o LLMRouter soberano."
    )


def test_llm_router_is_allowed_as_the_supervised_gateway() -> None:
    error_agent = AGENTS_DIR / "agent_erro_operacional.py"
    imports = _imports(error_agent)

    assert "app.services.llm_router" in imports
    assert not any(
        _is_prefixed_by(
            module,
            FORBIDDEN_PROVIDER_IMPORT_PREFIXES,
        )
        for module in imports
    )


@pytest.mark.parametrize(
    "b14_path",
    [
        *sorted(CONTRACTS_DIR.glob("*.py")),
        MISSION_FACTORY,
    ],
    ids=lambda path: path.name,
)
def test_b14_flow_does_not_call_run_all(
    b14_path: Path,
) -> None:
    calls = _calls_named(b14_path, "run_all")

    assert calls == [], (
        f"{b14_path.relative_to(ROOT)} chama run_all() nas linhas "
        f"{calls}; run_all() não pertence ao fluxo B14."
    )


def test_fastapi_lifespan_does_not_start_agent_scheduler() -> None:
    active_calls = _calls_named(MAIN_MODULE, "iniciar_loop")

    assert active_calls == [], (
        "O scheduler não pode ser activado no lifespan da API. "
        f"Chamadas activas encontradas nas linhas: {active_calls}"
    )
