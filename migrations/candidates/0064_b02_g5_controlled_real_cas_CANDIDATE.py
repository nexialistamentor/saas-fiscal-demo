"""B02 G5 real CAS -- CANDIDATO ISOLADO, nunca instalado.

Este ficheiro vive em migrations/candidates/, fora de migrations/versions/,
para que alembic upgrade head nunca o execute.

SQL interno reutilizado sem alteracao do candidato ja ratificado por Miguel,
SHA-256 do SQL original: {EXPECTED_SQL_SHA256}
"""
from alembic import op

revision = "0064_b02_g5_controlled_real_cas"
down_revision = "0063_adr020_policy_activation_atomicity"
branch_labels = None
depends_on = None

_SQL_ORIGINAL_SHA256 = "{EXPECTED_SQL_SHA256}"

_SQL = {sql_literal}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        raise RuntimeError("B02_G5_0064_POSTGRESQL_ONLY")
    op.execute(_SQL)


def downgrade() -> None:
    raise RuntimeError("B02_G5_0064_APPEND_ONLY_IRREVERSIBLE")
