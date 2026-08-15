"""Reconcile the pilot schema blockers already owned by revision 0043.

Revision ID: 0044_pilot_schema_blockers
Revises: 0043_reconcile_tabela_mva_schema
"""

from alembic import op
import sqlalchemy as sa


revision = "0044_pilot_schema_blockers"
down_revision = "0043_reconcile_tabela_mva_schema"
branch_labels = None
depends_on = None


_CANONICAL_ROLE_CHECK = (
    "((role)::text = ANY ((ARRAY['user'::character varying, "
    "'admin'::character varying, 'contador'::character varying])::text[]))"
)


def _column(bind, table_name, column_name):
    return bind.execute(
        sa.text(
            """
            SELECT a.attnotnull, t.typname
            FROM pg_catalog.pg_class AS c
            JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_attribute AS a ON a.attrelid = c.oid
            JOIN pg_catalog.pg_type AS t ON t.oid = a.atttypid
            WHERE n.nspname = current_schema()
              AND c.relname = :table_name
              AND c.relkind IN ('r', 'p')
              AND a.attname = :column_name
              AND a.attnum > 0
              AND NOT a.attisdropped
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).one_or_none()


def _null_count(bind, table_name, column_name):
    # Identifiers are closed constants supplied only by upgrade().
    return bind.execute(
        sa.text(
            f"SELECT count(*) FROM {table_name} "
            f"WHERE {column_name} IS NULL"
        )
    ).scalar_one()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("0044 requires PostgreSQL")

    # Complete every read-only gate before scheduling the first DDL.
    repairs = []
    for table_name, column_name, accepted_type in (
        ("usuarios", "consulta_paga", "bool"),
        ("planos", "limite_analises", "int4"),
    ):
        state = _column(bind, table_name, column_name)
        if state is None:
            raise RuntimeError(
                f"0044 missing {table_name}.{column_name}"
            )
        not_null, type_name = state
        if type_name != accepted_type:
            raise RuntimeError(
                f"0044 noncanonical type for {table_name}.{column_name}"
            )
        null_count = _null_count(bind, table_name, column_name)
        if null_count:
            raise RuntimeError(
                f"0044 NULL values in {table_name}.{column_name}"
            )
        if not not_null:
            repairs.append((table_name, column_name))

    role_state = _column(bind, "usuarios", "role")
    if role_state is None:
        raise RuntimeError("0044 missing usuarios.role")

    invalid_roles = bind.execute(
        sa.text(
            """
            SELECT count(*)
            FROM usuarios
            WHERE role IS NOT NULL
              AND role NOT IN ('user', 'admin', 'contador')
            """
        )
    ).scalar_one()
    if invalid_roles:
        raise RuntimeError("0044 invalid non-NULL usuarios.role values")

    constraints = bind.execute(
        sa.text(
            """
            SELECT
                con.conname,
                rel.relname,
                con.contype,
                con.convalidated,
                pg_catalog.pg_get_expr(con.conbin, con.conrelid, false)
            FROM pg_catalog.pg_constraint AS con
            JOIN pg_catalog.pg_class AS rel ON rel.oid = con.conrelid
            JOIN pg_catalog.pg_namespace AS nsp ON nsp.oid = rel.relnamespace
            LEFT JOIN pg_catalog.pg_attribute AS role_col
              ON role_col.attrelid = rel.oid
             AND role_col.attname = 'role'
             AND role_col.attnum > 0
             AND NOT role_col.attisdropped
            WHERE nsp.nspname = current_schema()
              AND (
                    con.conname = 'ck_usuarios_role_valido'
                    OR (
                        rel.relname = 'usuarios'
                        AND con.contype = 'c'
                        AND role_col.attnum = ANY (con.conkey)
                    )
                  )
            ORDER BY con.oid
            """
        )
    ).all()

    canonical = [
        row for row in constraints
        if row[0] == "ck_usuarios_role_valido"
        and row[1] == "usuarios"
        and row[2] == "c"
        and row[3] is True
        and row[4] == _CANONICAL_ROLE_CHECK
    ]
    if constraints:
        if len(constraints) != 1 or len(canonical) != 1:
            raise RuntimeError("0044 ambiguous or noncanonical role constraint")
        add_role_check = False
    else:
        add_role_check = True

    # Fixed execution order for the operations selected by the preflight.
    if ("usuarios", "consulta_paga") in repairs:
        op.alter_column("usuarios", "consulta_paga", nullable=False)
    if ("planos", "limite_analises") in repairs:
        op.alter_column("planos", "limite_analises", nullable=False)
    if add_role_check:
        op.create_check_constraint(
            "ck_usuarios_role_valido",
            "usuarios",
            "role IN ('user', 'admin', 'contador')",
        )


def downgrade() -> None:
    """Deliberate structural no-op: 0044 restores contract owned by 0043.

    Recreating the known drift on downgrade would violate that pre-existing
    contract, so only Alembic's revision marker is allowed to move backwards.
    """
