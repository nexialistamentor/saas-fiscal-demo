"""0016_add_insights_superseded



Repair production schema drift: table insights does not have the superseded

column expected by the ORM (InsightEngine / mapa_oportunidades_service).



Observed evidence:

  - Production Alembic current: 0015_add_fingerprint (head)

  - Railway PostgreSQL: insights without superseded column

  - Error: psycopg2.errors.UndefinedColumn:

          column insights.superseded does not exist



Repair:

  - ADD COLUMN IF NOT EXISTS superseded BOOLEAN NOT NULL DEFAULT false



Revision ID: 0016_add_insights_superseded

Revises: 0015_add_fingerprint

Create Date: 2026-07-12

"""



from alembic import op





revision: str = "0016_add_insights_superseded"

down_revision: str = "0015_add_fingerprint"

branch_labels = None

depends_on = None





def upgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0016 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE insights "

        "ADD COLUMN IF NOT EXISTS superseded BOOLEAN NOT NULL DEFAULT false"

    )





def downgrade():

    dialect = op.get_bind().dialect.name

    if dialect != "postgresql":

        raise Exception(

            "Migration 0016 is PostgreSQL-only. "

            "Current environment: " + dialect

        )



    op.execute(

        "ALTER TABLE insights "

        "DROP COLUMN IF EXISTS superseded"

    )

