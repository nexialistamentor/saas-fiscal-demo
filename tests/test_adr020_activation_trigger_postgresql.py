import importlib.util
import io
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations


MIGRATION_0024 = Path("migrations/versions/0024_adr020_activation_foundation.py")
MIGRATION_0028 = Path("migrations/versions/0028_adr020_atomic_activation_trigger_fix.py")


def _run(*args: str, input_sql: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=input_sql, text=True, capture_output=True, check=False)


def _psql(container: str, sql: str) -> subprocess.CompletedProcess[str]:
    return _run(
        "docker", "exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
        "-U", "postgres", "-d", "adr020", input_sql=sql,
    )


def _migration_sql(path: Path, module_name: str) -> str:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = io.StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": output, "transactional_ddl": True},
    )
    module.op = Operations(context)
    module.upgrade()
    return output.getvalue()


@pytest.fixture(scope="module")
def postgresql_0024() -> str:
    container = f"adr020-0028-{uuid.uuid4().hex[:12]}"
    started = _run(
        "docker", "run", "--detach", "--rm", "--name", container,
        "-e", "POSTGRES_PASSWORD=postgres", "-e", "POSTGRES_DB=adr020",
        "postgres:16-alpine",
    )
    assert started.returncode == 0, started.stderr
    try:
        stable_checks = 0
        for _ in range(60):
            ready = _run(
                "docker", "exec", container, "pg_isready", "-U", "postgres", "-d", "adr020"
            ).returncode == 0
            stable_checks = stable_checks + 1 if ready else 0
            if stable_checks == 3:
                break
            time.sleep(0.25)
        else:
            pytest.fail("PostgreSQL 16 Alpine did not become ready")

        predecessors = """
        CREATE FUNCTION adr020_reject_append_only_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'ADR-020 append-only'; END; $$;
        CREATE TABLE policy_versions (
          policy_id varchar(64), policy_version integer, policy_hash varchar(64),
          UNIQUE (policy_id, policy_version, policy_hash));
        CREATE TABLE policy_decisions (decision_id varchar(64) PRIMARY KEY);
        CREATE TABLE bootstrap_authority_records (bootstrap_authority_record_id varchar(64) PRIMARY KEY);
        """
        prepared = _psql(container, predecessors)
        assert prepared.returncode == 0, prepared.stderr
        upgraded = _psql(container, _migration_sql(MIGRATION_0024, "migration_0024_red"))
        assert upgraded.returncode == 0, upgraded.stderr
        yield container
    finally:
        _run("docker", "rm", "--force", container)


def test_0024_trigger_fails_on_valid_activation_execution_with_wrong_row_field(
    postgresql_0024: str,
) -> None:
    h = "a" * 64
    decision = _psql(
        postgresql_0024,
        f"""
        INSERT INTO activation_decisions (
          activation_decision_id, decision_action, decision_outcome, authorization_class,
          actor, institutional_role, target_scope, scope_hash, target_manifest,
          target_manifest_hash, authority_bindings, policy_bindings, coverage_binding,
          continuity_binding, precedence_binding, gates_evidence, rationale, evidence,
          idempotency_key, record_hash)
        VALUES ('decision-red', 'activate', 'approved', 'humana_delegada', 'actor', 'role',
          '{{}}', '{h}', '[]', '{h}', '{{}}', '[]', '{{}}', '{{}}', '{{}}', '{{}}',
          'valid decision', '{{}}', 'decision-red', '{h}');
        """,
    )
    assert decision.returncode == 0, decision.stderr

    execution = _psql(
        postgresql_0024,
        f"""
        INSERT INTO activation_executions (
          activation_execution_id, activation_decision_id, activation_decision_record_hash,
          decision_outcome, decision_action, authorization_class, execution_mode, state,
          scope_hash, target_manifest_hash, attempt_number, actor_or_worker, lease_id,
          fencing_token, idempotency_key, authority_bindings, policy_bindings,
          coverage_binding, continuity_binding, precedence_binding, gates_evidence,
          provenance, record_hash)
        VALUES ('execution-red', 'decision-red', '{h}', 'approved', 'activate',
          'humana_delegada', 'manual', 'completed', '{h}', '{h}', 1, 'worker', 'lease',
          1, 'execution-red', '{{}}', '[]', '{{}}', '{{}}', '{{}}', '{{}}', '{{}}', '{h}');
        """,
    )
    assert execution.returncode != 0
    assert 'record "new" has no field "is_complete"' in execution.stderr.lower()


@pytest.fixture(scope="module")
def postgresql_0028(postgresql_0024: str) -> str:
    upgraded = _psql(
        postgresql_0024,
        _migration_sql(MIGRATION_0028, "migration_0028_green"),
    )
    assert upgraded.returncode == 0, upgraded.stderr
    return postgresql_0024


def _insert_decision(container: str, suffix: str, outcome: str = "approved") -> None:
    h = "a" * 64
    result = _psql(
        container,
        f"""
        INSERT INTO activation_decisions (
          activation_decision_id, decision_action, decision_outcome, authorization_class,
          actor, institutional_role, target_scope, scope_hash, target_manifest,
          target_manifest_hash, authority_bindings, policy_bindings, coverage_binding,
          continuity_binding, precedence_binding, gates_evidence, rationale, evidence,
          idempotency_key, record_hash)
        VALUES ('decision-{suffix}', 'activate', '{outcome}', 'humana_delegada', 'actor',
          'role', '{{}}', '{h}', '[]', '{h}', '{{}}', '[]', '{{}}', '{{}}', '{{}}',
          '{{}}', 'decision', '{{}}', 'decision-{suffix}', '{suffix[0] * 64}');
        """,
    )
    assert result.returncode == 0, result.stderr


def _execution_sql(suffix: str, outcome: str = "approved") -> str:
    h = "a" * 64
    return f"""
    INSERT INTO activation_executions (
      activation_execution_id, activation_decision_id, activation_decision_record_hash,
      decision_outcome, decision_action, authorization_class, execution_mode, state,
      scope_hash, target_manifest_hash, attempt_number, actor_or_worker, lease_id,
      fencing_token, idempotency_key, authority_bindings, policy_bindings,
      coverage_binding, continuity_binding, precedence_binding, gates_evidence,
      provenance, record_hash)
    VALUES ('execution-{suffix}', 'decision-{suffix}', '{suffix[0] * 64}', '{outcome}',
      'activate', 'humana_delegada', 'manual', 'completed', '{h}', '{h}', 1, 'worker',
      'lease', 1, 'execution-{suffix}', '{{}}', '[]', '{{}}', '{{}}', '{{}}', '{{}}',
      '{{}}', '{suffix[-1] * 64}');
    """


def _generation_sql(suffix: str, complete: bool) -> str:
    h = "a" * 64
    return f"""
    INSERT INTO activation_generations (
      activation_generation_id, activation_execution_id, activation_decision_id,
      activation_decision_record_hash, target_manifest_hash, scope_descriptor,
      scope_hash, composition_manifest, composition_hash, policy_bindings,
      coverage_binding, continuity_binding, precedence_binding, gates_evidence,
      is_complete, effective_from, provenance, record_hash)
    VALUES ('generation-{suffix}', 'execution-{suffix}', 'decision-{suffix}',
      '{suffix[0] * 64}', '{h}', '{{}}', '{suffix[-1] * 64}', '[]',
      '{suffix[0] * 64}', '[]', '{{}}', '{{}}', '{{}}', '{{}}',
      {'true' if complete else 'false'}, now(), '{{}}', '{suffix[-1] * 64}');
    """


def test_0028_accepts_valid_execution_without_is_complete_access(postgresql_0028: str) -> None:
    _insert_decision(postgresql_0028, "b1")
    result = _psql(postgresql_0028, _execution_sql("b1"))
    assert result.returncode == 0, result.stderr


def test_0028_rejects_nonapproved_execution_with_historical_message(postgresql_0028: str) -> None:
    _insert_decision(postgresql_0028, "c2", "rejected")
    result = _psql(postgresql_0028, _execution_sql("c2", "rejected"))
    assert result.returncode != 0
    assert "ADR-020 only approved decision is executable" in result.stderr


def test_0028_accepts_complete_generation_without_execution_only_field_access(
    postgresql_0028: str,
) -> None:
    result = _psql(postgresql_0028, _generation_sql("b1", True))
    assert result.returncode == 0, result.stderr


def test_0028_rejects_incomplete_generation_with_historical_message(postgresql_0028: str) -> None:
    _insert_decision(postgresql_0028, "d3")
    execution = _psql(postgresql_0028, _execution_sql("d3"))
    assert execution.returncode == 0, execution.stderr
    generation = _psql(postgresql_0028, _generation_sql("d3", False))
    assert generation.returncode != 0
    assert "ADR-020 partial generation forbidden" in generation.stderr


def test_0028_preserves_exact_historical_trigger_associations(postgresql_0028: str) -> None:
    result = _psql(
        postgresql_0028,
        """
        SELECT tgname || '|' || c.relname || '|' || p.proname
        FROM pg_trigger t
        JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_proc p ON p.oid = t.tgfoid
        WHERE NOT t.tgisinternal AND p.proname = 'adr020_validate_atomic_activation'
        ORDER BY tgname;
        """,
    )
    assert result.returncode == 0, result.stderr
    associations = {line.strip() for line in result.stdout.splitlines() if "|" in line}
    assert associations == {
        "trg_activation_executions_validate_insert|activation_executions|adr020_validate_atomic_activation",
        "trg_activation_generations_validate_insert|activation_generations|adr020_validate_atomic_activation",
    }


def test_0028_installs_corrected_function_body_and_failed_rows_rollback(postgresql_0028: str) -> None:
    body = _psql(
        postgresql_0028,
        "SELECT pg_get_functiondef('adr020_validate_atomic_activation()'::regprocedure);",
    )
    assert body.returncode == 0, body.stderr
    assert "IF TG_TABLE_NAME = 'activation_executions' THEN" in body.stdout
    assert "ELSIF TG_TABLE_NAME = 'activation_generations' THEN" in body.stdout
    assert "unexpected table" in body.stdout

    counts = _psql(
        postgresql_0028,
        "SELECT (SELECT count(*) FROM activation_executions WHERE activation_execution_id='execution-c2')::text || '|' || (SELECT count(*) FROM activation_generations WHERE activation_generation_id='generation-d3')::text;",
    )
    assert counts.returncode == 0, counts.stderr
    assert "0|0" in counts.stdout


def test_0028_identity_lineage_and_irreversible_downgrade() -> None:
    spec = importlib.util.spec_from_file_location("migration_0028_static", MIGRATION_0028)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0028_adr020_atomic_trigger_fix"
    assert len(module.revision) <= 32
    assert module.down_revision == "0027_adr020_calc_replay"
    with pytest.raises(RuntimeError, match="irreversible"):
        module.downgrade()
