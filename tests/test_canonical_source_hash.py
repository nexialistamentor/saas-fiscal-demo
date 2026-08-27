from __future__ import annotations

import ast
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.canonical_source_hash import (
    REPO_ROOT,
    canonical_opaque_bytes_sha256,
    canonical_source_sha256,
)


_SOURCE_SUFFIXES = {".py", ".pyi", ".js", ".jsx", ".ts", ".tsx"}
_BINARY_SUFFIXES = {".db", ".gif", ".ico", ".jpeg", ".jpg", ".pdf", ".png", ".webp", ".xml"}
_SAME_CHECKOUT_MUTATION_GUARDS = {
    ("test_b13_ops_12c_binding_normativo.py", "test_real_manifest_bytes_are_unchanged"),
}


def _static_path(node: ast.AST, paths: dict[str, str | None]) -> str | None:
    if isinstance(node, ast.Name):
        return paths.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and node.args:
        if isinstance(node.func, ast.Name) and node.func.id == "Path":
            return _static_path(node.args[0], paths)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _static_path(node.left, paths)
        right = _static_path(node.right, paths)
        if left is not None and right is not None:
            return str(Path(left) / right)
    return None


def _read_target(node: ast.AST, paths: dict[str, str | None]) -> str | None | bool:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr == "read_bytes":
        return _static_path(node.func.value, paths)
    if node.func.attr != "read" or not isinstance(node.func.value, ast.Call):
        return False
    opener = node.func.value
    if not isinstance(opener.func, ast.Name) or opener.func.id != "open" or not opener.args:
        return False
    mode = opener.args[1] if len(opener.args) > 1 else None
    if not isinstance(mode, ast.Constant) or "b" not in str(mode.value):
        return False
    return _static_path(opener.args[0], paths)


def _raw_hash_targets(
    function: ast.AST,
    inherited_paths: dict[str, str | None] | None = None,
) -> list[str | None]:
    paths = dict(inherited_paths or {})
    byte_targets: dict[str, str | None] = {}
    targets: list[str | None] = []
    saw_physical_read = False
    raw_hash_count = 0

    nodes: list[ast.AST] = []

    class FunctionScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            if node is function:
                self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            if node is function:
                self.generic_visit(node)

        def generic_visit(self, node: ast.AST) -> None:
            nodes.append(node)
            super().generic_visit(node)

    FunctionScopeVisitor().visit(function)
    for node in nodes:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            read_target = _read_target(node.value, paths)
            if read_target is not False:
                saw_physical_read = True
                byte_targets[name] = read_target
            else:
                paths[name] = _static_path(node.value, paths)
        if not isinstance(node, ast.Call):
            continue
        is_sha256 = (
            isinstance(node.func, ast.Attribute) and node.func.attr == "sha256"
        ) or (isinstance(node.func, ast.Name) and node.func.id == "sha256")
        if not is_sha256 or not node.args:
            continue
        raw_hash_count += 1
        argument = node.args[0]
        direct_target = _read_target(argument, paths)
        if direct_target is not False:
            saw_physical_read = True
            targets.append(direct_target)
        elif isinstance(argument, ast.Name) and argument.id in byte_targets:
            targets.append(byte_targets[argument.id])
    if saw_physical_read and raw_hash_count > len(targets):
        targets.extend([None] * (raw_hash_count - len(targets)))
    return targets


def _read_identity(node: ast.AST, path_values: dict[str, str]) -> str | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr == "read_bytes":
        target = node.func.value
    elif (
        node.func.attr == "read"
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "open"
        and node.func.value.args
    ):
        opener = node.func.value
        mode = opener.args[1] if len(opener.args) > 1 else None
        if not isinstance(mode, ast.Constant) or "b" not in str(mode.value):
            return None
        target = opener.args[0]
    else:
        return None
    if isinstance(target, ast.Name) and target.id in path_values:
        return path_values[target.id]
    return ast.dump(target, include_attributes=False)


def _hash_input_name(node: ast.AST) -> str | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "hexdigest"
        and isinstance(node.func.value, ast.Call)
    ):
        node = node.func.value
    if not isinstance(node, ast.Call) or not node.args:
        return None
    is_sha256 = (
        isinstance(node.func, ast.Attribute) and node.func.attr == "sha256"
    ) or (isinstance(node.func, ast.Name) and node.func.id == "sha256")
    if not is_sha256 or not isinstance(node.args[0], ast.Name):
        return None
    return node.args[0].id


def _local_nodes(node: ast.AST) -> list[ast.AST]:
    nodes: list[ast.AST] = []

    class LocalScopeVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, child: ast.FunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_AsyncFunctionDef(self, child: ast.AsyncFunctionDef) -> None:
            if child is node:
                self.generic_visit(child)

        def visit_Lambda(self, child: ast.Lambda) -> None:
            return

        def visit_ClassDef(self, child: ast.ClassDef) -> None:
            return

        def generic_visit(self, child: ast.AST) -> None:
            nodes.append(child)
            super().generic_visit(child)

    LocalScopeVisitor().visit(node)
    return nodes


def _is_same_checkout_mutation_guard(function: ast.AST) -> bool:
    if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False

    path_values: dict[str, str] = {}
    reads: list[tuple[int, str, str]] = []
    hashes: list[tuple[int, str, str]] = []
    interventions: set[int] = set()

    for index, statement in enumerate(function.body):
        assigned_name = None
        value = None
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            assigned_name = statement.targets[0].id
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            assigned_name = statement.target.id
            value = statement.value

        if assigned_name is not None and value is not None:
            read_identity = _read_identity(value, path_values)
            hash_input = _hash_input_name(value)
            if read_identity is not None:
                reads.append((index, assigned_name, read_identity))
            elif hash_input is not None:
                hashes.append((index, assigned_name, hash_input))
            else:
                path_values[assigned_name] = ast.dump(value, include_attributes=False)

        if (
            not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and any(isinstance(node, ast.Call) for node in _local_nodes(statement))
        ):
            if not (
                assigned_name is not None
                and value is not None
                and (_read_identity(value, path_values) is not None or _hash_input_name(value) is not None)
            ):
                interventions.add(index)

    for before_read, after_read in zip(reads, reads[1:]):
        before_read_index, before_bytes, before_target = before_read
        after_read_index, after_bytes, after_target = after_read
        if before_target != after_target:
            continue
        for before_hash_event in hashes:
            before_hash_index, before_hash, before_input = before_hash_event
            if before_input != before_bytes or not (before_read_index < before_hash_index):
                continue
            for after_hash_event in hashes:
                after_hash_index, after_hash, after_input = after_hash_event
                if after_input != after_bytes or not (
                    before_hash_index < after_read_index < after_hash_index
                ):
                    continue
                if not any(before_hash_index < index < after_read_index for index in interventions):
                    continue

                required_pairs = {
                    frozenset((before_bytes, after_bytes)),
                    frozenset((before_hash, after_hash)),
                }
                found_pairs: set[frozenset[str]] = set()
                hash_comparison_is_safe = True
                for comparison in (
                    node for node in _local_nodes(function) if isinstance(node, ast.Compare)
                ):
                    names = [
                        operand.id
                        for operand in (comparison.left, *comparison.comparators)
                        if isinstance(operand, ast.Name)
                    ]
                    mentions_guard_hash = before_hash in names or after_hash in names
                    is_simple_equality = (
                        len(comparison.ops) == 1
                        and isinstance(comparison.ops[0], ast.Eq)
                        and len(names) == 2
                    )
                    pair = frozenset(names)
                    if mentions_guard_hash and (
                        not is_simple_equality
                        or pair != frozenset((before_hash, after_hash))
                    ):
                        hash_comparison_is_safe = False
                    if is_simple_equality:
                        found_pairs.add(pair)
                if hash_comparison_is_safe and required_pairs <= found_pairs:
                    return True
    return False


def _find_violations(tests_root: Path) -> list[str]:
    violations: list[str] = []
    for path in sorted(tests_root.rglob("test_*.py")):
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
        module_paths: dict[str, str | None] = {}
        for node in tree.body:
            if (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
            ):
                module_paths[node.targets[0].id] = _static_path(node.value, module_paths)
        for function in (
            node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ):
            if (
                (path.name, function.name) in _SAME_CHECKOUT_MUTATION_GUARDS
                and _is_same_checkout_mutation_guard(function)
            ):
                continue
            for target in _raw_hash_targets(function, module_paths):
                suffix = Path(target).suffix.lower() if target is not None else ""
                if suffix in _BINARY_SUFFIXES:
                    continue
                # Unknown physical targets fail closed; known source targets must
                # use canonical_source_sha256 instead of raw worktree bytes.
                relative_path = path.relative_to(tests_root).as_posix()
                violations.append(f"{relative_path}:{function.lineno}")
                break
    return violations


def test_no_absolute_source_text_hash_bypasses_canonical_helper() -> None:
    violations = _find_violations(REPO_ROOT / "tests")
    assert violations == [], (
        "absolute SOURCE TEXT hashes must use canonical_source_sha256; "
        f"violations={violations}"
    )


def test_canonical_hash_is_identical_for_lf_and_crlf_worktree_bytes() -> None:
    source = REPO_ROOT / "app" / "agents" / "ag_abertura_agent.py"
    lf = source.read_bytes().replace(b"\r\n", b"\n")
    with patch.object(Path, "read_bytes", return_value=lf):
        clean_hash = canonical_source_sha256(source)
    with patch.object(Path, "read_bytes", return_value=lf.replace(b"\n", b"\r\n")):
        crlf_hash = canonical_source_sha256(source)
    assert crlf_hash == clean_hash


def test_canonical_hash_changes_for_current_uncommitted_content() -> None:
    source = REPO_ROOT / "app" / "agents" / "ag_abertura_agent.py"
    lf = source.read_bytes().replace(b"\r\n", b"\n")
    with patch.object(Path, "read_bytes", return_value=lf):
        before = canonical_source_sha256(source)
    with patch.object(Path, "read_bytes", return_value=lf + b"# real change\n"):
        after = canonical_source_sha256(source)
    assert after != before


def test_canonical_hash_fails_closed_for_disallowed_attributes() -> None:
    source = REPO_ROOT / "app" / "agents" / "ag_abertura_agent.py"
    real_run = __import__("subprocess").run

    def run_with_bad_attributes(command, *args, **kwargs):
        result = real_run(command, *args, **kwargs)
        if command[1:3] == ["check-attr", "-z"]:
            result.stdout = result.stdout.replace("\0lf\0", "\0crlf\0", 1)
        return result

    with patch("tests.canonical_source_hash.subprocess.run", side_effect=run_with_bad_attributes):
        with pytest.raises(ValueError, match="not canonical"):
            canonical_source_sha256(source)


def test_opaque_hash_accepts_tracked_snapshot_exact_bytes() -> None:
    snapshot = REPO_ROOT / "data" / "mei" / "decreto_12797_2025_snapshot_2026-08-27.html"
    assert canonical_opaque_bytes_sha256(snapshot) == (
        "9C3FC6738634B9E1FCDDA94307CFD90FE028FFEDF34FF7391A99A0359AE6A52C"
    )


def test_opaque_hash_rejects_text_source() -> None:
    source = REPO_ROOT / "app" / "agents" / "ag_abertura_agent.py"
    with pytest.raises(ValueError, match="opaque attributes are not canonical"):
        canonical_opaque_bytes_sha256(source)


def test_opaque_hash_rejects_external_file() -> None:
    external = Path(sys.executable)
    with pytest.raises(ValueError, match="inside the repo"):
        canonical_opaque_bytes_sha256(external)


def test_opaque_hash_rejects_untracked_file() -> None:
    snapshot = REPO_ROOT / "data" / "mei" / "decreto_12797_2025_snapshot_2026-08-27.html"
    real_run = __import__("subprocess").run

    def run_as_untracked(command, *args, **kwargs):
        result = real_run(command, *args, **kwargs)
        if command[1:3] == ["ls-files", "--error-unmatch"]:
            result.returncode = 1
            result.stdout = ""
        return result

    with patch("tests.canonical_source_hash.subprocess.run", side_effect=run_as_untracked):
        with pytest.raises(ValueError, match="tracked by git"):
            canonical_opaque_bytes_sha256(snapshot)


@pytest.mark.parametrize(
    "attribute,value",
    [("filter", "active-filter"), ("working-tree-encoding", "UTF-16")],
    ids=["active-filter", "active-encoding"],
)
def test_opaque_hash_rejects_active_git_transform(attribute: str, value: str) -> None:
    snapshot = REPO_ROOT / "data" / "mei" / "decreto_12797_2025_snapshot_2026-08-27.html"
    real_run = __import__("subprocess").run

    def run_with_transform(command, *args, **kwargs):
        result = real_run(command, *args, **kwargs)
        if command[1:3] == ["check-attr", "-z"]:
            result.stdout = result.stdout.replace(
                f"\0{attribute}\0unspecified\0",
                f"\0{attribute}\0{value}\0",
                1,
            )
        return result

    with patch("tests.canonical_source_hash.subprocess.run", side_effect=run_with_transform):
        with pytest.raises(ValueError, match="opaque attributes are not canonical"):
            canonical_opaque_bytes_sha256(snapshot)


def _targets(snippet: str) -> list[str | None]:
    return _raw_hash_targets(ast.parse(snippet).body[0])


def test_nested_test_file_is_scanned_recursively(tmp_path: Path) -> None:
    nested = tmp_path / "subdir" / "test_nested.py"
    nested.parent.mkdir()
    nested.write_text(
        "def test_legacy_integrity():\n"
        "    raw = Path('app/foo.py').read_bytes()\n"
        "    assert hashlib.sha256(raw).hexdigest() == expected\n",
        encoding="utf-8",
    )
    assert _find_violations(tmp_path) == ["subdir/test_nested.py:1"]


def test_detection_is_independent_of_function_name() -> None:
    assert _targets(
        "def test_legacy_integrity():\n"
        "    raw = Path('app/foo.py').read_bytes()\n"
        "    assert hashlib.sha256(raw).hexdigest() == expected\n"
    ) == ["app/foo.py"]


def test_binary_mention_does_not_hide_source_target() -> None:
    assert _targets(
        "def test_mixed():\n"
        "    fixture = 'fixture.pdf'\n"
        "    raw = Path('app/foo.py').read_bytes()\n"
        "    assert hashlib.sha256(raw).hexdigest() == expected\n"
    ) == ["app/foo.py"]


def test_binary_path_actually_hashed_is_allowed(tmp_path: Path) -> None:
    test_file = tmp_path / "test_binary.py"
    test_file.write_text(
        "def test_pdf():\n"
        "    raw = Path('fixture.pdf').read_bytes()\n"
        "    assert hashlib.sha256(raw).hexdigest() == expected\n",
        encoding="utf-8",
    )
    assert _find_violations(tmp_path) == []


def test_ambiguous_physical_hash_fails_closed(tmp_path: Path) -> None:
    test_file = tmp_path / "test_dynamic.py"
    test_file.write_text(
        "def test_dynamic(target):\n"
        "    raw = Path(target).read_bytes()\n"
        "    assert hashlib.sha256(raw).hexdigest() == expected\n",
        encoding="utf-8",
    )
    assert _find_violations(tmp_path) == ["test_dynamic.py:1"]


def test_b13_same_checkout_mutation_guard_is_allowed(tmp_path: Path) -> None:
    test_file = tmp_path / "test_b13_ops_12c_binding_normativo.py"
    test_file.write_text(
        "def test_real_manifest_bytes_are_unchanged():\n"
        "    target = Path('manifest.json')\n"
        "    before_bytes = target.read_bytes()\n"
        "    before_hash = hashlib.sha256(before_bytes).hexdigest()\n"
        "    result = exercise_guard()\n"
        "    after_bytes = target.read_bytes()\n"
        "    after_hash = hashlib.sha256(after_bytes).hexdigest()\n"
        "    assert after_bytes == before_bytes\n"
        "    assert after_hash == before_hash\n",
        encoding="utf-8",
    )
    assert _find_violations(tmp_path) == []


def _write_b13_candidate(tmp_path: Path, body: str) -> None:
    (tmp_path / "test_b13_ops_12c_binding_normativo.py").write_text(
        "def test_real_manifest_bytes_are_unchanged():\n" + body,
        encoding="utf-8",
    )


def test_b13_name_does_not_allow_absolute_hash(tmp_path: Path) -> None:
    _write_b13_candidate(
        tmp_path,
        "    target = Path('manifest.json')\n"
        "    before_bytes = target.read_bytes()\n"
        "    before_hash = hashlib.sha256(before_bytes).hexdigest()\n"
        "    exercise_guard()\n"
        "    after_bytes = target.read_bytes()\n"
        "    after_hash = hashlib.sha256(after_bytes).hexdigest()\n"
        "    assert after_bytes == before_bytes\n"
        "    assert after_hash == expected\n",
    )
    assert _find_violations(tmp_path) == ["test_b13_ops_12c_binding_normativo.py:1"]


@pytest.mark.parametrize(
    "after_target,bytes_comparison,hash_comparison",
    [
        ("other", "    assert after_bytes == before_bytes\n", "    assert after_hash == before_hash\n"),
        ("target", "", "    assert after_hash == before_hash\n"),
        ("target", "    assert after_bytes == before_bytes\n", ""),
    ],
    ids=["different-targets", "missing-bytes-comparison", "missing-hash-comparison"],
)
def test_b13_incomplete_structure_fails_closed(
    tmp_path: Path,
    after_target: str,
    bytes_comparison: str,
    hash_comparison: str,
) -> None:
    _write_b13_candidate(
        tmp_path,
        "    target = Path('manifest.json')\n"
        "    other = Path('other.json')\n"
        "    before_bytes = target.read_bytes()\n"
        "    before_hash = hashlib.sha256(before_bytes).hexdigest()\n"
        "    exercise_guard()\n"
        f"    after_bytes = {after_target}.read_bytes()\n"
        "    after_hash = hashlib.sha256(after_bytes).hexdigest()\n"
        + bytes_comparison
        + hash_comparison,
    )
    assert _find_violations(tmp_path) == ["test_b13_ops_12c_binding_normativo.py:1"]


def test_real_b13_same_checkout_pattern_is_structurally_proved() -> None:
    path = REPO_ROOT / "tests" / "test_b13_ops_12c_binding_normativo.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "test_real_manifest_bytes_are_unchanged"
    )
    assert _is_same_checkout_mutation_guard(function)
