"""Contrato ADR-020 ? funda??o de rela??es normativas.

Este ficheiro permanece inicialmente RED at? existirem:
- NormativeRelationVersion;
- RelationReviewRecord;
- migration 0021_adr020_relation_foundation.

N?o autoriza activa??o, c?lculo, preced?ncia operacional, resolver,
workers, endpoints, scheduler ou execu??o.
"""

from pathlib import Path
from types import SimpleNamespace
import re

import pytest
import sqlalchemy as sa
from sqlalchemy import event

import app.models as models


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "migrations"
    / "versions"
    / "0021_adr020_relation_foundation.py"
)

RELATION_TYPES = {
    "rectifica",
    "republica",
    "altera",
    "substitui",
    "revoga",
    "complementa",
    "referencia",
    "sucede",
}

REVIEW_EVENTS = {
    "extracao_registada",
    "quarentena_registada",
    "validacao_iniciada",
    "revisao_reservada_iniciada",
    "revisao_concluida",
    "retirada_registada",
}

REVIEW_OUTCOMES = {
    "pendente",
    "validada",
    "rejeitada",
    "bloqueada",
    "retirada",
}


def _model(name: str):
    model = getattr(models, name, None)
    assert model is not None, f"modelo ausente: {name}"
    return model


def _columns(model) -> set[str]:
    return set(model.__table__.columns.keys())


def _check_sql(model) -> str:
    checks = [
        str(constraint.sqltext)
        for constraint in model.__table__.constraints
        if isinstance(constraint, sa.CheckConstraint)
    ]
    return " ".join(checks).lower()


def _unique_names(model) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }


def _migration_source() -> str:
    assert MIGRATION_PATH.exists(), (
        "migration ausente: "
        "0021_adr020_relation_foundation.py"
    )
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_models_and_tables_exist() -> None:
    relation = _model("NormativeRelationVersion")
    review = _model("RelationReviewRecord")

    assert relation.__tablename__ == "normative_relation_versions"
    assert review.__tablename__ == "relation_review_records"


def test_normative_relation_version_contains_only_immutable_content() -> None:
    relation = _model("NormativeRelationVersion")
    columns = _columns(relation)

    required = {
        "normative_relation_version_record_id",
        "normative_relation_id",
        "normative_relation_version",
        "normative_relation_hash",
        "source_subject_type",
        "source_subject_id",
        "source_subject_version",
        "source_subject_hash",
        "target_subject_type",
        "target_subject_id",
        "target_subject_version",
        "target_subject_hash",
        "relation_type",
        "declared_material_validity",
        "structured_content",
        "evidence",
        "normative_references",
        "exact_precedence_policy_reference",
        "provenance",
        "created_at",
        "record_hash",
    }

    forbidden = {
        "decision",
        "decision_state",
        "review_state",
        "status",
        "approved",
        "rejected",
        "blocked",
        "active",
        "activation",
        "suspended",
        "operational_revocation",
        "resolver_effect",
        "calculation_authority",
        "current_subject",
        "latest_subject",
        "current_version",
        "latest_version",
    }

    assert required <= columns
    assert forbidden.isdisjoint(columns)


def test_relation_binds_exact_source_and_target_subjects() -> None:
    relation = _model("NormativeRelationVersion")
    table = relation.__table__

    exact_fields = {
        "source_subject_type",
        "source_subject_id",
        "source_subject_version",
        "source_subject_hash",
        "target_subject_type",
        "target_subject_id",
        "target_subject_version",
        "target_subject_hash",
    }

    for field in exact_fields:
        assert table.c[field].nullable is False

    checks = _check_sql(relation)

    assert "source_subject_version" in checks
    assert "target_subject_version" in checks
    assert "source_subject_hash" in checks
    assert "target_subject_hash" in checks

    assert "current" not in _columns(relation)
    assert "latest" not in _columns(relation)


def test_relation_type_is_explicit_and_closed() -> None:
    relation = _model("NormativeRelationVersion")
    checks = _check_sql(relation)

    assert "relation_type" in checks

    for relation_type in RELATION_TYPES:
        assert relation_type in checks


def test_relation_identity_and_hashes_are_unique() -> None:
    relation = _model("NormativeRelationVersion")
    names = _unique_names(relation)

    assert "uq_normative_relation_versions_identity" in names
    assert "uq_normative_relation_versions_exact_subject" in names
    assert "uq_normative_relation_versions_relation_hash" in names
    assert "uq_normative_relation_versions_record_hash" in names


def test_relation_review_record_has_exact_review_fields_only() -> None:
    review = _model("RelationReviewRecord")
    columns = _columns(review)

    required = {
        "relation_review_record_id",
        "subject_id",
        "subject_version",
        "subject_hash",
        "reviewer",
        "review_event",
        "outcome",
        "evidence",
        "timestamp",
        "record_hash",
    }

    forbidden = {
        "status",
        "state",
        "active",
        "activation",
        "calculation_authority",
        "resolver_effect",
        "precedence_effect",
        "decision",
        "approved",
        "rejected",
    }

    assert required <= columns
    assert forbidden.isdisjoint(columns)

    for field in required:
        assert review.__table__.c[field].nullable is False


def test_review_references_exact_relation_id_version_and_hash() -> None:
    review = _model("RelationReviewRecord")

    expected_local = (
        "subject_id",
        "subject_version",
        "subject_hash",
    )
    expected_remote = (
        "normative_relation_versions.normative_relation_id",
        "normative_relation_versions.normative_relation_version",
        "normative_relation_versions.normative_relation_hash",
    )

    matches = []

    for constraint in review.__table__.constraints:
        if not isinstance(constraint, sa.ForeignKeyConstraint):
            continue

        local = tuple(
            element.parent.name
            for element in constraint.elements
        )
        remote = tuple(
            (
                f"{element.column.table.name}."
                f"{element.column.name}"
            )
            for element in constraint.elements
        )

        matches.append((constraint.name, local, remote))

    assert (
        "fk_relation_review_records_exact_relation",
        expected_local,
        expected_remote,
    ) in matches


def test_review_event_and_outcome_are_separate_closed_enums() -> None:
    review = _model("RelationReviewRecord")
    checks = _check_sql(review)

    assert "review_event" in checks
    assert "outcome" in checks

    for review_event in REVIEW_EVENTS:
        assert review_event in checks

    for outcome in REVIEW_OUTCOMES:
        assert outcome in checks

    assert "revisao_concluida" in checks
    assert "validada" in checks
    assert "rejeitada" in checks
    assert "bloqueada" in checks


def test_invalid_review_event_outcome_pair_is_rejected() -> None:
    validator = getattr(
        models,
        "_adr020_validate_relation_review_insert",
        None,
    )
    assert validator is not None

    target = SimpleNamespace(
        relation_review_record_id="review-1",
        subject_id="relation-1",
        subject_version=1,
        subject_hash="a" * 64,
        reviewer="auditor",
        review_event="revisao_concluida",
        outcome="pendente",
        evidence={"source": "test"},
        record_hash="b" * 64,
    )

    with pytest.raises(ValueError, match="event/outcome"):
        validator(None, None, target)


def test_models_are_append_only_and_have_insert_validators() -> None:
    relation = _model("NormativeRelationVersion")
    review = _model("RelationReviewRecord")

    relation_validator = getattr(
        models,
        "_adr020_validate_normative_relation_version_insert",
        None,
    )
    review_validator = getattr(
        models,
        "_adr020_validate_relation_review_insert",
        None,
    )
    mutation_guard = getattr(
        models,
        "_adr020_reject_append_only_mutation",
        None,
    )

    assert relation_validator is not None
    assert review_validator is not None
    assert mutation_guard is not None

    assert event.contains(
        relation,
        "before_insert",
        relation_validator,
    )
    assert event.contains(
        review,
        "before_insert",
        review_validator,
    )

    for model in (relation, review):
        assert event.contains(
            model,
            "before_update",
            mutation_guard,
        )
        assert event.contains(
            model,
            "before_delete",
            mutation_guard,
        )


def test_migration_identity_lineage_and_exact_scope() -> None:
    source = _migration_source()

    assert (
        'revision: str = "0021_adr020_relation_foundation"'
        in source
    )
    assert (
        'down_revision: str = "0020_adr020_rule_foundation"'
        in source
    )

    created_tables = re.findall(
        r'op\.create_table\(\s*["\']([^"\']+)["\']',
        source,
    )

    assert created_tables == [
        "normative_relation_versions",
        "relation_review_records",
    ]


def test_migration_declares_relational_and_review_contracts() -> None:
    source = _migration_source().lower()

    required_fragments = {
        "normative_relation_id",
        "normative_relation_version",
        "normative_relation_hash",
        "source_subject_type",
        "source_subject_id",
        "source_subject_version",
        "source_subject_hash",
        "target_subject_type",
        "target_subject_id",
        "target_subject_version",
        "target_subject_hash",
        "relation_type",
        "fk_relation_review_records_exact_relation",
        "adr020_validate_normative_relation_version",
        "adr020_validate_relation_review_event",
        "review_event",
        "outcome",
        "forbidden relationreviewrecord transition",
        "postgresql-only",
        "before update or delete",
        "before truncate",
        "for table_name in _append_only_tables",
    }

    for fragment in required_fragments:
        assert fragment in source

    for relation_type in RELATION_TYPES:
        assert relation_type in source

    for review_event in REVIEW_EVENTS:
        assert review_event in source

    for outcome in REVIEW_OUTCOMES:
        assert outcome in source


def test_migration_is_irreversible_and_grants_no_authority() -> None:
    source = _migration_source()
    lowered = source.lower()

    assert "irreversible" in lowered
    assert "raise runtimeerror" in lowered
    assert "op.drop_table" not in lowered

    downgrade = lowered.split("def downgrade()", 1)[1]
    assert "truncate" not in downgrade

    assert "does not authorize" in lowered
    assert "activation" in lowered
    assert "calculation" in lowered
    assert "resolver" in lowered
    assert "precedence" in lowered
