"""DT-CONTADOR-01: contador_empresa_vinculo — vínculo soberano contador↔empresa

Revision ID: 0012_contador_empresa_vinculo
Revises: 0011_unique_relatorio_xml_chave
Create Date: 2026-06-23

ADR-004: nenhum contador actua sobre documento de empresa sem vínculo
activo, atribuição válida e escopo definido.

Esta migration cria a entidade base do Modelo D-Soberano.

POSTGRESQL-ONLY — decisão institucional ADR-004 / DT-CONTADOR-01.
SQLite é ambiente de testes funcionais, não fonte canónica de schema.
A migration falha explicitamente se executada fora de PostgreSQL.

Escopo desta revision (1 intenção):
  - Tabela contador_empresa_vinculo
  - escopo_chave VARCHAR(100) NOT NULL — chave canónica de unicidade
  - escopo JSONB nullable — detalhe auditável / expansível
  - Check constraints de domínio (origem, status, INV-VINCULO-05, escopo_chave)
  - Índices operacionais
  - INV-VINCULO-03: partial unique em (contador_id, empresa_id, escopo_chave)
    WHERE status = 'activo'

INV-VINCULO-05: origem='sistema' exige policy_version NOT NULL
  Enforced no banco: origem != 'sistema' OR policy_version IS NOT NULL

Fora de escopo aqui (migration seguinte):
  - homologacao_atribuicao (0013)
  - Models SQLAlchemy / serviço de autorização
  - DT-DB-01 (import circular database.py)

Sem backfill. Sem dados legados a migrar — tabela nova, vazia.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0012_contador_empresa_vinculo'
down_revision: str = '0011_unique_relatorio_xml_chave'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarda PostgreSQL-only — falha limpo em ambiente errado
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0012_contador_empresa_vinculo é PostgreSQL-only "
            "por decisão ADR-004 / DT-CONTADOR-01. "
            f"Dialect detectado: {bind.dialect.name}"
        )

    op.create_table(
        'contador_empresa_vinculo',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'contador_id',
            sa.Integer(),
            sa.ForeignKey('perfis_contador.id'),
            nullable=False,
        ),
        sa.Column(
            'empresa_id',
            sa.Integer(),
            sa.ForeignKey('empresas.id'),
            nullable=False,
        ),
        # Chave canónica de unicidade — lowercase, sem espaços
        # Exemplos: homologacao_documental, parecer_tecnico, analise_xml
        sa.Column('escopo_chave', sa.String(100), nullable=False),
        # Detalhe auditável — não usado no índice único
        sa.Column('escopo', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('origem', sa.String(20), nullable=False),
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='activo',
        ),
        sa.Column(
            'criado_por_user_id',
            sa.Integer(),
            sa.ForeignKey('usuarios.id'),
            nullable=False,
        ),
        # Snapshot legível — não identificador soberano primário
        sa.Column('criado_por_email', sa.String(255), nullable=False),
        sa.Column(
            'criado_em',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('validade', sa.DateTime(), nullable=True),
        # Obrigatório quando origem='sistema' (enforced por check abaixo)
        sa.Column('policy_version', sa.String(50), nullable=True),
        sa.Column('revogado_em', sa.DateTime(), nullable=True),
        sa.Column(
            'revogado_por_user_id',
            sa.Integer(),
            sa.ForeignKey('usuarios.id'),
            nullable=True,
        ),
    )

    # Domínio de origem
    op.create_check_constraint(
        'ck_vinculo_origem_valida',
        'contador_empresa_vinculo',
        "origem IN ('admin', 'cliente', 'sistema')",
    )

    # Domínio de status
    op.create_check_constraint(
        'ck_vinculo_status_valido',
        'contador_empresa_vinculo',
        "status IN ('activo', 'suspenso', 'revogado', 'expirado')",
    )

    # INV-VINCULO-05 — matching autónomo exige policy auditável
    op.create_check_constraint(
        'ck_vinculo_sistema_exige_policy',
        'contador_empresa_vinculo',
        "origem != 'sistema' OR policy_version IS NOT NULL",
    )

    # escopo_chave normalizado — apenas lowercase + caracteres canónicos
    op.create_check_constraint(
        'ck_vinculo_escopo_chave_normalizado',
        'contador_empresa_vinculo',
        "escopo_chave = lower(escopo_chave)",
    )

    # escopo_chave não pode ser vazio ou só espaços
    op.create_check_constraint(
        'ck_vinculo_escopo_chave_nao_vazio',
        'contador_empresa_vinculo',
        "length(trim(escopo_chave)) > 0",
    )

    # Índices operacionais
    op.create_index(
        'ix_vinculo_contador_id',
        'contador_empresa_vinculo',
        ['contador_id'],
    )
    op.create_index(
        'ix_vinculo_empresa_id',
        'contador_empresa_vinculo',
        ['empresa_id'],
    )
    op.create_index(
        'ix_vinculo_status',
        'contador_empresa_vinculo',
        ['status'],
    )

    # INV-VINCULO-03 — um vínculo activo por (contador, empresa, escopo_chave)
    # escopo_chave é NOT NULL, logo um único índice parcial é suficiente
    op.execute("""
        CREATE UNIQUE INDEX uq_vinculo_activo_escopo_chave
        ON contador_empresa_vinculo (contador_id, empresa_id, escopo_chave)
        WHERE status = 'activo'
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_vinculo_activo_escopo_chave')
    op.drop_index('ix_vinculo_status', table_name='contador_empresa_vinculo')
    op.drop_index('ix_vinculo_empresa_id', table_name='contador_empresa_vinculo')
    op.drop_index('ix_vinculo_contador_id', table_name='contador_empresa_vinculo')
    op.drop_constraint('ck_vinculo_escopo_chave_nao_vazio', 'contador_empresa_vinculo', type_='check')
    op.drop_constraint('ck_vinculo_escopo_chave_normalizado', 'contador_empresa_vinculo', type_='check')
    op.drop_constraint('ck_vinculo_sistema_exige_policy', 'contador_empresa_vinculo', type_='check')
    op.drop_constraint('ck_vinculo_status_valido', 'contador_empresa_vinculo', type_='check')
    op.drop_constraint('ck_vinculo_origem_valida', 'contador_empresa_vinculo', type_='check')
    op.drop_table('contador_empresa_vinculo')
