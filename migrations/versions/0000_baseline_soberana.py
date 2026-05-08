"""
BASELINE SOBERANA — estado oficial da plataforma L2 em 2026-05-08.

Esta migração representa o schema real do PostgreSQL Railway.

Permite bootstrap limpo de qualquer ambiente sem dependência de create_all.


Revision ID: 0000_baseline
Revises: None
Create Date: 2026-05-08

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0000_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = ('baseline',)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('planos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(), nullable=False),
        sa.Column('limite_cnpjs', sa.Integer(), nullable=False),
        sa.Column('limite_analises', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('preco', sa.Numeric(10, 2), nullable=False, server_default='0.00'),
        sa.Column('billing_type', sa.String(), nullable=False, server_default='monthly'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('tipo_acesso', sa.String(), nullable=False, server_default='relatorio'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nome'),
    )
    op.create_index('ix_planos_id', 'planos', ['id'])

    op.create_table('usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('plano_id', sa.Integer(), sa.ForeignKey('planos.id'), nullable=True),
        sa.Column('consulta_paga', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('role', sa.String(20), nullable=False, server_default='user'),
        sa.Column('cpf', sa.String(11), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('cpf'),
        sa.CheckConstraint("role IN ('user', 'admin', 'contador')", name='ck_usuarios_role_valido'),
    )
    op.create_index('ix_usuarios_id', 'usuarios', ['id'])
    op.create_index('ix_usuarios_email', 'usuarios', ['email'])
    op.create_index('ix_usuarios_role', 'usuarios', ['role'])
    op.create_index('ix_usuarios_cpf', 'usuarios', ['cpf'])

    op.create_table('empresas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cnpj', sa.String(), nullable=True),
        sa.Column('razao_social', sa.String(), nullable=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('regime_tributario', sa.String(50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_empresas_id', 'empresas', ['id'])

    op.create_table('referencias_legais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(50), nullable=True),
        sa.Column('titulo', sa.String(200), nullable=True),
        sa.Column('fundamento', sa.Text(), nullable=True),
        sa.Column('descricao', sa.Text(), nullable=True),
        sa.Column('uf', sa.String(2), nullable=True),
        sa.Column('vigencia_inicio', sa.Date(), nullable=True),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('fonte_url', sa.String(500), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('relatorios_analise',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('analysis_type', sa.String(), nullable=True),
        sa.Column('xml_chave', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('tempo_execucao', sa.Float(), nullable=True),
        sa.Column('total_alertas', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('score_resultante', sa.Float(), nullable=True),
        sa.Column('resultado_json', sa.JSON(), nullable=True),
        sa.Column('fingerprint', sa.String(64), nullable=True),
        sa.Column('pago', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('memorial_gerado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_relatorios_analise_id', 'relatorios_analise', ['id'])

    op.create_table('documentos_fiscais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('chave_nfe', sa.String(), nullable=True),
        sa.Column('numero_nota', sa.String(), nullable=True),
        sa.Column('data_emissao', sa.Date(), nullable=True),
        sa.Column('tipo', sa.String(), nullable=True),
        sa.Column('valor_total', sa.Float(), nullable=True),
        sa.Column('mva_utilizada', sa.Float(), nullable=True),
        sa.Column('uf_emit', sa.String(2), nullable=True),
        sa.Column('uf_dest', sa.String(2), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('itens_fiscais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('documento_id', sa.Integer(), sa.ForeignKey('documentos_fiscais.id'), nullable=True),
        sa.Column('ncm', sa.String(), nullable=True),
        sa.Column('cfop', sa.String(), nullable=True),
        sa.Column('valor_produto', sa.Float(), nullable=True),
        sa.Column('base_icms', sa.Float(), nullable=True),
        sa.Column('valor_icms', sa.Float(), nullable=True),
        sa.Column('base_st', sa.Float(), nullable=True),
        sa.Column('valor_st', sa.Float(), nullable=True),
        sa.Column('quantidade', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('insights',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=False),
        sa.Column('relatorio_analise_id', sa.Integer(), sa.ForeignKey('relatorios_analise.id'), nullable=True),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('valor_estimado', sa.Float(), nullable=True, server_default='0'),
        sa.Column('impacto', sa.String(), nullable=True),
        sa.Column('descricao', sa.String(), nullable=True),
        sa.Column('recomendacao', sa.String(), nullable=True),
        sa.Column('ncm', sa.String(), nullable=True),
        sa.Column('payload_json', sa.JSON(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('superseded', sa.Boolean(), nullable=False, server_default='false'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_insights_id', 'insights', ['id'])
    op.create_index('ix_insights_empresa_id', 'insights', ['empresa_id'])
    op.create_index('ix_insights_ncm', 'insights', ['ncm'])
    op.create_index('ix_insights_tipo', 'insights', ['tipo'])

    op.create_table('alertas_fiscais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agente', sa.String(), nullable=True),
        sa.Column('tipo', sa.String(), nullable=True),
        sa.Column('descricao', sa.String(), nullable=True),
        sa.Column('nivel', sa.String(), nullable=True),
        sa.Column('empresa_id', sa.Integer(), nullable=True),
        sa.Column('relatorio_analise_id', sa.Integer(), sa.ForeignKey('relatorios_analise.id'), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('silenciado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processado_em', sa.DateTime(), nullable=True),
        sa.Column('processado_por', sa.String(100), nullable=True),
        sa.Column('notas_resolucao', sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_alertas_fiscais_id', 'alertas_fiscais', ['id'])
    op.create_index('ix_alertas_fiscais_agente', 'alertas_fiscais', ['agente'])

    op.create_table('tabela_mva',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estado', sa.String(), nullable=True),
        sa.Column('ncm', sa.String(), nullable=True),
        sa.Column('mva', sa.Float(), nullable=True),
        sa.Column('aliquota_interna', sa.Float(), nullable=True),
        sa.Column('vigencia_inicio', sa.Date(), nullable=True),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('fonte_legal', sa.String(), nullable=True),
        sa.Column('nivel_confianca_fonte', sa.String(), nullable=True),
        sa.Column('fonte_url', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('tabela_pmpf',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('estado', sa.String(2), nullable=True),
        sa.Column('ncm', sa.String(20), nullable=True),
        sa.Column('cest', sa.String(9), nullable=True),
        sa.Column('marca', sa.String(200), nullable=True),
        sa.Column('embalagem_ml', sa.Integer(), nullable=True),
        sa.Column('pmpf_reais', sa.Float(), nullable=True),
        sa.Column('aliquota_interna', sa.Float(), nullable=True),
        sa.Column('vigencia_inicio', sa.Date(), nullable=True),
        sa.Column('vigencia_fim', sa.Date(), nullable=True),
        sa.Column('fonte_legal', sa.String(500), nullable=True),
        sa.Column('url_fonte', sa.String(1000), nullable=True),
        sa.Column('nivel_confianca_fonte', sa.String(40), nullable=True),
        sa.Column('importado_por', sa.String(100), nullable=True),
        sa.Column('importado_em', sa.DateTime(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('termos_aceitacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('versao_termos', sa.String(50), nullable=False),
        sa.Column('aceite_em', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('consentimentos_lgpd',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('versao_politica', sa.String(50), nullable=False),
        sa.Column('finalidade', sa.String(200), nullable=False),
        sa.Column('consentiu', sa.Boolean(), nullable=False),
        sa.Column('consentiu_em', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('pagamentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('plano_id', sa.Integer(), sa.ForeignKey('planos.id'), nullable=True),
        sa.Column('relatorio_analise_id', sa.Integer(), sa.ForeignKey('relatorios_analise.id'), nullable=True),
        sa.Column('idempotency_key', sa.String(), nullable=False),
        sa.Column('valor', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('confirmado_em', sa.DateTime(), nullable=True),
        sa.Column('mp_payment_id', sa.String(), nullable=True),
        sa.Column('mp_status_raw', sa.String(), nullable=True),
        sa.Column('payment_method_id', sa.String(), nullable=False, server_default='pix'),
        sa.Column('qr_code', sa.String(), nullable=True),
        sa.Column('qr_code_base64', sa.String(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key'),
        sa.UniqueConstraint('mp_payment_id'),
    )
    op.create_index('ix_pagamentos_id', 'pagamentos', ['id'])
    op.create_index('ix_pagamentos_mp_payment_id', 'pagamentos', ['mp_payment_id'], unique=True)
    op.create_index('ix_pagamentos_idempotency_key', 'pagamentos', ['idempotency_key'], unique=True)

    op.create_table('documentos_rendimento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('tipo_rendimento', sa.String(20), nullable=True),
        sa.Column('descricao', sa.String(), nullable=True),
        sa.Column('valor', sa.Float(), nullable=True),
        sa.Column('ano_referencia', sa.Integer(), nullable=True),
        sa.Column('mes_referencia', sa.Integer(), nullable=True),
        sa.Column('arquivo_nome', sa.String(), nullable=True),
        sa.Column('arquivo_path', sa.String(), nullable=True),
        sa.Column('fonte_pagadora', sa.String(), nullable=True),
        sa.Column('confianca_extracao', sa.String(10), nullable=True),
        sa.Column('campos_corrigidos', sa.JSON(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('relatorios_mei',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('resultado', sa.Text(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('request_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('path', sa.String(500), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('engine_resultados',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('relatorio_analise_id', sa.Integer(), sa.ForeignKey('relatorios_analise.id'), nullable=True),
        sa.Column('engine_nome', sa.String(), nullable=True),
        sa.Column('resultado', sa.JSON(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('metricas_snapshot',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('total_execucoes', sa.Integer(), nullable=True),
        sa.Column('total_erros', sa.Integer(), nullable=True),
        sa.Column('tempo_total', sa.Float(), nullable=True),
        sa.Column('tempo_medio', sa.Float(), nullable=True),
        sa.Column('por_tipo', sa.JSON(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('inteligencia_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('score_global', sa.Float(), nullable=True),
        sa.Column('risco_tributario', sa.String(), nullable=True),
        sa.Column('maturidade_tributaria', sa.String(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        sa.Column('uf_cobertura', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('uso_plataforma',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('analises_mes', sa.Integer(), nullable=True),
        sa.Column('xmls_processados', sa.Integer(), nullable=True),
        sa.Column('mes', sa.Integer(), nullable=True),
        sa.Column('ano', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table('auditoria_estoque',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresas.id'), nullable=True),
        sa.Column('ncm', sa.String(20), nullable=True),
        sa.Column('estoque_fiscal', sa.Float(), nullable=True),
        sa.Column('estoque_erp', sa.Float(), nullable=True),
        sa.Column('diferenca', sa.Float(), nullable=True),
        sa.Column('risco_desvio', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('auditoria_estoque')
    op.drop_table('uso_plataforma')
    op.drop_table('inteligencia_snapshots')
    op.drop_table('metricas_snapshot')
    op.drop_table('engine_resultados')
    op.drop_table('request_logs')
    op.drop_table('relatorios_mei')
    op.drop_table('documentos_rendimento')
    op.drop_table('pagamentos')
    op.drop_table('consentimentos_lgpd')
    op.drop_table('termos_aceitacao')
    op.drop_table('tabela_pmpf')
    op.drop_table('tabela_mva')
    op.drop_table('alertas_fiscais')
    op.drop_table('insights')
    op.drop_table('itens_fiscais')
    op.drop_table('documentos_fiscais')
    op.drop_table('relatorios_analise')
    op.drop_table('referencias_legais')
    op.drop_table('empresas')
    op.drop_table('usuarios')
    op.drop_table('planos')
