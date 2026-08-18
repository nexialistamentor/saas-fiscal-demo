"""Deterministic MEI publication/reachability census — minimal V1 core.

This first implementation is intentionally narrow. It proves the three real
entrypoints fixed by the RED contract before the scanner is expanded to the
full adversarial surface.

No network. No LLM. No production mutation.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "MEI_PUBLICATION_REACHABILITY_CENSUS_V1"
PRODUCER_ID = "app.services.tax_engines.mei_constants.calcular_das_mei"


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    path: Path
    tree: ast.Module
    imports: dict[str, str]
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef]


def _module_name(path: Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _parse_app() -> dict[str, ModuleInfo]:
    app_root = ROOT / "app"
    if not app_root.is_dir():
        raise RuntimeError(f"MEI_REACHABILITY_APP_ROOT_MISSING:{app_root}")

    modules: dict[str, ModuleInfo] = {}
    for path in sorted(app_root.rglob("*.py")):
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise RuntimeError(
                f"MEI_REACHABILITY_SCAN_FAILED:{relative}:{type(exc).__name__}:{exc}"
            ) from exc

        imports: dict[str, str] = {}
        functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        module = _module_name(path)

        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                for alias in node.names:
                    imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[-1]] = alias.name
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[node.name] = node
            elif isinstance(node, ast.ClassDef):
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions[f"{node.name}.{member.name}"] = member

        modules[module] = ModuleInfo(module, path, tree, imports, functions)

    return modules


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts: list[str] = [node.func.attr]
        current: ast.AST = node.func.value
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
    return None


def _mounted_routers(modules: dict[str, ModuleInfo]) -> dict[str, tuple[str, str]]:
    main = modules["app.main"]
    mounted: dict[str, tuple[str, str]] = {}

    for node in ast.walk(main.tree):
        if not isinstance(node, ast.Call):
            continue
        if not (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "app"
            and node.func.attr == "include_router"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            continue

        local_router_name = node.args[0].id
        target = main.imports.get(local_router_name)
        if target is None or "." not in target:
            continue
        module_name, router_object = target.rsplit(".", 1)
        prefix = ""
        for keyword in node.keywords:
            if keyword.arg == "prefix":
                prefix = _literal_string(keyword.value) or ""
        mounted[module_name] = (router_object, prefix)

    return mounted


def _route_decorator(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    router_object: str,
) -> str | None:
    for decorator in node.decorator_list:
        if not isinstance(decorator, ast.Call) or not decorator.args:
            continue
        func = decorator.func
        if not (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and func.value.id == router_object
            and func.attr.lower() in {"get", "post", "put", "patch", "delete"}
        ):
            continue
        return _literal_string(decorator.args[0])
    return None


def _condition_mentions_mei(test: ast.AST) -> bool:
    try:
        text = ast.unparse(test).lower()
    except Exception:
        return False
    return "mei" in text and ("tipo" in text or "regime" in text or "contribuinte" in text)


def _extract_blocker_code(raise_node: ast.Raise) -> str | None:
    exc = raise_node.exc
    if not isinstance(exc, ast.Call):
        return None
    name = _call_name(exc)
    if name is None or not name.endswith("HTTPException"):
        return None

    for keyword in exc.keywords:
        if keyword.arg != "detail" or not isinstance(keyword.value, ast.Dict):
            continue
        for key, value in zip(keyword.value.keys, keyword.value.values):
            if _literal_string(key) == "tipo_bloqueio":
                return _literal_string(value)
    return None


def _mei_blocker(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str | None:
    """Return a proven terminal blocker for an explicit MEI branch.

    Minimal V1 deliberately accepts only a top-level MEI ``if`` containing an
    unconditional top-level ``raise HTTPException`` in that branch. Nested
    validation raises do not replace the terminal blocker.
    """
    for statement in node.body:
        if not isinstance(statement, ast.If) or not _condition_mentions_mei(statement.test):
            continue
        for child in reversed(statement.body):
            if isinstance(child, ast.Raise):
                blocker = _extract_blocker_code(child)
                if blocker:
                    return blocker
    return None


def _resolve_name(module: ModuleInfo, name: str) -> str | None:
    if name in module.functions:
        return f"{module.name}.{name}"
    return module.imports.get(name)


def _function_node(
    modules: dict[str, ModuleInfo],
    function_id: str,
) -> tuple[ModuleInfo, ast.FunctionDef | ast.AsyncFunctionDef] | None:
    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if not function_id.startswith(prefix):
            continue
        local_name = function_id[len(prefix):]
        node = modules[module_name].functions.get(local_name)
        if node is not None:
            return modules[module_name], node
    return None


def _mei_specific_statements(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    specific: list[ast.stmt] = []
    for statement in node.body:
        if isinstance(statement, ast.If) and _condition_mentions_mei(statement.test):
            specific.extend(statement.body)
    return specific or list(node.body)


def _direct_callees(
    module: ModuleInfo,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    callees: list[str] = []
    for statement in _mei_specific_statements(node):
        for call in [item for item in ast.walk(statement) if isinstance(item, ast.Call)]:
            name = _call_name(call)
            if name is None or "." in name:
                continue
            resolved = _resolve_name(module, name)
            if resolved is not None:
                callees.append(resolved)
    return sorted(set(callees))


def _assistant_trace(
    modules: dict[str, ModuleInfo],
    route_function_id: str,
) -> list[str]:
    """Follow the currently proven Assistant MEI lineage.

    Generic direct Python calls are resolved from AST imports/local functions.
    The orchestrator→registry dispatch is one explicit V1 semantic edge because
    the runtime call is indirect through ``ENGINE_REGISTRY``.
    """
    target_sequence = [
        "app.services.assistente_service.responder_pergunta",
        "app.services.assistente_service._resposta_assistente_mei",
        "app.services.analysis_orchestrator.executar_analise",
    ]

    trace = [route_function_id]
    current = route_function_id
    for expected in target_sequence:
        found = _function_node(modules, current)
        if found is None:
            raise RuntimeError(f"MEI_REACHABILITY_UNRESOLVED_FUNCTION:{current}")
        module, node = found
        callees = _direct_callees(module, node)
        if expected not in callees:
            raise RuntimeError(
                f"MEI_REACHABILITY_UNRESOLVED_EDGE:{current}->{expected}"
            )
        trace.append(expected)
        current = expected

    # The current repository dispatches mei_tax indirectly through
    # ENGINE_REGISTRY. Keep that indirection explicit rather than pretending it
    # is a normal direct call.
    engine_id = "app.services.tax_engines.mei_tax_engine.MEITaxEngine.execute"
    engine = _function_node(modules, engine_id)
    if engine is None:
        raise RuntimeError(f"MEI_REACHABILITY_UNRESOLVED_FUNCTION:{engine_id}")
    engine_module, engine_node = engine
    if PRODUCER_ID not in _direct_callees(engine_module, engine_node):
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_EDGE:{engine_id}->{PRODUCER_ID}"
        )

    trace.extend([engine_id, PRODUCER_ID])
    return trace


def build_census() -> dict:
    modules = _parse_app()
    mounted = _mounted_routers(modules)
    paths: list[dict] = []

    for module_name, (router_object, prefix) in sorted(mounted.items()):
        module = modules.get(module_name)
        if module is None:
            raise RuntimeError(f"MEI_REACHABILITY_ROUTER_MODULE_MISSING:{module_name}")

        for local_name, node in sorted(module.functions.items()):
            if "." in local_name:
                continue
            route_path = _route_decorator(node, router_object=router_object)
            if route_path is None:
                continue
            entrypoint = f"{prefix}{route_path}" or "/"
            function_id = f"{module_name}.{local_name}"

            blocker = _mei_blocker(node)
            if blocker is not None:
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "BLOCKED_MEI",
                        "blocked_before_producer": True,
                        "blocker_code": blocker,
                        "producer_ids": [],
                        "sink_kinds": [],
                        "trace": [function_id],
                    }
                )
                continue

            if entrypoint == "/perguntar":
                trace = _assistant_trace(modules, function_id)
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "REACHABLE_MEI",
                        "blocked_before_producer": False,
                        "blocker_code": None,
                        "producer_ids": [PRODUCER_ID],
                        "sink_kinds": ["PUBLICATION"],
                        "trace": trace,
                    }
                )

    paths.sort(key=lambda item: item["entrypoint"])
    blocked = any(
        item["mei_reachability"] == "REACHABLE_MEI"
        and item["producer_ids"]
        and "PUBLICATION" in item["sink_kinds"]
        for item in paths
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "scan_complete": True,
        "status": "BLOCKED" if blocked else "UNRESOLVED",
        "paths": paths,
    }
