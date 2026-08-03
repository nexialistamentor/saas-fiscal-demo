"""ADR-020 exact PolicyBinding activation gate (PostgreSQL-only)."""

from alembic import op


revision = "0030_adr020_policy_binding_gate"
down_revision = "0029_adr020_activation_exec_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0030_adr020_policy_binding_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_policy_binding_activations()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            binding jsonb;
        BEGIN
            IF jsonb_typeof(NEW.policy_bindings) IS DISTINCT FROM 'array'
               OR NEW.policy_bindings = '[]'::jsonb THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_POLICY_BINDING_ACTIVATION_MISMATCH';
            END IF;

            FOR binding IN
                SELECT value FROM jsonb_array_elements(NEW.policy_bindings)
            LOOP
                IF NOT EXISTS (
                    SELECT 1
                      FROM policy_activations
                     WHERE policy_activations.policy_type = binding ->> 'policy_type'
                       AND policy_activations.policy_id = binding ->> 'policy_id'
                       AND policy_activations.policy_version =
                           (binding ->> 'policy_version')::integer
                       AND policy_activations.policy_hash = binding ->> 'policy_hash'
                       AND policy_activations.policy_activation_id =
                           binding ->> 'policy_activation_id'
                       AND policy_activations.record_hash =
                           binding ->> 'policy_activation_record_hash'
                ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23503',
                        MESSAGE = 'ADR020_POLICY_BINDING_ACTIVATION_MISMATCH';
                END IF;
            END LOOP;

            RETURN NEW;
        EXCEPTION
            WHEN OTHERS THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_POLICY_BINDING_ACTIVATION_MISMATCH';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_adr020_validate_policy_binding_activations
        BEFORE INSERT ON activation_decisions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_policy_binding_activations();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0030_adr020_policy_binding_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
