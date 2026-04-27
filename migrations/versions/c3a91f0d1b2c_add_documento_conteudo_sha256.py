"""add documento conteudo_sha256 (fingerprint)

Revision ID: c3a91f0d1b2c
Revises: b2422ebc2669
Create Date: 2026-04-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a91f0d1b2c"
down_revision: Union[str, Sequence[str], None] = "b2422ebc2669"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documentos_fiscais", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("conteudo_sha256", sa.String(length=64), nullable=True),
            )
            batch_op.create_index(
                "ix_documentos_fiscais_conteudo_sha256",
                ["conteudo_sha256"],
                unique=False,
            )
            batch_op.create_unique_constraint(
                "uq_documentos_fiscais_empresa_conteudo_sha256",
                ["empresa_id", "conteudo_sha256"],
            )
    else:
        op.add_column(
            "documentos_fiscais",
            sa.Column("conteudo_sha256", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "ix_documentos_fiscais_conteudo_sha256",
            "documentos_fiscais",
            ["conteudo_sha256"],
            unique=False,
        )
        op.create_unique_constraint(
            "uq_documentos_fiscais_empresa_conteudo_sha256",
            "documentos_fiscais",
            ["empresa_id", "conteudo_sha256"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("documentos_fiscais", schema=None) as batch_op:
            batch_op.drop_constraint(
                "uq_documentos_fiscais_empresa_conteudo_sha256",
                type_="unique",
            )
            batch_op.drop_index("ix_documentos_fiscais_conteudo_sha256")
            batch_op.drop_column("conteudo_sha256")
    else:
        op.drop_constraint(
            "uq_documentos_fiscais_empresa_conteudo_sha256",
            "documentos_fiscais",
            type_="unique",
        )
        op.drop_index("ix_documentos_fiscais_conteudo_sha256", table_name="documentos_fiscais")
        op.drop_column("documentos_fiscais", "conteudo_sha256")
