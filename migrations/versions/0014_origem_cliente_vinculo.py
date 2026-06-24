"""0014_origem_cliente_vinculo

Adiciona coluna origem_cliente a contador_empresa_vinculo.

ADR-005 — Carteira Contador Anti-Captura:
  origem         = quem criou tecnicamente o vínculo
  origem_cliente = de onde veio a relação comercial do cliente

Valores:
  contador_parceiro  — empresa veio da carteira de um contador parceiro
  plataforma_directa — empresa entrou directamente pela plataforma
  empresa_directa    — empresa estabeleceu relação directa sem intermediário
  legado             — vínculos anteriores a esta ADR (backfill retroactivo apenas)

INV-CARTEIRA-06: "legado" só para backfill histórico.
Novos vínculos devem declarar origem_cliente explicitamente.
server_default é removido após backfill para forçar declaração explícita.

Revision ID: 0014
Revises: 0013
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    dialect = op.get_bind().dialect.name
    if dialect != "postgresql":
        raise Exception(
            "Migration 0014 é PostgreSQL-only. "
            "Ambiente actual: " + dialect
        )

    # 1. Adicionar coluna como nullable com default temporário para backfill
    op.add_column(
        "contador_empresa_vinculo",
        sa.Column(
            "origem_cliente",
            sa.String(30),
            nullable=True,
            server_default="legado",
        ),
    )

    # 2. Backfill: vínculos existentes recebem "legado"
    op.execute(
        "UPDATE contador_empresa_vinculo "
        "SET origem_cliente = 'legado' "
        "WHERE origem_cliente IS NULL"
    )

    # 3. Tornar não-nullable e remover server_default
    # INV-CARTEIRA-06: novos vínculos devem declarar origem_cliente — sem default silencioso
    op.alter_column(
        "contador_empresa_vinculo",
        "origem_cliente",
        existing_type=sa.String(30),
        nullable=False,
        server_default=None,
    )

    # 4. Check constraint de domínio
    op.create_check_constraint(
        "ck_vinculo_origem_cliente_dominio",
        "contador_empresa_vinculo",
        "origem_cliente IN ('contador_parceiro', 'plataforma_directa', 'empresa_directa', 'legado')",
    )

    # 5. Índice para filtrar carteira do contador
    op.create_index(
        "ix_vinculo_origem_cliente",
        "contador_empresa_vinculo",
        ["origem_cliente"],
    )


def downgrade():
    op.drop_index("ix_vinculo_origem_cliente", table_name="contador_empresa_vinculo")
    op.drop_constraint(
        "ck_vinculo_origem_cliente_dominio",
        "contador_empresa_vinculo",
        type_="check",
    )
    op.drop_column("contador_empresa_vinculo", "origem_cliente")
