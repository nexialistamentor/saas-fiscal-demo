"""Fecha unicidade canonica de CNPJ em empresas."""

from alembic import op
import sqlalchemy as sa


revision: str = "0054_empresa_cnpj_unique"
down_revision: str = "0053_tax_report_checkout_intents"
branch_labels = None
depends_on = None


_CONSTRAINT_NAME = "uq_empresas_cnpj"
_PLACEHOLDER_HISTORICO = "00000000000000"


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name != "postgresql":
        raise RuntimeError("0054 requires PostgreSQL")

    # Evidencia de producao mostrou este valor exclusivamente em registros
    # sinteticos de smoke. CNPJ ausente deve ser NULL, nao um identificador falso.
    bind.execute(
        sa.text(
            """
            UPDATE empresas
            SET cnpj = NULL
            WHERE cnpj = :placeholder
            """
        ),
        {"placeholder": _PLACEHOLDER_HISTORICO},
    )

    duplicados = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT cnpj
                FROM empresas
                WHERE cnpj IS NOT NULL
                GROUP BY cnpj
                HAVING COUNT(*) > 1
            ) AS grupos_duplicados
            """
        )
    ).scalar_one()

    if duplicados != 0:
        raise RuntimeError(
            "0054 blocked: duplicate non-null empresas.cnpj remain"
        )

    op.create_unique_constraint(
        _CONSTRAINT_NAME,
        "empresas",
        ["cnpj"],
    )


def downgrade() -> None:
    op.drop_constraint(
        _CONSTRAINT_NAME,
        "empresas",
        type_="unique",
    )
