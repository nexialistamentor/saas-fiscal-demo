"""ADR-020 exact ActivationDecision bindings gate (PostgreSQL-only)."""

from alembic import op


revision = "0029_adr020_activation_exec_gate"
down_revision = "0028_adr020_atomic_trigger_fix"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError(
            "Migration 0029_adr020_activation_exec_gate is PostgreSQL-only"
        )

    op.execute(
        """
        CREATE FUNCTION adr020_validate_activation_execution_decision_bindings()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            sovereign_decision activation_decisions%ROWTYPE;
        BEGIN
            SELECT *
              INTO STRICT sovereign_decision
              FROM activation_decisions
             WHERE activation_decision_id = NEW.activation_decision_id
               AND record_hash = NEW.activation_decision_record_hash;

            IF NEW.authority_bindings IS DISTINCT FROM sovereign_decision.authority_bindings
               OR NEW.policy_bindings IS DISTINCT FROM sovereign_decision.policy_bindings
               OR NEW.coverage_binding IS DISTINCT FROM sovereign_decision.coverage_binding
               OR NEW.continuity_binding IS DISTINCT FROM sovereign_decision.continuity_binding
               OR NEW.precedence_binding IS DISTINCT FROM sovereign_decision.precedence_binding
               OR NEW.gates_evidence IS DISTINCT FROM sovereign_decision.gates_evidence
            THEN
                RAISE EXCEPTION
                    'ADR-020 activation execution bindings diverge from exact sovereign decision';
            END IF;

            RETURN NEW;
        EXCEPTION
            WHEN NO_DATA_FOUND THEN
                RAISE EXCEPTION
                    'ADR-020 exact sovereign activation decision not found';
            WHEN TOO_MANY_ROWS THEN
                RAISE EXCEPTION
                    'ADR-020 exact sovereign activation decision cardinality violation';
            WHEN OTHERS THEN
                RAISE;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_activation_executions_exact_decision_bindings
        BEFORE INSERT ON activation_executions
        FOR EACH ROW
        EXECUTE FUNCTION adr020_validate_activation_execution_decision_bindings();
        """
    )


def downgrade():
    raise RuntimeError(
        "Migration 0029_adr020_activation_exec_gate is irreversible by ratified "
        "ADR-020 append-only requirements"
    )
