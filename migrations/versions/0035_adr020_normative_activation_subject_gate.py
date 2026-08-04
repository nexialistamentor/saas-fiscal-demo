"""ADR-020 exact NormativeActivation subject gate (PostgreSQL-only)."""

from alembic import op


revision = "0035_adr020_subject_gate"
down_revision = "0034_adr020_precedence_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0035_adr020_subject_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_normative_activation_subject()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            exact_match_count integer;
        BEGIN
            IF NEW.subject_type = 'rule_version' THEN
                SELECT count(*)
                  INTO exact_match_count
                  FROM rule_versions
                 WHERE rule_id = NEW.subject_id
                   AND rule_version = NEW.subject_version
                   AND rule_hash = NEW.subject_hash;
            ELSIF NEW.subject_type = 'normative_relation_version' THEN
                SELECT count(*)
                  INTO exact_match_count
                  FROM normative_relation_versions
                 WHERE normative_relation_id = NEW.subject_id
                   AND normative_relation_version = NEW.subject_version
                   AND normative_relation_hash = NEW.subject_hash;
            ELSE
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_NORMATIVE_ACTIVATION_SUBJECT_MISMATCH';
            END IF;

            IF exact_match_count <> 1 THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_NORMATIVE_ACTIVATION_SUBJECT_MISMATCH';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_adr020_validate_normative_activation_subject
        BEFORE INSERT ON normative_activations
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_normative_activation_subject();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0035_adr020_subject_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
