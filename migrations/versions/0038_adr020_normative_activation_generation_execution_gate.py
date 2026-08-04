"""ADR-020 activation/generation execution equality gate (PostgreSQL-only)."""

from alembic import op


revision = "0038_adr020_generation_exec_gate"
down_revision = "0037_adr020_generation_fk"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0038_adr020_generation_exec_gate is PostgreSQL-only"
        )
    op.execute("""
        CREATE OR REPLACE FUNCTION
        adr020_validate_normative_activation_generation_execution()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            generation_execution_id text;
        BEGIN
            SELECT activation_execution_id
              INTO generation_execution_id
              FROM activation_generations
             WHERE activation_generation_id = NEW.activation_generation_id;

            IF NOT FOUND THEN
                RETURN NEW;
            END IF;

            IF generation_execution_id IS DISTINCT FROM NEW.activation_execution_id THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_NORMATIVE_ACTIVATION_GENERATION_EXECUTION_MISMATCH';
            END IF;

            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER
        trg_adr020_validate_normative_activation_subject_review_gexec
        BEFORE INSERT ON normative_activations
        FOR EACH ROW
        EXECUTE FUNCTION
        adr020_validate_normative_activation_generation_execution();
    """)


def downgrade():
    raise RuntimeError(
        "Migration 0038_adr020_generation_exec_gate is irreversible by "
        "ratified ADR-020 append-only requirements"
    )
