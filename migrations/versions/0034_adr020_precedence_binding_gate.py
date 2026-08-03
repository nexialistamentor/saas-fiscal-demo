"""ADR-020 exact precedence PolicyBinding gate (PostgreSQL-only)."""

from alembic import op


revision = "0034_adr020_precedence_gate"
down_revision = "0033_adr020_continuity_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0034_adr020_precedence_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_precedence_binding_policy()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            exact_match_count integer;
        BEGIN
            IF jsonb_typeof(NEW.precedence_binding) IS DISTINCT FROM 'object'
               OR jsonb_typeof(
                    NEW.precedence_binding -> 'precedence_subject_type'
                  ) IS DISTINCT FROM 'string'
               OR NEW.precedence_binding -> 'precedence_subject_type'
                  IS DISTINCT FROM '"normative_precedence"'::jsonb
               OR jsonb_typeof(
                    NEW.precedence_binding -> 'precedence_policy_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.precedence_binding -> 'precedence_policy_version'
                  ) IS DISTINCT FROM 'number'
               OR jsonb_typeof(
                    NEW.precedence_binding -> 'precedence_policy_hash'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.precedence_binding -> 'precedence_policy_activation_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.precedence_binding
                    -> 'precedence_policy_activation_record_hash'
                  ) IS DISTINCT FROM 'string' THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_PRECEDENCE_BINDING_POLICY_MISMATCH';
            END IF;

            IF jsonb_typeof(NEW.policy_bindings) IS DISTINCT FROM 'array' THEN
                RETURN NEW;
            END IF;

            SELECT count(*)
              INTO exact_match_count
              FROM jsonb_array_elements(NEW.policy_bindings) AS binding
             WHERE binding -> 'policy_type' =
                   '"normative_precedence"'::jsonb
               AND binding -> 'policy_id' =
                   NEW.precedence_binding -> 'precedence_policy_id'
               AND binding -> 'policy_version' =
                   NEW.precedence_binding -> 'precedence_policy_version'
               AND binding -> 'policy_hash' =
                   NEW.precedence_binding -> 'precedence_policy_hash'
               AND binding -> 'policy_activation_id' =
                   NEW.precedence_binding -> 'precedence_policy_activation_id'
               AND binding -> 'policy_activation_record_hash' =
                   NEW.precedence_binding
                   -> 'precedence_policy_activation_record_hash';

            IF exact_match_count <> 1 THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_PRECEDENCE_BINDING_POLICY_MISMATCH';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_adr020_validate_precedence_binding_policy
        BEFORE INSERT ON activation_decisions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_precedence_binding_policy();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0034_adr020_precedence_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
