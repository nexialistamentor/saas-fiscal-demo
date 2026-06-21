"""DT-FLUXO-03: UNIQUE constraint em relatorios_analise para dedup de XML

Revision ID: 0011_unique_relatorio_xml_chave
Revises: 0010_add_campos_estruturados
Create Date: 2026-06-20

Protecao no banco contra TOCTOU caracterizado em
tests/test_pipeline_xml_concorrencia.py (DT-FLUXO-03).

UniqueConstraint(empresa_id, xml_chave, analysis_type) — NULLs em
xml_chave ou empresa_id sao tratados como distintos pelo PostgreSQL
(comportamento padrao SQL), logo a constraint so protege analises
XML reais (xml_chave preenchida), sem afectar mei_tax, tax_planning,
tax_recovery, empresa_tax.

Confirmado por auditoria: zero duplicados existentes nesta chave
logica antes desta migracao (verificado em ambiente local).
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0011_unique_relatorio_xml_chave'
down_revision: str = '0010_add_campos_estruturados'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_relatorios_analise_empresa_xml_tipo',
        'relatorios_analise',
        ['empresa_id', 'xml_chave', 'analysis_type'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_relatorios_analise_empresa_xml_tipo',
        'relatorios_analise',
        type_='unique',
    )
