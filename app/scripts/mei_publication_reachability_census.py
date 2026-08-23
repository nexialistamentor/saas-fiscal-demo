"""Deterministic MEI publication/reachability census — minimal V1 core.

This first implementation is intentionally narrow. It proves the three real
entrypoints fixed by the RED contract before the scanner is expanded to the
full adversarial surface.

No network. No LLM. No production mutation.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "MEI_PUBLICATION_REACHABILITY_CENSUS_V1"
PRODUCER_ID = "app.services.tax_engines.mei_constants.calcular_das_mei"
PRODUCER_MODULE_ID = PRODUCER_ID.rsplit(".", 1)[0]
FORMALIZACAO_COMPARE_ID = "app.services.regime_engine.comparar_regimes"
MEI_ENGINE_EXECUTE_ID = "app.services.tax_engines.mei_tax_engine.MEITaxEngine.execute"


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


def _bound_names(target: ast.AST) -> set[str]:
    """Return statically bound names from a Python assignment/delete target."""
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        names: set[str] = set()
        for item in target.elts:
            names.update(_bound_names(item))
        return names
    if isinstance(target, ast.Starred):
        return _bound_names(target.value)
    return set()


def _fail_on_import_rebinding(
    node: ast.AST,
    imports: dict[str, str],
    *,
    module: str,
) -> None:
    """Fail closed when a previously imported local name is rebound."""
    rebound: set[str] = set()
    if isinstance(node, ast.Assign):
        for target in node.targets:
            rebound.update(_bound_names(target))
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        rebound.update(_bound_names(node.target))
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        rebound.add(node.name)
    elif isinstance(node, ast.Delete):
        for target in node.targets:
            rebound.update(_bound_names(target))

    collisions = sorted(rebound.intersection(imports))
    if collisions:
        raise RuntimeError(
            f"MEI_REACHABILITY_REBINDING:{module}:{','.join(collisions)}"
        )


def _fail_on_dynamic_mei_access(module_info: ModuleInfo) -> None:
    """Fail closed on dynamic attribute access to the canonical MEI producer module."""
    for node in ast.walk(module_info.tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            continue

        local_name = node.args[0].id
        target = module_info.imports.get(local_name)
        if target is None:
            continue
        if target == PRODUCER_MODULE_ID or target.startswith(PRODUCER_MODULE_ID + "."):
            raise RuntimeError(
                f"MEI_REACHABILITY_DYNAMIC_ACCESS:{module_info.name}:{local_name}"
            )


def _fail_on_dynamic_mei_import(module_info: ModuleInfo) -> None:
    """Fail closed when importlib dynamically loads the canonical MEI module."""
    for node in ast.walk(module_info.tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue

        target: str | None = None
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
            and isinstance(node.func.value, ast.Name)
            and module_info.imports.get(node.func.value.id) == "importlib"
        ):
            target = "importlib.import_module"
        elif isinstance(node.func, ast.Name):
            target = module_info.imports.get(node.func.id)

        if target != "importlib.import_module":
            continue

        module_name = _literal_string(node.args[0])
        if module_name is None:
            continue
        if module_name == PRODUCER_MODULE_ID or module_name.startswith(PRODUCER_MODULE_ID + "."):
            raise RuntimeError(
                f"MEI_REACHABILITY_DYNAMIC_IMPORT:{module_info.name}:{module_name}"
            )


def _resolve_reexport_target(
    modules: dict[str, ModuleInfo],
    target: str,
    *,
    seen: frozenset[str] = frozenset(),
) -> str:
    """Collapse a static import/reexport chain to its original target."""
    if target in seen:
        raise RuntimeError(f"MEI_REACHABILITY_REEXPORT_CYCLE:{target}")

    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if not target.startswith(prefix):
            continue
        symbol = target[len(prefix):]
        next_target = modules[module_name].imports.get(symbol)
        if next_target is None and "." not in symbol:
            assignments = [
                statement
                for statement in modules[module_name].tree.body
                if (
                    isinstance(statement, ast.Assign)
                    and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)
                    and statement.targets[0].id == symbol
                )
            ]
            if len(assignments) == 1:
                value = assignments[0].value
                if isinstance(value, ast.Name):
                    definitions = [
                        item
                        for item in modules[module_name].tree.body
                        if isinstance(item, ast.ClassDef)
                        and item.name == value.id
                    ]
                    if len(definitions) == 1:
                        return f"{module_name}.{value.id}"
                if isinstance(value, ast.Call):
                    constructor_name = _call_name(value)
                    definitions = [
                        item
                        for item in modules[module_name].tree.body
                        if isinstance(item, ast.ClassDef)
                        and item.name == constructor_name
                    ]
                    if constructor_name is not None and len(definitions) == 1:
                        return f"{module_name}.{constructor_name}"
        if next_target is None:
            return target
        return _resolve_reexport_target(
            modules,
            next_target,
            seen=seen | {target},
        )
    return target


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
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                raise RuntimeError(
                    f"MEI_REACHABILITY_UNRESOLVED_RELATIVE_IMPORT:{module}:{node.lineno}"
                )
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                for alias in node.names:
                    imports[alias.asname or alias.name] = f"{node.module}.{alias.name}"
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[-1]] = alias.name
            else:
                _fail_on_import_rebinding(node, imports, module=module)
                if (
                    isinstance(node, ast.Assign)
                    and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in imports
                ):
                    imports[node.targets[0].id] = imports[node.value.id]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    functions[node.name] = node
                elif isinstance(node, ast.ClassDef):
                    for member in node.body:
                        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            functions[f"{node.name}.{member.name}"] = member

        modules[module] = ModuleInfo(module, path, tree, imports, functions)

    for module in modules.values():
        for local_name, target in list(module.imports.items()):
            module.imports[local_name] = _resolve_reexport_target(modules, target)

    for module in modules.values():
        _fail_on_dynamic_mei_access(module)
        _fail_on_dynamic_mei_import(module)

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


def _router_intrinsic_prefix(module: ModuleInfo, router_object: str) -> str:
    """Resolve a literal prefix declared on the router's APIRouter constructor."""
    for statement in module.tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == router_object
            for target in statement.targets
        ):
            continue
        if not isinstance(statement.value, ast.Call):
            continue
        call_name = _call_name(statement.value)
        if call_name is None or not call_name.endswith("APIRouter"):
            continue
        for keyword in statement.value.keywords:
            if keyword.arg != "prefix":
                continue
            prefix = _literal_string(keyword.value)
            if prefix is None:
                raise RuntimeError(
                    f"MEI_REACHABILITY_DYNAMIC_ROUTER_PREFIX:{module.name}:{router_object}"
                )
            return prefix
        return ""
    return ""


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
        if isinstance(statement.test, ast.BoolOp):
            continue
        if (
            isinstance(statement.test, ast.UnaryOp)
            and isinstance(statement.test.op, ast.Not)
        ):
            continue
        if (
            isinstance(statement.test, ast.Compare)
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.NotEq)
        ):
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
    if "." in name:
        root_name, remainder = name.split(".", 1)
        imported_module = module.imports.get(root_name)
        if imported_module is not None:
            return f"{imported_module}.{remainder}"
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


def _orm_session_operations(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> list[str]:
    """Return direct ORM-like session operations invoked on function parameters."""
    found = _function_node(modules, function_id)
    if found is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_ORM_FUNCTION:{function_id}"
        )

    _, node = found
    parameter_names = {
        arg.arg
        for arg in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    }
    recognized = {"add", "commit", "flush", "refresh", "rollback"}
    operations: list[tuple[int, int, str]] = []
    stack: list[ast.AST] = list(reversed(node.body))

    while stack:
        item = stack.pop()
        if isinstance(
            item,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
        ):
            continue
        if (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and isinstance(item.func.value, ast.Name)
            and item.func.value.id in parameter_names
            and item.func.attr in recognized
        ):
            operations.append((item.lineno, item.col_offset, item.func.attr))
        stack.extend(reversed(list(ast.iter_child_nodes(item))))

    operations.sort()
    return [operation for _, _, operation in operations]


def _orm_persistence_operations(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> list[str]:
    """Return ORM session operations relevant to persistence writes."""
    return [
        operation
        for operation in _orm_session_operations(modules, function_id=function_id)
        if operation in {"add", "commit", "flush"}
    ]


def _static_function_callers(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> list[str]:
    """Return direct statically resolved function callers, scope-local only.

    V1 follows ordinary call syntax through the existing static import/name
    resolver. Nested functions, classes, and lambdas are separate scopes and are
    not attributed to their outer function. Dynamic dispatch is intentionally
    outside this primitive.
    """

    def scope_calls(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
        calls: list[ast.Call] = []
        stack: list[ast.AST] = list(reversed(function_node.body))
        while stack:
            item = stack.pop()
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(item, ast.Call):
                calls.append(item)
            children = list(ast.iter_child_nodes(item))
            stack.extend(reversed(children))
        return calls

    callers: set[str] = set()
    for module_name in sorted(modules):
        module = modules[module_name]
        for local_name, function_node in sorted(module.functions.items()):
            caller_id = f"{module.name}.{local_name}"
            for call in scope_calls(function_node):
                call_name = _call_name(call)
                if call_name is None:
                    continue
                if _resolve_name(module, call_name) == function_id:
                    callers.add(caller_id)
                    break

    return sorted(callers)


def _class_reachability_inventory(
    modules: dict[str, ModuleInfo],
    *,
    class_id: str,
) -> dict:
    """Separate physical class presence from proven static caller reachability.

    V1 only recognizes direct static class-constructor calls that resolve through
    the existing import table (or a same-module class name). Presence by itself
    is inventory and must not be promoted to reachability.
    """
    class_module: ModuleInfo | None = None
    class_name: str | None = None
    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if class_id.startswith(prefix):
            class_module = modules[module_name]
            class_name = class_id[len(prefix):]
            break

    if class_module is None or class_name is None or "." in class_name:
        return {
            "class_id": class_id,
            "present": False,
            "caller_ids": [],
            "reachability": "NOT_PRESENT",
        }

    definitions = [
        node
        for node in class_module.tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(definitions) > 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_CLASS_INVENTORY:{class_id}:duplicate_definition"
        )
    if not definitions:
        return {
            "class_id": class_id,
            "present": False,
            "caller_ids": [],
            "reachability": "NOT_PRESENT",
        }

    caller_ids: set[str] = set()
    for module in modules.values():
        for local_name, function_node in module.functions.items():
            function_id = f"{module.name}.{local_name}"
            for call in (
                item for item in ast.walk(function_node) if isinstance(item, ast.Call)
            ):
                call_name = _call_name(call)
                if call_name is None:
                    continue
                resolved = _resolve_name(module, call_name)
                if resolved is None and module.name == class_module.name and call_name == class_name:
                    resolved = class_id
                if resolved == class_id:
                    caller_ids.add(function_id)

    callers = sorted(caller_ids)
    return {
        "class_id": class_id,
        "present": True,
        "caller_ids": callers,
        "reachability": "STATIC_CALLER" if callers else "INVENTORY_ONLY",
    }


def _background_root_inventory(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    """Keep a background function as inventory until root reachability is proven.

    This first contract proves only the negative boundary: physical presence and
    even a MEI producer call inside the function do not make it a root. Any
    external static call or module-level reference is left unresolved until a
    specific registration/call-root shape is separately qualified.
    """
    found = _function_node(modules, function_id)
    if found is None:
        return {
            "function_id": function_id,
            "present": False,
            "registration_ids": [],
            "is_root": False,
            "reachability": "NOT_PRESENT",
        }

    references: set[str] = set()
    for module in modules.values():
        for local_name, function_node in module.functions.items():
            candidate_id = f"{module.name}.{local_name}"
            if candidate_id == function_id:
                continue
            for call in (
                item for item in ast.walk(function_node) if isinstance(item, ast.Call)
            ):
                call_name = _call_name(call)
                if call_name is not None and _resolve_name(module, call_name) == function_id:
                    references.add(candidate_id)

        for statement in module.tree.body:
            if isinstance(
                statement,
                (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                continue
            for call in (
                item for item in ast.walk(statement) if isinstance(item, ast.Call)
            ):
                call_name = _call_name(call)
                if call_name is not None and _resolve_name(module, call_name) == function_id:
                    references.add(f"{module.name}:<module>")
                for argument in call.args:
                    if not isinstance(argument, ast.Name):
                        continue
                    target = module.imports.get(argument.id)
                    if target is None and argument.id in module.functions:
                        target = f"{module.name}.{argument.id}"
                    if target == function_id:
                        references.add(f"{module.name}:<module>")

    if references:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_BACKGROUND_ROOT:"
            f"{function_id}:{','.join(sorted(references))}"
        )

    return {
        "function_id": function_id,
        "present": True,
        "registration_ids": [],
        "is_root": False,
        "reachability": "INVENTORY_ONLY",
    }


def _fastapi_background_root_inventory(
    modules: dict[str, ModuleInfo],
    *,
    mounted: dict[str, tuple[str, str]],
) -> list[dict]:
    """Discover statically registered FastAPI BackgroundTasks roots on mounted routes."""
    registrations: dict[str, set[str]] = {}

    for module_name, (router_object, _) in sorted(mounted.items()):
        module = modules.get(module_name)
        if module is None:
            raise RuntimeError(f"MEI_REACHABILITY_ROUTER_MODULE_MISSING:{module_name}")

        for local_name, function_node in sorted(module.functions.items()):
            if "." in local_name:
                continue
            if _route_decorator(function_node, router_object=router_object) is None:
                continue

            background_parameters: set[str] = set()
            parameters = [
                *function_node.args.posonlyargs,
                *function_node.args.args,
                *function_node.args.kwonlyargs,
            ]
            for parameter in parameters:
                annotation = parameter.annotation
                if not isinstance(annotation, ast.Name):
                    continue
                if module.imports.get(annotation.id) == "fastapi.BackgroundTasks":
                    background_parameters.add(parameter.arg)

            if not background_parameters:
                continue

            route_function_id = f"{module_name}.{local_name}"
            for call in (
                item for item in ast.walk(function_node) if isinstance(item, ast.Call)
            ):
                if not (
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr == "add_task"
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id in background_parameters
                ):
                    continue

                if not call.args:
                    raise RuntimeError(
                        "MEI_REACHABILITY_UNRESOLVED_BACKGROUND_REGISTRATION:"
                        f"{route_function_id}:BackgroundTasks.add_task:no_target"
                    )

                target = _resolve_symbol_reference(module, call.args[0])
                if target is None or _function_node(modules, target) is None:
                    raise RuntimeError(
                        "MEI_REACHABILITY_UNRESOLVED_BACKGROUND_REGISTRATION:"
                        f"{route_function_id}:BackgroundTasks.add_task:unresolved_target"
                    )

                registration_id = (
                    f"{route_function_id}:BackgroundTasks.add_task"
                )
                registrations.setdefault(target, set()).add(registration_id)

    return [
        {
            "function_id": function_id,
            "present": True,
            "registration_ids": sorted(registration_ids),
            "is_root": True,
            "reachability": "REGISTERED_BACKGROUND_ROOT",
        }
        for function_id, registration_ids in sorted(registrations.items())
    ]


def _rq_background_root_inventory(
    modules: dict[str, ModuleInfo],
    *,
    mounted: dict[str, tuple[str, str]],
) -> list[dict]:
    """Discover proven RQ Queue.enqueue roots reachable from mounted routes."""

    def scoped_nodes(
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ast.AST]:
        nodes: list[ast.AST] = []
        stack: list[ast.AST] = list(reversed(function_node.body))
        while stack:
            item = stack.pop()
            if isinstance(
                item,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                continue
            nodes.append(item)
            stack.extend(reversed(list(ast.iter_child_nodes(item))))
        return nodes

    def local_imports(
        function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> dict[str, str]:
        imports: dict[str, str] = {}
        for item in scoped_nodes(function_node):
            if not (
                isinstance(item, ast.ImportFrom)
                and item.level == 0
                and item.module
            ):
                continue
            for alias in item.names:
                local_name = alias.asname or alias.name
                target = f"{item.module}.{alias.name}"
                previous = imports.get(local_name)
                if previous is not None and previous != target:
                    raise RuntimeError(
                        "MEI_REACHABILITY_UNRESOLVED_RQ_IMPORT_REBINDING:"
                        f"{local_name}:{previous}:{target}"
                    )
                imports[local_name] = target
        return imports

    def proven_rq_queue_symbol(target: str) -> bool:
        if target != "app.queue.redis_queue.analysis_queue":
            return False

        queue_module = modules.get("app.queue.redis_queue")
        if queue_module is None:
            return False
        if queue_module.imports.get("Queue") != "rq.Queue":
            return False

        assignments = [
            statement
            for statement in queue_module.tree.body
            if (
                isinstance(statement, ast.Assign)
                and len(statement.targets) == 1
                and isinstance(statement.targets[0], ast.Name)
                and statement.targets[0].id == "analysis_queue"
            )
        ]
        if len(assignments) != 1:
            return False

        value = assignments[0].value
        if not isinstance(value, ast.Call):
            return False

        call_name = _call_name(value)
        if call_name is None or _resolve_name(queue_module, call_name) != "rq.Queue":
            return False

        if len(value.args) != 1 or _literal_string(value.args[0]) != "analysis":
            return False
        if any(keyword.arg is None for keyword in value.keywords):
            return False

        keywords = {keyword.arg: keyword.value for keyword in value.keywords}
        if set(keywords) != {"connection"}:
            return False
        return (
            isinstance(keywords["connection"], ast.Name)
            and keywords["connection"].id == "redis_conn"
        )

    registrations: dict[str, set[str]] = {}

    for module_name, (router_object, _) in sorted(mounted.items()):
        module = modules.get(module_name)
        if module is None:
            raise RuntimeError(
                f"MEI_REACHABILITY_ROUTER_MODULE_MISSING:{module_name}"
            )

        for local_name, route_node in sorted(module.functions.items()):
            if "." in local_name:
                continue
            if _route_decorator(route_node, router_object=router_object) is None:
                continue

            route_function_id = f"{module_name}.{local_name}"

            helper_ids = [
                callee
                for callee in _direct_callees(module, route_node)
                if (
                    callee.startswith(module_name + ".")
                    and _function_node(modules, callee) is not None
                )
            ]

            for helper_id in sorted(set(helper_ids)):
                found = _function_node(modules, helper_id)
                if found is None:
                    continue
                helper_module, helper_node = found
                imports = local_imports(helper_node)

                for call in (
                    item
                    for item in scoped_nodes(helper_node)
                    if isinstance(item, ast.Call)
                ):
                    if not (
                        isinstance(call.func, ast.Attribute)
                        and call.func.attr == "enqueue"
                        and isinstance(call.func.value, ast.Name)
                    ):
                        continue

                    queue_local_name = call.func.value.id
                    queue_target = imports.get(queue_local_name)
                    if queue_target is None:
                        continue
                    if not queue_target.startswith("app.queue.redis_queue."):
                        continue
                    if not proven_rq_queue_symbol(queue_target):
                        raise RuntimeError(
                            "MEI_REACHABILITY_UNRESOLVED_RQ_REGISTRATION:"
                            f"{helper_id}:{queue_local_name}:unproven_queue"
                        )

                    if not call.args:
                        raise RuntimeError(
                            "MEI_REACHABILITY_UNRESOLVED_RQ_REGISTRATION:"
                            f"{helper_id}:RQ.Queue.enqueue:no_target"
                        )

                    target = _resolve_symbol_reference(helper_module, call.args[0])
                    if target is None or _function_node(modules, target) is None:
                        raise RuntimeError(
                            "MEI_REACHABILITY_UNRESOLVED_RQ_REGISTRATION:"
                            f"{helper_id}:RQ.Queue.enqueue:unresolved_target"
                        )

                    registration_id = (
                        f"{route_function_id}->{helper_id}:RQ.Queue.enqueue"
                    )
                    registrations.setdefault(target, set()).add(registration_id)

    return [
        {
            "function_id": function_id,
            "present": True,
            "registration_ids": sorted(registration_ids),
            "is_root": True,
            "reachability": "REGISTERED_BACKGROUND_ROOT",
        }
        for function_id, registration_ids in sorted(registrations.items())
    ]


def _alternative_producer_inventory(
    modules: dict[str, ModuleInfo],
    *,
    canonical_producer_id: str,
) -> dict[str, list[str]]:
    """Inventory wrappers that provably return a canonical producer value.

    V1 accepts only one simple-name assignment from the canonical producer and a
    later return expression that statically contains that same name. Mere calls
    are not enough: callers that consume the value without returning it are not
    promoted to alternative producers. Nested function/class scopes are not
    traversed as part of the outer candidate.
    """

    def scope_nodes(roots: list[ast.AST]) -> list[ast.AST]:
        nodes: list[ast.AST] = []
        stack = list(reversed(roots))
        while stack:
            item = stack.pop()
            nodes.append(item)
            if isinstance(
                item,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                continue
            children = list(ast.iter_child_nodes(item))
            stack.extend(reversed(children))
        return nodes

    def branch_path(
        roots: list[ast.AST],
        target: ast.AST,
    ) -> tuple[tuple[int, str], ...]:
        found: tuple[tuple[int, str], ...] | None = None

        def visit(item: ast.AST, path: tuple[tuple[int, str], ...]) -> None:
            nonlocal found
            if found is not None:
                return
            if item is target:
                found = path
                return
            if isinstance(
                item,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            ):
                return
            if isinstance(item, ast.If):
                visit(item.test, path)
                for child in item.body:
                    visit(child, path + ((id(item), "body"),))
                for child in item.orelse:
                    visit(child, path + ((id(item), "orelse"),))
                return
            for child in ast.iter_child_nodes(item):
                visit(child, path)

        for root in roots:
            visit(root, ())
            if found is not None:
                break
        return found or ()

    def same_executable_branch(
        roots: list[ast.AST],
        left: ast.AST,
        right: ast.AST,
    ) -> bool:
        left_path = dict(branch_path(roots, left))
        right_path = dict(branch_path(roots, right))
        return not any(
            if_id in right_path and right_path[if_id] != branch
            for if_id, branch in left_path.items()
        )

    inventory: dict[str, list[str]] = {}

    for module_name in sorted(modules):
        module = modules[module_name]
        for local_name, function_node in sorted(module.functions.items()):
            function_id = f"{module.name}.{local_name}"
            if function_id == "app.auth_router.register_user":
                auth_inventory = _auth_register_no_canonical_mei_inventory(
                    modules,
                    route_function_id=function_id,
                )
                paths.append({
                    "entrypoint": entrypoint,
                    "function_id": function_id,
                    "blocked_before_producer": False,
                    "blocker_code": None,
                    **auth_inventory,
                })
                continue
            if function_id == canonical_producer_id:
                continue

            function_roots = list(function_node.body)
            function_scope = scope_nodes(function_roots)
            assignments: list[ast.Assign] = []
            for item in function_scope:
                if not (
                    isinstance(item, ast.Assign)
                    and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                    and isinstance(item.value, ast.Call)
                ):
                    continue
                call_name = _call_name(item.value)
                if (
                    call_name is not None
                    and _resolve_name(module, call_name) == canonical_producer_id
                ):
                    assignments.append(item)

            if len(assignments) != 1:
                continue

            assignment = assignments[0]
            value_name = assignment.targets[0].id
            returns = [
                item
                for item in function_scope
                if isinstance(item, ast.Return)
                and item.value is not None
                and any(
                    isinstance(child, ast.Name) and child.id == value_name
                    for child in scope_nodes([item.value])
                )
                and item.lineno > assignment.lineno
            ]
            if len(returns) != 1:
                continue

            return_node = returns[0]
            rebound_assignments = [
                item
                for item in function_scope
                if isinstance(item, ast.Assign)
                and item is not assignment
                and assignment.lineno < item.lineno < return_node.lineno
                and any(value_name in _bound_names(target) for target in item.targets)
                and same_executable_branch(function_roots, assignment, item)
            ]
            if rebound_assignments:
                continue

            inventory[function_id] = [canonical_producer_id]

    return inventory


def _direct_returned_alternative_producer(
    module: ModuleInfo,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    alternative_producers: dict[str, list[str]],
    *,
    function_id: str,
) -> str | None:
    """Resolve one directly returned proven alternative producer.

    V1 accepts only top-level ``return alternative_producer(...)``. Calls that
    are merely consumed or assigned are not publication proof. Multiple direct
    alternative returns are ambiguous and fail closed.
    """
    matches: list[str] = []
    for statement in node.body:
        if not (
            isinstance(statement, ast.Return)
            and isinstance(statement.value, ast.Call)
        ):
            continue
        call_name = _call_name(statement.value)
        if call_name is None:
            continue
        resolved = _resolve_name(module, call_name)
        if resolved in alternative_producers:
            matches.append(resolved)

    unique = sorted(set(matches))
    if len(unique) > 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ALTERNATIVE_PUBLICATION:"
            f"{function_id}:{','.join(unique)}"
        )
    return unique[0] if unique else None


def _mei_specific_statements(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    specific: list[ast.stmt] = []
    for statement in node.body:
        if isinstance(statement, ast.If) and _condition_mentions_mei(statement.test):
            if isinstance(statement.test, ast.BoolOp):
                return list(node.body)
            if (
                isinstance(statement.test, ast.UnaryOp)
                and isinstance(statement.test.op, ast.Not)
            ):
                return list(node.body)
            if (
                isinstance(statement.test, ast.Compare)
                and len(statement.test.ops) == 1
                and isinstance(statement.test.ops[0], ast.NotEq)
            ):
                return list(node.body)
            specific.extend(statement.body)
    return specific or list(node.body)


@lru_cache(maxsize=None)
def _app_class_defines_method(class_id: str, method_name: str) -> bool:
    """Prove one direct method exists on one statically resolved app class."""
    if not class_id.startswith("app.") or "." not in class_id or "." in method_name:
        return False

    module_name, class_name = class_id.rsplit(".", 1)
    module_path = ROOT.joinpath(*module_name.split("."))
    candidates = (
        module_path.with_suffix(".py"),
        module_path / "__init__.py",
    )
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return False

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError(
            f"MEI_REACHABILITY_CLASS_SCAN_FAILED:{class_id}:{type(exc).__name__}:{exc}"
        ) from exc

    definitions = [
        item
        for item in tree.body
        if isinstance(item, ast.ClassDef) and item.name == class_name
    ]
    if len(definitions) > 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_CLASS_INVENTORY:{class_id}:duplicate_definition"
        )
    if not definitions:
        return False

    return any(
        isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
        and member.name == method_name
        for member in definitions[0].body
    )


def _direct_app_base_method(
    module: ModuleInfo,
    *,
    class_name: str,
    method_name: str,
) -> str | None:
    """Resolve a method on one direct statically known app base class."""
    definitions = [
        item
        for item in module.tree.body
        if isinstance(item, ast.ClassDef) and item.name == class_name
    ]
    if len(definitions) != 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_INHERITANCE:{module.name}.{class_name}:owner"
        )

    class_node = definitions[0]
    resolved_bases: list[str] = []
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            base_name = base.id
        elif isinstance(base, ast.Attribute):
            base_name = ast.unparse(base)
        else:
            continue

        base_id = _resolve_name(module, base_name)
        if base_id is None and isinstance(base, ast.Name):
            if any(
                isinstance(item, ast.ClassDef) and item.name == base.id
                for item in module.tree.body
            ):
                base_id = f"{module.name}.{base.id}"
        if base_id is not None and base_id.startswith("app."):
            resolved_bases.append(base_id)

    if not resolved_bases:
        return None
    if len(class_node.bases) != 1 or len(resolved_bases) != 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_INHERITANCE:"
            f"{module.name}.{class_name}:{method_name}:ambiguous_bases"
        )

    base_id = resolved_bases[0]
    if _app_class_defines_method(base_id, method_name):
        return f"{base_id}.{method_name}"
    return None



@lru_cache(maxsize=None)
def _static_returned_fastapi_dependency_callees(factory_id: str, _root_key: str) -> tuple[str, ...]:
    """Resolve a simple app dependency factory using the qualified app inventory."""
    if not factory_id.startswith("app.") or "." not in factory_id:
        return ()

    modules = _parse_app()
    found = _function_node(modules, factory_id)
    if found is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_FASTAPI_DEPENDENCY_FACTORY:{factory_id}:function"
        )

    factory_module, factory = found
    nested = {
        statement.name: statement
        for statement in factory.body
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    returns: list[ast.Return] = []
    stack: list[ast.AST] = list(reversed(factory.body))
    while stack:
        item = stack.pop()
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(item, ast.Return):
            returns.append(item)
            continue
        stack.extend(reversed(list(ast.iter_child_nodes(item))))

    returned_names: list[str] = []
    for return_node in returns:
        if not (
            isinstance(return_node.value, ast.Name)
            and return_node.value.id in nested
        ):
            raise RuntimeError(
                f"MEI_REACHABILITY_UNRESOLVED_FASTAPI_DEPENDENCY_FACTORY:"
                f"{factory_id}:returned_dependency"
            )
        returned_names.append(return_node.value.id)

    if not returned_names or len(set(returned_names)) != 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_FASTAPI_DEPENDENCY_FACTORY:"
            f"{factory_id}:returned_dependency"
        )

    returned_name = returned_names[0]
    returned_node = nested[returned_name]
    qualified_module = ModuleInfo(
        factory_module.name,
        factory_module.path,
        factory_module.tree,
        factory_module.imports,
        {**factory_module.functions, **nested},
    )
    return tuple(_direct_callees(qualified_module, returned_node))


def _fastapi_dependency_callees(
    module: ModuleInfo,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    """Return app callables executed through FastAPI Depends defaults."""
    defaults = [
        *node.args.defaults,
        *(default for default in node.args.kw_defaults if default is not None),
    ]
    callees: list[str] = []

    for default in defaults:
        for item in ast.walk(default):
            if not isinstance(item, ast.Call):
                continue
            call_name = _call_name(item)
            if call_name is None or _resolve_name(module, call_name) != "fastapi.Depends":
                continue
            if len(item.args) != 1:
                continue

            dependency = item.args[0]
            if isinstance(dependency, ast.Name):
                dependency_name = dependency.id
                resolved = _resolve_name(module, dependency_name)
                if resolved is not None and resolved.startswith("app."):
                    callees.append(resolved)
                continue

            if isinstance(dependency, ast.Attribute):
                dependency_name = ast.unparse(dependency)
                resolved = _resolve_name(module, dependency_name)
                if resolved is not None and resolved.startswith("app."):
                    callees.append(resolved)
                continue

            if isinstance(dependency, ast.Call):
                factory_name = _call_name(dependency)
                if factory_name is None:
                    continue
                factory_id = _resolve_name(module, factory_name)
                if factory_id is None or not factory_id.startswith("app."):
                    continue
                callees.append(factory_id)
                callees.extend(
                    _static_returned_fastapi_dependency_callees(
                        factory_id, str(ROOT.resolve())
                    )
                )

    return sorted(set(callees))


def _direct_callees(
    module: ModuleInfo,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    callees: list[str] = _fastapi_dependency_callees(module, node)
    owner_class: str | None = None
    for local_name, function_node in module.functions.items():
        if function_node is node and "." in local_name:
            owner_class = local_name.rsplit(".", 1)[0]
            break

    statements = _mei_specific_statements(node)

    local_imports: dict[str, str] = {}
    import_stack: list[ast.AST] = list(reversed(node.body))
    while import_stack:
        item = import_stack.pop()
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(item, ast.ImportFrom):
            if item.level != 0:
                raise RuntimeError(
                    f"MEI_REACHABILITY_UNRESOLVED_LOCAL_RELATIVE_IMPORT:"
                    f"{module.name}.{node.name}:{item.lineno}"
                )
            if item.module:
                for alias in item.names:
                    target = f"{item.module}.{alias.name}"
                    if not target.startswith("app."):
                        continue
                    local_name = alias.asname or alias.name
                    previous = local_imports.get(local_name)
                    if previous is not None and previous != target:
                        raise RuntimeError(
                            f"MEI_REACHABILITY_UNRESOLVED_LOCAL_IMPORT:"
                            f"{module.name}.{node.name}:{local_name}:ambiguous"
                        )
                    local_imports[local_name] = target
            continue
        if isinstance(item, ast.Import):
            for alias in item.names:
                if alias.name != "app" and not alias.name.startswith("app."):
                    continue
                if alias.asname:
                    local_name = alias.asname
                    target = alias.name
                else:
                    local_name = alias.name.split(".", 1)[0]
                    target = local_name
                previous = local_imports.get(local_name)
                if previous is not None and previous != target:
                    raise RuntimeError(
                        f"MEI_REACHABILITY_UNRESOLVED_LOCAL_IMPORT:"
                        f"{module.name}.{node.name}:{local_name}:ambiguous"
                    )
                local_imports[local_name] = target
            continue
        import_stack.extend(reversed(list(ast.iter_child_nodes(item))))

    resolution_module = ModuleInfo(
        module.name,
        module.path,
        module.tree,
        {**module.imports, **local_imports},
        module.functions,
    )

    scoped_nodes: list[ast.AST] = []
    scope_stack: list[ast.AST] = list(reversed(statements))
    while scope_stack:
        item = scope_stack.pop()
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        scoped_nodes.append(item)
        scope_stack.extend(reversed(list(ast.iter_child_nodes(item))))

    binding_counts: dict[str, int] = {}
    for item in scoped_nodes:
        if isinstance(item, ast.ExceptHandler) and item.name:
            binding_counts[item.name] = binding_counts.get(item.name, 0) + 1
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            binding_counts[item.id] = binding_counts.get(item.id, 0) + 1

    parameter_names = {
        arg.arg
        for arg in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        )
    }
    if node.args.vararg is not None:
        parameter_names.add(node.args.vararg.arg)
    if node.args.kwarg is not None:
        parameter_names.add(node.args.kwarg.arg)

    rebound_local_imports = sorted(
        name
        for name in local_imports
        if binding_counts.get(name, 0) or name in parameter_names
    )
    if rebound_local_imports:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_LOCAL_IMPORT_REBINDING:"
            f"{module.name}.{node.name}:{','.join(rebound_local_imports)}"
        )

    local_instances: dict[str, str] = {}
    for item in scoped_nodes:
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Call)
        ):
            continue
        constructor_name = _call_name(item.value)
        if constructor_name is None:
            continue
        constructor_id = _resolve_name(resolution_module, constructor_name)
        local_name = item.targets[0].id
        if (
            constructor_id is not None
            and constructor_id.startswith("app.")
            and binding_counts.get(local_name) == 1
        ):
            local_instances[local_name] = constructor_id

    for call in (item for item in scoped_nodes if isinstance(item, ast.Call)):
        name = _call_name(call)
        resolved: str | None = None

        if (
            name is None
            and isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Call)
        ):
            constructor_call = call.func.value
            constructor_name = _call_name(constructor_call)
            if constructor_name is not None:
                constructor_id = _resolve_name(resolution_module, constructor_name)
                method_name = call.func.attr
                if (
                    constructor_id is not None
                    and constructor_id.startswith("app.")
                    and _app_class_defines_method(constructor_id, method_name)
                ):
                    resolved = f"{constructor_id}.{method_name}"

        if name is None and resolved is None:
            continue
        if resolved is None:
            resolved = _resolve_name(resolution_module, name)
        if resolved is None and owner_class is not None and name is not None and name.startswith("self."):
            method_name = name.split(".", 1)[1]
            local_target = f"{owner_class}.{method_name}"
            if local_target in module.functions:
                resolved = f"{module.name}.{local_target}"
            else:
                resolved = _direct_app_base_method(
                    module,
                    class_name=owner_class,
                    method_name=method_name,
                )
        if resolved is None and name is not None and "." in name:
            local_name, method_name = name.split(".", 1)
            class_id = local_instances.get(local_name)
            if class_id is not None and _app_class_defines_method(class_id, method_name):
                resolved = f"{class_id}.{method_name}"

        if resolved is None:
            continue

        if resolved.startswith("app.") and _app_class_defines_method(resolved, "__init__"):
            callees.append(f"{resolved}.__init__")
        else:
            callees.append(resolved)

    return sorted(set(callees))



def _is_plain_app_class_constructor(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Return True only for a physically simple app class constructor."""
    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if not target_id.startswith(prefix):
            continue

        class_name = target_id[len(prefix):]
        if "." in class_name:
            return False

        definitions = [
            item
            for item in modules[module_name].tree.body
            if isinstance(item, ast.ClassDef) and item.name == class_name
        ]
        if len(definitions) != 1:
            return False

        class_node = definitions[0]
        if class_node.bases or class_node.keywords or class_node.decorator_list:
            return False

        if any(
            isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name in {"__init__", "__new__"}
            for member in class_node.body
        ):
            return False

        return True

    return False


def _is_plain_builtin_exception_constructor(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Return True only for a direct ``Exception`` subclass with no custom constructor."""
    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if not target_id.startswith(prefix):
            continue

        class_name = target_id[len(prefix):]
        if "." in class_name:
            return False

        definitions = [
            item
            for item in modules[module_name].tree.body
            if isinstance(item, ast.ClassDef) and item.name == class_name
        ]
        if len(definitions) != 1:
            return False

        class_node = definitions[0]
        if (
            len(class_node.bases) != 1
            or not isinstance(class_node.bases[0], ast.Name)
            or class_node.bases[0].id not in {"Exception", "ValueError"}
            or class_node.keywords
            or class_node.decorator_list
        ):
            return False

        return not any(
            isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
            and member.name in {"__init__", "__new__"}
            for member in class_node.body
        )

    return False


def _is_inert_declarative_model_constructor(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Qualify only the proven local SQLAlchemy declarative-model topology."""
    prefix = "app.models."
    if not target_id.startswith(prefix):
        return False

    class_name = target_id[len(prefix):]
    if not class_name or "." in class_name:
        return False

    models_module = modules.get("app.models")
    database_module = modules.get("app.database")
    if models_module is None or database_module is None:
        return False

    if models_module.imports.get("Base") != "app.database.Base":
        return False
    if database_module.imports.get("declarative_base") != "sqlalchemy.orm.declarative_base":
        return False

    base_assignments = [
        statement
        for statement in database_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "Base"
        )
    ]
    if len(base_assignments) != 1:
        return False

    base_value = base_assignments[0].value
    if not isinstance(base_value, ast.Call):
        return False
    base_call_name = _call_name(base_value)
    if (
        base_call_name is None
        or _resolve_name(database_module, base_call_name)
        != "sqlalchemy.orm.declarative_base"
        or base_value.args
        or base_value.keywords
    ):
        return False

    definitions = [
        item
        for item in models_module.tree.body
        if isinstance(item, ast.ClassDef) and item.name == class_name
    ]
    if len(definitions) != 1:
        return False

    class_node = definitions[0]
    if (
        len(class_node.bases) != 1
        or not isinstance(class_node.bases[0], ast.Name)
        or class_node.bases[0].id != "Base"
        or class_node.keywords
        or class_node.decorator_list
    ):
        return False

    for member in class_node.body:
        if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if member.name in {"__init__", "__new__"} or member.decorator_list:
            return False

    validator_maps: list[ast.Dict] = []
    for statement in models_module.tree.body:
        value = None
        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_ADR020_INSERT_VALIDATORS"
                for target in statement.targets
            )
        ):
            value = statement.value
        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "_ADR020_INSERT_VALIDATORS"
        ):
            value = statement.value

        if isinstance(value, ast.Dict):
            validator_maps.append(value)

    if len(validator_maps) != 1:
        return False

    validator_keys = {
        key.id
        for key in validator_maps[0].keys
        if isinstance(key, ast.Name)
    }
    if class_name in validator_keys:
        return False

    for module in modules.values():
        for call in [
            item
            for item in ast.walk(module.tree)
            if isinstance(item, ast.Call)
        ]:
            call_name = _call_name(call)
            if call_name is None:
                continue
            resolved = _resolve_name(module, call_name)
            if resolved not in {
                "sqlalchemy.event.listen",
                "sqlalchemy.event.listens_for",
            }:
                continue
            if not call.args:
                return False

            target = call.args[0]
            if isinstance(target, ast.Name):
                if target.id in {class_name, "Base"}:
                    return False
                if (
                    module.name == "app.models"
                    and target.id == "_adr020_append_only_model"
                ):
                    continue

            return False

    return True


def _is_sqlalchemy_column_descriptor_helper(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Qualify only proven SQLAlchemy Column ``desc``/``is_`` helpers."""
    prefix = "app.models."
    if not target_id.startswith(prefix):
        return False

    parts = target_id[len(prefix):].split(".")
    if len(parts) != 3:
        return False

    class_name, attribute_name, method_name = parts
    if method_name not in {"asc", "desc", "in_", "is_", "isnot"}:
        return False

    models_module = modules.get("app.models")
    if models_module is None:
        return False
    if models_module.imports.get("Column") != "sqlalchemy.Column":
        return False

    definitions = [
        item
        for item in models_module.tree.body
        if isinstance(item, ast.ClassDef) and item.name == class_name
    ]
    if len(definitions) != 1:
        return False

    assignments = [
        member
        for member in definitions[0].body
        if (
            isinstance(member, ast.Assign)
            and len(member.targets) == 1
            and isinstance(member.targets[0], ast.Name)
            and member.targets[0].id == attribute_name
        )
    ]
    if len(assignments) != 1:
        return False

    value = assignments[0].value
    if not isinstance(value, ast.Call):
        return False

    call_name = _call_name(value)
    if call_name is None:
        return False

    return _resolve_name(models_module, call_name) == "sqlalchemy.Column"



def _is_inert_fastapi_security_dependency_object(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Qualify only statically constructed FastAPI security dependency objects."""
    split = _split_imported_symbol(modules, target_id)
    if split is None:
        return False

    module, symbol = split
    if "." in symbol:
        return False

    assignments = [
        statement
        for statement in module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == symbol
        )
    ]
    if len(assignments) != 1:
        return False

    value = assignments[0].value
    if not isinstance(value, ast.Call):
        return False

    call_name = _call_name(value)
    if call_name is None:
        return False

    if _resolve_name(module, call_name) != "fastapi.security.OAuth2PasswordBearer":
        return False

    if value.args or any(keyword.arg is None for keyword in value.keywords):
        return False

    token_url = [
        keyword.value
        for keyword in value.keywords
        if keyword.arg == "tokenUrl"
    ]
    if len(token_url) != 1:
        return False
    if not (
        isinstance(token_url[0], ast.Constant)
        and isinstance(token_url[0].value, str)
        and token_url[0].value
    ):
        return False

    return True

def _is_inert_sqlalchemy_sessionmaker_factory(
    modules: dict[str, ModuleInfo],
    target_id: str,
) -> bool:
    """Qualify only the proven inert app.database.SessionLocal factory."""
    if target_id != "app.database.SessionLocal":
        return False

    database_module = modules.get("app.database")
    if database_module is None:
        return False
    if (
        database_module.imports.get("sessionmaker")
        != "sqlalchemy.orm.sessionmaker"
    ):
        return False
    if database_module.imports.get("create_engine") != "sqlalchemy.create_engine":
        return False

    session_assignments = [
        statement
        for statement in database_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "SessionLocal"
        )
    ]
    if len(session_assignments) != 1:
        return False

    session_value = session_assignments[0].value
    if not isinstance(session_value, ast.Call):
        return False

    session_call_name = _call_name(session_value)
    if session_call_name is None:
        return False
    if (
        _resolve_name(database_module, session_call_name)
        != "sqlalchemy.orm.sessionmaker"
    ):
        return False
    if session_value.args:
        return False
    if any(keyword.arg is None for keyword in session_value.keywords):
        return False

    session_keywords = {
        keyword.arg: keyword.value
        for keyword in session_value.keywords
    }
    if set(session_keywords) != {"autocommit", "autoflush", "bind"}:
        return False
    if not (
        isinstance(session_keywords["autocommit"], ast.Constant)
        and session_keywords["autocommit"].value is False
    ):
        return False
    if not (
        isinstance(session_keywords["autoflush"], ast.Constant)
        and session_keywords["autoflush"].value is False
    ):
        return False
    if not (
        isinstance(session_keywords["bind"], ast.Name)
        and session_keywords["bind"].id == "engine"
    ):
        return False

    engine_assignments = [
        statement
        for statement in database_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "engine"
        )
    ]
    if len(engine_assignments) != 1:
        return False

    engine_value = engine_assignments[0].value
    if not isinstance(engine_value, ast.Call):
        return False
    engine_call_name = _call_name(engine_value)
    if engine_call_name is None:
        return False
    if _resolve_name(database_module, engine_call_name) != "sqlalchemy.create_engine":
        return False

    sqlalchemy_events: list[tuple[str, ast.Call]] = []
    for module in modules.values():
        for call in ast.walk(module.tree):
            if not isinstance(call, ast.Call):
                continue
            call_name = _call_name(call)
            if call_name is None:
                continue
            resolved = _resolve_name(module, call_name)
            if resolved in {
                "sqlalchemy.event.listen",
                "sqlalchemy.event.listens_for",
            }:
                sqlalchemy_events.append((module.name, call))

    if len(sqlalchemy_events) != 3:
        return False

    event_names: set[str] = set()
    for module_name, call in sqlalchemy_events:
        if module_name != "app.models":
            return False
        call_name = _call_name(call)
        if call_name is None:
            return False
        if _resolve_name(modules[module_name], call_name) != "sqlalchemy.event.listen":
            return False
        if len(call.args) < 2:
            return False
        if not (
            isinstance(call.args[0], ast.Name)
            and call.args[0].id == "_adr020_append_only_model"
        ):
            return False
        if not (
            isinstance(call.args[1], ast.Constant)
            and isinstance(call.args[1].value, str)
        ):
            return False
        event_names.add(call.args[1].value)

    if event_names != {"before_insert", "before_update", "before_delete"}:
        return False

    return True

def _reachable_orm_persistence_sinks(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    """Return ORM persistence sinks reachable through the resolved app call graph."""
    pending = [function_id]
    seen: set[str] = set()
    sink_operations: dict[str, list[str]] = {}
    unresolved_app_callees: set[str] = set()

    def inert_app_target(target: str) -> bool:
        return (
            _is_plain_app_class_constructor(modules, target)
            or _is_plain_builtin_exception_constructor(modules, target)
            or _is_inert_declarative_model_constructor(modules, target)
            or _is_sqlalchemy_column_descriptor_helper(modules, target)
            or _is_inert_sqlalchemy_sessionmaker_factory(modules, target)
        )

    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)

        found = _function_node(modules, current)
        if found is None:
            if inert_app_target(current):
                continue
            if current.startswith("app."):
                unresolved_app_callees.add(current)
            continue

        module, node = found
        operations = _orm_persistence_operations(
            modules,
            function_id=current,
        )
        if operations:
            sink_operations[current] = operations

        for callee in _direct_callees(module, node):
            if not callee.startswith("app."):
                continue
            if _function_node(modules, callee) is None:
                if inert_app_target(callee):
                    continue
                unresolved_app_callees.add(callee)
                continue
            if callee not in seen:
                pending.append(callee)

    unresolved = sorted(unresolved_app_callees)
    return {
        "sink_operations": {
            sink_id: sink_operations[sink_id]
            for sink_id in sorted(sink_operations)
        },
        "unresolved_app_callees": unresolved,
        "scan_complete": not unresolved,
    }


def _insights_engine_registry_dispatch_inventory(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    # Qualify the central immutable ENGINES dispatcher without executing app code.
    if function_id != "app.services.insights_engine.executar_engines":
        return {"producer_ids": [], "qualified_accessors": []}

    found = _function_node(modules, function_id)
    registry = modules.get("app.services.engine_registry")
    if found is None or registry is None:
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:inventory")

    module, node = found
    if module.imports.get("ENGINES") != "app.services.engine_registry.ENGINES":
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:ENGINES_import")

    assignments = _module_assignments(registry)
    engines_raw = assignments.get("_ENGINES_RAW")
    engines_view = assignments.get("ENGINES")
    if not isinstance(engines_raw, ast.Dict) or not isinstance(engines_view, ast.Call):
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:registry_shape")

    view_name = _call_name(engines_view)
    if (
        view_name is None
        or _resolve_name(registry, view_name) != "types.MappingProxyType"
        or len(engines_view.args) != 1
        or not isinstance(engines_view.args[0], ast.Name)
        or engines_view.args[0].id != "_ENGINES_RAW"
        or engines_view.keywords
    ):
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:immutable_view")

    mei_class_node = _dict_value_for_string_key(modules, registry, engines_raw, "mei_tax")
    if mei_class_node is None:
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:mei_entry")

    mei_class = _resolve_symbol_reference(registry, mei_class_node)
    if mei_class != "app.services.tax_engines.mei_tax_engine.MEITaxEngine":
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:mei_class:{mei_class}"
        )

    source = ast.unparse(node)
    required = (
        "for nome, engine_class in ENGINES.items():",
        "engine = engine_class()",
        "elif nome == ANALYSIS_TYPE_MEI_TAX:",
        "resultados[nome] = engine.execute(contexto_mei)",
    )
    if any(fragment not in source for fragment in required):
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:shape")

    engine_id = _resolve_mei_registry_engine(modules)
    if engine_id != MEI_ENGINE_EXECUTE_ID:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:engine:{engine_id}"
        )
    engine_found = _function_node(modules, engine_id)
    if engine_found is None:
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:engine_function")
    engine_module, engine_node = engine_found
    if PRODUCER_ID not in _direct_callees(engine_module, engine_node):
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_ENGINE_DISPATCH:producer_edge")

    return {
        "producer_ids": [PRODUCER_ID],
        "qualified_accessors": [
            "app.services.engine_registry.ENGINES.items",
        ],
    }


def _insights_engine_registry_metadata_inventory(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    """Qualify the separate ENGINES.get metadata read without hiding execution."""
    target_function = (
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
    )
    if function_id != target_function:
        return {"qualified_accessors": []}

    found = _function_node(modules, function_id)
    if found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ENGINE_METADATA:inventory"
        )

    module, node = found
    if module.imports.get("ENGINES") != "app.services.engine_registry.ENGINES":
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ENGINE_METADATA:ENGINES_import"
        )

    assignments = [
        item
        for item in ast.walk(node)
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "engine_class"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "ENGINES.get"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "nome"
            and not item.value.keywords
        )
    ]
    if len(assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ENGINE_METADATA:get_shape"
        )

    parents = {
        child: parent
        for parent in ast.walk(node)
        for child in ast.iter_child_nodes(parent)
    }
    for name_node in ast.walk(node):
        if not (
            isinstance(name_node, ast.Name)
            and name_node.id == "engine_class"
            and isinstance(name_node.ctx, ast.Load)
        ):
            continue

        parent = parents.get(name_node)
        safe_compare = (
            isinstance(parent, ast.Compare)
            and parent.left is name_node
            and len(parent.ops) == 1
            and isinstance(parent.ops[0], (ast.Is, ast.IsNot))
            and len(parent.comparators) == 1
            and isinstance(parent.comparators[0], ast.Constant)
            and parent.comparators[0].value is None
        )
        safe_getattr = (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "getattr"
            and len(parent.args) == 3
            and parent.args[0] is name_node
            and isinstance(parent.args[1], ast.Constant)
            and parent.args[1].value == "versao"
            and isinstance(parent.args[2], ast.Constant)
            and parent.args[2].value is None
            and not parent.keywords
        )
        if not (safe_compare or safe_getattr):
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_ENGINE_METADATA:unsafe_use"
            )

    return {
        "qualified_accessors": [
            "app.services.engine_registry.ENGINES.get",
        ],
    }


def _insights_engine_mei_component_inventory(
    modules: dict[str, ModuleInfo],
) -> dict:
    """Prove the reusable canonical-MEI lineage inside InsightEngine itself."""
    engine_method_id = (
        "app.services.insights_engine.InsightEngine.gerar_insights_empresa"
    )
    dispatcher_id = "app.services.insights_engine.executar_engines"
    flags_helper_id = (
        "app.services.context_flags_service.anexar_flags_nos_resultados_engines"
    )

    method_found = _function_node(modules, engine_method_id)
    init_found = _function_node(
        modules,
        "app.services.insights_engine.InsightEngine.__init__",
    )
    flags_found = _function_node(modules, flags_helper_id)

    if method_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_COMPONENT:engine_method"
        )
    if init_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_COMPONENT:engine_init"
        )
    if flags_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_COMPONENT:flags_helper"
        )

    method_module, method_node = method_found
    _, init_node = init_found
    _, flags_node = flags_found

    # Prove self.db is exactly the db constructor parameter, without making
    # self.<anything> a generic ORM-session rule.
    init_args = [
        arg.arg
        for arg in (
            *init_node.args.posonlyargs,
            *init_node.args.args,
            *init_node.args.kwonlyargs,
        )
    ]
    if init_args != ["self", "db"]:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:init_signature"
        )

    db_bindings = [
        item
        for item in ast.walk(init_node)
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Attribute)
            and isinstance(item.targets[0].value, ast.Name)
            and item.targets[0].value.id == "self"
            and item.targets[0].attr == "db"
            and isinstance(item.value, ast.Name)
            and item.value.id == "db"
        )
    ]
    if len(db_bindings) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:self_db_binding"
        )

    # Reuse the already-qualified immutable ENGINES dispatcher proof.
    dispatch = _insights_engine_registry_dispatch_inventory(
        modules,
        function_id=dispatcher_id,
    )
    if dispatch["producer_ids"] != [PRODUCER_ID]:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:dispatcher_producer"
        )

    # The method must receive the dispatcher mapping in resultados_engines.
    dispatcher_assignments = [
        item
        for item in ast.walk(method_node)
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "resultados_engines"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) is not None
            and _resolve_name(
                method_module,
                _call_name(item.value),
            )
            == dispatcher_id
        )
    ]
    if len(dispatcher_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:dispatcher_assignment"
        )
    dispatcher_assignment = dispatcher_assignments[0]

    # Prove the context-flags helper structurally. Quoting/style emitted by
    # ast.unparse() is not evidence; the AST topology itself is the contract.
    flags_args = [
        arg.arg
        for arg in (
            *flags_node.args.posonlyargs,
            *flags_node.args.args,
            *flags_node.args.kwonlyargs,
        )
    ]
    if (
        flags_args != ["resultados", "context_flags"]
        or flags_node.args.vararg is not None
        or flags_node.args.kwarg is not None
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_signature"
        )

    flags_body = list(flags_node.body)
    if (
        flags_body
        and isinstance(flags_body[0], ast.Expr)
        and isinstance(flags_body[0].value, ast.Constant)
        and isinstance(flags_body[0].value.value, str)
    ):
        flags_body = flags_body[1:]

    if len(flags_body) != 4:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_preservation"
        )

    base_statement, out_statement, flags_loop, flags_return = flags_body

    if not (
        isinstance(base_statement, ast.Assign)
        and len(base_statement.targets) == 1
        and isinstance(base_statement.targets[0], ast.Name)
        and base_statement.targets[0].id == "base"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_base"
        )

    if not (
        isinstance(out_statement, ast.Assign)
        and len(out_statement.targets) == 1
        and isinstance(out_statement.targets[0], ast.Name)
        and out_statement.targets[0].id == "out"
        and isinstance(out_statement.value, ast.Dict)
        and not out_statement.value.keys
        and not out_statement.value.values
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_output_init"
        )

    if not (
        isinstance(flags_loop, ast.For)
        and isinstance(flags_loop.target, ast.Tuple)
        and len(flags_loop.target.elts) == 2
        and all(isinstance(elt, ast.Name) for elt in flags_loop.target.elts)
        and [elt.id for elt in flags_loop.target.elts] == ["nome", "res"]
        and isinstance(flags_loop.iter, ast.Call)
        and _call_name(flags_loop.iter) == "resultados.items"
        and not flags_loop.iter.args
        and not flags_loop.iter.keywords
        and len(flags_loop.body) == 1
        and isinstance(flags_loop.body[0], ast.If)
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_loop"
        )

    flags_if = flags_loop.body[0]
    if not (
        isinstance(flags_if.test, ast.Call)
        and _call_name(flags_if.test) == "isinstance"
        and len(flags_if.test.args) == 2
        and isinstance(flags_if.test.args[0], ast.Name)
        and flags_if.test.args[0].id == "res"
        and isinstance(flags_if.test.args[1], ast.Name)
        and flags_if.test.args[1].id == "dict"
        and not flags_if.test.keywords
        and len(flags_if.body) == 3
        and len(flags_if.orelse) == 1
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_branch"
        )

    copy_statement, context_statement, merged_statement = flags_if.body

    if not (
        isinstance(copy_statement, ast.Assign)
        and len(copy_statement.targets) == 1
        and isinstance(copy_statement.targets[0], ast.Name)
        and copy_statement.targets[0].id == "merged"
        and isinstance(copy_statement.value, ast.Call)
        and _call_name(copy_statement.value) == "dict"
        and len(copy_statement.value.args) == 1
        and isinstance(copy_statement.value.args[0], ast.Name)
        and copy_statement.value.args[0].id == "res"
        and not copy_statement.value.keywords
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_copy"
        )

    if not (
        isinstance(context_statement, ast.Assign)
        and len(context_statement.targets) == 1
        and isinstance(context_statement.targets[0], ast.Subscript)
        and isinstance(context_statement.targets[0].value, ast.Name)
        and context_statement.targets[0].value.id == "merged"
        and _literal_string(context_statement.targets[0].slice)
        == "context_flags"
        and isinstance(context_statement.value, ast.Call)
        and _call_name(context_statement.value) == "dict"
        and len(context_statement.value.args) == 1
        and isinstance(context_statement.value.args[0], ast.Name)
        and context_statement.value.args[0].id == "base"
        and not context_statement.value.keywords
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_enrichment"
        )

    if not (
        isinstance(merged_statement, ast.Assign)
        and len(merged_statement.targets) == 1
        and isinstance(merged_statement.targets[0], ast.Subscript)
        and isinstance(merged_statement.targets[0].value, ast.Name)
        and merged_statement.targets[0].value.id == "out"
        and isinstance(merged_statement.targets[0].slice, ast.Name)
        and merged_statement.targets[0].slice.id == "nome"
        and isinstance(merged_statement.value, ast.Name)
        and merged_statement.value.id == "merged"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_dict_result"
        )

    passthrough_statement = flags_if.orelse[0]
    if not (
        isinstance(passthrough_statement, ast.Assign)
        and len(passthrough_statement.targets) == 1
        and isinstance(passthrough_statement.targets[0], ast.Subscript)
        and isinstance(passthrough_statement.targets[0].value, ast.Name)
        and passthrough_statement.targets[0].value.id == "out"
        and isinstance(passthrough_statement.targets[0].slice, ast.Name)
        and passthrough_statement.targets[0].slice.id == "nome"
        and isinstance(passthrough_statement.value, ast.Name)
        and passthrough_statement.value.id == "res"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_passthrough"
        )

    if not (
        isinstance(flags_return, ast.Return)
        and isinstance(flags_return.value, ast.Name)
        and flags_return.value.id == "out"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_return"
        )

    flag_assignments = [
        item
        for item in ast.walk(method_node)
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "resultados_engines"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) is not None
            and _resolve_name(
                method_module,
                _call_name(item.value),
            )
            == flags_helper_id
            and len(item.value.args) == 2
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "resultados_engines"
            and not item.value.keywords
        )
    ]
    if len(flag_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_assignment"
        )
    flags_assignment = flag_assignments[0]

    if dispatcher_assignment.lineno >= flags_assignment.lineno:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:flags_ordering"
        )

    # Prove the enriched mapping preserves each dispatcher result by key.
    enriched_initializers = [
        item
        for item in method_node.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "resultados_engines_enriquecidos"
            and isinstance(item.value, ast.Dict)
            and not item.value.keys
            and not item.value.values
        )
    ]
    if len(enriched_initializers) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:enriched_init"
        )
    enriched_initializer = enriched_initializers[0]

    result_loops = []
    for item in ast.walk(method_node):
        if not isinstance(item, ast.For):
            continue
        if not (
            isinstance(item.target, ast.Tuple)
            and len(item.target.elts) == 2
            and all(isinstance(elt, ast.Name) for elt in item.target.elts)
            and [elt.id for elt in item.target.elts] == ["nome", "resultado"]
            and isinstance(item.iter, ast.Call)
            and _call_name(item.iter) == "resultados_engines.items"
            and not item.iter.args
            and not item.iter.keywords
        ):
            continue
        result_loops.append(item)

    if len(result_loops) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:result_loop"
        )
    result_loop = result_loops[0]

    res_copies = [
        item
        for item in result_loop.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "res"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "dict"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "resultado"
            and not item.value.keywords
        )
    ]
    if len(res_copies) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:result_copy"
        )

    enriched_writes = [
        item
        for item in result_loop.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Subscript)
            and isinstance(item.targets[0].value, ast.Name)
            and item.targets[0].value.id == "resultados_engines_enriquecidos"
            and isinstance(item.targets[0].slice, ast.Name)
            and item.targets[0].slice.id == "nome"
            and isinstance(item.value, ast.Name)
            and item.value.id == "res"
        )
    ]
    if len(enriched_writes) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:enriched_write"
        )

    # Persistence must be causally tied to the same copied MEI-capable result.
    registro_assignments = [
        item
        for item in result_loop.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "registro"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "EngineResultado"
        )
    ]
    if len(registro_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_result_record"
        )

    registro_assignment = registro_assignments[0]
    if (
        method_module.imports.get("EngineResultado")
        != "app.models.EngineResultado"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_result_model"
        )

    registro_keywords = {
        keyword.arg: keyword.value
        for keyword in registro_assignment.value.keywords
        if keyword.arg is not None
    }
    persisted_result = registro_keywords.get("resultado")
    persisted_name = registro_keywords.get("engine_nome")
    if not (
        isinstance(persisted_result, ast.Name)
        and persisted_result.id == "res"
        and isinstance(persisted_name, ast.Name)
        and persisted_name.id == "nome"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_result_lineage"
        )

    causal_adds = [
        item
        for item in result_loop.body
        if (
            isinstance(item, ast.Expr)
            and isinstance(item.value, ast.Call)
            and isinstance(item.value.func, ast.Attribute)
            and item.value.func.attr == "add"
            and isinstance(item.value.func.value, ast.Attribute)
            and isinstance(item.value.func.value.value, ast.Name)
            and item.value.func.value.value.id == "self"
            and item.value.func.value.attr == "db"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "registro"
            and not item.value.keywords
        )
    ]
    if len(causal_adds) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:causal_persistence"
        )

    # Publication must contain exactly the enriched mapping.
    publication_returns = []
    for item in ast.walk(method_node):
        if not isinstance(item, ast.Return) or not isinstance(item.value, ast.Dict):
            continue
        matches = [
            value
            for key, value in zip(item.value.keys, item.value.values)
            if _literal_string(key) == "resultados_engines"
        ]
        if (
            len(matches) == 1
            and isinstance(matches[0], ast.Name)
            and matches[0].id == "resultados_engines_enriquecidos"
        ):
            publication_returns.append(item)

    if len(publication_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_publication"
        )
    publication_return = publication_returns[0]

    ordered = [
        dispatcher_assignment,
        flags_assignment,
        enriched_initializer,
        result_loop,
        publication_return,
    ]
    if [item.lineno for item in ordered] != sorted(
        item.lineno for item in ordered
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:method_ordering"
        )

    downstream = _background_downstream_inventory(
        modules,
        function_id=engine_method_id,
    )
    if (
        downstream["producer_ids"] != [PRODUCER_ID]
        or not downstream["downstream_scan_complete"]
        or downstream["unresolved_app_callees"]
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_COMPONENT:downstream"
        )

    # Instance-held session operations are inventoried only after the exact
    # __init__(db) -> self.db binding above has been proven.
    persistence_operations = []
    for item in ast.walk(method_node):
        if not (
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and item.func.attr in {"add", "flush", "commit"}
            and isinstance(item.func.value, ast.Attribute)
            and isinstance(item.func.value.value, ast.Name)
            and item.func.value.value.id == "self"
            and item.func.value.attr == "db"
        ):
            continue
        persistence_operations.append(
            (item.lineno, item.col_offset, item.func.attr)
        )

    persistence_operations.sort()
    operations = [
        operation for _, _, operation in persistence_operations
    ]
    if not {"add", "flush", "commit"}.issubset(set(operations)):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:persistence_operations"
        )

    component_trace = [
        engine_method_id,
        dispatcher_id,
        MEI_ENGINE_EXECUTE_ID,
        PRODUCER_ID,
    ]

    return {
        "producer_ids": [PRODUCER_ID],
        "component_trace": component_trace,
        "lineage_provenance": {
            "dispatcher_result": "resultados_engines[nome]",
            "flags_transform": flags_helper_id,
            "enriched_result": "resultados_engines_enriquecidos[nome]",
            "persistence_model": "app.models.EngineResultado",
            "persistence_field": "resultado",
            "component_return_field": "resultados_engines",
        },
        "persistence_inventory": {
            "qualified_trace": component_trace,
            "sink_operations": {
                engine_method_id: operations,
            },
            "unresolved_app_callees": [],
            "scan_complete": True,
        },
        "unresolved_app_callees": downstream["unresolved_app_callees"],
        "downstream_scan_complete": downstream["downstream_scan_complete"],
    }

def _insights_engine_mei_sink_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Prove the direct /insights HTTP consumer of the reusable InsightEngine proof."""
    expected_route = "app.routers.insights_router.obter_insights"
    if route_function_id != expected_route:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:"
            f"{route_function_id}"
        )

    route_found = _function_node(modules, route_function_id)
    if route_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:function"
        )

    route_module, route_node = route_found
    if (
        route_module.imports.get("InsightEngine")
        != "app.services.insights_engine.InsightEngine"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_import"
        )

    engine_assignments = [
        item
        for item in route_node.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "engine"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "InsightEngine"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "db"
            and not item.value.keywords
        )
    ]
    if len(engine_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:engine_construction"
        )

    route_returns = [
        item
        for item in route_node.body
        if (
            isinstance(item, ast.Return)
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "engine.gerar_insights_empresa"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Attribute)
            and isinstance(item.value.args[0].value, ast.Name)
            and item.value.args[0].value.id == "empresa"
            and item.value.args[0].attr == "id"
            and not item.value.keywords
        )
    ]
    if len(route_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:publication_return"
        )

    if engine_assignments[0].lineno >= route_returns[0].lineno:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_INSIGHTS_ROUTE:route_ordering"
        )

    component = _insights_engine_mei_component_inventory(modules)
    trace = [route_function_id, *component["component_trace"]]

    persistence = dict(component["persistence_inventory"])
    persistence["qualified_trace"] = trace

    provenance = dict(component["lineage_provenance"])
    provenance["publication_field"] = "resultados_engines"

    return {
        "mei_reachability": "REACHABLE_MEI",
        "producer_ids": component["producer_ids"],
        "sink_kinds": ["PUBLICATION", "PERSISTENCE"],
        "trace": trace,
        "lineage_provenance": provenance,
        "persistence_inventory": persistence,
        "unresolved_app_callees": component["unresolved_app_callees"],
        "downstream_scan_complete": component["downstream_scan_complete"],
    }

def _background_downstream_inventory(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    """Qualify one registered background root through the resolved app call graph."""
    pending = [function_id]
    seen: set[str] = set()
    producer_ids: set[str] = set()
    unresolved_app_callees: set[str] = set()

    while pending:
        current = pending.pop(0)
        if current in seen:
            continue
        seen.add(current)

        if current == PRODUCER_ID:
            producer_ids.add(PRODUCER_ID)
            continue

        found = _function_node(modules, current)
        if found is None:
            if (
                _is_plain_app_class_constructor(modules, current)
                or _is_plain_builtin_exception_constructor(modules, current)
                or _is_inert_declarative_model_constructor(modules, current)
                or _is_sqlalchemy_column_descriptor_helper(modules, current)
                or _is_inert_sqlalchemy_sessionmaker_factory(modules, current)
                or _is_inert_fastapi_security_dependency_object(modules, current)
            ):
                continue
            if current.startswith("app."):
                unresolved_app_callees.add(current)
            continue

        module, node = found
        dispatch = _insights_engine_registry_dispatch_inventory(
            modules,
            function_id=current,
        )
        metadata = _insights_engine_registry_metadata_inventory(
            modules,
            function_id=current,
        )
        qualified_accessors = set(
            dispatch["qualified_accessors"] + metadata["qualified_accessors"]
        )
        producer_ids.update(dispatch["producer_ids"])

        for callee in _direct_callees(module, node):
            if callee in qualified_accessors:
                continue
            if callee == PRODUCER_ID:
                producer_ids.add(PRODUCER_ID)
                continue
            if not callee.startswith("app."):
                continue
            if _function_node(modules, callee) is None:
                if (
                    _is_plain_app_class_constructor(modules, callee)
                    or _is_plain_builtin_exception_constructor(modules, callee)
                    or _is_inert_declarative_model_constructor(modules, callee)
                    or _is_sqlalchemy_column_descriptor_helper(modules, callee)
                    or _is_inert_sqlalchemy_sessionmaker_factory(modules, callee)
                    or _is_inert_fastapi_security_dependency_object(modules, callee)
                ):
                    continue
                unresolved_app_callees.add(callee)
                continue
            if callee not in seen:
                pending.append(callee)

    unresolved = sorted(unresolved_app_callees)
    return {
        "producer_ids": sorted(producer_ids),
        "unresolved_app_callees": unresolved,
        "downstream_scan_complete": not unresolved,
    }


def _relatorio_analysis_type_mei_sink_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Prove the tax_recovery /relatorio consumer of InsightEngine."""
    expected_route = "app.routes.relatorio_router.obter_relatorio_por_tipo"
    analysis_types_module_id = "app.services.analysis_types"

    if route_function_id != expected_route:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            f"{route_function_id}"
        )

    route_found = _function_node(modules, route_function_id)
    analysis_types_module = modules.get(analysis_types_module_id)

    if route_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:function"
        )
    if analysis_types_module is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "analysis_types_module"
        )

    route_module, route_node = route_found

    if (
        route_module.imports.get("InsightEngine")
        != "app.services.insights_engine.InsightEngine"
        or route_module.imports.get("ANALYSIS_TYPE_TAX_RECOVERY")
        != "app.services.analysis_types.ANALYSIS_TYPE_TAX_RECOVERY"
        or route_module.imports.get("ANALYSIS_TYPES_RELATORIO_GET")
        != "app.services.analysis_types.ANALYSIS_TYPES_RELATORIO_GET"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:imports"
        )

    # Prove the canonical literal represented by the tax-recovery symbol.
    tax_recovery_constants = [
        statement
        for statement in analysis_types_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "ANALYSIS_TYPE_TAX_RECOVERY"
            and _literal_string(statement.value) == "tax_recovery"
        )
    ]
    if len(tax_recovery_constants) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "tax_recovery_constant"
        )

    # The publicly accepted domain must actually contain tax_recovery.
    allowed_domains = [
        statement.value
        for statement in analysis_types_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "ANALYSIS_TYPES_RELATORIO_GET"
            and isinstance(statement.value, ast.Tuple)
        )
    ]
    if len(allowed_domains) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "allowed_domain"
        )

    allowed_names = [
        element.id
        for element in allowed_domains[0].elts
        if isinstance(element, ast.Name)
    ]
    if (
        len(allowed_names) != len(allowed_domains[0].elts)
        or "ANALYSIS_TYPE_TAX_RECOVERY" not in allowed_names
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "tax_recovery_not_allowed"
        )

    # relatorio_router must expose exactly that domain through ANALYSIS_TYPES.
    route_domain_aliases = [
        statement
        for statement in route_module.tree.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "ANALYSIS_TYPES"
            and isinstance(statement.value, ast.Name)
            and statement.value.id == "ANALYSIS_TYPES_RELATORIO_GET"
        )
    ]
    if len(route_domain_aliases) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "route_domain_alias"
        )

    # The route must reject values outside ANALYSIS_TYPES before its branches.
    domain_guards = [
        statement
        for statement in route_node.body
        if (
            isinstance(statement, ast.If)
            and isinstance(statement.test, ast.Compare)
            and isinstance(statement.test.left, ast.Name)
            and statement.test.left.id == "analysis_type"
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.NotIn)
            and len(statement.test.comparators) == 1
            and isinstance(statement.test.comparators[0], ast.Name)
            and statement.test.comparators[0].id == "ANALYSIS_TYPES"
            and any(
                isinstance(item, ast.Raise)
                for item in ast.walk(statement)
            )
        )
    ]
    if len(domain_guards) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "domain_guard"
        )

    # Identify the real tax_recovery branch.
    recovery_branches = [
        statement
        for statement in route_node.body
        if (
            isinstance(statement, ast.If)
            and isinstance(statement.test, ast.Compare)
            and isinstance(statement.test.left, ast.Name)
            and statement.test.left.id == "analysis_type"
            and len(statement.test.ops) == 1
            and isinstance(statement.test.ops[0], ast.Eq)
            and len(statement.test.comparators) == 1
            and isinstance(statement.test.comparators[0], ast.Name)
            and statement.test.comparators[0].id
            == "ANALYSIS_TYPE_TAX_RECOVERY"
        )
    ]
    if len(recovery_branches) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "tax_recovery_branch"
        )
    recovery_branch = recovery_branches[0]

    empresa_branches = [
        item
        for item in recovery_branch.body
        if (
            isinstance(item, ast.If)
            and isinstance(item.test, ast.Name)
            and item.test.id == "empresa_id"
        )
    ]
    if len(empresa_branches) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "empresa_branch"
        )
    empresa_branch = empresa_branches[0]

    engine_assignments = [
        item
        for item in empresa_branch.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "engine"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value) == "InsightEngine"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "db"
            and not item.value.keywords
        )
    ]
    if len(engine_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "engine_construction"
        )

    result_assignments = [
        item
        for item in empresa_branch.body
        if (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and item.targets[0].id == "resultado"
            and isinstance(item.value, ast.Call)
            and _call_name(item.value)
            == "engine.gerar_insights_empresa"
            and len(item.value.args) == 1
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == "empresa_id"
            and not item.value.keywords
        )
    ]
    if len(result_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "engine_result"
        )

    publication_returns = []
    for item in empresa_branch.body:
        if not isinstance(item, ast.Return) or not isinstance(item.value, ast.Dict):
            continue

        pairs = {
            _literal_string(key): value
            for key, value in zip(item.value.keys, item.value.values)
            if _literal_string(key) is not None
        }
        analysis_value = pairs.get("analysis_type")
        relatorio_value = pairs.get("relatorio")

        if (
            isinstance(analysis_value, ast.Name)
            and analysis_value.id == "ANALYSIS_TYPE_TAX_RECOVERY"
            and isinstance(relatorio_value, ast.Name)
            and relatorio_value.id == "resultado"
        ):
            publication_returns.append(item)

    if len(publication_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "publication_return"
        )

    ordered = [
        domain_guards[0],
        recovery_branch,
        engine_assignments[0],
        result_assignments[0],
        publication_returns[0],
    ]
    if [item.lineno for item in ordered] != sorted(
        item.lineno for item in ordered
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:ordering"
        )

    component = _insights_engine_mei_component_inventory(modules)

    downstream = _background_downstream_inventory(
        modules,
        function_id=route_function_id,
    )
    if (
        downstream["producer_ids"] != [PRODUCER_ID]
        or not downstream["downstream_scan_complete"]
        or downstream["unresolved_app_callees"]
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_ANALYSIS_TYPE:"
            "downstream"
        )

    trace = [route_function_id, *component["component_trace"]]

    persistence = dict(component["persistence_inventory"])
    persistence["qualified_trace"] = trace

    provenance = dict(component["lineage_provenance"])
    provenance.update(
        {
            "analysis_type_branch": "tax_recovery",
            "publication_field": "relatorio",
        }
    )

    return {
        "mei_reachability": "REACHABLE_MEI",
        "producer_ids": component["producer_ids"],
        "sink_kinds": ["PUBLICATION", "PERSISTENCE"],
        "trace": trace,
        "lineage_provenance": provenance,
        "persistence_inventory": persistence,
        "unresolved_app_callees": downstream["unresolved_app_callees"],
        "downstream_scan_complete": downstream["downstream_scan_complete"],
    }

def _relatorio_pdf_mei_persistence_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Prove /relatorio/relatorio-pdf reaches canonical MEI persistence only."""
    expected_route = "app.routes.relatorio_router.relatorio_pdf"
    service_id = (
        "app.services.registro_analise_service."
        "executar_e_registrar_analise_xml"
    )

    if route_function_id != expected_route:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            f"{route_function_id}"
        )

    route_found = _function_node(modules, route_function_id)
    service_found = _function_node(modules, service_id)

    if route_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:route"
        )
    if service_found is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:service"
        )

    route_module, route_node = route_found
    _, service_node = service_found

    if (
        route_module.imports.get("executar_e_registrar_analise_xml")
        != service_id
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:service_import"
        )

    # Route must forward its empresa_id into the persisted-analysis service.
    service_calls = [
        node
        for node in ast.walk(route_node)
        if (
            isinstance(node, ast.Call)
            and _call_name(node) == "executar_e_registrar_analise_xml"
        )
    ]
    if len(service_calls) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:service_call"
        )

    service_call = service_calls[0]
    if not (
        len(service_call.args) == 4
        and isinstance(service_call.args[0], ast.Name)
        and service_call.args[0].id == "db"
        and isinstance(service_call.args[1], ast.Name)
        and service_call.args[1].id == "xml_bytes"
        and isinstance(service_call.args[2], ast.Name)
        and service_call.args[2].id == "user_id"
        and isinstance(service_call.args[3], ast.Name)
        and service_call.args[3].id == "empresa_id"
        and len(service_call.keywords) == 1
        and service_call.keywords[0].arg == "limite_analises"
        and isinstance(service_call.keywords[0].value, ast.Name)
        and service_call.keywords[0].value.id == "limite_analises"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "empresa_id_forwarding"
        )

    # The service must have a reachable empresa_id branch containing the
    # InsightEngine execution. This is the causal gate for MEI persistence.
    empresa_branches = [
        node
        for node in ast.walk(service_node)
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "empresa_id"
            and any(
                isinstance(item, ast.Call)
                and _call_name(item) == "engine.gerar_insights_empresa"
                for item in ast.walk(node)
            )
        )
    ]
    if len(empresa_branches) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:empresa_branch"
        )
    empresa_branch = empresa_branches[0]

    local_imports = [
        node
        for node in ast.walk(empresa_branch)
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "app.services.insights_engine"
            and len(node.names) == 1
            and node.names[0].name == "InsightEngine"
            and node.names[0].asname is None
        )
    ]
    if len(local_imports) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "insightengine_import"
        )

    engine_assignments = [
        node
        for node in ast.walk(empresa_branch)
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "engine"
            and isinstance(node.value, ast.Call)
            and _call_name(node.value) == "InsightEngine"
            and len(node.value.args) == 1
            and isinstance(node.value.args[0], ast.Name)
            and node.value.args[0].id == "db"
            and not node.value.keywords
        )
    ]
    if len(engine_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "engine_construction"
        )

    engine_calls = [
        node
        for node in ast.walk(empresa_branch)
        if (
            isinstance(node, ast.Call)
            and _call_name(node) == "engine.gerar_insights_empresa"
        )
    ]
    if len(engine_calls) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "engine_execution"
        )

    engine_call = engine_calls[0]
    keywords = {
        keyword.arg: keyword.value
        for keyword in engine_call.keywords
        if keyword.arg is not None
    }
    empresa_value = keywords.get("empresa_id")
    relatorio_value = keywords.get("relatorio_analise_id")

    if not (
        not engine_call.args
        and len(keywords) == 2
        and isinstance(empresa_value, ast.Name)
        and empresa_value.id == "empresa_id"
        and isinstance(relatorio_value, ast.Attribute)
        and isinstance(relatorio_value.value, ast.Name)
        and relatorio_value.value.id == "rel"
        and relatorio_value.attr == "id"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "engine_arguments"
        )

    if engine_assignments[0].lineno >= engine_call.lineno:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:"
            "engine_ordering"
        )

    # Reuse the already-proven component persistence. Do not infer publication:
    # executar_analise_xml() returns the XML result separately from InsightEngine.
    component = _insights_engine_mei_component_inventory(modules)

    downstream = _background_downstream_inventory(
        modules,
        function_id=route_function_id,
    )
    if (
        downstream["producer_ids"] != [PRODUCER_ID]
        or not downstream["downstream_scan_complete"]
        or downstream["unresolved_app_callees"]
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_RELATORIO_PDF:downstream"
        )

    trace = [
        route_function_id,
        service_id,
        *component["component_trace"],
    ]

    persistence = dict(component["persistence_inventory"])
    persistence["qualified_trace"] = trace

    provenance = dict(component["lineage_provenance"])
    provenance.pop("component_return_field", None)
    provenance["persistence_guard"] = "empresa_id"

    return {
        "mei_reachability": "REACHABLE_MEI",
        "producer_ids": component["producer_ids"],
        "sink_kinds": ["PERSISTENCE"],
        "trace": trace,
        "lineage_provenance": provenance,
        "persistence_inventory": persistence,
        "unresolved_app_callees": downstream["unresolved_app_callees"],
        "downstream_scan_complete": downstream["downstream_scan_complete"],
    }

def _auth_register_no_canonical_mei_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Qualify only the exact constructor topology used by /auth/register."""
    expected_route = "app.auth_router.register_user"
    user_id = "app.models.User"
    response_id = "app.schemas.user_schema.UserResponse"

    if route_function_id != expected_route:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:route"
        )

    found = _function_node(modules, route_function_id)
    models_module = modules.get("app.models")
    database_module = modules.get("app.database")
    schema_module = modules.get("app.schemas.user_schema")

    if (
        found is None
        or models_module is None
        or database_module is None
        or schema_module is None
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:modules"
        )

    route_module, route_node = found

    downstream = _background_downstream_inventory(
        modules,
        function_id=route_function_id,
    )

    if downstream["producer_ids"]:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:producer"
        )

    if sorted(downstream["unresolved_app_callees"]) != sorted(
        [user_id, response_id]
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:unexpected_downstream"
        )

    if (
        route_module.imports.get("models") != "app.models"
        or route_module.imports.get("UserResponse") != response_id
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:imports"
        )

    # Exact SQLAlchemy User construction used by the route.
    user_calls = [
        node
        for node in ast.walk(route_node)
        if isinstance(node, ast.Call)
        and _call_name(node) == "models.User"
    ]
    if len(user_calls) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_call"
        )

    if (
        models_module.imports.get("Base") != "app.database.Base"
        or database_module.imports.get("declarative_base")
        != "sqlalchemy.orm.declarative_base"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:base"
        )

    user_defs = [
        node
        for node in models_module.tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "User"
    ]
    if len(user_defs) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_def"
        )

    user_class = user_defs[0]

    if not (
        len(user_class.bases) == 1
        and isinstance(user_class.bases[0], ast.Name)
        and user_class.bases[0].id == "Base"
        and not user_class.keywords
        and not user_class.decorator_list
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_inheritance"
        )

    methods = [
        node
        for node in user_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    # User may contain only the proven non-constructor property is_admin.
    if len(methods) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_methods"
        )

    method = methods[0]
    if not (
        method.name == "is_admin"
        and len(method.decorator_list) == 1
        and isinstance(method.decorator_list[0], ast.Name)
        and method.decorator_list[0].id == "property"
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_property"
        )

    # Explicitly forbid custom constructor hooks.
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in {"__init__", "__new__"}
        for node in user_class.body
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_constructor"
        )

    # Preserve the existing ADR-020 insert-validator boundary.
    validator_maps = []
    for statement in models_module.tree.body:
        value = None

        if (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_ADR020_INSERT_VALIDATORS"
                for target in statement.targets
            )
        ):
            value = statement.value

        elif (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "_ADR020_INSERT_VALIDATORS"
        ):
            value = statement.value

        if isinstance(value, ast.Dict):
            validator_maps.append(value)

    if len(validator_maps) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:validator_map"
        )

    validator_keys = {
        key.id
        for key in validator_maps[0].keys
        if isinstance(key, ast.Name)
    }

    if "User" in validator_keys:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:user_validator"
        )

    # Exact UserResponse topology: direct BaseModel, fields/config only.
    if schema_module.imports.get("BaseModel") != "pydantic.BaseModel":
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:basemodel"
        )

    response_defs = [
        node
        for node in schema_module.tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "UserResponse"
    ]
    if len(response_defs) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:response_def"
        )

    response_class = response_defs[0]

    if not (
        len(response_class.bases) == 1
        and isinstance(response_class.bases[0], ast.Name)
        and response_class.bases[0].id == "BaseModel"
        and not response_class.keywords
        and not response_class.decorator_list
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:response_inheritance"
        )

    # Any method/validator means this special qualification no longer applies.
    if any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in response_class.body
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:response_methods"
        )

    fields = [
        node.target.id
        for node in response_class.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    ]

    if fields != ["id", "email", "empresa_id", "role"]:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:response_fields"
        )

    # The route must directly return UserResponse.
    response_returns = [
        node
        for node in ast.walk(route_node)
        if (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and _call_name(node.value) == "UserResponse"
        )
    ]

    if len(response_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_AUTH_REGISTER:response_return"
        )

    return {
        "mei_reachability": "NO_CANONICAL_MEI_PRODUCER",
        "producer_ids": [],
        "sink_kinds": [],
        "trace": [route_function_id],
        "unresolved_app_callees": [],
        "downstream_scan_complete": True,
    }

def _system_metrics_no_canonical_mei_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Qualify only the proven module-literal-dict reads of /system/metrics."""
    expected_route = "app.routes.metrics_router.obter_metricas"
    orchestrator_id = "app.services.analysis_orchestrator"

    mapping_names = (
        "degraded_engines",
        "engine_ab_testing",
        "engine_blocked_until",
        "engine_failures",
        "engine_versions",
    )
    expected_unresolved = sorted(
        f"{orchestrator_id}.{name}.get"
        for name in mapping_names
    )

    if route_function_id != expected_route:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:route"
        )

    route_found = _function_node(modules, route_function_id)
    metrics_module = modules.get("app.routes.metrics_router")
    orchestrator = modules.get(orchestrator_id)

    if (
        route_found is None
        or metrics_module is None
        or orchestrator is None
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:modules"
        )

    _, route_node = route_found

    # First preserve the ordinary scanner evidence. This exception is allowed
    # only for the exact five unresolved mapping reads already measured.
    downstream = _background_downstream_inventory(
        modules,
        function_id=route_function_id,
    )

    if downstream["producer_ids"]:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
            "producer_present"
        )

    if sorted(downstream["unresolved_app_callees"]) != expected_unresolved:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
            "unexpected_downstream"
        )

    # Route topology must still call the two local read-only assembly helpers.
    route_calls = {
        _call_name(call)
        for call in ast.walk(route_node)
        if isinstance(call, ast.Call)
    }
    if not {"_status_engines", "_calcular_alertas"}.issubset(route_calls):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
            "route_helpers"
        )

    status_node = metrics_module.functions.get("_status_engines")
    alertas_node = metrics_module.functions.get("_calcular_alertas")

    if status_node is None or alertas_node is None:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
            "helper_functions"
        )

    # Each imported mapping must resolve to the exact orchestrator symbol.
    for name in mapping_names:
        if (
            metrics_module.imports.get(name)
            != f"{orchestrator_id}.{name}"
        ):
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
                f"import:{name}"
            )

    # _status_engines must perform exactly one .get() on each qualified map,
    # and no other method call on those mapping objects.
    mapping_method_calls = []
    for call in (
        node
        for node in ast.walk(status_node)
        if isinstance(node, ast.Call)
    ):
        call_name = _call_name(call)
        if call_name is None or "." not in call_name:
            continue

        root, method = call_name.split(".", 1)
        if root not in mapping_names:
            continue

        mapping_method_calls.append((root, method))

    if sorted(mapping_method_calls) != sorted(
        (name, "get") for name in mapping_names
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
            "mapping_operations"
        )

    # Each mapping must have exactly one module-level binding and that binding
    # must be an AST dict literal. Any later rebinding invalidates the proof.
    for name in mapping_names:
        bindings = []

        for statement in orchestrator.tree.body:
            if isinstance(statement, ast.Assign):
                if any(
                    isinstance(target, ast.Name)
                    and target.id == name
                    for target in statement.targets
                ):
                    bindings.append(statement)

            elif (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id == name
            ):
                bindings.append(statement)

        if len(bindings) != 1:
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
                f"binding_count:{name}"
            )

        binding = bindings[0]
        value = (
            binding.value
            if isinstance(binding, (ast.Assign, ast.AnnAssign))
            else None
        )

        if not isinstance(value, ast.Dict):
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_SYSTEM_METRICS:"
                f"non_literal_mapping:{name}"
            )

    return {
        "mei_reachability": "NO_CANONICAL_MEI_PRODUCER",
        "producer_ids": [],
        "sink_kinds": [],
        "trace": [
            route_function_id,
            "app.routes.metrics_router._status_engines",
            "app.routes.metrics_router._calcular_alertas",
        ],
        "qualified_mapping_reads": [
            f"{orchestrator_id}.{name}.get"
            for name in mapping_names
        ],
        "unresolved_app_callees": [],
        "downstream_scan_complete": True,
    }

def _default_route_reachability_inventory(
    modules: dict[str, ModuleInfo],
    *,
    function_id: str,
) -> dict:
    """Classify a mounted route only from a complete canonical-MEI reachability proof."""
    downstream = _background_downstream_inventory(
        modules,
        function_id=function_id,
    )
    producer_ids = downstream["producer_ids"]
    scan_complete = downstream["downstream_scan_complete"]

    if not scan_complete or producer_ids:
        mei_reachability = "UNRESOLVED_MEI"
    else:
        mei_reachability = "NO_CANONICAL_MEI_PRODUCER"

    return {
        "mei_reachability": mei_reachability,
        **downstream,
    }


def _module_assignments(module: ModuleInfo) -> dict[str, ast.AST]:
    assignments: dict[str, ast.AST] = {}
    for statement in module.tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            assignments[target.id] = statement.value
    return assignments


def _split_imported_symbol(
    modules: dict[str, ModuleInfo],
    target: str,
) -> tuple[ModuleInfo, str] | None:
    for module_name in sorted(modules, key=len, reverse=True):
        prefix = module_name + "."
        if target.startswith(prefix):
            return modules[module_name], target[len(prefix):]
    return None


def _static_string_value(
    modules: dict[str, ModuleInfo],
    module: ModuleInfo,
    node: ast.AST,
    *,
    seen: frozenset[str] = frozenset(),
) -> str | None:
    literal = _literal_string(node)
    if literal is not None:
        return literal
    if not isinstance(node, ast.Name):
        return None

    marker = f"{module.name}:{node.id}"
    if marker in seen:
        return None
    next_seen = seen | {marker}

    local_value = _module_assignments(module).get(node.id)
    if local_value is not None:
        return _static_string_value(
            modules,
            module,
            local_value,
            seen=next_seen,
        )

    imported = module.imports.get(node.id)
    if imported is None:
        return None
    split = _split_imported_symbol(modules, imported)
    if split is None:
        return None
    imported_module, symbol = split
    imported_value = _module_assignments(imported_module).get(symbol)
    if imported_value is None:
        return None
    return _static_string_value(
        modules,
        imported_module,
        imported_value,
        seen=next_seen,
    )


def _dict_value_for_string_key(
    modules: dict[str, ModuleInfo],
    module: ModuleInfo,
    node: ast.AST,
    key: str,
) -> ast.AST | None:
    if not isinstance(node, ast.Dict):
        return None
    for key_node, value_node in zip(node.keys, node.values):
        if key_node is None:
            continue
        if _static_string_value(modules, module, key_node) == key:
            return value_node
    return None


def _resolve_symbol_reference(module: ModuleInfo, node: ast.AST) -> str | None:
    if not isinstance(node, ast.Name):
        return None
    imported = module.imports.get(node.id)
    if imported is not None:
        return imported
    if node.id in module.functions:
        return f"{module.name}.{node.id}"
    return None


def _resolve_mei_registry_engine(modules: dict[str, ModuleInfo]) -> str | None:
    """Resolve the static MEI v1 registry target without executing application code."""
    registry = modules.get("app.services.engine_registry")
    if registry is None:
        return None
    assignments = _module_assignments(registry)

    registry_raw = assignments.get("_ENGINE_REGISTRY_RAW")
    if registry_raw is None:
        registry_raw = assignments.get("ENGINE_REGISTRY")
    if registry_raw is None:
        return None

    mei_entry = _dict_value_for_string_key(modules, registry, registry_raw, "mei_tax")
    if mei_entry is None:
        return None
    v1_entry = _dict_value_for_string_key(modules, registry, mei_entry, "v1")
    if v1_entry is None:
        return None

    direct_target = _resolve_symbol_reference(registry, v1_entry)
    if direct_target is not None:
        return direct_target

    if not isinstance(v1_entry, ast.Call) or not v1_entry.args:
        return None
    call_name = _call_name(v1_entry)
    if call_name is None:
        return None
    resolved_factory = _resolve_name(registry, call_name)
    if resolved_factory != "app.services.engine_registry._execute_engine_v1":
        return None
    if _static_string_value(modules, registry, v1_entry.args[0]) != "mei_tax":
        return None

    engines_raw = assignments.get("_ENGINES_RAW")
    if engines_raw is None:
        return None
    engine_class_node = _dict_value_for_string_key(
        modules,
        registry,
        engines_raw,
        "mei_tax",
    )
    if engine_class_node is None:
        return None
    engine_class = _resolve_symbol_reference(registry, engine_class_node)
    if engine_class is None:
        return None
    return f"{engine_class}.execute"


def _assistant_trace(
    modules: dict[str, ModuleInfo],
    route_function_id: str,
) -> list[str]:
    """Follow the currently proven Assistant MEI lineage."""
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

    engine_id = _resolve_mei_registry_engine(modules)
    if engine_id != MEI_ENGINE_EXECUTE_ID:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_REGISTRY:{engine_id or 'unknown'}"
        )

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


def _assistant_sink_kinds(modules: dict[str, ModuleInfo]) -> list[str]:
    """Prove the real Assistant MEI path crosses the orchestrator cache."""
    function_id = "app.services.analysis_orchestrator.executar_analise"
    found = _function_node(modules, function_id)
    if found is None:
        raise RuntimeError(f"MEI_REACHABILITY_UNRESOLVED_FUNCTION:{function_id}")
    module, node = found
    branches = [
        statement
        for statement in node.body
        if isinstance(statement, ast.If)
        and ast.unparse(statement.test) == "t == ANALYSIS_TYPE_MEI_TAX"
    ]
    cache_hits = [
        statement
        for statement in node.body
        if isinstance(statement, ast.If)
        and ast.unparse(statement.test) == "cache_key in analysis_cache"
        and "return analysis_cache[cache_key]" in ast.unparse(statement)
    ]
    if (
        not isinstance(_module_assignments(module).get("analysis_cache"), ast.Dict)
        or len(cache_hits) != 1
        or len(branches) != 1
        or cache_hits[0].lineno >= branches[0].lineno
        or "analysis_cache[cache_key] = resultado" not in ast.unparse(branches[0])
    ):
        raise RuntimeError("MEI_REACHABILITY_UNRESOLVED_CACHE:assistant_mei")
    return ["CACHE", "PUBLICATION"]


def _assistant_orm_persistence_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Prove Assistant MEI ORM persistence only after the qualified registry trace."""
    qualified_trace = _assistant_trace(modules, route_function_id)
    sink_operations: dict[str, list[str]] = {}

    for function_id in qualified_trace:
        if _function_node(modules, function_id) is None:
            raise RuntimeError(
                f"MEI_REACHABILITY_UNRESOLVED_ORM_FUNCTION:{function_id}"
            )
        operations = _orm_persistence_operations(
            modules,
            function_id=function_id,
        )
        if operations:
            sink_operations[function_id] = operations

    engine_scan = _reachable_orm_persistence_sinks(
        modules,
        function_id=MEI_ENGINE_EXECUTE_ID,
    )
    for sink_id, operations in engine_scan["sink_operations"].items():
        sink_operations[sink_id] = operations

    unresolved = list(engine_scan["unresolved_app_callees"])
    return {
        "qualified_trace": qualified_trace,
        "sink_operations": {
            sink_id: sink_operations[sink_id]
            for sink_id in sorted(sink_operations)
        },
        "unresolved_app_callees": unresolved,
        "scan_complete": not unresolved,
    }


def _formalizacao_compare_trace(
    modules: dict[str, ModuleInfo],
    route_function_id: str,
) -> list[str]:
    """Prove a mounted formalizacao route reaches the MEI comparison producer."""
    route = _function_node(modules, route_function_id)
    if route is None:
        raise RuntimeError(f"MEI_REACHABILITY_UNRESOLVED_FUNCTION:{route_function_id}")
    route_module, route_node = route
    if FORMALIZACAO_COMPARE_ID not in _direct_callees(route_module, route_node):
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_EDGE:{route_function_id}->{FORMALIZACAO_COMPARE_ID}"
        )

    compare = _function_node(modules, FORMALIZACAO_COMPARE_ID)
    if compare is None:
        raise RuntimeError(f"MEI_REACHABILITY_UNRESOLVED_FUNCTION:{FORMALIZACAO_COMPARE_ID}")
    compare_module, compare_node = compare
    if PRODUCER_ID not in _direct_callees(compare_module, compare_node):
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_EDGE:{FORMALIZACAO_COMPARE_ID}->{PRODUCER_ID}"
        )

    return [route_function_id, FORMALIZACAO_COMPARE_ID, PRODUCER_ID]


def _formalizacao_orm_persistence_inventory(
    modules: dict[str, ModuleInfo],
    *,
    route_function_id: str,
) -> dict:
    """Prove ORM persistence across the qualified formalizacao MEI decision path."""
    qualified_trace = _formalizacao_compare_trace(modules, route_function_id)
    route_scan = _reachable_orm_persistence_sinks(
        modules,
        function_id=route_function_id,
    )
    return {
        "qualified_trace": qualified_trace,
        "sink_operations": route_scan["sink_operations"],
        "unresolved_app_callees": route_scan["unresolved_app_callees"],
        "scan_complete": route_scan["scan_complete"],
    }


def _contains_name(node: ast.AST, name: str) -> bool:
    return any(isinstance(item, ast.Name) and item.id == name for item in ast.walk(node))


def _single_name_assignment(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    name: str,
) -> ast.Assign:
    matches = [
        item
        for item in ast.walk(function_node)
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Name)
        and item.targets[0].id == name
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:{name}"
        )
    return matches[0]


def _regime_decision_provenance(modules: dict[str, ModuleInfo]) -> dict:
    """Prove the real MEI DAS value reaches the recommended-regime decision."""
    compare = _function_node(modules, FORMALIZACAO_COMPARE_ID)
    if compare is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:{FORMALIZACAO_COMPARE_ID}"
        )
    module, node = compare

    monthly = _single_name_assignment(node, "_das_mensal")
    if not isinstance(monthly.value, ast.Call):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:_das_mensal"
        )
    monthly_call = _call_name(monthly.value)
    if monthly_call is None or _resolve_name(module, monthly_call) != PRODUCER_ID:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:_das_mensal"
        )

    annual = _single_name_assignment(node, "_das_anual")
    if not (
        isinstance(annual.value, ast.Call)
        and _call_name(annual.value) == "round"
        and annual.value.args
        and _contains_name(annual.value.args[0], "_das_mensal")
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:_das_anual"
        )

    result_assignments = [
        item
        for item in ast.walk(node)
        if isinstance(item, ast.Assign)
        and len(item.targets) == 1
        and isinstance(item.targets[0], ast.Subscript)
        and isinstance(item.targets[0].value, ast.Name)
        and item.targets[0].value.id == "resultados"
        and _literal_string(item.targets[0].slice) == "mei"
    ]
    if len(result_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ResultadoRegime.carga_anual"
        )
    result_assignment = result_assignments[0]
    if not isinstance(result_assignment.value, ast.Call):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ResultadoRegime.carga_anual"
        )
    result_call_name = _call_name(result_assignment.value)
    if result_call_name is None or not result_call_name.endswith("ResultadoRegime"):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ResultadoRegime.carga_anual"
        )
    carga_keyword = next(
        (kw for kw in result_assignment.value.keywords if kw.arg == "carga_anual"),
        None,
    )
    if carga_keyword is None or not _contains_name(carga_keyword.value, "_das_anual"):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ResultadoRegime.carga_anual"
        )

    ordered = _single_name_assignment(node, "ordenados")
    if not (
        isinstance(ordered.value, ast.Call)
        and _call_name(ordered.value) == "sorted"
        and ordered.value.args
        and _contains_name(ordered.value.args[0], "resultados")
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:sorted:key:carga_anual"
        )
    key_keyword = next((kw for kw in ordered.value.keywords if kw.arg == "key"), None)
    if not (
        key_keyword is not None
        and isinstance(key_keyword.value, ast.Lambda)
        and any(
            isinstance(item, ast.Attribute) and item.attr == "carga_anual"
            for item in ast.walk(key_keyword.value.body)
        )
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:sorted:key:carga_anual"
        )

    best = _single_name_assignment(node, "regime_melhor")
    if not _contains_name(best.value, "ordenados"):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:regime_melhor"
        )

    decision_returns = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Return) or not isinstance(item.value, ast.Call):
            continue
        call_name = _call_name(item.value)
        if call_name is None or not call_name.endswith("ResultadoComparacao"):
            continue
        keyword = next(
            (kw for kw in item.value.keywords if kw.arg == "regime_recomendado"),
            None,
        )
        if keyword is not None and _contains_name(keyword.value, "regime_melhor"):
            decision_returns.append(item)
    if len(decision_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ResultadoComparacao.regime_recomendado"
        )

    ordered_nodes = [
        monthly,
        annual,
        result_assignment,
        ordered,
        best,
        decision_returns[0],
    ]
    if [item.lineno for item in ordered_nodes] != sorted(item.lineno for item in ordered_nodes):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_DECISION_PROVENANCE:ordering"
        )

    return {
        "producer_id": PRODUCER_ID,
        "function_id": FORMALIZACAO_COMPARE_ID,
        "steps": [
            "_das_mensal",
            "_das_anual",
            "ResultadoRegime.carga_anual",
            "sorted:key:carga_anual",
            "regime_melhor",
            "ResultadoComparacao.regime_recomendado",
        ],
    }


def _argument_provenance_trace(
    modules: dict[str, ModuleInfo],
    *,
    producer_id: str,
    caller_function_id: str,
    callee_function_id: str,
) -> list[str]:
    """Trace one static producer→argument→parameter→return edge.

    This primitive deliberately accepts only a single regular positional
    parameter, a single producer assignment in the caller, one direct call with
    that value as its sole argument, a direct callee return of the parameter,
    and a direct caller return of the call result. Ambiguity fails closed.
    """
    caller = _function_node(modules, caller_function_id)
    callee = _function_node(modules, callee_function_id)
    if caller is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:{caller_function_id}"
        )
    if callee is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:{callee_function_id}"
        )

    caller_module, caller_node = caller
    _, callee_node = callee

    producer_assignments = []
    for item in caller_node.body:
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Call)
        ):
            continue
        call_name = _call_name(item.value)
        if call_name is not None and _resolve_name(caller_module, call_name) == producer_id:
            producer_assignments.append(item)
    if len(producer_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:producer_assignment"
        )
    producer_assignment = producer_assignments[0]
    producer_name = producer_assignment.targets[0].id

    signature = callee_node.args
    if (
        len(signature.args) != 1
        or signature.posonlyargs
        or signature.kwonlyargs
        or signature.vararg is not None
        or signature.kwarg is not None
        or signature.defaults
        or any(default is not None for default in signature.kw_defaults)
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:callee_signature"
        )
    parameter_name = signature.args[0].arg

    callee_returns = [
        item
        for item in callee_node.body
        if isinstance(item, ast.Return)
        and isinstance(item.value, ast.Name)
        and item.value.id == parameter_name
    ]
    if len(callee_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:callee_return"
        )

    call_assignments = []
    for item in caller_node.body:
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Call)
            and len(item.value.args) == 1
            and not item.value.keywords
            and isinstance(item.value.args[0], ast.Name)
            and item.value.args[0].id == producer_name
        ):
            continue
        call_name = _call_name(item.value)
        if call_name is not None and _resolve_name(caller_module, call_name) == callee_function_id:
            call_assignments.append(item)
    if len(call_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:callee_call"
        )
    call_assignment = call_assignments[0]
    result_name = call_assignment.targets[0].id

    caller_returns = [
        item
        for item in caller_node.body
        if isinstance(item, ast.Return)
        and isinstance(item.value, ast.Name)
        and item.value.id == result_name
    ]
    if len(caller_returns) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:caller_return"
        )
    caller_return = caller_returns[0]

    if not (
        producer_assignment.lineno < call_assignment.lineno < caller_return.lineno
    ):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_ARGUMENT_PROVENANCE:ordering"
        )

    return [
        producer_id,
        f"{caller_function_id}:{producer_name}",
        f"{callee_function_id}:{parameter_name}",
        f"{callee_function_id}:return",
        f"{caller_function_id}:{result_name}",
        f"{caller_function_id}:return",
    ]


def _value_provenance_trace(
    modules: dict[str, ModuleInfo],
    *,
    producer_id: str,
    source_function_id: str,
    sink_function_id: str,
) -> list[str]:
    """Trace one of the explicitly proven V1 value-provenance shapes.

    Supported here, and only here:
    1. producer → dict literal → return → wrapper → literal subscript → return;
    2. producer → direct return → wrapper → f-string → return;
    3. producer → direct return → wrapper → static cache write/read → return;
    4. producer → direct return → wrapper → static persistence call → return.

    Ambiguity, duplicate candidate edges, dynamic keys, or structural changes
    fail closed rather than being guessed.
    """
    source = _function_node(modules, source_function_id)
    sink = _function_node(modules, sink_function_id)
    if source is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:{source_function_id}"
        )
    if sink is None:
        raise RuntimeError(
            f"MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:{sink_function_id}"
        )

    source_module, source_node = source
    sink_module, sink_node = sink

    producer_assignments: list[ast.Assign] = []
    for item in ast.walk(source_node):
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Call)
        ):
            continue
        call_name = _call_name(item.value)
        if call_name is not None and _resolve_name(source_module, call_name) == producer_id:
            producer_assignments.append(item)
    if len(producer_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:producer_assignment"
        )
    producer_assignment = producer_assignments[0]
    producer_name = producer_assignment.targets[0].id

    wrapper_assignments: list[ast.Assign] = []
    for item in ast.walk(sink_node):
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Call)
        ):
            continue
        call_name = _call_name(item.value)
        if call_name is not None and _resolve_name(sink_module, call_name) == source_function_id:
            wrapper_assignments.append(item)
    if len(wrapper_assignments) != 1:
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:wrapper_assignment"
        )
    wrapper_assignment = wrapper_assignments[0]
    wrapper_name = wrapper_assignment.targets[0].id

    dict_candidates: list[tuple[ast.Assign, str]] = []
    for item in ast.walk(source_node):
        if not (
            isinstance(item, ast.Assign)
            and len(item.targets) == 1
            and isinstance(item.targets[0], ast.Name)
            and isinstance(item.value, ast.Dict)
        ):
            continue
        for key_node, value_node in zip(item.value.keys, item.value.values):
            key = _literal_string(key_node)
            if key is None:
                continue
            if isinstance(value_node, ast.Name) and value_node.id == producer_name:
                dict_candidates.append((item, key))

    direct_source_returns = [
        item
        for item in ast.walk(source_node)
        if isinstance(item, ast.Return)
        and isinstance(item.value, ast.Name)
        and item.value.id == producer_name
    ]

    if len(dict_candidates) == 1 and not direct_source_returns:
        dict_assignment, dict_key = dict_candidates[0]
        envelope_name = dict_assignment.targets[0].id
        source_returns = [
            item
            for item in ast.walk(source_node)
            if isinstance(item, ast.Return)
            and isinstance(item.value, ast.Name)
            and item.value.id == envelope_name
        ]
        if len(source_returns) != 1:
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:source_return"
            )
        source_return = source_returns[0]

        subscript_assignments: list[ast.Assign] = []
        for item in ast.walk(sink_node):
            if not (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and isinstance(item.value, ast.Subscript)
                and isinstance(item.value.value, ast.Name)
                and item.value.value.id == wrapper_name
                and _literal_string(item.value.slice) == dict_key
            ):
                continue
            subscript_assignments.append(item)
        if len(subscript_assignments) != 1:
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:subscript_assignment"
            )
        subscript_assignment = subscript_assignments[0]
        value_name = subscript_assignment.targets[0].id

        sink_returns = [
            item
            for item in ast.walk(sink_node)
            if isinstance(item, ast.Return)
            and isinstance(item.value, ast.Name)
            and item.value.id == value_name
        ]
        if len(sink_returns) != 1:
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:sink_return"
            )
        sink_return = sink_returns[0]

        if not (
            producer_assignment.lineno < dict_assignment.lineno < source_return.lineno
            and wrapper_assignment.lineno < subscript_assignment.lineno < sink_return.lineno
        ):
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:ordering"
            )

        return [
            producer_id,
            f"{source_function_id}:{producer_name}",
            f"{source_function_id}:{envelope_name}[{dict_key!r}]",
            f"{source_function_id}:return",
            f"{sink_function_id}:{wrapper_name}",
            f"{sink_function_id}:{value_name}",
            f"{sink_function_id}:return",
        ]

    if not dict_candidates and len(direct_source_returns) == 1:
        source_return = direct_source_returns[0]

        fstring_assignments: list[ast.Assign] = []
        for item in ast.walk(sink_node):
            if not (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and isinstance(item.value, ast.JoinedStr)
            ):
                continue
            formatted_names = [
                formatted.value.id
                for formatted in item.value.values
                if isinstance(formatted, ast.FormattedValue)
                and isinstance(formatted.value, ast.Name)
            ]
            if formatted_names == [wrapper_name]:
                fstring_assignments.append(item)

        cache_writes: list[tuple[ast.Assign, str, str]] = []
        for item in ast.walk(sink_node):
            if not (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Subscript)
                and isinstance(item.targets[0].value, ast.Name)
                and isinstance(item.value, ast.Name)
                and item.value.id == wrapper_name
            ):
                continue
            cache_name = item.targets[0].value.id
            cache_key = _literal_string(item.targets[0].slice)
            if cache_key is None:
                continue
            module_value = _module_assignments(sink_module).get(cache_name)
            if not isinstance(module_value, ast.Dict):
                continue
            if "cache" not in cache_name.lower():
                continue
            cache_writes.append((item, cache_name, cache_key))

        persistence_assignments: list[tuple[ast.Assign, str]] = []
        for item in ast.walk(sink_node):
            if not (
                isinstance(item, ast.Assign)
                and len(item.targets) == 1
                and isinstance(item.targets[0], ast.Name)
                and isinstance(item.value, ast.Call)
                and len(item.value.args) == 1
                and not item.value.keywords
                and isinstance(item.value.args[0], ast.Name)
                and item.value.args[0].id == wrapper_name
            ):
                continue
            call_name = _call_name(item.value)
            if call_name is None:
                continue
            resolved = _resolve_name(sink_module, call_name)
            if resolved is None:
                continue
            persistence_name = resolved.rsplit(".", 1)[-1]
            if "persist" not in persistence_name.lower():
                continue
            persistence_function = _function_node(modules, resolved)
            if persistence_function is None:
                continue
            _, persistence_node = persistence_function
            if len(persistence_node.args.args) != 1:
                continue
            parameter_name = persistence_node.args.args[0].arg
            persistence_returns = [
                returned
                for returned in ast.walk(persistence_node)
                if isinstance(returned, ast.Return)
                and isinstance(returned.value, ast.Name)
                and returned.value.id == parameter_name
            ]
            if len(persistence_returns) != 1:
                continue
            persistence_assignments.append((item, persistence_name))

        if (
            len(fstring_assignments) == 1
            and not cache_writes
            and not persistence_assignments
        ):
            fstring_assignment = fstring_assignments[0]
            message_name = fstring_assignment.targets[0].id

            sink_returns = [
                item
                for item in ast.walk(sink_node)
                if isinstance(item, ast.Return)
                and isinstance(item.value, ast.Name)
                and item.value.id == message_name
            ]
            if len(sink_returns) != 1:
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:sink_return"
                )
            sink_return = sink_returns[0]

            if not (
                producer_assignment.lineno < source_return.lineno
                and wrapper_assignment.lineno < fstring_assignment.lineno < sink_return.lineno
            ):
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:ordering"
                )

            return [
                producer_id,
                f"{source_function_id}:{producer_name}",
                f"{source_function_id}:return",
                f"{sink_function_id}:{wrapper_name}",
                f"{sink_function_id}:{message_name}:f-string",
                f"{sink_function_id}:return",
            ]

        if (
            not fstring_assignments
            and len(cache_writes) == 1
            and not persistence_assignments
        ):
            cache_write, cache_name, cache_key = cache_writes[0]
            cache_reads: list[ast.Assign] = []
            for item in ast.walk(sink_node):
                if not (
                    isinstance(item, ast.Assign)
                    and len(item.targets) == 1
                    and isinstance(item.targets[0], ast.Name)
                    and isinstance(item.value, ast.Subscript)
                    and isinstance(item.value.value, ast.Name)
                    and item.value.value.id == cache_name
                    and _literal_string(item.value.slice) == cache_key
                ):
                    continue
                cache_reads.append(item)
            if len(cache_reads) != 1:
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:cache_read"
                )
            cache_read = cache_reads[0]
            cached_name = cache_read.targets[0].id

            sink_returns = [
                item
                for item in ast.walk(sink_node)
                if isinstance(item, ast.Return)
                and isinstance(item.value, ast.Name)
                and item.value.id == cached_name
            ]
            if len(sink_returns) != 1:
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:sink_return"
                )
            sink_return = sink_returns[0]

            if not (
                producer_assignment.lineno < source_return.lineno
                and wrapper_assignment.lineno
                < cache_write.lineno
                < cache_read.lineno
                < sink_return.lineno
            ):
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:ordering"
                )

            return [
                producer_id,
                f"{source_function_id}:{producer_name}",
                f"{source_function_id}:return",
                f"{sink_function_id}:{wrapper_name}",
                f"{sink_function_id}:{cache_name}[{cache_key!r}]:cache",
                f"{sink_function_id}:{cached_name}",
                f"{sink_function_id}:return",
            ]

        if (
            not fstring_assignments
            and not cache_writes
            and len(persistence_assignments) == 1
        ):
            persistence_assignment, persistence_name = persistence_assignments[0]
            persisted_name = persistence_assignment.targets[0].id
            sink_returns = [
                item
                for item in ast.walk(sink_node)
                if isinstance(item, ast.Return)
                and isinstance(item.value, ast.Name)
                and item.value.id == persisted_name
            ]
            if len(sink_returns) != 1:
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:sink_return"
                )
            sink_return = sink_returns[0]

            if not (
                producer_assignment.lineno < source_return.lineno
                and wrapper_assignment.lineno
                < persistence_assignment.lineno
                < sink_return.lineno
            ):
                raise RuntimeError(
                    "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:ordering"
                )

            return [
                producer_id,
                f"{source_function_id}:{producer_name}",
                f"{source_function_id}:return",
                f"{sink_function_id}:{wrapper_name}",
                f"{sink_function_id}:{persistence_name}:persistence",
                f"{sink_function_id}:{persisted_name}",
                f"{sink_function_id}:return",
            ]

        if fstring_assignments or cache_writes or persistence_assignments:
            raise RuntimeError(
                "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:sink_shape_ambiguous"
            )

    raise RuntimeError(
        "MEI_REACHABILITY_UNRESOLVED_VALUE_PROVENANCE:source_shape"
    )


def _persisted_mei_report_publication_source(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict | None:
    """Return persistence evidence when a route publishes stored MEI-capable results."""
    has_relatorio_model = any(
        (
            isinstance(item, ast.Name)
            and item.id == "RelatorioAnalise"
        )
        or (
            isinstance(item, ast.Attribute)
            and item.attr == "RelatorioAnalise"
        )
        for item in ast.walk(node)
    )
    has_resultado_json = any(
        isinstance(item, ast.Attribute) and item.attr == "resultado_json"
        for item in ast.walk(node)
    )
    if not (has_relatorio_model and has_resultado_json):
        return None

    mei_filter = any(
        isinstance(item, ast.Compare)
        and isinstance(item.left, ast.Attribute)
        and item.left.attr == "analysis_type"
        and any(
            (
                isinstance(comparator, ast.Name)
                and comparator.id == "ANALYSIS_TYPE_MEI_TAX"
            )
            or (
                isinstance(comparator, ast.Constant)
                and comparator.value == "mei_tax"
            )
            for comparator in item.comparators
        )
        for item in ast.walk(node)
    )

    source = {
        "model": "app.models.RelatorioAnalise",
        "field": "resultado_json",
        "lineage_proven": False,
    }
    if mei_filter:
        return {
            **source,
            "analysis_type": "mei_tax",
        }
    return {
        **source,
        "analysis_type_filter": None,
        "may_include_analysis_type": "mei_tax",
    }


def _gate_a_blocked_by_paths(paths: list[dict]) -> bool:
    """Return whether a qualified MEI producer reaches a Gate A sink."""
    gate_a_sinks = {"PUBLICATION", "DECISION", "CACHE", "PERSISTENCE"}
    return any(
        item["mei_reachability"] == "REACHABLE_MEI"
        and item["producer_ids"]
        and any(kind in gate_a_sinks for kind in item["sink_kinds"])
        for item in paths
    )


def build_census() -> dict:
    modules = _parse_app()
    alternative_producers = _alternative_producer_inventory(
        modules,
        canonical_producer_id=PRODUCER_ID,
    )
    mounted = _mounted_routers(modules)
    background_roots = [
        _background_root_inventory(
            modules,
            function_id="app.agents.agent_scheduler.AgentScheduler.iniciar_loop",
        )
    ]
    registered_background_roots = _fastapi_background_root_inventory(
        modules,
        mounted=mounted,
    )
    registered_background_roots.extend(
        _rq_background_root_inventory(
            modules,
            mounted=mounted,
        )
    )
    for root in registered_background_roots:
        root.update(
            _background_downstream_inventory(
                modules,
                function_id=root["function_id"],
            )
        )
    background_roots.extend(registered_background_roots)
    background_root_ids = [item["function_id"] for item in background_roots]
    if len(background_root_ids) != len(set(background_root_ids)):
        raise RuntimeError(
            "MEI_REACHABILITY_UNRESOLVED_BACKGROUND_ROOT_DUPLICATE:"
            f"{','.join(sorted(background_root_ids))}"
        )
    background_roots.sort(key=lambda item: item["function_id"])
    paths: list[dict] = []
    mounted_entrypoints: set[str] = set()

    for module_name, (router_object, prefix) in sorted(mounted.items()):
        module = modules.get(module_name)
        if module is None:
            raise RuntimeError(f"MEI_REACHABILITY_ROUTER_MODULE_MISSING:{module_name}")
        router_prefix = _router_intrinsic_prefix(module, router_object)

        for local_name, node in sorted(module.functions.items()):
            if "." in local_name:
                continue
            route_path = _route_decorator(node, router_object=router_object)
            if route_path is None:
                continue
            entrypoint = f"{prefix}{router_prefix}{route_path}" or "/"
            mounted_entrypoints.add(entrypoint)
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

            alternative_producer_id = _direct_returned_alternative_producer(
                module,
                node,
                alternative_producers,
                function_id=function_id,
            )
            if alternative_producer_id is not None:
                canonical_ids = alternative_producers[alternative_producer_id]
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "REACHABLE_MEI",
                        "blocked_before_producer": False,
                        "blocker_code": None,
                        "producer_ids": canonical_ids,
                        "sink_kinds": ["PUBLICATION"],
                        "trace": [function_id, alternative_producer_id, *canonical_ids],
                    }
                )
                continue

            if entrypoint == "/perguntar":
                trace = _assistant_trace(modules, function_id)
                persistence = _assistant_orm_persistence_inventory(
                    modules,
                    route_function_id=function_id,
                )
                sink_kinds = _assistant_sink_kinds(modules)
                if persistence["sink_operations"]:
                    sink_kinds = [*sink_kinds, "PERSISTENCE"]
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "REACHABLE_MEI",
                        "blocked_before_producer": False,
                        "blocker_code": None,
                        "producer_ids": [PRODUCER_ID],
                        "sink_kinds": sink_kinds,
                        "trace": trace,
                        "persistence_inventory": persistence,
                    }
                )
                continue

            if entrypoint in {
                "/formalizacao/comparar-regimes",
                "/formalizacao/simular-empresa",
            }:
                trace = _formalizacao_compare_trace(modules, function_id)
                persistence = _formalizacao_orm_persistence_inventory(
                    modules,
                    route_function_id=function_id,
                )
                decision_provenance = _regime_decision_provenance(modules)
                sink_kinds = ["DECISION"]
                if persistence["sink_operations"]:
                    sink_kinds = [*sink_kinds, "PERSISTENCE"]
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "REACHABLE_MEI",
                        "blocked_before_producer": False,
                        "blocker_code": None,
                        "producer_ids": [PRODUCER_ID],
                        "sink_kinds": sink_kinds,
                        "trace": trace,
                        "decision_provenance": decision_provenance,
                        "persistence_inventory": persistence,
                    }
                )
                continue

            if function_id == "app.routes.metrics_router.obter_metricas":
                system_metrics_inventory = _system_metrics_no_canonical_mei_inventory(
                    modules,
                    route_function_id=function_id,
                )
                paths.append({
                    "entrypoint": entrypoint,
                    "function_id": function_id,
                    "blocked_before_producer": False,
                    "blocker_code": None,
                    **system_metrics_inventory,
                })
                continue
            if function_id == "app.routers.insights_router.obter_insights":
                insights_inventory = _insights_engine_mei_sink_inventory(
                    modules,
                    route_function_id=function_id,
                )
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "blocked_before_producer": False,
                        "blocker_code": None,
                        **insights_inventory,
                    }
                )
                continue
            if function_id == "app.routes.relatorio_router.obter_relatorio_por_tipo":
                relatorio_inventory = _relatorio_analysis_type_mei_sink_inventory(
                    modules,
                    route_function_id=function_id,
                )
                paths.append({
                    "entrypoint": entrypoint,
                    "function_id": function_id,
                    "blocked_before_producer": False,
                    "blocker_code": None,
                    **relatorio_inventory,
                })
                continue
            if function_id == "app.routes.relatorio_router.relatorio_pdf":
                relatorio_pdf_inventory = _relatorio_pdf_mei_persistence_inventory(
                    modules,
                    route_function_id=function_id,
                )
                paths.append({
                    "entrypoint": entrypoint,
                    "function_id": function_id,
                    "blocked_before_producer": False,
                    "blocker_code": None,
                    **relatorio_pdf_inventory,
                })
                continue
            persistence_source = _persisted_mei_report_publication_source(node)
            if persistence_source is not None:
                paths.append(
                    {
                        "entrypoint": entrypoint,
                        "function_id": function_id,
                        "mei_reachability": "UNRESOLVED_MEI",
                        "blocked_before_producer": False,
                        "blocker_code": "PERSISTED_MEI_PROVENANCE_UNPROVEN",
                        "producer_ids": [],
                        "sink_kinds": ["PUBLICATION"],
                        "trace": [function_id],
                        "persistence_source": persistence_source,
                    }
                )
                continue

            default_inventory = _default_route_reachability_inventory(
                modules,
                function_id=function_id,
            )
            paths.append(
                {
                    "entrypoint": entrypoint,
                    "function_id": function_id,
                    "blocked_before_producer": False,
                    "blocker_code": None,
                    "sink_kinds": [],
                    "trace": [function_id],
                    **default_inventory,
                }
            )

    paths.sort(key=lambda item: item["entrypoint"])
    classified_entrypoints = {item["entrypoint"] for item in paths}
    unclassified_entrypoints = sorted(
        mounted_entrypoints - classified_entrypoints
    )
    route_coverage_complete = not unclassified_entrypoints
    blocked = _gate_a_blocked_by_paths(paths)
    scan_complete = (
        all(
            item.get("persistence_inventory", {}).get("scan_complete", True)
            for item in paths
        )
        and all(
            item.get("downstream_scan_complete", True)
            for item in background_roots
        )
        and all(
            item.get("mei_reachability") != "UNRESOLVED_MEI"
            for item in paths
        )
        and route_coverage_complete
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "scan_complete": scan_complete,
        "status": "UNRESOLVED" if not scan_complete else ("BLOCKED" if blocked else "UNRESOLVED"),
        "route_coverage_complete": route_coverage_complete,
        "unclassified_entrypoints": unclassified_entrypoints,
        "alternative_producers": alternative_producers,
        "background_roots": background_roots,
        "paths": paths,
    }
