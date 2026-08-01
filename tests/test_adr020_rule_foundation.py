import ast
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
    event,
)

from app import models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "migrations"
    / "versions"
    / "0020_adr020_rule_foundation.py"
)


def _sha(character: str) -> str:
    return character * 64


def _check_sql(table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _foreign_key_pairs(table) -> set[tuple[tuple[str, str], ...]]:
    result = set()
    for constraint in table.constraints:
        if not isinstance(constraint, ForeignKeyConstraint):
            continue
        result.add(
            tuple(
                (element.parent.name, element.target_fullname)
                for element in constraint.elements
            )
        )
    return result


def _constraint_names(table, constraint_type) -> set[str]:
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type)
        and constraint.name
    }


def _literal_assignment(tree: ast.Module, name: str):
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            return ast.literal_eval(node.value)

        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ):
            return ast.literal_eval(node.value)

    raise AssertionError(f"Assignment {name!r} not found")


def _review(**overrides):
    payload = dict(
        rule_review_record_id="review-record-1",
        subject_id="rule-1",
        subject_version=1,
        subject_hash=_sha("a"),
        reviewer="reviewer",
        review_event="extracao_registada",
        outcome="pendente",
        evidence={},
        timestamp=datetime.now(timezone.utc),
        record_hash=_sha("b"),
    )
    payload.update(overrides)
    return models.RuleReviewRecord(**payload)


def test_commit_3_exposes_exact_rule_models():
    assert models.RuleVersion.__tablename__ == "rule_versions"
    assert (
        models.RuleReviewRecord.__tablename__
        == "rule_review_records"
    )


def test_rule_version_contains_only_immutable_normative_content():
    columns = set(models.RuleVersion.__table__.columns.keys())

    assert {
        "rule_id",
        "rule_version",
        "rule_hash",
        "extraction_result_id",
        "extraction_result_record_hash",
        "structured_content",
        "declared_material_validity",
        "normative_references",
        "exact_precedence_policy_reference",
        "evidence",
        "provenance",
        "created_at",
    } <= columns

    forbidden = {
        "status",
        "state",
        "review_event",
        "outcome",
        "em_quarentena",
        "em_validacao",
        "em_revisao_reservada",
        "validada",
        "rejeitada",
        "bloqueada",
        "retirada",
        "active",
        "activo",
        "activation_state",
        "calculation_authorized",
        "updated_at",
    }

    assert not (forbidden & columns)


def test_rule_version_binds_exact_extraction_result_record_hash():
    pairs = _foreign_key_pairs(models.RuleVersion.__table__)

    assert (
        (
            (
                "extraction_result_id",
                "extraction_results.extraction_result_id",
            ),
            (
                "extraction_result_record_hash",
                "extraction_results.record_hash",
            ),
        )
        in pairs
    )


def test_rule_version_identity_and_hash_are_unique():
    names = _constraint_names(
        models.RuleVersion.__table__,
        UniqueConstraint,
    )

    assert "uq_rule_versions_identity" in names
    assert "uq_rule_versions_rule_hash" in names


def test_rule_review_record_has_exact_subject_identity():
    columns = set(
        models.RuleReviewRecord.__table__.columns.keys()
    )

    assert {
        "rule_review_record_id",
        "subject_id",
        "subject_version",
        "subject_hash",
        "reviewer",
        "review_event",
        "outcome",
        "evidence",
        "timestamp",
        "record_hash",
    } <= columns


def test_review_event_and_outcome_are_separate_enumerations():
    checks = _check_sql(models.RuleReviewRecord.__table__)

    for review_event in (
        "extracao_registada",
        "quarentena_registada",
        "validacao_iniciada",
        "revisao_reservada_iniciada",
        "revisao_concluida",
        "retirada_registada",
    ):
        assert review_event in checks

    for outcome in (
        "pendente",
        "validada",
        "rejeitada",
        "bloqueada",
        "retirada",
    ):
        assert outcome in checks


def test_review_validator_rejects_event_outcome_confusion():
    target = _review(
        review_event="revisao_concluida",
        outcome="pendente",
    )

    with pytest.raises(ValueError, match="event/outcome"):
        models._adr020_validate_rule_review_insert(
            None,
            None,
            target,
        )


def test_validated_review_does_not_create_operational_authority():
    columns = set(
        models.RuleReviewRecord.__table__.columns.keys()
    )

    assert not (
        {
            "active",
            "activo",
            "activation_id",
            "activation_state",
            "calculation_authorized",
            "resolver_effect",
        }
        & columns
    )


def test_commit_3_models_are_append_only():
    listener = models._adr020_reject_append_only_mutation

    for model in (
        models.RuleVersion,
        models.RuleReviewRecord,
    ):
        assert event.contains(
            model,
            "before_update",
            listener,
        )
        assert event.contains(
            model,
            "before_delete",
            listener,
        )
        assert model in models._ADR020_INSERT_VALIDATORS
        assert event.contains(
            model,
            "before_insert",
            models._ADR020_INSERT_VALIDATORS[model],
        )


def test_migration_0020_identity_lineage_and_exact_two_tables():
    assert MIGRATION_PATH.is_file()

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    revision = _literal_assignment(tree, "revision")

    assert revision == "0020_adr020_rule_foundation"
    assert len(revision) <= 32
    assert (
        _literal_assignment(tree, "down_revision")
        == "0019_adr020_extraction"
    )

    created_tables = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "create_table" or not node.args:
            continue

        created_tables.add(ast.literal_eval(node.args[0]))

    assert created_tables == {
        "rule_versions",
        "rule_review_records",
    }


def test_migration_0020_enforces_exact_result_and_review_contract():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "fk_rule_versions_exact_extraction_result" in source
    assert "extraction_result_record_hash" in source
    assert "adr020_validate_rule_version" in source
    assert "adr020_validate_rule_review_event" in source
    assert "review_event" in source
    assert "outcome" in source
    assert "forbidden RuleReviewRecord transition" in source


def test_migration_0020_is_append_only_and_irreversible():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert "PostgreSQL-only" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "BEFORE TRUNCATE" in source
    assert "for table_name in _APPEND_ONLY_TABLES" in source

    downgrade_node = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "downgrade"
    )

    downgrade_source = ast.get_source_segment(
        source,
        downgrade_node,
    )

    assert "irreversible" in downgrade_source
    assert "raise RuntimeError" in downgrade_source
    assert "drop_table" not in downgrade_source
    assert "TRUNCATE" not in downgrade_source


def test_commit_3_does_not_authorize_activation_or_calculation():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "does not authorize" in source
    assert "activation" in source
    assert "calculation" in source