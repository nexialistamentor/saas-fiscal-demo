"""ADR-020 exact continuity PolicyBinding gate (PostgreSQL-only)."""

from alembic import op


revision = "0033_adr020_continuity_gate"
down_revision = "0032_adr020_coverage_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0033_adr020_continuity_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_continuity_binding_policy()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            exact_match_count integer;
        BEGIN
            IF jsonb_typeof(NEW.continuity_binding) IS DISTINCT FROM 'object'
               OR jsonb_typeof(
                    NEW.continuity_binding -> 'continuity_subject_type'
                  ) IS DISTINCT FROM 'string'
               OR NEW.continuity_binding -> 'continuity_subject_type'
                  IS DISTINCT FROM '"normative_continuity"'::jsonb
               OR jsonb_typeof(
                    NEW.continuity_binding -> 'continuity_policy_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.continuity_binding -> 'continuity_policy_version'
                  ) IS DISTINCT FROM 'number'
               OR jsonb_typeof(
                    NEW.continuity_binding -> 'continuity_policy_hash'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.continuity_binding -> 'continuity_policy_activation_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.continuity_binding
                    -> 'continuity_policy_activation_record_hash'
                  ) IS DISTINCT FROM 'string' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_CONTINUITY_BINDING_POLICY_MISMATCH';
            END IF;

            IF jsonb_typeof(NEW.policy_bindings) IS DISTINCT FROM 'array' THEN
                RETURN NEW;
            END IF;

            SELECT count(*)
              INTO exact_match_count
              FROM jsonb_array_elements(NEW.policy_bindings) AS binding
             WHERE binding -> 'policy_type' =
                   '"normative_continuity"'::jsonb
               AND binding -> 'policy_id' =
                   NEW.continuity_binding -> 'continuity_policy_id'
               AND binding -> 'policy_version' =
                   NEW.continuity_binding -> 'continuity_policy_version'
               AND binding -> 'policy_hash' =
                   NEW.continuity_binding -> 'continuity_policy_hash'
               AND binding -> 'policy_activation_id' =
                   NEW.continuity_binding -> 'continuity_policy_activation_id'
               AND binding -> 'policy_activation_record_hash' =
                   NEW.continuity_binding
                   -> 'continuity_policy_activation_record_hash';

            IF exact_match_count <> 1 THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_CONTINUITY_BINDING_POLICY_MISMATCH';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_adr020_validate_continuity_binding_policy
        BEFORE INSERT ON activation_decisions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_continuity_binding_policy();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0033_adr020_continuity_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
