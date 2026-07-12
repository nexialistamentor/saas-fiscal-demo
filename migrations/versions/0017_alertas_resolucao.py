"""0017_alertas_resolucao



Repair production schema drift: table alertas_fiscais does not have the

resolution fields expected by the ORM.



Observed evidence:

  - Railway PostgreSQL: alertas_fiscais has silenciado but lacks processado,

    processado_em, processado_por and notas_resolucao

  - Error: psycopg2.errors.UndefinedColumn:

          column alertas_fiscais.processado does not exist



Repair:

  - ADD COLUMN IF NOT EXISTS processado BOOLEAN NOT NULL DEFAULT false

  - ADD COLUMN IF NOT EXISTS processado_em TIMESTAMP

  - ADD COLUMN IF NOT EXISTS processado_por VARCHAR(100)

  - ADD COLUMN IF NOT EXISTS notas_resolucao VARCHAR(1000)



Revision ID: 0017_alertas_resolucao

Revises: 0016_add_insights_superseded

Create Date: 2026-07-12

"""



from alembic import op





revision: str = "0017_alertas_resolucao"

down_revision: str = "0016_add_insights_superseded"

branch_labels = None

depends_on = None





def upgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0017 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE alertas_fiscais "

        "ADD COLUMN IF NOT EXISTS processado BOOLEAN NOT NULL DEFAULT false, "

        "ADD COLUMN IF NOT EXISTS processado_em TIMESTAMP, "

        "ADD COLUMN IF NOT EXISTS processado_por VARCHAR(100), "

        "ADD COLUMN IF NOT EXISTS notas_resolucao VARCHAR(1000)"

    )





def downgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0017 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE alertas_fiscais "

        "DROP COLUMN IF EXISTS notas_resolucao, "

        "DROP COLUMN IF EXISTS processado_por, "

        "DROP COLUMN IF EXISTS processado_em, "

        "DROP COLUMN IF EXISTS processado"

    )

