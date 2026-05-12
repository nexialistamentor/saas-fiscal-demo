"""add check constraint perfis_contador status

Revision ID: 0007_constraint_perfil_contador
Revises: 0006_homologacoes_documentais
Create Date: 2026-05-12
"""
from alembic import op

revision: str = '0007_constraint_perfil_contador'
down_revision: str = '0006_homologacoes_documentais'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_perfis_contador_status_valido",
        "perfis_contador",
        "status IN ('pendente', 'aprovado', 'suspenso')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_perfis_contador_status_valido",
        "perfis_contador",
        type_="check",
    )
