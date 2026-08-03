"""ADR-020 exact CoverageContract binding gate (PostgreSQL-only)."""

from alembic import op


revision = "0032_adr020_coverage_gate"
down_revision = "0031_adr020_bootstrap_binding"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0032_adr020_coverage_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_coverage_binding_contract()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF jsonb_typeof(NEW.coverage_binding) IS DISTINCT FROM 'object'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'coverage_subject_type'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'coverage_contract_record_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'coverage_contract_id'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'contract_version'
                  ) IS DISTINCT FROM 'number'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'contract_hash'
                  ) IS DISTINCT FROM 'string'
               OR jsonb_typeof(
                    NEW.coverage_binding -> 'coverage_contract_record_hash'
                  ) IS DISTINCT FROM 'string'
               OR NEW.coverage_binding ->> 'coverage_subject_type'
                  IS DISTINCT FROM 'coverage_contract'
               OR NOT EXISTS (
                    SELECT 1
                      FROM coverage_contracts
                     WHERE coverage_contracts.coverage_contract_record_id =
                           NEW.coverage_binding ->> 'coverage_contract_record_id'
                       AND coverage_contracts.coverage_contract_id =
                           NEW.coverage_binding ->> 'coverage_contract_id'
                       AND to_jsonb(coverage_contracts.contract_version) =
                           NEW.coverage_binding -> 'contract_version'
                       AND coverage_contracts.contract_hash =
                           NEW.coverage_binding ->> 'contract_hash'
                       AND coverage_contracts.record_hash =
                           NEW.coverage_binding ->> 'coverage_contract_record_hash'
               ) THEN
                RAISE EXCEPTION USING
                    ERRCODE = '23503',
                    MESSAGE = 'ADR020_COVERAGE_BINDING_CONTRACT_MISMATCH';
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_adr020_validate_coverage_binding_contract
        BEFORE INSERT ON activation_decisions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_coverage_binding_contract();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0032_adr020_coverage_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
