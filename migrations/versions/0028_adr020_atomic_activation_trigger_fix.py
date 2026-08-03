"""ADR-020 prospective atomic activation trigger repair (PostgreSQL-only).

Revision ID: 0028_adr020_atomic_trigger_fix
Revises: 0027_adr020_calc_replay
"""

from alembic import op


revision: str = "0028_adr020_atomic_trigger_fix"
down_revision: str = "0027_adr020_calc_replay"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Migration 0028_adr020_atomic_trigger_fix is PostgreSQL-only")

    op.execute(
        """CREATE OR REPLACE FUNCTION adr020_validate_atomic_activation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF TG_TABLE_NAME = 'activation_executions' THEN
            IF NEW.decision_outcome <> 'approved' THEN
              RAISE EXCEPTION 'ADR-020 only approved decision is executable';
            END IF;
          ELSIF TG_TABLE_NAME = 'activation_generations' THEN
            IF NOT NEW.is_complete THEN
              RAISE EXCEPTION 'ADR-020 partial generation forbidden';
            END IF;
          ELSE
            RAISE EXCEPTION USING MESSAGE =
              'ADR-020 atomic activation trigger attached to unexpected table: ' || TG_TABLE_NAME;
          END IF;
          RETURN NEW;
        END;
        $$;"""
    )


def downgrade():
    raise RuntimeError(
        "Migration 0028_adr020_atomic_trigger_fix is irreversible; "
        "the defective historical trigger body must not be restored"
    )
