"""0015_add_fingerprint



Repair production schema drift: table relatorios_analise is marked at

Alembic head, but does not have the fingerprint column expected by the ORM

and used by XML analysis/deduplication.



Observed evidence:

  - Production Alembic current: 0014_origem_cliente_vinculo (head)

  - Railway PostgreSQL: relatorios_analise without fingerprint column

  - Error: psycopg2.errors.UndefinedColumn:

          column relatorios_analise.fingerprint does not exist



Repair:

  - ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64)



Revision ID: 0015_add_fingerprint

Revises: 0014_origem_cliente_vinculo

Create Date: 2026-07-12

"""



from alembic import op





revision: str = "0015_add_fingerprint"

down_revision: str = "0014_origem_cliente_vinculo"

branch_labels = None

depends_on = None





def upgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0015 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE relatorios_analise "

        "ADD COLUMN IF NOT EXISTS fingerprint VARCHAR(64)"

    )





def downgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0015 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE relatorios_analise "

        "DROP COLUMN IF EXISTS fingerprint"

    )

