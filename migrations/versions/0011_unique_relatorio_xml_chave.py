"""DT-FLUXO-03: dedup de relatorios_analise + UNIQUE constraint

Revision ID: 0011_unique_relatorio_xml_chave
Revises: 0010_add_campos_estruturados
Create Date: 2026-06-20

Producao revelou duplicados reais em relatorios_analise -- confirma
DT-FLUXO-03 nao era teorico. Pre-auditoria (read-only) confirmou:
  - 2 grupos duplicados (empresa_id=4, dois xml_chave distintos)
  - 22 registos perdedores no total
  - 0 pagamentos ligados aos perdedores (risco financeiro nulo)
  - 154 linhas em engine_resultados a reatribuir antes do delete

Esta migration deduplica ANTES de criar a UNIQUE constraint:
1. Identifica grupos duplicados por (empresa_id, xml_chave, analysis_type)
2. Vencedor = MAX(id) -- mesmo criterio ja usado em
   registro_analise_service.py (order_by id.desc())
3. Reatribui FKs das 4 tabelas filhas (pagamentos, alertas_fiscais,
   insights, engine_resultados) do perdedor para o vencedor
4. Remove os registos perdedores
5. Verifica que nao restam duplicados -- aborta se restarem
6. So entao cria a UNIQUE constraint

Nao apaga nada sem reatribuir FK primeiro -- evita quebra de
integridade referencial e perda de vinculo financeiro (pagamentos).
"""
from alembic import op
import sqlalchemy as sa

revision: str = '0011_unique_relatorio_xml_chave'
down_revision: str = '0010_add_campos_estruturados'
branch_labels = None
depends_on = None


_TABELAS_FILHAS = [
    "pagamentos",
    "alertas_fiscais",
    "insights",
    "engine_resultados",
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Identificar grupos duplicados e o vencedor de cada grupo
    grupos = conn.execute(sa.text("""
        SELECT empresa_id, xml_chave, analysis_type,
               MAX(id) AS winner_id,
               array_agg(id) AS all_ids
        FROM relatorios_analise
        WHERE xml_chave IS NOT NULL AND empresa_id IS NOT NULL
        GROUP BY empresa_id, xml_chave, analysis_type
        HAVING COUNT(*) > 1
    """)).fetchall()

    for grupo in grupos:
        winner_id = grupo.winner_id
        loser_ids = [i for i in grupo.all_ids if i != winner_id]

        if not loser_ids:
            continue

        # 2. Reatribuir FKs de cada tabela filha: perdedores -> vencedor
        for tabela in _TABELAS_FILHAS:
            conn.execute(
                sa.text(f"""
                    UPDATE {tabela}
                    SET relatorio_analise_id = :winner_id
                    WHERE relatorio_analise_id = ANY(:loser_ids)
                """),
                {"winner_id": winner_id, "loser_ids": loser_ids},
            )

        # 3. Remover os registos perdedores, agora sem FKs pendentes
        conn.execute(
            sa.text("""
                DELETE FROM relatorios_analise
                WHERE id = ANY(:loser_ids)
            """),
            {"loser_ids": loser_ids},
        )

    # 4. Verificacao de seguranca -- aborta se a dedup nao foi completa
    restantes = conn.execute(sa.text("""
        SELECT COUNT(*)
        FROM (
            SELECT empresa_id, xml_chave, analysis_type
            FROM relatorios_analise
            WHERE xml_chave IS NOT NULL
              AND empresa_id IS NOT NULL
            GROUP BY empresa_id, xml_chave, analysis_type
            HAVING COUNT(*) > 1
        ) d
    """)).scalar()

    if restantes:
        raise RuntimeError(
            f"DT-FLUXO-03: ainda existem {restantes} grupos duplicados "
            "apos deduplicacao. Constraint NAO criada. Investigar antes "
            "de re-executar esta migration."
        )

    # 5. So agora criar a constraint -- dedup provada, nao falha
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
    # Nota: a deduplicacao do upgrade() nao e reversivel -- os registos
    # perdedores removidos nao podem ser recriados pelo downgrade.
    # Isto e aceitavel porque eram, por definicao, duplicados redundantes
    # da mesma analise (mesmo xml_chave + empresa_id + analysis_type).
