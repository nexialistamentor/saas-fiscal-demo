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
AGENT_EXECUTOR = AGENTS_DIR / "agent_executor.py"
MAIN_MODULE = APP_DIR / "main.py"

COORDINATION_MODULES = {
    "__init__.py",
    "agent_executor.py",
    "agent_registry.py",
    "agent_scheduler.py",
    "mission_factory.py",
}

NON_PERSISTING_AGENT_MODULES = (
    AGENTS_DIR / "ag_abertura_agent.py",
    AGENTS_DIR / "ag_encerramento_agent.py",
    AGENTS_DIR / "agent_erro_operacional.py",
    AGENTS_DIR / "auditor_fiscal_agent.py",
    AGENTS_DIR / "consistency_audit_agent.py",
    AGENTS_DIR / "data_sanitization_agent.py",
    AGENTS_DIR / "memorial_validator_agent.py",
    AGENTS_DIR / "normative_watchdog_agent.py",
    AGENTS_DIR / "performance_agent.py",
    AGENTS_DIR / "repair_agent.py",
    AGENTS_DIR / "security_audit_agent.py",
)

PERSISTENCE_MUTATION_METHODS = {
    "add",
    "add_all",
    "commit",
    "delete",
    "execute",
    "executemany",
    "flush",
    "merge",
    "bulk_save_objects",
    "bulk_insert_mappings",
    "bulk_update_mappings",
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



def _root_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_name(node.value)
    if isinstance(node, ast.Call):
        return _root_name(node.func)
    if isinstance(node, ast.Subscript):
        return _root_name(node.value)
    return None


def _session_names(path: Path) -> set[str]:
    tree = _parse(path)
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in node.args.args:
                annotation = arg.annotation
                if (
                    isinstance(annotation, ast.Name)
                    and annotation.id == "Session"
                ) or (
                    isinstance(annotation, ast.Attribute)
                    and annotation.attr == "Session"
                ):
                    names.add(arg.arg)

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if not isinstance(value, ast.Call):
                continue
            called = _root_name(value.func)
            if called != "SessionLocal":
                continue

            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            for target in targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)

    return names


def _persistence_mutation_calls(path: Path) -> list[tuple[int, str]]:
    tree = _parse(path)
    session_names = _session_names(path)
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue

        method = node.func.attr
        if method not in PERSISTENCE_MUTATION_METHODS:
            continue

        receiver = _root_name(node.func.value)
        if receiver in session_names:
            violations.append((node.lineno, method))

    return sorted(violations)


def _defines_executable_agent(path: Path) -> bool:
    tree = _parse(path)

    return any(
        isinstance(node, ast.ClassDef)
        and any(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "run"
            for item in node.body
        )
        for node in tree.body
    )


def _operational_agent_modules() -> list[Path]:
    return sorted(
        path
        for path in AGENTS_DIR.glob("*.py")
        if _defines_executable_agent(path)
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

def test_agent_executor_does_not_import_persistence_infrastructure() -> None:
    imports = _imports(AGENT_EXECUTOR)
    forbidden_prefixes = (
        "app.database",
        "app.models",
        "sqlalchemy",
    )

    forbidden = sorted(
        module
        for module in imports
        if _is_prefixed_by(module, forbidden_prefixes)
    )

    assert forbidden == [], (
        "AgentExecutor nao pode importar infraestrutura de persistencia: "
        f"{forbidden}. Efeitos pertencem a fronteira soberana."
    )

@pytest.mark.parametrize(
    "agent_path",
    NON_PERSISTING_AGENT_MODULES,
    ids=lambda path: path.name,
)
def test_non_persisting_agents_do_not_call_persistence_mutations(
    agent_path: Path,
) -> None:
    violations = _persistence_mutation_calls(agent_path)

    assert violations == [], (
        f"{agent_path.relative_to(ROOT)} executa primitivas de persistencia "
        f"{violations}; agentes read-only/advisory devem produzir resultado, "
        "nao efeitos persistentes."
    )


def test_scheduler_does_not_default_concrete_tenant_identity() -> None:
    scheduler_module = AGENTS_DIR / "agent_scheduler.py"
    tree = ast.parse(
        scheduler_module.read_text(encoding="utf-8")
    )

    violations = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ):
            continue

        positional_args = [
            *node.args.posonlyargs,
            *node.args.args,
        ]
        positional_defaults = [
            None
        ] * (
            len(positional_args) - len(node.args.defaults)
        ) + list(node.args.defaults)

        argument_defaults = [
            *zip(positional_args, positional_defaults),
            *zip(
                node.args.kwonlyargs,
                node.args.kw_defaults,
            ),
        ]

        for argument, default in argument_defaults:
            if argument.arg not in {
                "empresa_id",
                "tenant_id",
            }:
                continue

            if default is None:
                continue

            if (
                isinstance(default, ast.Constant)
                and default.value is None
            ):
                continue

            violations.append(
                (
                    node.name,
                    argument.arg,
                    node.lineno,
                    ast.unparse(default),
                )
            )

    assert violations == [], (
        "Scheduler não pode inventar identidade tenant "
        "por default concreto. Violações: "
        f"{violations}"
    )
