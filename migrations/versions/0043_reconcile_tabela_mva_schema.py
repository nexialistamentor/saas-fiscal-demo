"""0043_reconcile_tabela_mva_schema

Reconciliacao soberana do schema fisico de tabela_mva.

Revision ID: 0043_reconcile_tabela_mva_schema
Revises: 0042_patrol_effect_idempotency
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa


revision: str = "0043_reconcile_tabela_mva_schema"
down_revision: str = "0042_patrol_effect_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "0043 requires PostgreSQL"
        )

    inspected_columns = sa.inspect(bind).get_columns("tabela_mva")
    existing_columns = {
        column["name"]
        for column in inspected_columns
    }
    column_definitions = {
        column["name"]: column
        for column in inspected_columns
    }

    canonical_lengths = {
        "fonte_legal": 500,
        "nivel_confianca_fonte": 40,
        "fonte_url": 1000,
        "url_fonte": 1000,
        "importado_por": 100,
    }

    columns_to_narrow = []

    for column_name, canonical_length in canonical_lengths.items():
        definition = column_definitions.get(column_name)
        if definition is None:
            continue

        column_type = definition["type"]
        if not isinstance(column_type, sa.String):
            continue

        current_length = column_type.length
        requires_narrowing_guard = (
            current_length is None
            or current_length > canonical_length
        )
        if not requires_narrowing_guard:
            continue

        oversized_count = bind.execute(
            sa.text(
                f"""
                SELECT COUNT(*)
                FROM tabela_mva
                WHERE {column_name} IS NOT NULL
                  AND char_length({column_name}) > {canonical_length}
                """
            )
        ).scalar_one()

        if oversized_count:
            raise RuntimeError(
                "0043 values exceed canonical length"
            )

        if column_name != "fonte_url":
            columns_to_narrow.append(
                (column_name, canonical_length)
            )

    if (
        "fonte_url" in existing_columns
        and "url_fonte" in existing_columns
    ):
        conflict_count = bind.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM tabela_mva
                WHERE fonte_url IS NOT NULL
                  AND url_fonte IS NOT NULL
                  AND fonte_url IS DISTINCT FROM url_fonte
                """
            )
        ).scalar_one()

        if conflict_count:
            raise RuntimeError(
                "0043 conflicting fonte_url and url_fonte"
            )

    for column_name, canonical_length in columns_to_narrow:
        op.alter_column(
            "tabela_mva",
            column_name,
            type_=sa.String(length=canonical_length),
        )

    if (
        "fonte_url" in existing_columns
        and "url_fonte" in existing_columns
    ):
        bind.execute(
            sa.text(
                """
                UPDATE tabela_mva
                SET url_fonte = fonte_url
                WHERE url_fonte IS NULL
                  AND fonte_url IS NOT NULL
                """
            )
        )
        op.drop_column("tabela_mva", "fonte_url")
        existing_columns.remove("fonte_url")

    if (
        "fonte_url" in existing_columns
        and "url_fonte" not in existing_columns
    ):
        op.alter_column(
            "tabela_mva",
            "fonte_url",
            new_column_name="url_fonte",
            type_=sa.String(length=1000),
        )
        existing_columns.remove("fonte_url")
        existing_columns.add("url_fonte")

    required_columns = (
        sa.Column("fonte_legal", sa.String(length=500), nullable=True),
        sa.Column(
            "nivel_confianca_fonte",
            sa.String(length=40),
            nullable=True,
        ),
        sa.Column("url_fonte", sa.String(length=1000), nullable=True),
        sa.Column("importado_em", sa.DateTime(), nullable=True),
        sa.Column("importado_por", sa.String(length=100), nullable=True),
    )

    for column in required_columns:
        if column.name not in existing_columns:
            op.add_column("tabela_mva", column)


def downgrade() -> None:
    raise RuntimeError(
        "0043 tabela_mva reconciliation is irreversible"
    )
