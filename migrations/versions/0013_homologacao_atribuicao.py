"""DT-CONTADOR-01: homologacao_atribuicao — atribuição soberana documento↔contador

Revision ID: 0013_homologacao_atribuicao
Revises: 0012_contador_empresa_vinculo
Create Date: 2026-06-23

ADR-004: nenhum contador pode actuar sobre documento sem vínculo activo,
atribuição válida e escopo definido.

POSTGRESQL-ONLY — decisão institucional ADR-004 / DT-CONTADOR-01.
A migration falha explicitamente se executada fora de PostgreSQL.

Escopo desta revision (1 intenção):
  - Tabela homologacao_atribuicao
  - Check constraints de domínio (status, complexidade, modo_atribuicao)
  - INV-VINCULO-02: partial unique (documento_ingerido_id, escopo_chave)
    WHERE status IN ('atribuida', 'aceite')
  - INV-VINCULO-05 reforçado: modo_atribuicao='manual' OR policy_version IS NOT NULL
  - escopo_chave normalizado (lowercase, não vazio)
  - Índices operacionais

Nota institucional — INV-VINCULO-01:
  INV-VINCULO-01 (documento.empresa_id == atribuicao.empresa_id ==
  vinculo.empresa_id) NÃO é enforced por FK composta nesta revision.
  Motivo: documentos_ingeridos não possui UNIQUE(id, empresa_id) e é
  tabela legada com dados em produção. Alterar essa tabela requer
  auditoria própria fora do escopo de DT-CONTADOR-01.
  A coerência é garantida provisoriamente pela service layer DT-CONTADOR-01.

Dívida registada:
  DT-CONTADOR-02 — avaliar constraints compostas para enforçar INV-VINCULO-01
  no banco após auditoria de documentos_ingeridos e contador_empresa_vinculo.

Fora de escopo aqui:
  - Models SQLAlchemy (entregável separado)
  - Serviço de autorização / refactor de criar_fila_homologacao
  - Alteração ao router /assumir
  - UNIQUE(id, empresa_id) em documentos_ingeridos (DT-CONTADOR-02)
  - DT-DB-01 (import circular database.py)

Sem backfill. Tabela nova, vazia.
HomologacaoDocumental existente antes de DT-CONTADOR-01 é legado tolerado —
não tem homologacao_atribuicao correspondente (ressalva ADR-004).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0013_homologacao_atribuicao'
down_revision: str = '0012_contador_empresa_vinculo'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarda PostgreSQL-only — falha limpo em ambiente errado
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0013_homologacao_atribuicao é PostgreSQL-only "
            "por decisão ADR-004 / DT-CONTADOR-01. "
            f"Dialect detectado: {bind.dialect.name}"
        )

    op.create_table(
        'homologacao_atribuicao',
        sa.Column('id', sa.Integer(), primary_key=True),
        # INV-VINCULO-01: coerência empresa garantida pela service layer (DT-CONTADOR-02)
        sa.Column(
            'documento_ingerido_id',
            sa.Integer(),
            sa.ForeignKey('documentos_ingeridos.id'),
            nullable=False,
        ),
        sa.Column(
            'empresa_id',
            sa.Integer(),
            sa.ForeignKey('empresas.id'),
            nullable=False,
        ),
        sa.Column(
            'contador_id',
            sa.Integer(),
            sa.ForeignKey('perfis_contador.id'),
            nullable=False,
        ),
        sa.Column(
            'vinculo_id',
            sa.Integer(),
            sa.ForeignKey('contador_empresa_vinculo.id'),
            nullable=False,
        ),
        # Chave canónica de escopo — mesma semântica que contador_empresa_vinculo.escopo_chave
        # Exemplos: homologacao_documental, parecer_tecnico, analise_xml
        sa.Column('escopo_chave', sa.String(100), nullable=False),
        # Detalhe do escopo atribuído — não usado no índice único
        # escopo_chave = unicidade operacional
        # escopo JSONB = detalhe da autorização
        # auditoria JSONB = trilha do acto de atribuição
        sa.Column('escopo', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        # Estados activos: atribuida, aceite
        # Estados finais: concluida, recusada, expirada
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='atribuida',
        ),
        sa.Column('complexidade', sa.String(20), nullable=False),
        sa.Column('modo_atribuicao', sa.String(20), nullable=False),
        # Obrigatório quando modo_atribuicao != 'manual' (enforced por check abaixo)
        sa.Column('policy_version', sa.String(50), nullable=True),
        sa.Column('regra_matching_id', sa.String(100), nullable=True),
        sa.Column(
            'atribuido_em',
            sa.DateTime(),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('aceite_em', sa.DateTime(), nullable=True),
        sa.Column('concluido_em', sa.DateTime(), nullable=True),
        # Trilha operacional V1 — direcção soberana é ledger append-only (ADR-004)
        sa.Column('auditoria', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # Domínio de status
    op.create_check_constraint(
        'ck_atribuicao_status_valido',
        'homologacao_atribuicao',
        "status IN ('atribuida', 'aceite', 'concluida', 'recusada', 'expirada')",
    )

    # Domínio de complexidade
    op.create_check_constraint(
        'ck_atribuicao_complexidade_valida',
        'homologacao_atribuicao',
        "complexidade IN ('baixa', 'media', 'alta')",
    )

    # Domínio de modo_atribuicao
    op.create_check_constraint(
        'ck_atribuicao_modo_valido',
        'homologacao_atribuicao',
        "modo_atribuicao IN ('automatico', 'recomendado', 'manual')",
    )

    # INV-VINCULO-05 reforçado — automatico e recomendado exigem policy auditável
    # manual pode não exigir (ex: Miguel atribui directamente no piloto)
    # length(trim(...)) > 0 impede policy_version = '' ou '   '
    op.create_check_constraint(
        'ck_atribuicao_nao_manual_exige_policy',
        'homologacao_atribuicao',
        "modo_atribuicao = 'manual' OR length(trim(policy_version)) > 0",
    )

    # escopo_chave normalizado — lowercase, não vazio, formato canónico
    # PostgreSQL-only: regex via ~ operador
    op.create_check_constraint(
        'ck_atribuicao_escopo_chave_normalizado',
        'homologacao_atribuicao',
        "escopo_chave = lower(escopo_chave)",
    )
    op.create_check_constraint(
        'ck_atribuicao_escopo_chave_nao_vazio',
        'homologacao_atribuicao',
        "length(trim(escopo_chave)) > 0",
    )
    # Impede espaços, acentos e caracteres especiais — só a-z, 0-9, _.:-
    op.create_check_constraint(
        'ck_atribuicao_escopo_chave_formato',
        'homologacao_atribuicao',
        "escopo_chave ~ '^[a-z0-9_.:-]+$'",
    )

    # Índices operacionais
    op.create_index(
        'ix_atribuicao_documento_id',
        'homologacao_atribuicao',
        ['documento_ingerido_id'],
    )
    op.create_index(
        'ix_atribuicao_contador_id',
        'homologacao_atribuicao',
        ['contador_id'],
    )
    op.create_index(
        'ix_atribuicao_vinculo_id',
        'homologacao_atribuicao',
        ['vinculo_id'],
    )
    op.create_index(
        'ix_atribuicao_status',
        'homologacao_atribuicao',
        ['status'],
    )

    # INV-VINCULO-02 — um documento não pode ter mais de uma atribuição activa
    # por escopo_chave. Estados activos: atribuida, aceite.
    op.execute("""
        CREATE UNIQUE INDEX uq_atribuicao_activa_por_documento_escopo
        ON homologacao_atribuicao (documento_ingerido_id, escopo_chave)
        WHERE status IN ('atribuida', 'aceite')
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS uq_atribuicao_activa_por_documento_escopo')
    op.drop_index('ix_atribuicao_status', table_name='homologacao_atribuicao')
    op.drop_index('ix_atribuicao_vinculo_id', table_name='homologacao_atribuicao')
    op.drop_index('ix_atribuicao_contador_id', table_name='homologacao_atribuicao')
    op.drop_index('ix_atribuicao_documento_id', table_name='homologacao_atribuicao')
    op.drop_constraint('ck_atribuicao_escopo_chave_formato', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_escopo_chave_nao_vazio', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_escopo_chave_normalizado', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_nao_manual_exige_policy', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_modo_valido', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_complexidade_valida', 'homologacao_atribuicao', type_='check')
    op.drop_constraint('ck_atribuicao_status_valido', 'homologacao_atribuicao', type_='check')
    op.drop_table('homologacao_atribuicao')
