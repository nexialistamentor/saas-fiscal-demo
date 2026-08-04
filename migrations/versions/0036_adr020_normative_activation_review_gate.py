"""ADR-020 exact NormativeActivation subject review gate (PostgreSQL-only)."""

from alembic import op

revision = "0036_adr020_review_gate"
down_revision = "0035_adr020_subject_gate"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Migration 0036_adr020_review_gate is PostgreSQL-only")
    op.execute("""
        CREATE FUNCTION adr020_validate_normative_activation_review()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE exact_match_count integer;
        BEGIN
            IF NEW.subject_type = 'rule_version' THEN
                SELECT count(*) INTO exact_match_count
                FROM rule_review_records
                WHERE rule_review_record_id = NEW.review_record_id
                  AND record_hash = NEW.review_record_hash
                  AND subject_id = NEW.subject_id
                  AND subject_version = NEW.subject_version
                  AND subject_hash = NEW.subject_hash;
            ELSIF NEW.subject_type = 'normative_relation_version' THEN
                SELECT count(*) INTO exact_match_count
                FROM relation_review_records
                WHERE relation_review_record_id = NEW.review_record_id
                  AND record_hash = NEW.review_record_hash
                  AND subject_id = NEW.subject_id
                  AND subject_version = NEW.subject_version
                  AND subject_hash = NEW.subject_hash;
            ELSE
                RAISE EXCEPTION USING ERRCODE = '23503',
                    MESSAGE = 'ADR020_NORMATIVE_ACTIVATION_REVIEW_MISMATCH';
            END IF;
            IF exact_match_count <> 1 THEN
                RAISE EXCEPTION USING ERRCODE = '23503',
                    MESSAGE = 'ADR020_NORMATIVE_ACTIVATION_REVIEW_MISMATCH';
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_adr020_validate_normative_activation_subject_review
        BEFORE INSERT ON normative_activations
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_normative_activation_review();
    """)


def downgrade():
    raise RuntimeError(
        "Migration 0036_adr020_review_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
