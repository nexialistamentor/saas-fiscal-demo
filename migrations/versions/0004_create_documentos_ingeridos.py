"""create documentos_ingeridos: evidência do pipeline documental

Revision ID: 0004_documentos_ingeridos
Revises: 0003_pagamento_tentativas
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_documentos_ingeridos"
down_revision: str = "0003_pagamento_tentativas"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documentos_ingeridos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=True),
        sa.Column("conteudo_sha256", sa.String(length=64), nullable=False),
        sa.Column("evidencia_em", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("versao_pipeline", sa.String(length=32), nullable=False),
        sa.Column("tipo_documento", sa.String(length=32), nullable=False),
        sa.Column("score_confianca", sa.Float(), nullable=False),
        sa.Column("decisao", sa.String(length=32), nullable=False),
        sa.Column(
            "requereu_ocr",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "campos_extraidos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "campos_nao_extraidos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "motivos",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "validado_humano",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("validado_por", sa.String(length=255), nullable=True),
        sa.Column("validado_em", sa.DateTime(), nullable=True),
        sa.Column("nome_ficheiro", sa.String(length=512), nullable=True),
        sa.Column(
            "tamanho_bytes",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_index(
        "ix_documentos_ingeridos_user_id",
        "documentos_ingeridos",
        ["user_id"],
    )
    op.create_index(
        "ix_documentos_ingeridos_empresa_id",
        "documentos_ingeridos",
        ["empresa_id"],
    )
    op.create_index(
        "ix_documentos_ingeridos_conteudo_sha256",
        "documentos_ingeridos",
        ["conteudo_sha256"],
    )
    op.create_index(
        "ix_documentos_ingeridos_tipo_documento",
        "documentos_ingeridos",
        ["tipo_documento"],
    )
    op.create_index(
        "ix_documentos_ingeridos_decisao",
        "documentos_ingeridos",
        ["decisao"],
    )


def downgrade() -> None:
    op.drop_index("ix_documentos_ingeridos_decisao", table_name="documentos_ingeridos")
    op.drop_index("ix_documentos_ingeridos_tipo_documento", table_name="documentos_ingeridos")
    op.drop_index("ix_documentos_ingeridos_conteudo_sha256", table_name="documentos_ingeridos")
    op.drop_index("ix_documentos_ingeridos_empresa_id", table_name="documentos_ingeridos")
    op.drop_index("ix_documentos_ingeridos_user_id", table_name="documentos_ingeridos")
    op.drop_table("documentos_ingeridos")
