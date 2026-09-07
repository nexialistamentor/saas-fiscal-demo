"""Contrato RED para capacidade de ``alembic_version.version_num``."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import String


ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
REVISION_0044 = "0044_payments_durable_ledger"
REVISION_0045 = "0045_multi_vertical_checkout_catalog"
TOPOLOGY_MARKER = "ALEMBIC_BRANCH_TOPOLOGY_UNEXPECTED"
BRIDGE_MISSING_MARKER = "ALEMBIC_VERSION_CAPACITY_BRIDGE_MISSING"


@pytest.fixture(scope="module")
def revision_census() -> dict[str, Any]:
    config = Config(str(ALEMBIC_INI))
    scripts = ScriptDirectory.from_config(config)
    revisions = list(scripts.walk_revisions())
    by_id = {revision.revision: revision for revision in revisions}
    parents: dict[str, tuple[str, ...]] = {}
    children: defaultdict[str, list[str]] = defaultdict(list)

    for revision in revisions:
        raw_parents = revision.down_revision
        if raw_parents is None:
            revision_parents: tuple[str, ...] = ()
        elif isinstance(raw_parents, str):
            revision_parents = (raw_parents,)
        else:
            revision_parents = tuple(raw_parents)
        parents[revision.revision] = revision_parents
        for parent in revision_parents:
            children[parent].append(revision.revision)

    return {
        "scripts": scripts,
        "revisions": revisions,
        "by_id": by_id,
        "parents": parents,
        "children": {key: sorted(value) for key, value in children.items()},
        "heads": tuple(scripts.get_heads()),
        "max_revision_length": max(len(revision.revision) for revision in revisions),
    }


def _affected_chain(census: dict[str, Any]) -> list[str]:
    by_id = census["by_id"]
    children = census["children"]
    heads = set(census["heads"])

    if REVISION_0044 not in by_id or REVISION_0045 not in by_id:
        pytest.fail(TOPOLOGY_MARKER, pytrace=False)
    if len(heads) != 1:
        pytest.fail(TOPOLOGY_MARKER, pytrace=False)

    chain = [REVISION_0044]
    visited = {REVISION_0044}
    current = REVISION_0044
    while current not in heads:
        direct_children = children.get(current, [])
        if len(direct_children) != 1:
            pytest.fail(TOPOLOGY_MARKER, pytrace=False)
        current = direct_children[0]
        if current in visited:
            pytest.fail(TOPOLOGY_MARKER, pytrace=False)
        visited.add(current)
        chain.append(current)

    if set(chain).intersection(heads) != heads:
        pytest.fail(TOPOLOGY_MARKER, pytrace=False)
    if REVISION_0045 not in chain:
        pytest.fail(TOPOLOGY_MARKER, pytrace=False)

    for revision_id in chain[1:]:
        if len(census["parents"].get(revision_id, ())) != 1:
            pytest.fail(TOPOLOGY_MARKER, pytrace=False)
        if len(children.get(revision_id, [])) > 1:
            pytest.fail(TOPOLOGY_MARKER, pytrace=False)

    return chain


def _bridge_or_skip(census: dict[str, Any]) -> Any:
    direct_child = census["children"][REVISION_0044][0]
    if direct_child == REVISION_0045:
        pytest.skip(BRIDGE_MISSING_MARKER)
    return census["by_id"][direct_child]


def _capture_version_num_alteration(
    monkeypatch: pytest.MonkeyPatch,
    bridge: Any,
    operation_name: str,
) -> dict[str, Any]:
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def record_alter_column(*args: Any, **kwargs: Any) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr(bridge.module.op, "alter_column", record_alter_column)
    getattr(bridge.module, operation_name)()

    relevant = []
    for args, kwargs in calls:
        table_name = args[0] if len(args) > 0 else kwargs.get("table_name")
        column_name = args[1] if len(args) > 1 else kwargs.get("column_name")
        if table_name == "alembic_version" and column_name == "version_num":
            relevant.append(kwargs)

    assert len(relevant) == 1
    return relevant[0]


def _assert_expanded_capacity(
    alteration: dict[str, Any], max_revision_length: int
) -> None:
    existing_type = alteration.get("existing_type")
    new_type = alteration.get("type_")
    assert isinstance(existing_type, String)
    assert existing_type.length == 32
    assert isinstance(new_type, String)
    assert new_type.length is not None
    assert new_type.length > 32
    assert new_type.length >= max_revision_length


def test_01_topology_is_compatible_with_one_linear_bridge(
    revision_census: dict[str, Any],
) -> None:
    _affected_chain(revision_census)


def test_02_capacity_bridge_is_present(revision_census: dict[str, Any]) -> None:
    _affected_chain(revision_census)
    direct_child = revision_census["children"][REVISION_0044][0]
    if direct_child == REVISION_0045:
        pytest.fail(BRIDGE_MISSING_MARKER, pytrace=False)

    bridge_children = revision_census["children"].get(direct_child, [])
    assert bridge_children == [REVISION_0045]


def test_03_bridge_has_downgrade_safe_identity(
    revision_census: dict[str, Any],
) -> None:
    _affected_chain(revision_census)
    bridge = _bridge_or_skip(revision_census)

    assert isinstance(bridge.revision, str)
    assert len(bridge.revision) <= 32
    assert bridge.down_revision == REVISION_0044
    assert revision_census["by_id"][REVISION_0045].down_revision == bridge.revision
    assert len(REVISION_0044) <= 32


def test_04_bridge_upgrade_expands_capacity_dynamically(
    revision_census: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _affected_chain(revision_census)
    bridge = _bridge_or_skip(revision_census)
    alteration = _capture_version_num_alteration(monkeypatch, bridge, "upgrade")
    _assert_expanded_capacity(
        alteration, revision_census["max_revision_length"]
    )


def test_05_future_revision_ids_cannot_exceed_bridge_capacity(
    revision_census: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _affected_chain(revision_census)
    bridge = _bridge_or_skip(revision_census)
    alteration = _capture_version_num_alteration(monkeypatch, bridge, "upgrade")
    capacity = alteration.get("type_")

    assert isinstance(capacity, String)
    assert capacity.length is not None
    assert capacity.length >= revision_census["max_revision_length"]


def test_06_bridge_downgrade_restores_safe_legacy_capacity(
    revision_census: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    _affected_chain(revision_census)
    bridge = _bridge_or_skip(revision_census)

    assert isinstance(bridge.revision, str)
    assert len(bridge.revision) <= 32
    assert bridge.down_revision == REVISION_0044
    assert len(REVISION_0044) <= 32

    alteration = _capture_version_num_alteration(monkeypatch, bridge, "downgrade")
    existing_type = alteration.get("existing_type")
    restored_type = alteration.get("type_")
    assert isinstance(existing_type, String)
    assert existing_type.length is not None
    assert existing_type.length > 32
    assert existing_type.length >= revision_census["max_revision_length"]
    assert isinstance(restored_type, String)
    assert restored_type.length == 32
