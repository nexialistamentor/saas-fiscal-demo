"""Censo deterministico de autoridade normativa do motor MEI.

Nao consulta rede.
Nao usa LLM.
Nao altera producao.
Apenas descobre e classifica evidencia fisica do repositorio.
"""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from collections import Counter
from pathlib import Path
from datetime import date

from pydantic import ValidationError

from app.schemas.source_authority_schema import (
    NormativeBindingBatchRequest,
    NormativeBindingReasonCode,
)
from app.services.source_authority_guard import validar_bindings_normativos


ROOT = Path(__file__).resolve().parents[2]
CONSTANTS_PATH = ROOT / "app/services/tax_engines/mei_constants.py"


@dataclass(frozen=True)
class CallSiteRecord:
    arquivo: str
    linha: int


@dataclass(frozen=True, order=True)
class UsageRecord:
    constante_id: str
    arquivo: str
    linha: int
    categoria: str
    evidencia: str


@dataclass(frozen=True)
class ConstantRecord:
    constante_id: str
    arquivo_definicao: str
    linha_definicao: int
    call_sites: tuple[CallSiteRecord, ...]


@dataclass(frozen=True, order=True)
class CensusFinding:
    code: str
    arquivo: str
    linha: int | None
    detalhe: str


@dataclass(frozen=True)
class CallSiteScanReport:
    call_sites: dict[str, tuple[CallSiteRecord, ...]]
    findings: tuple[CensusFinding, ...]
    files_discovered: int
    files_parsed: int
    scan_complete: bool


@dataclass(frozen=True)
class BindingDiscoveryReport:
    bindings: tuple[dict, ...]
    sources: dict[str, dict]
    findings: tuple[CensusFinding, ...]


@dataclass(frozen=True, order=True)
class UsageIdentity:
    constante_id: str
    arquivo: str
    linha: int


@dataclass(frozen=True)
class ReconciliationReport:
    structural_total: int
    semantic_total: int
    unaccounted: tuple[UsageIdentity, ...]
    orphan: tuple[UsageIdentity, ...]
    duplicates: tuple[UsageIdentity, ...]


_USAGE_CATEGORIES = frozenset(
    {"DECISION", "CALCULATION", "PRESENTATION", "INFRASTRUCTURE", "UNRESOLVED"}
)


def _classify_constant_usages_in_tree(
    *, tree: ast.AST, constant_names: set[str], arquivo: str,
    canonical_names: dict[int, str] | None = None,
) -> tuple[UsageRecord, ...]:
    """Classifica cada load canónico pelo seu contexto AST imediato comprovável."""
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    identities = canonical_names or {
        id(node): node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id in constant_names
    }
    records: list[UsageRecord] = []

    def contains(container: ast.AST | None, target: ast.AST) -> bool:
        return container is not None and any(part is target for part in ast.walk(container))

    def assigned_lineage(node: ast.AST) -> tuple[str, str] | None:
        cursor = parents.get(node)
        assignment: ast.Assign | ast.AnnAssign | ast.NamedExpr | None = None
        while cursor is not None:
            if isinstance(cursor, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                assignment = cursor
                break
            if isinstance(cursor, ast.stmt):
                break
            cursor = parents.get(cursor)
        if assignment is None:
            return None
        targets = assignment.targets if isinstance(assignment, ast.Assign) else [assignment.target]
        names = sorted(
            part.id for target in targets for part in ast.walk(target)
            if isinstance(part, ast.Name) and isinstance(part.ctx, ast.Store)
        )
        if not names:
            return None
        for name in names:
            circulated = any(
                isinstance(part, ast.Name) and isinstance(part.ctx, ast.Load)
                and part.id == name and not contains(assignment, part)
                for part in ast.walk(tree)
            )
            if circulated:
                return name, type(assignment.value).__name__
        return None

    for node in ast.walk(tree):
        constant = identities.get(id(node))
        if constant is None:
            continue

        category = "UNRESOLVED"
        evidence_node = parents.get(node)
        cursor = evidence_node
        ancestors: list[ast.AST] = []
        statement: ast.stmt | None = None
        while cursor is not None:
            if isinstance(cursor, ast.stmt):
                statement = cursor
                break
            ancestors.append(cursor)
            cursor = parents.get(cursor)

        lineage = assigned_lineage(node)
        in_branch_test = (
            isinstance(statement, (ast.If, ast.While))
            and contains(statement.test, node)
        )
        in_if_expression_test = any(
            isinstance(item, ast.IfExp) and contains(item.test, node)
            for item in ancestors
        )

        if lineage is not None:
            category = "UNRESOLVED"
            evidence_node = None
            evidence = f"UNRESOLVED_LINEAGE:{lineage[0]}:{lineage[1]}"
        elif any(isinstance(item, ast.FormattedValue) for item in ancestors):
            category = "PRESENTATION"
        elif in_branch_test or in_if_expression_test or any(isinstance(item, (ast.Compare, ast.BoolOp)) for item in ancestors):
            category = "DECISION"
        elif any(isinstance(item, (ast.BinOp, ast.UnaryOp)) for item in ancestors):
            category = "CALCULATION"
        elif any(isinstance(item, (ast.Dict, ast.List, ast.Tuple, ast.Set)) for item in ancestors):
            category = "INFRASTRUCTURE"
        elif isinstance(evidence_node, ast.Call) and isinstance(evidence_node.func, ast.Name):
            if evidence_node.func.id in {"int", "float"}:
                category = "CALCULATION"
            elif evidence_node.func.id in {"str", "repr", "format"}:
                category = "PRESENTATION"

        if lineage is None:
            evidence = type(evidence_node).__name__ if evidence_node is not None else "Root"
        records.append(UsageRecord(constant, arquivo, node.lineno, category, evidence))

    return tuple(sorted(records, key=lambda item: (item.constante_id, item.arquivo, item.linha, item.categoria, item.evidencia)))


_FATAL_SCAN_CODES = frozenset(
    {
        "MEI_NORMATIVE_CENSUS_APP_ROOT_MISSING",
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE",
    }
)


def _finding(
    code: str,
    *,
    arquivo: str,
    linha: int | None = None,
    detalhe: str = "",
) -> CensusFinding:
    if not code.startswith("MEI_NORMATIVE_CENSUS_"):
        raise ValueError(f"codigo de finding invalido: {code}")

    return CensusFinding(
        code=code,
        arquivo=arquivo,
        linha=linha,
        detalhe=detalhe,
    )


def _discover_call_sites(
    constant_names: set[str],
) -> dict[str, tuple[CallSiteRecord, ...]]:
    found: dict[str, list[CallSiteRecord]] = {
        name: [] for name in constant_names
    }

    app_root = ROOT / "app"
    canonical_module = "app.services.tax_engines.mei_constants"

    if not app_root.is_dir():
        raise RuntimeError(
            f"MEI_NORMATIVE_CENSUS_APP_ROOT_MISSING:{app_root}"
        )

    paths = tuple(sorted(app_root.rglob("*.py")))
    parsed_files: dict[Path, ast.AST] = {}

    for candidate in paths:
        relative = str(candidate.relative_to(ROOT)).replace("\\", "/")

        try:
            source = candidate.read_text(encoding="utf-8")
            parsed_files[candidate] = ast.parse(
                source,
                filename=str(candidate),
            )
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            raise RuntimeError(
                "MEI_NORMATIVE_CENSUS_SCAN_FAILED:"
                f"{relative}:{type(exc).__name__}:{exc}"
            ) from exc

    for candidate, candidate_tree in parsed_files.items():
        relative = str(
            candidate.relative_to(ROOT)
        ).replace("\\", "/")

        importlib_aliases: set[str] = set()
        import_module_aliases: set[str] = set()

        for node in candidate_tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "importlib":
                        importlib_aliases.add(
                            alias.asname or alias.name
                        )

            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == "importlib"
            ):
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_aliases.add(
                            alias.asname or alias.name
                        )

        for node in ast.walk(candidate_tree):
            if not isinstance(node, ast.Call):
                continue

            dynamic_import_kind: str | None = None

            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in importlib_aliases
                and node.func.attr == "import_module"
            ):
                dynamic_import_kind = "importlib.import_module"

            elif (
                isinstance(node.func, ast.Name)
                and node.func.id in import_module_aliases
            ):
                dynamic_import_kind = "import_module"

            elif (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            ):
                dynamic_import_kind = "__import__"

            if dynamic_import_kind is None:
                continue

            if not node.args:
                raise RuntimeError(
                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT:"
                    f"{relative}:{node.lineno}:"
                    f"{dynamic_import_kind}:MISSING_MODULE"
                )

            module_argument = node.args[0]

            if (
                isinstance(module_argument, ast.Constant)
                and isinstance(module_argument.value, str)
            ):
                if module_argument.value == canonical_module:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT:"
                        f"{relative}:{node.lineno}:"
                        f"{dynamic_import_kind}:{canonical_module}"
                    )
            else:
                raise RuntimeError(
                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT:"
                    f"{relative}:{node.lineno}:"
                    f"{dynamic_import_kind}:NON_LITERAL_MODULE"
                )

    def module_name(candidate: Path) -> str:
        relative_module = candidate.relative_to(ROOT).with_suffix("")
        parts = list(relative_module.parts)

        if parts and parts[-1] == "__init__":
            parts.pop()

        if not parts:
            raise RuntimeError(
                "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE:"
                f"{candidate}"
            )

        return ".".join(parts)

    potential_reexports: dict[str, dict[str, str]] = {}
    exporter_paths: dict[str, str] = {}

    for candidate, candidate_tree in parsed_files.items():
        if candidate == CONSTANTS_PATH:
            continue

        exports: dict[str, str] = {}

        for node in candidate_tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue

            absolute_direct = (
                node.level == 0
                and node.module == canonical_module
            )
            relative_direct = (
                node.level == 1
                and node.module == "mei_constants"
                and candidate.parent == CONSTANTS_PATH.parent
            )

            if not (absolute_direct or relative_direct):
                continue

            for alias in node.names:
                if alias.name in constant_names:
                    exports[alias.asname or alias.name] = alias.name

        if exports:
            candidate_module = module_name(candidate)
            potential_reexports[candidate_module] = exports
            exporter_paths[candidate_module] = str(
                candidate.relative_to(ROOT)
            ).replace("\\", "/")

    for consumer_path, consumer_tree in parsed_files.items():
        for node in ast.walk(consumer_tree):
            if not isinstance(node, ast.ImportFrom):
                continue

            if node.level != 0 or node.module not in potential_reexports:
                continue

            exports = potential_reexports[node.module]

            for alias in node.names:
                if alias.name not in exports:
                    continue

                canonical_name = exports[alias.name]

                raise RuntimeError(
                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_REEXPORT:"
                    f"{exporter_paths[node.module]}:"
                    f"{canonical_name}:consumer="
                    f"{str(consumer_path.relative_to(ROOT)).replace(chr(92), '/')}:"
                    f"{node.lineno}"
                )

    for path in paths:
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        tree = parsed_files[path]

        direct_aliases: dict[str, str] = {}
        module_aliases: set[str] = set()

        if path != CONSTANTS_PATH:
            top_level_nodes = set(tree.body)

            for node in ast.walk(tree):
                if not isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue

                is_canonical = False

                if isinstance(node, ast.Import):
                    is_canonical = any(
                        alias.name == canonical_module
                        for alias in node.names
                    )

                elif isinstance(node, ast.ImportFrom):
                    absolute_direct = (
                        node.level == 0
                        and node.module == canonical_module
                    )
                    relative_direct = (
                        node.level == 1
                        and node.module == "mei_constants"
                        and path.parent == CONSTANTS_PATH.parent
                    )
                    absolute_package = (
                        node.level == 0
                        and node.module == "app.services.tax_engines"
                        and any(
                            alias.name == "mei_constants"
                            for alias in node.names
                        )
                    )
                    relative_package = (
                        node.level == 1
                        and node.module is None
                        and path.parent == CONSTANTS_PATH.parent
                        and any(
                            alias.name == "mei_constants"
                            for alias in node.names
                        )
                    )

                    is_canonical = (
                        absolute_direct
                        or relative_direct
                        or absolute_package
                        or relative_package
                    )

                if is_canonical and node not in top_level_nodes:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT_SCOPE:"
                        f"{relative}:{node.lineno}"
                    )

            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name != canonical_module:
                            continue

                        if alias.asname is None:
                            raise RuntimeError(
                                "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT:"
                                f"{relative}:{node.lineno}:"
                                "CANONICAL_MODULE_WITHOUT_ALIAS"
                            )

                        module_aliases.add(alias.asname)

                elif isinstance(node, ast.ImportFrom):
                    absolute_direct = (
                        node.level == 0
                        and node.module == canonical_module
                    )
                    relative_direct = (
                        node.level == 1
                        and node.module == "mei_constants"
                        and path.parent == CONSTANTS_PATH.parent
                    )

                    if absolute_direct or relative_direct:
                        for alias in node.names:
                            if alias.name == "*":
                                raise RuntimeError(
                                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT:"
                                    f"{relative}:{node.lineno}:STAR_IMPORT"
                                )

                            if alias.name in constant_names:
                                local_name = alias.asname or alias.name
                                direct_aliases[local_name] = alias.name

                    absolute_package = (
                        node.level == 0
                        and node.module == "app.services.tax_engines"
                    )
                    relative_package = (
                        node.level == 1
                        and node.module is None
                        and path.parent == CONSTANTS_PATH.parent
                    )

                    if absolute_package or relative_package:
                        for alias in node.names:
                            if alias.name != "mei_constants":
                                continue

                            local_name = alias.asname or alias.name
                            module_aliases.add(local_name)

        if path != CONSTANTS_PATH:
            for candidate in ast.walk(tree):
                rebound_name: str | None = None

                if (
                    isinstance(candidate, ast.Name)
                    and isinstance(candidate.ctx, (ast.Store, ast.Del))
                ):
                    rebound_name = candidate.id

                elif isinstance(candidate, ast.arg):
                    rebound_name = candidate.arg

                elif (
                    isinstance(candidate, ast.ExceptHandler)
                    and isinstance(candidate.name, str)
                ):
                    rebound_name = candidate.name

                if (
                    rebound_name in direct_aliases
                    or rebound_name in module_aliases
                ):
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_REBINDING:"
                        f"{relative}:{candidate.lineno}:{rebound_name}"
                    )

        for node in ast.walk(tree):
            if path != CONSTANTS_PATH:
                escape_value = None
                escape_kind: str | None = None

                if isinstance(node, ast.Return):
                    escape_value = node.value
                    escape_kind = "RETURN"

                elif isinstance(node, ast.Yield):
                    escape_value = node.value
                    escape_kind = "YIELD"

                elif isinstance(node, ast.YieldFrom):
                    escape_value = node.value
                    escape_kind = "YIELD_FROM"

                escaped_constant: str | None = None

                if escape_value is not None:
                    for candidate in ast.walk(escape_value):
                        if (
                            isinstance(candidate, ast.Name)
                            and isinstance(candidate.ctx, ast.Load)
                            and candidate.id in direct_aliases
                        ):
                            escaped_constant = direct_aliases[
                                candidate.id
                            ]
                            break

                        if (
                            isinstance(candidate, ast.Attribute)
                            and isinstance(candidate.ctx, ast.Load)
                            and isinstance(candidate.value, ast.Name)
                            and candidate.value.id in module_aliases
                            and candidate.attr in constant_names
                        ):
                            escaped_constant = candidate.attr
                            break

                if escaped_constant is not None:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_VALUE_ESCAPE:"
                        f"{relative}:{node.lineno}:"
                        f"{escaped_constant}:{escape_kind}"
                    )

                rebound_name: str | None = None

                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, (ast.Store, ast.Del))
                ):
                    rebound_name = node.id

                elif isinstance(node, ast.arg):
                    rebound_name = node.arg

                elif (
                    isinstance(node, ast.ExceptHandler)
                    and isinstance(node.name, str)
                ):
                    rebound_name = node.name

                if (
                    rebound_name in direct_aliases
                    or rebound_name in module_aliases
                ):
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_REBINDING:"
                        f"{relative}:{node.lineno}:{rebound_name}"
                    )

            if path != CONSTANTS_PATH:
                propagated_constant: str | None = None
                propagated_target: str | None = None

                assignment_value = None
                assignment_targets = []

                if isinstance(node, ast.Assign):
                    assignment_value = node.value
                    assignment_targets = list(node.targets)

                elif isinstance(node, ast.AnnAssign):
                    assignment_value = node.value
                    assignment_targets = [node.target]

                elif isinstance(node, ast.NamedExpr):
                    assignment_value = node.value
                    assignment_targets = [node.target]

                if assignment_value is not None:
                    if (
                        isinstance(assignment_value, ast.Name)
                        and isinstance(assignment_value.ctx, ast.Load)
                        and assignment_value.id in direct_aliases
                    ):
                        propagated_constant = direct_aliases[
                            assignment_value.id
                        ]

                    elif (
                        isinstance(assignment_value, ast.Attribute)
                        and isinstance(assignment_value.ctx, ast.Load)
                        and isinstance(assignment_value.value, ast.Name)
                        and assignment_value.value.id in module_aliases
                        and assignment_value.attr in constant_names
                    ):
                        propagated_constant = assignment_value.attr

                if propagated_constant is not None:
                    local_targets: list[str] = []

                    for target in assignment_targets:
                        for candidate in ast.walk(target):
                            if (
                                isinstance(candidate, ast.Name)
                                and isinstance(candidate.ctx, ast.Store)
                            ):
                                local_targets.append(candidate.id)

                    if local_targets:
                        propagated_target = sorted(local_targets)[0]

                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS:"
                        f"{relative}:{node.lineno}:"
                        f"{propagated_constant}:"
                        f"{propagated_target or 'UNRESOLVED_TARGET'}"
                    )

            if (
                path != CONSTANTS_PATH
                and isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id
                in {"getattr", "hasattr", "setattr", "delattr"}
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in module_aliases
            ):
                if len(node.args) < 2:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS:"
                        f"{relative}:{node.lineno}:"
                        f"{node.func.id}:MISSING_ATTRIBUTE"
                    )

                attribute = node.args[1]

                if (
                    isinstance(attribute, ast.Constant)
                    and isinstance(attribute.value, str)
                ):
                    if attribute.value in constant_names:
                        raise RuntimeError(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS:"
                            f"{relative}:{node.lineno}:"
                            f"{node.func.id}:{attribute.value}"
                        )
                else:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS:"
                        f"{relative}:{node.lineno}:"
                        f"{node.func.id}:NON_LITERAL_ATTRIBUTE"
                    )

            if isinstance(node, ast.Call):
                crossed_constant: str | None = None

                call_values = list(node.args)
                call_values.extend(
                    keyword.value
                    for keyword in node.keywords
                )

                for value in call_values:
                    if path == CONSTANTS_PATH:
                        if (
                            isinstance(value, ast.Name)
                            and isinstance(value.ctx, ast.Load)
                            and value.id in constant_names
                        ):
                            crossed_constant = value.id

                    else:
                        if (
                            isinstance(value, ast.Name)
                            and isinstance(value.ctx, ast.Load)
                            and value.id in direct_aliases
                        ):
                            crossed_constant = direct_aliases[value.id]

                        elif (
                            isinstance(value, ast.Attribute)
                            and isinstance(value.ctx, ast.Load)
                            and isinstance(value.value, ast.Name)
                            and value.value.id in module_aliases
                            and value.attr in constant_names
                        ):
                            crossed_constant = value.attr

                    if crossed_constant is not None:
                        break

                if crossed_constant is not None:
                    raise RuntimeError(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_CALL_BOUNDARY:"
                        f"{relative}:{node.lineno}:"
                        f"{crossed_constant}"
                    )

            if path == CONSTANTS_PATH:
                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id in constant_names
                ):
                    found[node.id].append(
                        CallSiteRecord(
                            arquivo=relative,
                            linha=node.lineno,
                        )
                    )
                continue

            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in direct_aliases
            ):
                canonical_name = direct_aliases[node.id]
                found[canonical_name].append(
                    CallSiteRecord(
                        arquivo=relative,
                        linha=node.lineno,
                    )
                )

            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in module_aliases
                and node.attr in constant_names
            ):
                found[node.attr].append(
                    CallSiteRecord(
                        arquivo=relative,
                        linha=node.lineno,
                    )
                )

    return {
        name: tuple(
            sorted(
                set(records),
                key=lambda item: (item.arquivo, item.linha),
            )
        )
        for name, records in found.items()
    }


def _discover_constant_definitions() -> tuple[tuple[str, int], ...]:
    try:
        source = CONSTANTS_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(CONSTANTS_PATH))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise RuntimeError(
            "MEI_NORMATIVE_CENSUS_SCAN_FAILED:"
            f"{str(CONSTANTS_PATH.relative_to(ROOT)).replace(chr(92), '/')}:"
            f"{type(exc).__name__}:{exc}"
        ) from exc

    definitions: list[tuple[str, int]] = []

    for node in tree.body:
        names: list[tuple[str, int]] = []

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append((target.id, node.lineno))

        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.append((node.target.id, node.lineno))

        for name, lineno in names:
            if name.isupper():
                definitions.append((name, lineno))

    definition_lines: dict[str, list[int]] = {}

    for name, lineno in definitions:
        definition_lines.setdefault(name, []).append(lineno)

    duplicates = {
        name: tuple(lines)
        for name, lines in definition_lines.items()
        if len(lines) > 1
    }

    if duplicates:
        details = ";".join(
            f"{name}:{','.join(str(line) for line in lines)}"
            for name, lines in sorted(duplicates.items())
        )
        raise RuntimeError(
            "MEI_NORMATIVE_CENSUS_DUPLICATE_DEFINITION:"
            f"{details}"
        )

    return tuple(definitions)



_FINDING_PRIORITY = {
    "MEI_NORMATIVE_CENSUS_APP_ROOT_MISSING": 0,
    "MEI_NORMATIVE_CENSUS_SCAN_FAILED": 1,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE": 2,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT": 3,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_REEXPORT": 4,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT_SCOPE": 5,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT": 6,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_REBINDING": 7,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_VALUE_ESCAPE": 8,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS": 9,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS": 10,
    "MEI_NORMATIVE_CENSUS_UNRESOLVED_CALL_BOUNDARY": 11,
}


def _finding_sort_key(item: CensusFinding) -> tuple:
    return (
        _FINDING_PRIORITY.get(item.code, 999),
        item.arquivo,
        item.linha if item.linha is not None else -1,
        item.detalhe,
    )


def _finding_runtime_message(item: CensusFinding) -> str:
    parts = [item.code, item.arquivo]

    if item.linha is not None:
        parts.append(str(item.linha))

    if item.detalhe:
        parts.append(item.detalhe)

    return ":".join(parts)


def _scan_call_sites_report(
    constant_names: set[str],
) -> CallSiteScanReport:
    app_root = ROOT / "app"
    canonical_module = "app.services.tax_engines.mei_constants"

    empty = {
        name: ()
        for name in sorted(constant_names)
    }

    if not app_root.is_dir():
        finding = _finding(
            "MEI_NORMATIVE_CENSUS_APP_ROOT_MISSING",
            arquivo=str(app_root),
        )
        return CallSiteScanReport(
            call_sites=empty,
            findings=(finding,),
            files_discovered=0,
            files_parsed=0,
            scan_complete=False,
        )

    paths = tuple(sorted(app_root.rglob("*.py")))
    parsed_files: dict[Path, ast.AST] = {}
    findings: set[CensusFinding] = set()

    def relative(candidate: Path) -> str:
        return str(
            candidate.relative_to(ROOT)
        ).replace("\\", "/")

    for candidate in paths:
        rel = relative(candidate)

        try:
            source = candidate.read_text(encoding="utf-8")
            parsed_files[candidate] = ast.parse(
                source,
                filename=str(candidate),
            )
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            findings.add(
                _finding(
                    "MEI_NORMATIVE_CENSUS_SCAN_FAILED",
                    arquivo=rel,
                    detalhe=f"{type(exc).__name__}:{exc}",
                )
            )

    def module_name(candidate: Path) -> str | None:
        try:
            rel = candidate.relative_to(ROOT).with_suffix("")
        except ValueError:
            findings.add(
                _finding(
                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE",
                    arquivo=str(candidate),
                    detalhe="OUTSIDE_ROOT",
                )
            )
            return None

        parts = list(rel.parts)

        if parts and parts[-1] == "__init__":
            parts.pop()

        if not parts:
            findings.add(
                _finding(
                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE",
                    arquivo=relative(candidate),
                    detalhe="EMPTY_MODULE_NAME",
                )
            )
            return None

        return ".".join(parts)

    def import_is_canonical(
        node: ast.Import | ast.ImportFrom,
        candidate: Path,
    ) -> bool:
        if isinstance(node, ast.Import):
            return any(
                alias.name == canonical_module
                for alias in node.names
            )

        absolute_direct = (
            node.level == 0
            and node.module == canonical_module
        )
        relative_direct = (
            node.level == 1
            and node.module == "mei_constants"
            and candidate.parent == CONSTANTS_PATH.parent
        )
        absolute_package = (
            node.level == 0
            and node.module == "app.services.tax_engines"
            and any(
                alias.name == "mei_constants"
                for alias in node.names
            )
        )
        relative_package = (
            node.level == 1
            and node.module is None
            and candidate.parent == CONSTANTS_PATH.parent
            and any(
                alias.name == "mei_constants"
                for alias in node.names
            )
        )

        return (
            absolute_direct
            or relative_direct
            or absolute_package
            or relative_package
        )

    aliases_by_path: dict[
        Path,
        tuple[dict[str, str], set[str]],
    ] = {}

    reexports: dict[str, tuple[str, dict[str, str]]] = {}

    for candidate, tree in parsed_files.items():
        rel = relative(candidate)
        direct_aliases: dict[str, str] = {}
        module_aliases: set[str] = set()

        if candidate != CONSTANTS_PATH:
            top_level_ids = {
                id(node)
                for node in tree.body
            }

            for node in ast.walk(tree):
                if (
                    isinstance(node, (ast.Import, ast.ImportFrom))
                    and import_is_canonical(node, candidate)
                    and id(node) not in top_level_ids
                ):
                    findings.add(
                        _finding(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT_SCOPE",
                            arquivo=rel,
                            linha=node.lineno,
                            detalhe="CANONICAL_IMPORT_NOT_TOP_LEVEL",
                        )
                    )

            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name != canonical_module:
                            continue

                        if alias.asname is None:
                            findings.add(
                                _finding(
                                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT",
                                    arquivo=rel,
                                    linha=node.lineno,
                                    detalhe="CANONICAL_MODULE_WITHOUT_ALIAS",
                                )
                            )
                            continue

                        module_aliases.add(alias.asname)

                elif isinstance(node, ast.ImportFrom):
                    absolute_direct = (
                        node.level == 0
                        and node.module == canonical_module
                    )
                    relative_direct = (
                        node.level == 1
                        and node.module == "mei_constants"
                        and candidate.parent == CONSTANTS_PATH.parent
                    )

                    if absolute_direct or relative_direct:
                        for alias in node.names:
                            if alias.name == "*":
                                findings.add(
                                    _finding(
                                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_IMPORT",
                                        arquivo=rel,
                                        linha=node.lineno,
                                        detalhe="STAR_IMPORT",
                                    )
                                )
                                continue

                            if alias.name in constant_names:
                                direct_aliases[
                                    alias.asname or alias.name
                                ] = alias.name

                    absolute_package = (
                        node.level == 0
                        and node.module == "app.services.tax_engines"
                    )
                    relative_package = (
                        node.level == 1
                        and node.module is None
                        and candidate.parent == CONSTANTS_PATH.parent
                    )

                    if absolute_package or relative_package:
                        for alias in node.names:
                            if alias.name != "mei_constants":
                                continue

                            module_aliases.add(
                                alias.asname or alias.name
                            )

        aliases_by_path[candidate] = (
            direct_aliases,
            module_aliases,
        )

        if direct_aliases:
            mod = module_name(candidate)
            if mod is not None:
                reexports[mod] = (
                    rel,
                    dict(direct_aliases),
                )

    for consumer_path, tree in parsed_files.items():
        consumer_rel = relative(consumer_path)

        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue

            if node.level != 0 or node.module not in reexports:
                continue

            exporter_rel, exported_names = reexports[node.module]

            for alias in node.names:
                if alias.name not in exported_names:
                    continue

                findings.add(
                    _finding(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_REEXPORT",
                        arquivo=exporter_rel,
                        linha=node.lineno,
                        detalhe=(
                            f"{exported_names[alias.name]}:"
                            f"consumer={consumer_rel}"
                        ),
                    )
                )

    for candidate, tree in parsed_files.items():
        rel = relative(candidate)
        direct_aliases, module_aliases = aliases_by_path[candidate]

        importlib_aliases: set[str] = set()
        import_module_aliases: set[str] = set()

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "importlib":
                        importlib_aliases.add(
                            alias.asname or alias.name
                        )

            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module == "importlib"
            ):
                for alias in node.names:
                    if alias.name == "import_module":
                        import_module_aliases.add(
                            alias.asname or alias.name
                        )

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            kind: str | None = None

            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in importlib_aliases
                and node.func.attr == "import_module"
            ):
                kind = "importlib.import_module"

            elif (
                isinstance(node.func, ast.Name)
                and node.func.id in import_module_aliases
            ):
                kind = "import_module"

            elif (
                isinstance(node.func, ast.Name)
                and node.func.id == "__import__"
            ):
                kind = "__import__"

            if kind is None:
                continue

            if not node.args:
                findings.add(
                    _finding(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT",
                        arquivo=rel,
                        linha=node.lineno,
                        detalhe=f"{kind}:MISSING_MODULE",
                    )
                )
                continue

            module_arg = node.args[0]

            if (
                isinstance(module_arg, ast.Constant)
                and isinstance(module_arg.value, str)
            ):
                if module_arg.value == canonical_module:
                    findings.add(
                        _finding(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT",
                            arquivo=rel,
                            linha=node.lineno,
                            detalhe=f"{kind}:{canonical_module}",
                        )
                    )
            else:
                findings.add(
                    _finding(
                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_IMPORT",
                        arquivo=rel,
                        linha=node.lineno,
                        detalhe=f"{kind}:NON_LITERAL_MODULE",
                    )
                )

        if candidate != CONSTANTS_PATH:
            for node in ast.walk(tree):
                rebound_name: str | None = None

                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, (ast.Store, ast.Del))
                ):
                    rebound_name = node.id

                elif isinstance(node, ast.arg):
                    rebound_name = node.arg

                elif (
                    isinstance(node, ast.ExceptHandler)
                    and isinstance(node.name, str)
                ):
                    rebound_name = node.name

                if (
                    rebound_name in direct_aliases
                    or rebound_name in module_aliases
                ):
                    findings.add(
                        _finding(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_REBINDING",
                            arquivo=rel,
                            linha=node.lineno,
                            detalhe=rebound_name or "",
                        )
                    )

        def canonical_from_node(
            value: ast.AST | None,
        ) -> str | None:
            if value is None:
                return None

            if candidate == CONSTANTS_PATH:
                if (
                    isinstance(value, ast.Name)
                    and isinstance(value.ctx, ast.Load)
                    and value.id in constant_names
                ):
                    return value.id
                return None

            if (
                isinstance(value, ast.Name)
                and isinstance(value.ctx, ast.Load)
                and value.id in direct_aliases
            ):
                return direct_aliases[value.id]

            if (
                isinstance(value, ast.Attribute)
                and isinstance(value.ctx, ast.Load)
                and isinstance(value.value, ast.Name)
                and value.value.id in module_aliases
                and value.attr in constant_names
            ):
                return value.attr

            return None

        for node in ast.walk(tree):
            if candidate != CONSTANTS_PATH:
                escape_value: ast.AST | None = None
                escape_kind: str | None = None

                if isinstance(node, ast.Return):
                    escape_value = node.value
                    escape_kind = "RETURN"
                elif isinstance(node, ast.Yield):
                    escape_value = node.value
                    escape_kind = "YIELD"
                elif isinstance(node, ast.YieldFrom):
                    escape_value = node.value
                    escape_kind = "YIELD_FROM"

                if escape_value is not None:
                    escaped: str | None = None

                    for part in ast.walk(escape_value):
                        escaped = canonical_from_node(part)
                        if escaped is not None:
                            break

                    if escaped is not None:
                        findings.add(
                            _finding(
                                "MEI_NORMATIVE_CENSUS_UNRESOLVED_VALUE_ESCAPE",
                                arquivo=rel,
                                linha=node.lineno,
                                detalhe=f"{escaped}:{escape_kind}",
                            )
                        )

                assignment_value: ast.AST | None = None
                assignment_targets: list[ast.AST] = []

                if isinstance(node, ast.Assign):
                    assignment_value = node.value
                    assignment_targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    assignment_value = node.value
                    assignment_targets = [node.target]
                elif isinstance(node, ast.NamedExpr):
                    assignment_value = node.value
                    assignment_targets = [node.target]

                propagated = canonical_from_node(
                    assignment_value
                )

                if propagated is not None:
                    local_targets: list[str] = []

                    for target in assignment_targets:
                        for part in ast.walk(target):
                            if (
                                isinstance(part, ast.Name)
                                and isinstance(part.ctx, ast.Store)
                            ):
                                local_targets.append(part.id)

                    target_name = (
                        sorted(local_targets)[0]
                        if local_targets
                        else "UNRESOLVED_TARGET"
                    )

                    findings.add(
                        _finding(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_LOCAL_ALIAS",
                            arquivo=rel,
                            linha=node.lineno,
                            detalhe=f"{propagated}:{target_name}",
                        )
                    )

                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id
                    in {"getattr", "hasattr", "setattr", "delattr"}
                    and node.args
                    and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in module_aliases
                ):
                    if len(node.args) < 2:
                        findings.add(
                            _finding(
                                "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS",
                                arquivo=rel,
                                linha=node.lineno,
                                detalhe=f"{node.func.id}:MISSING_ATTRIBUTE",
                            )
                        )
                    else:
                        attribute = node.args[1]

                        if (
                            isinstance(attribute, ast.Constant)
                            and isinstance(attribute.value, str)
                        ):
                            if attribute.value in constant_names:
                                findings.add(
                                    _finding(
                                        "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS",
                                        arquivo=rel,
                                        linha=node.lineno,
                                        detalhe=(
                                            f"{node.func.id}:"
                                            f"{attribute.value}"
                                        ),
                                    )
                                )
                        else:
                            findings.add(
                                _finding(
                                    "MEI_NORMATIVE_CENSUS_UNRESOLVED_DYNAMIC_ACCESS",
                                    arquivo=rel,
                                    linha=node.lineno,
                                    detalhe=(
                                        f"{node.func.id}:"
                                        "NON_LITERAL_ATTRIBUTE"
                                    ),
                                )
                            )

            if isinstance(node, ast.Call):
                crossed: str | None = None

                values = list(node.args)
                values.extend(
                    keyword.value
                    for keyword in node.keywords
                )

                for value in values:
                    crossed = canonical_from_node(value)
                    if crossed is not None:
                        break

                safe_builtin_transform = (
                    isinstance(node.func, ast.Name)
                    and node.func.id
                    in {"str", "int", "float", "bool", "bytes", "repr", "format"}
                )

                if crossed is not None and not safe_builtin_transform:
                    findings.add(
                        _finding(
                            "MEI_NORMATIVE_CENSUS_UNRESOLVED_CALL_BOUNDARY",
                            arquivo=rel,
                            linha=node.lineno,
                            detalhe=crossed,
                        )
                    )

    found: dict[str, set[CallSiteRecord]] = {
        name: set()
        for name in constant_names
    }

    for candidate, tree in parsed_files.items():
        rel = relative(candidate)
        direct_aliases, module_aliases = aliases_by_path[candidate]

        for node in ast.walk(tree):
            if candidate == CONSTANTS_PATH:
                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id in constant_names
                ):
                    found[node.id].add(
                        CallSiteRecord(
                            arquivo=rel,
                            linha=node.lineno,
                        )
                    )
                continue

            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in direct_aliases
            ):
                found[
                    direct_aliases[node.id]
                ].add(
                    CallSiteRecord(
                        arquivo=rel,
                        linha=node.lineno,
                    )
                )

            elif (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and isinstance(node.value, ast.Name)
                and node.value.id in module_aliases
                and node.attr in constant_names
            ):
                found[node.attr].add(
                    CallSiteRecord(
                        arquivo=rel,
                        linha=node.lineno,
                    )
                )

    normalized_call_sites = {
        name: tuple(
            sorted(
                records,
                key=lambda item: (
                    item.arquivo,
                    item.linha,
                ),
            )
        )
        for name, records in found.items()
    }

    ordered_findings = tuple(
        sorted(
            findings,
            key=_finding_sort_key,
        )
    )

    fatal_codes = {
        "MEI_NORMATIVE_CENSUS_APP_ROOT_MISSING",
        "MEI_NORMATIVE_CENSUS_SCAN_FAILED",
        "MEI_NORMATIVE_CENSUS_UNRESOLVED_MODULE",
    }

    scan_complete = (
        len(parsed_files) == len(paths)
        and not any(
            item.code in fatal_codes
            for item in ordered_findings
        )
    )

    return CallSiteScanReport(
        call_sites=normalized_call_sites,
        findings=ordered_findings,
        files_discovered=len(paths),
        files_parsed=len(parsed_files),
        scan_complete=scan_complete,
    )


# Wrapper strict preservado para as catracas unitarias existentes.
def _discover_call_sites(
    constant_names: set[str],
) -> dict[str, tuple[CallSiteRecord, ...]]:
    report = _scan_call_sites_report(constant_names)

    if report.findings:
        raise RuntimeError(
            _finding_runtime_message(report.findings[0])
        )

    return report.call_sites

def discover_mei_constants() -> tuple[ConstantRecord, ...]:
    definitions = _discover_constant_definitions()

    call_sites = _discover_call_sites(
        {name for name, _ in definitions}
    )

    records = [
        ConstantRecord(
            constante_id=name,
            arquivo_definicao=str(
                CONSTANTS_PATH.relative_to(ROOT)
            ).replace("\\", "/"),
            linha_definicao=lineno,
            call_sites=call_sites[name],
        )
        for name, lineno in definitions
    ]

    return tuple(
        sorted(records, key=lambda item: item.constante_id)
    )


def _discover_usage_records(constant_names: set[str]) -> tuple[UsageRecord, ...]:
    canonical_module = "app.services.tax_engines.mei_constants"
    records: list[UsageRecord] = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        direct: dict[str, str] = {}
        modules: set[str] = set()
        if path != CONSTANTS_PATH:
            for node in tree.body:
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == canonical_module and alias.asname:
                            modules.add(alias.asname)
                elif isinstance(node, ast.ImportFrom):
                    direct_import = node.module == canonical_module or (
                        node.level == 1 and node.module == "mei_constants"
                        and path.parent == CONSTANTS_PATH.parent
                    )
                    package_import = node.module == "app.services.tax_engines" or (
                        node.level == 1 and node.module is None
                        and path.parent == CONSTANTS_PATH.parent
                    )
                    if direct_import:
                        for alias in node.names:
                            if alias.name in constant_names:
                                direct[alias.asname or alias.name] = alias.name
                    elif package_import:
                        for alias in node.names:
                            if alias.name == "mei_constants":
                                modules.add(alias.asname or alias.name)

        identities: dict[int, str] = {}
        for node in ast.walk(tree):
            if path == CONSTANTS_PATH and isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in constant_names:
                identities[id(node)] = node.id
            elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in direct:
                identities[id(node)] = direct[node.id]
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and isinstance(node.value, ast.Name) and node.value.id in modules and node.attr in constant_names:
                identities[id(node)] = node.attr

        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        records.extend(_classify_constant_usages_in_tree(
            tree=tree, constant_names=constant_names, arquivo=rel,
            canonical_names=identities,
        ))
    return tuple(sorted(records))


def _reconcile_call_sites_and_usages(
    call_sites: dict[str, tuple[CallSiteRecord, ...]],
    usages: tuple[UsageRecord, ...],
) -> ReconciliationReport:
    structural = tuple(
        UsageIdentity(constant, site.arquivo, site.linha)
        for constant, sites in sorted(call_sites.items())
        for site in sites
    )
    semantic = tuple(
        UsageIdentity(item.constante_id, item.arquivo, item.linha)
        for item in usages
    )
    structural_set = set(structural)
    semantic_counts = Counter(semantic)
    semantic_set = set(semantic_counts)
    return ReconciliationReport(
        structural_total=len(structural),
        semantic_total=len(semantic),
        unaccounted=tuple(sorted(structural_set - semantic_set)),
        orphan=tuple(sorted(semantic_set - structural_set)),
        duplicates=tuple(sorted(
            identity for identity, count in semantic_counts.items()
            if count > 1
        )),
    )


def _binding_sort_key(item: dict) -> tuple[str, ...]:
    target_type = "constante" if "constante_id" in item else "dataset"
    target_id = item.get("constante_id", item.get("dataset_id", ""))
    return (
        target_type,
        str(target_id),
        str(item.get("fonte_id", "")),
        str(item.get("versao_fonte", "")),
        str(item.get("vigencia_inicio", "")),
        str(item.get("vigencia_fim") or ""),
        str(item.get("jurisdicao_codigo", "")),
        str(item.get("risco", "")),
        json.dumps(item.get("invariantes"), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


def _load_local_normative_evidence() -> BindingDiscoveryReport:
    """Aceita somente envelopes persistidos do contrato BatchRequest canónico."""
    bindings: list[dict] = []
    findings: list[CensusFinding] = []

    def contains_target(value: object) -> bool:
        if isinstance(value, dict):
            return (
                "constante_id" in value
                or "dataset_id" in value
                or any(contains_target(item) for item in value.values())
            )
        if isinstance(value, list):
            return any(contains_target(item) for item in value)
        return False
    data_root = ROOT / "data"
    if not data_root.is_dir():
        return BindingDiscoveryReport((), {}, ())
    for path in sorted(data_root.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        is_batch_candidate = isinstance(payload, dict) and (
            "bindings" in payload or "contexto" in payload
        )
        if is_batch_candidate:
            try:
                request = NormativeBindingBatchRequest.model_validate(payload)
            except ValidationError as exc:
                findings.append(_finding(
                    "MEI_NORMATIVE_CENSUS_BINDING_DISCOVERY_UNRESOLVED",
                    arquivo=relative,
                    detalhe=f"INVALID_CANONICAL_BATCH:{exc.error_count()}",
                ))
            else:
                bindings.extend(request.model_dump(mode="json")["bindings"])
            continue

        if contains_target(payload):
            findings.append(_finding(
                "MEI_NORMATIVE_CENSUS_BINDING_DISCOVERY_UNRESOLVED",
                arquivo=relative,
                detalhe="TARGET_OUTSIDE_CANONICAL_BATCH",
            ))
    manifest_path = data_root / "fontes_tributarias_manifest.json"
    if not manifest_path.is_file():
        return BindingDiscoveryReport(tuple(bindings), {}, tuple(sorted(findings, key=_finding_sort_key)))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sources = {
        item["id"]: item for item in manifest.get("fontes", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    return BindingDiscoveryReport(tuple(bindings), sources, tuple(sorted(findings, key=_finding_sort_key)))


def _evaluate_constant(
    *, record: ConstantRecord, usages: tuple[UsageRecord, ...],
    bindings: list[dict], sources: dict[str, dict],
    reference_date: date | None = None,
) -> dict:
    categories = sorted({item.categoria for item in usages})
    normative = any(item.categoria in {"DECISION", "CALCULATION", "PRESENTATION", "UNRESOLVED"} for item in usages)
    reasons: set[str] = set()
    matched = sorted(
        (item for item in bindings if item.get("constante_id") == record.constante_id),
        key=_binding_sort_key,
    )
    final_status = "NON_NORMATIVE"

    if not usages:
        final_status = "UNRESOLVED"
        reasons.add("NO_USAGE_EVIDENCE")
    elif any(item.categoria == "UNRESOLVED" for item in usages):
        final_status = "UNRESOLVED"
        reasons.add("USAGE_UNRESOLVED")
    elif normative and not matched:
        final_status = "BLOCKED"
        reasons.add("BINDING_MISSING")
    elif normative:
        if reference_date is None:
            final_status = "UNRESOLVED"
            reasons.add("UNRESOLVED_TEMPORAL")
        else:
            jurisdiction = matched[0].get("jurisdicao_codigo", "")
            payload = {
                "contexto": {
                    "data_referencia": (
                        reference_date.isoformat()
                        if isinstance(reference_date, date)
                        else reference_date
                    ),
                    "jurisdicao_codigo": jurisdiction,
                    "uso_solicitado": "decisao_definitiva",
                },
                "bindings": matched,
            }
            try:
                request = NormativeBindingBatchRequest.model_validate(payload)
            except ValidationError:
                canonical_payload = payload
            else:
                canonical_payload = request.model_dump(mode="json")
            canonical = validar_bindings_normativos(canonical_payload)
            reasons.update(reason.code.value for reason in canonical.reasons)
            if canonical.autorizado_fundamentar_decisao:
                final_status = "AUTHORIZED"
            elif any(
                reason.code in {
                    NormativeBindingReasonCode.BINDING_DUPLICADO,
                    NormativeBindingReasonCode.BINDINGS_CONFLITANTES,
                    NormativeBindingReasonCode.ALVO_NORMATIVO_AMBIGUO,
                }
                for reason in canonical.reasons
            ):
                final_status = "UNRESOLVED"
            else:
                final_status = "BLOCKED"

    return {
        **asdict(record),
        "usos": [asdict(item) for item in sorted(usages)],
        "categorias": categories,
        "normative_reachability": normative,
        "bindings": matched,
        "binding_status": "FOUND" if matched else "MISSING",
        "source_authority": [
            {
                "fonte_id": item.get("fonte_id"),
                "versao_fonte": item.get("versao_fonte"),
                "vigencia_inicio": item.get("vigencia_inicio"),
                "vigencia_fim": item.get("vigencia_fim"),
                "jurisdicao_codigo": item.get("jurisdicao_codigo"),
                "risco": item.get("risco"),
                "pode_fundamentar_decisao": sources.get(item.get("fonte_id"), {}).get("pode_fundamentar_decisao"),
                "alvos_normativos_autorizados": sources.get(item.get("fonte_id"), {}).get("alvos_normativos_autorizados"),
            }
            for item in matched
        ],
        "final_status": final_status,
        "reasons": sorted(reasons),
    }


def build_census() -> dict:
    definitions = _discover_constant_definitions()
    constant_names = {
        name
        for name, _ in definitions
    }

    report = _scan_call_sites_report(constant_names)

    constants = tuple(
        sorted(
            (
                ConstantRecord(
                    constante_id=name,
                    arquivo_definicao=str(
                        CONSTANTS_PATH.relative_to(ROOT)
                    ).replace("\\", "/"),
                    linha_definicao=lineno,
                    call_sites=report.call_sites.get(name, ()),
                )
                for name, lineno in definitions
            ),
            key=lambda item: item.constante_id,
        )
    )

    try:
        usages = _discover_usage_records(constant_names)
        evidence = _load_local_normative_evidence()
        bindings, sources = list(evidence.bindings), evidence.sources
        if evidence.findings:
            report = CallSiteScanReport(
                report.call_sites,
                tuple(sorted((*report.findings, *evidence.findings), key=_finding_sort_key)),
                report.files_discovered,
                report.files_parsed,
                False,
            )
    except (OSError, UnicodeDecodeError, SyntaxError, json.JSONDecodeError) as exc:
        usages, bindings, sources = (), [], {}
        report = CallSiteScanReport(report.call_sites, tuple(sorted((*report.findings, _finding(
            "MEI_NORMATIVE_CENSUS_EVIDENCE_SCAN_FAILED", arquivo="data", detalhe=f"{type(exc).__name__}:{exc}"
        )), key=_finding_sort_key)), report.files_discovered, report.files_parsed, False)

    evaluated = [
        _evaluate_constant(
            record=item,
            usages=tuple(usage for usage in usages if usage.constante_id == item.constante_id),
            bindings=bindings,
            sources=sources,
        ) for item in constants
    ]
    reconciliation = _reconcile_call_sites_and_usages(report.call_sites, usages)
    reconciliation_findings = tuple(
        _finding(
            f"MEI_NORMATIVE_CENSUS_RECONCILIATION_{kind}",
            arquivo=identity.arquivo,
            linha=identity.linha,
            detalhe=identity.constante_id,
        )
        for kind, identities in (
            ("UNACCOUNTED", reconciliation.unaccounted),
            ("ORPHAN", reconciliation.orphan),
            ("DUPLICATE", reconciliation.duplicates),
        )
        for identity in identities
    )
    normative_findings = tuple(
        _finding(
            f"MEI_NORMATIVE_CENSUS_{reason}",
            arquivo=item["arquivo_definicao"],
            linha=item["linha_definicao"],
            detalhe=item["constante_id"],
        )
        for item in evaluated
        for reason in item["reasons"]
    )
    all_findings = tuple(sorted((*report.findings, *reconciliation_findings, *normative_findings), key=_finding_sort_key))
    status = "BLOCKED" if (
        not report.scan_complete or report.findings or reconciliation_findings
        or any(item["final_status"] in {"BLOCKED", "UNRESOLVED"} for item in evaluated)
    ) else "AUTHORIZED"

    return {
        "schema_version": "MEI_NORMATIVE_CENSUS_V1",
        "status": status,
        "scan_complete": report.scan_complete,
        "files_discovered": report.files_discovered,
        "files_parsed": report.files_parsed,
        "findings_total": len(all_findings),
        "findings": [
            asdict(item)
            for item in all_findings
        ],
        "constants_total": len(constants),
        "usages_total": len(usages),
        "reconciliation": {
            "structural_total": reconciliation.structural_total,
            "semantic_total": reconciliation.semantic_total,
            "unaccounted": [asdict(item) for item in reconciliation.unaccounted],
            "orphan": [asdict(item) for item in reconciliation.orphan],
            "duplicates": [asdict(item) for item in reconciliation.duplicates],
        },
        "constants": evaluated,
    }


def main() -> int:
    print(
        json.dumps(
            build_census(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
