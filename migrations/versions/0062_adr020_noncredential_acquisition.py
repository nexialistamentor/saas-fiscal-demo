"""ADR-020 R4F prospective acquisition proof. REVIEW CANDIDATE; not applied.

Only database-local transactional DDL. No grants, roles, policy activations,
network, data rewriting, historical migration changes or bypass switches.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0062_adr020_noncredential_acquisition'
down_revision = '0061_enterprise_documental_checkout_intent'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        raise RuntimeError('B02_POSTGRESQL_REQUIRED')
    for table in ('acquisition_executions','normative_artifacts'):
        op.add_column(table, sa.Column('b02_completion_txid', sa.Text(), nullable=True))
    op.create_unique_constraint('uq_b02_execution_exact_hash', 'acquisition_executions',
        ['acquisition_execution_record_id','record_hash','acquisition_execution_id','artifact_reference_id','attempt_number'])
    op.create_table('acquisition_mode_bindings',
        sa.Column('mode_binding_id', sa.String(255), nullable=False, primary_key=True),
        sa.Column('planning_execution_record_id', sa.String(255), nullable=False),
        sa.Column('planning_execution_record_hash', sa.String(64), nullable=False),
        sa.Column('acquisition_execution_id', sa.String(255), nullable=False),
        sa.Column('artifact_reference_id', sa.String(255), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(255), nullable=False),
        sa.Column('actor', sa.String(255), nullable=False),
        sa.Column('adapter_contract_binding', postgresql.JSONB(), nullable=False),
        sa.Column('acquisition_contract_binding', postgresql.JSONB(), nullable=False),
        sa.Column('source_identity_binding', postgresql.JSONB(), nullable=False),
        sa.Column('source_scope', postgresql.JSONB(), nullable=False),
        sa.Column('tenant_scope', postgresql.JSONB(), nullable=False),
        sa.Column('scope_hash', sa.String(64), nullable=False),
        sa.Column('security_policy_binding', postgresql.JSONB(), nullable=False),
        sa.Column('sanitization_policy_binding', postgresql.JSONB(), nullable=False),
        sa.Column('bound_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('provenance', postgresql.JSONB(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_id', sa.String(255), nullable=False),
        sa.Column('canonicalization_contract_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_hash', sa.String(64), nullable=False),
        sa.Column('assigned_txid', sa.String(255), nullable=False),
        sa.Column('record_hash', sa.String(64), nullable=False),
        sa.UniqueConstraint('mode_binding_id','record_hash', name='uq_b02_acquisition00'),
        sa.UniqueConstraint('record_hash', name='uq_b02_acquisition01'),
        sa.UniqueConstraint('acquisition_execution_id','attempt_number', name='uq_b02_acquisition02'),
        sa.UniqueConstraint('mode_binding_id','record_hash','acquisition_execution_id','artifact_reference_id','attempt_number', name='uq_b02_acquisition03'),
        sa.ForeignKeyConstraint(['planning_execution_record_id', 'planning_execution_record_hash', 'acquisition_execution_id', 'artifact_reference_id', 'attempt_number'],['acquisition_executions.acquisition_execution_record_id', 'acquisition_executions.record_hash', 'acquisition_executions.acquisition_execution_id', 'acquisition_executions.artifact_reference_id', 'acquisition_executions.attempt_number'], name='fk_b02_00', ondelete='RESTRICT'),
        sa.CheckConstraint('schema_version=1', name='ck_b02_00'),
        sa.CheckConstraint("canonicalization_contract_id='ADR020_B02_INTEGER_JSON_UTF8_V1' AND canonicalization_contract_version=1 AND canonicalization_contract_hash='a4b480d7a6fedd54b5c020e338f7dbc133ef0fc87a1ffefdbf1de5e088632fd1'", name='ck_b02_01'),
        sa.CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'", name='ck_b02_02'),
        sa.CheckConstraint("planning_execution_record_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_03'),
        sa.CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_04'),
        sa.CheckConstraint("canonicalization_contract_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_05'),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_06'),
        sa.CheckConstraint('attempt_number > 0', name='ck_b02_07'),
        sa.CheckConstraint("mode IN ('EXTERNAL_CREDENTIALLED','EXTERNAL_PUBLIC_NO_CREDENTIALS','LOCAL_CAS_INCORPORATION')", name='ck_b02_08'),
    )
    op.create_table('noncredential_acquisition_receipts',
        sa.Column('receipt_id', sa.String(255), nullable=False, primary_key=True),
        sa.Column('receipt_hash', sa.String(64), nullable=False),
        sa.Column('mode_binding_id', sa.String(255), nullable=False),
        sa.Column('mode_binding_hash', sa.String(64), nullable=False),
        sa.Column('start_execution_record_id', sa.String(255), nullable=False),
        sa.Column('start_execution_record_hash', sa.String(64), nullable=False),
        sa.Column('acquisition_execution_id', sa.String(255), nullable=False),
        sa.Column('artifact_reference_id', sa.String(255), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('mode', sa.String(255), nullable=False),
        sa.Column('source_identity_binding', postgresql.JSONB(), nullable=False),
        sa.Column('source_scope', postgresql.JSONB(), nullable=False),
        sa.Column('tenant_scope', postgresql.JSONB(), nullable=False),
        sa.Column('acquisition_contract_binding', postgresql.JSONB(), nullable=False),
        sa.Column('security_policy_binding', postgresql.JSONB(), nullable=False),
        sa.Column('sanitization_policy_binding', postgresql.JSONB(), nullable=False),
        sa.Column('artifact_hash', sa.String(64), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('media_type', sa.String(255), nullable=False),
        sa.Column('content_reference', postgresql.JSONB(), nullable=False),
        sa.Column('transport_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('cas_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('component_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('redaction_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('execution_proof_binding', postgresql.JSONB(), nullable=False),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('receipt_created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('acquisition_outcome', sa.String(255), nullable=False),
        sa.Column('creator', sa.String(255), nullable=False),
        sa.Column('provenance', postgresql.JSONB(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_id', sa.String(255), nullable=False),
        sa.Column('canonicalization_contract_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_hash', sa.String(64), nullable=False),
        sa.Column('assigned_txid', sa.String(255), nullable=False),
        sa.Column('record_hash', sa.String(64), nullable=False),
        sa.UniqueConstraint('receipt_id','record_hash', name='uq_b02_noncredential10'),
        sa.UniqueConstraint('record_hash', name='uq_b02_noncredential11'),
        sa.UniqueConstraint('receipt_id','receipt_hash', name='uq_b02_noncredential12'),
        sa.UniqueConstraint('acquisition_execution_id','attempt_number', name='uq_b02_noncredential13'),
        sa.ForeignKeyConstraint(['mode_binding_id', 'mode_binding_hash', 'acquisition_execution_id', 'artifact_reference_id', 'attempt_number'],['acquisition_mode_bindings.mode_binding_id', 'acquisition_mode_bindings.record_hash', 'acquisition_mode_bindings.acquisition_execution_id', 'acquisition_mode_bindings.artifact_reference_id', 'acquisition_mode_bindings.attempt_number'], name='fk_b02_10', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['start_execution_record_id', 'start_execution_record_hash', 'acquisition_execution_id', 'artifact_reference_id', 'attempt_number'],['acquisition_executions.acquisition_execution_record_id', 'acquisition_executions.record_hash', 'acquisition_executions.acquisition_execution_id', 'acquisition_executions.artifact_reference_id', 'acquisition_executions.attempt_number'], name='fk_b02_11', ondelete='RESTRICT'),
        sa.CheckConstraint('schema_version=1', name='ck_b02_10'),
        sa.CheckConstraint("canonicalization_contract_id='ADR020_B02_INTEGER_JSON_UTF8_V1' AND canonicalization_contract_version=1 AND canonicalization_contract_hash='a4b480d7a6fedd54b5c020e338f7dbc133ef0fc87a1ffefdbf1de5e088632fd1'", name='ck_b02_11'),
        sa.CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'", name='ck_b02_12'),
        sa.CheckConstraint("receipt_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_13'),
        sa.CheckConstraint("mode_binding_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_14'),
        sa.CheckConstraint("start_execution_record_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_15'),
        sa.CheckConstraint("artifact_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_16'),
        sa.CheckConstraint("canonicalization_contract_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_17'),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_18'),
        sa.CheckConstraint('attempt_number > 0 AND byte_size > 0', name='ck_b02_19'),
        sa.CheckConstraint("mode IN ('EXTERNAL_PUBLIC_NO_CREDENTIALS','LOCAL_CAS_INCORPORATION')", name='ck_b02_110'),
        sa.CheckConstraint("(mode='LOCAL_CAS_INCORPORATION' AND acquisition_outcome IN ('incorporated','missing_object','integrity_mismatch','indeterminate','cancelled_before_read')) OR (mode='EXTERNAL_PUBLIC_NO_CREDENTIALS' AND acquisition_outcome IN ('acquired','source_rejected','no_content_valid','transport_failed','indeterminate','cancelled_before_dispatch'))", name='ck_b02_111'),
    )
    op.create_table('noncredential_sanitization_verifications',
        sa.Column('verification_id', sa.String(255), nullable=False, primary_key=True),
        sa.Column('receipt_id', sa.String(255), nullable=False),
        sa.Column('receipt_hash', sa.String(64), nullable=False),
        sa.Column('verification_engine_id', sa.String(255), nullable=False),
        sa.Column('verification_engine_version', sa.Integer(), nullable=False),
        sa.Column('verification_engine_hash', sa.String(64), nullable=False),
        sa.Column('inspected_component_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('violation_manifest', postgresql.JSONB(), nullable=False),
        sa.Column('verification_outcome', sa.String(255), nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('verifier', sa.String(255), nullable=False),
        sa.Column('sanitization_policy_binding', postgresql.JSONB(), nullable=False),
        sa.Column('provenance', postgresql.JSONB(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_id', sa.String(255), nullable=False),
        sa.Column('canonicalization_contract_version', sa.Integer(), nullable=False),
        sa.Column('canonicalization_contract_hash', sa.String(64), nullable=False),
        sa.Column('assigned_txid', sa.String(255), nullable=False),
        sa.Column('record_hash', sa.String(64), nullable=False),
        sa.UniqueConstraint('verification_id','record_hash', name='uq_b02_noncredential20'),
        sa.UniqueConstraint('record_hash', name='uq_b02_noncredential21'),
        sa.UniqueConstraint('receipt_id','receipt_hash', name='uq_b02_noncredential22'),
        sa.ForeignKeyConstraint(['receipt_id', 'receipt_hash'],['noncredential_acquisition_receipts.receipt_id', 'noncredential_acquisition_receipts.receipt_hash'], name='fk_b02_20', ondelete='RESTRICT'),
        sa.CheckConstraint('schema_version=1', name='ck_b02_20'),
        sa.CheckConstraint("canonicalization_contract_id='ADR020_B02_INTEGER_JSON_UTF8_V1' AND canonicalization_contract_version=1 AND canonicalization_contract_hash='a4b480d7a6fedd54b5c020e338f7dbc133ef0fc87a1ffefdbf1de5e088632fd1'", name='ck_b02_21'),
        sa.CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'", name='ck_b02_22'),
        sa.CheckConstraint("receipt_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_23'),
        sa.CheckConstraint("verification_engine_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_24'),
        sa.CheckConstraint("canonicalization_contract_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_25'),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'", name='ck_b02_26'),
        sa.CheckConstraint('verification_engine_version > 0', name='ck_b02_27'),
        sa.CheckConstraint("verification_outcome IN ('verified_sanitized','verified_violation','inconclusive')", name='ck_b02_28'),
    )
    op.execute(r'''
-- Candidate database-local functions, SECURITY INVOKER throughout.
CREATE FUNCTION b02_canonical_json(v jsonb) RETURNS text LANGUAGE plpgsql
IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
DECLARE result text;
BEGIN
 CASE jsonb_typeof(v)
 WHEN 'object' THEN
  SELECT '{'||coalesce(string_agg(to_jsonb(key)::text||':'||public.b02_canonical_json(value),',' ORDER BY key COLLATE "C"),'')||'}' INTO result FROM jsonb_each(v);
 WHEN 'array' THEN
  SELECT '['||coalesce(string_agg(public.b02_canonical_json(value),',' ORDER BY ord),'')||']' INTO result FROM jsonb_array_elements(v) WITH ORDINALITY e(value,ord);
 WHEN 'number' THEN
  IF v::text !~ '^-?(0|[1-9][0-9]*)$' THEN RAISE EXCEPTION 'CANONICALIZATION_INVALID'; END IF;
  result:=v::text;
 ELSE result:=v::text;
 END CASE;
 RETURN result;
END $$;
CREATE FUNCTION b02_json_hash(v jsonb) RETURNS text LANGUAGE sql
IMMUTABLE STRICT SET search_path=pg_catalog,public AS $$
 SELECT encode(public.digest(convert_to(public.b02_canonical_json(v),'UTF8'),'sha256'),'hex')
$$;

-- No new policy type or authority table. This predicate consumes an explicit
-- subordinate grant in an existing, exact, active institutional policy.
CREATE FUNCTION b02_policy_grant(b jsonb, purpose text, scope_value jsonb, mode_value text, effective_at timestamptz DEFAULT statement_timestamp())
RETURNS jsonb LANGUAGE plpgsql STABLE SET search_path=pg_catalog,public AS $$
DECLARE p public.policy_versions%ROWTYPE; a public.policy_activations%ROWTYPE; g jsonb;
BEGIN
 IF jsonb_typeof(b) IS DISTINCT FROM 'object' OR NOT b ?& ARRAY['policy_type','policy_id','policy_version','policy_hash','policy_activation_id','policy_activation_record_hash']
 THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 SELECT * INTO p FROM public.policy_versions WHERE policy_id=b->>'policy_id' AND policy_version=(b->>'policy_version')::integer AND policy_hash=b->>'policy_hash' AND policy_type=b->>'policy_type';
 IF NOT FOUND THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 SELECT * INTO a FROM public.policy_activations WHERE policy_activation_id=b->>'policy_activation_id' AND record_hash=b->>'policy_activation_record_hash' AND policy_id=p.policy_id AND policy_version=p.policy_version AND policy_hash=p.policy_hash AND policy_type=p.policy_type AND state='activa' AND activated_at<=effective_at;
 IF NOT FOUND THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 g:=p.rules->'b02_noncredential'->purpose;
 -- No default interval, scope, actor, contract or verifier is inferred.
 IF g IS NULL OR g->>'schema' IS DISTINCT FROM 'B02_POLICY_GRANT_V1'
 OR g->'scope' IS DISTINCT FROM scope_value OR p.scope IS DISTINCT FROM scope_value
 OR NOT coalesce(g->'modes' ? mode_value,false)
 OR NOT coalesce(p.modalities ? mode_value,false)
 OR a.modality IS DISTINCT FROM mode_value OR a.domain IS DISTINCT FROM p.domain
 OR NOT (a.operational_interval ?& ARRAY['from','until'])
 OR a.operational_interval->>'from' IS NULL OR a.operational_interval->>'until' IS NULL
 OR effective_at>statement_timestamp()
 OR effective_at < (a.operational_interval->>'from')::timestamptz
 OR effective_at >= (a.operational_interval->>'until')::timestamptz
 OR statement_timestamp() < (a.operational_interval->>'from')::timestamptz
 OR statement_timestamp() >= (a.operational_interval->>'until')::timestamptz
 THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 RETURN g;
END $$;

CREATE FUNCTION b02_stamp_existing() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public SET timezone='UTC' AS $$
DECLARE exec_id text; attempt_value integer; new_mode boolean; hash_required boolean; expected text;
BEGIN
 IF NEW.b02_completion_txid IS NOT NULL THEN RAISE EXCEPTION 'B02_SERVER_TXID_ONLY'; END IF;
 NEW.b02_completion_txid:=pg_current_xact_id()::text;
 exec_id:=NEW.acquisition_execution_id;
 IF TG_TABLE_NAME='acquisition_executions' THEN attempt_value:=NEW.attempt_number;
 ELSE attempt_value:=NEW.acquisition_attempt_number; END IF;
 SELECT EXISTS(SELECT 1 FROM public.acquisition_mode_bindings WHERE acquisition_execution_id=exec_id AND attempt_number=attempt_value AND mode<>'EXTERNAL_CREDENTIALLED') INTO new_mode;
 IF new_mode THEN
  IF TG_TABLE_NAME='acquisition_executions' THEN hash_required:=(NEW.projected_state='concluida');
  ELSE hash_required:=true; END IF;
  IF hash_required THEN
   expected:=public.b02_json_hash(to_jsonb(NEW)-ARRAY['record_hash','b02_completion_txid']);
   IF NEW.record_hash IS NOT NULL AND NEW.record_hash IS DISTINCT FROM expected THEN RAISE EXCEPTION 'B02_RECORD_HASH_DIVERGENCE'; END IF;
   NEW.record_hash:=expected;
  END IF;
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION b02_validate_new_proof() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public SET timezone='UTC' AS $$
DECLARE j jsonb; expected text; material text; b public.acquisition_mode_bindings%ROWTYPE;
 r public.noncredential_acquisition_receipts%ROWTYPE; e public.acquisition_executions%ROWTYPE;
 ref public.artifact_references%ROWTYPE; g jsonb; s jsonb; p jsonb;
BEGIN
 IF NEW.assigned_txid IS NOT NULL THEN RAISE EXCEPTION 'B02_SERVER_TXID_ONLY'; END IF;
 NEW.assigned_txid:=pg_current_xact_id()::text;
 -- This reviewed local candidate admits synthetic proofs only; real evidence
 -- requires its own implementation/authority gate, never two asserted names.
 IF NEW.provenance->'synthetic_only' IS DISTINCT FROM 'true'::jsonb THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 IF TG_TABLE_NAME='acquisition_mode_bindings' THEN
  SELECT * INTO e FROM public.acquisition_executions WHERE acquisition_execution_record_id=NEW.planning_execution_record_id AND record_hash=NEW.planning_execution_record_hash AND acquisition_execution_id=NEW.acquisition_execution_id AND artifact_reference_id=NEW.artifact_reference_id AND attempt_number=NEW.attempt_number AND execution_event='criacao' AND projected_state='planeada';
  IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_PLANNING_REQUIRED'; END IF;
  PERFORM 1 FROM public.acquisition_executions WHERE acquisition_execution_id=NEW.acquisition_execution_id AND attempt_number=NEW.attempt_number AND event_sequence>1;
  IF FOUND OR e.b02_completion_txid IS DISTINCT FROM NEW.assigned_txid THEN RAISE EXCEPTION 'B02_MODE_MUST_PRECEDE_ACTION'; END IF;
  IF e.actor_or_worker IS DISTINCT FROM NEW.actor OR NEW.bound_at < e.occurred_at THEN RAISE EXCEPTION 'B02_ACTOR_OR_CHRONOLOGY_DIVERGENCE'; END IF;
  SELECT * INTO ref FROM public.artifact_references WHERE artifact_reference_record_id=e.artifact_reference_record_id;
  IF NEW.source_identity_binding IS DISTINCT FROM jsonb_build_object('source_id',ref.source_id,'exact_locator',ref.exact_locator)
  OR NEW.scope_hash IS DISTINCT FROM public.b02_json_hash(NEW.source_scope) THEN RAISE EXCEPTION 'B02_SOURCE_OR_SCOPE_DIVERGENCE'; END IF;
  IF NEW.mode='EXTERNAL_CREDENTIALLED' THEN RAISE EXCEPTION 'CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN'; END IF;
  g:=public.b02_policy_grant(NEW.security_policy_binding,'security',NEW.source_scope,NEW.mode,NEW.bound_at);
  s:=public.b02_policy_grant(NEW.sanitization_policy_binding,'sanitization',NEW.source_scope,NEW.mode,NEW.bound_at);
  IF NOT coalesce(g->'actors' ? NEW.actor,false) OR g->'adapter_contract_binding' IS DISTINCT FROM NEW.adapter_contract_binding
  OR g->'acquisition_contract_binding' IS DISTINCT FROM NEW.acquisition_contract_binding
  OR NEW.adapter_contract_binding->>'version' IS DISTINCT FROM e.adapter_version
  OR g->'tenant_scope' IS DISTINCT FROM NEW.tenant_scope THEN RAISE EXCEPTION 'B02_EXACT_CONTRACT_REQUIRED'; END IF;
  IF NOT (NEW.adapter_contract_binding ?& ARRAY['id','version','hash']) OR NOT (NEW.acquisition_contract_binding ?& ARRAY['id','version','hash'])
  OR coalesce(NEW.adapter_contract_binding->>'hash','') !~ '^[0-9a-f]{64}$'
  OR coalesce(NEW.acquisition_contract_binding->>'hash','') !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'B02_EXACT_CONTRACT_REQUIRED'; END IF;
 ELSIF TG_TABLE_NAME='noncredential_acquisition_receipts' THEN
  SELECT * INTO b FROM public.acquisition_mode_bindings WHERE mode_binding_id=NEW.mode_binding_id AND record_hash=NEW.mode_binding_hash AND acquisition_execution_id=NEW.acquisition_execution_id AND artifact_reference_id=NEW.artifact_reference_id AND attempt_number=NEW.attempt_number;
  IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_BINDING_REQUIRED'; END IF;
  IF b.mode='EXTERNAL_CREDENTIALLED' THEN RAISE EXCEPTION 'CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN'; END IF;
  IF NEW.mode IS DISTINCT FROM b.mode OR NEW.assigned_txid IS DISTINCT FROM b.assigned_txid THEN RAISE EXCEPTION 'B02_MODE_OR_TRANSACTION_DIVERGENCE'; END IF;
  SELECT * INTO e FROM public.acquisition_executions WHERE acquisition_execution_record_id=NEW.start_execution_record_id AND record_hash=NEW.start_execution_record_hash AND acquisition_execution_id=NEW.acquisition_execution_id AND artifact_reference_id=NEW.artifact_reference_id AND attempt_number=NEW.attempt_number AND execution_event='inicio' AND projected_state='em_execucao' AND previous_acquisition_execution_record_id=b.planning_execution_record_id;
  IF NOT FOUND OR e.b02_completion_txid IS DISTINCT FROM NEW.assigned_txid THEN RAISE EXCEPTION 'B02_EXACT_START_REQUIRED'; END IF;
  IF EXISTS(SELECT 1 FROM public.secret_access_execution_records WHERE acquisition_execution_id=NEW.acquisition_execution_id)
  OR EXISTS(SELECT 1 FROM public.credential_use_records WHERE acquisition_execution_id=NEW.acquisition_execution_id)
  THEN RAISE EXCEPTION 'NONCREDENTIAL_CHAIN_CONTRADICTION'; END IF;
  IF NEW.source_identity_binding IS DISTINCT FROM b.source_identity_binding OR NEW.source_scope IS DISTINCT FROM b.source_scope OR NEW.tenant_scope IS DISTINCT FROM b.tenant_scope
  OR NEW.acquisition_contract_binding IS DISTINCT FROM b.acquisition_contract_binding OR NEW.security_policy_binding IS DISTINCT FROM b.security_policy_binding OR NEW.sanitization_policy_binding IS DISTINCT FROM b.sanitization_policy_binding THEN RAISE EXCEPTION 'B02_SOURCE_CONTRACT_OR_POLICY_DIVERGENCE'; END IF;
  PERFORM public.b02_policy_grant(NEW.security_policy_binding,'security',NEW.source_scope,NEW.mode,NEW.observed_at);
  PERFORM public.b02_policy_grant(NEW.sanitization_policy_binding,'sanitization',NEW.source_scope,NEW.mode,NEW.observed_at);
  IF NEW.observed_at<e.started_at OR NEW.receipt_created_at<NEW.observed_at OR NEW.creator IS DISTINCT FROM b.actor THEN RAISE EXCEPTION 'B02_RECEIPT_CHRONOLOGY_OR_ACTOR'; END IF;
  IF NEW.mode='LOCAL_CAS_INCORPORATION' THEN
   IF NEW.transport_manifest IS DISTINCT FROM '{}'::jsonb THEN RAISE EXCEPTION 'CAS_EXTERNAL_TRANSPORT_FORBIDDEN'; END IF;
   IF NEW.cas_manifest->'read_observed' IS DISTINCT FROM 'true'::jsonb OR NEW.cas_manifest->'components_complete' IS DISTINCT FROM 'true'::jsonb
   OR NEW.cas_manifest->>'object_uri' IS DISTINCT FROM 'cas+sha256://'||NEW.artifact_hash||'/'||NEW.byte_size::text
   OR NEW.cas_manifest->>'recalculated_hash' IS DISTINCT FROM NEW.artifact_hash OR NEW.cas_manifest->>'recalculated_size' IS DISTINCT FROM NEW.byte_size::text
   OR NOT (NEW.cas_manifest ?& ARRAY['custody_contract_binding','prior_evidence_bindings','read_observed_at'])
   OR jsonb_typeof(NEW.cas_manifest->'prior_evidence_bindings') IS DISTINCT FROM 'array' OR NEW.cas_manifest->'prior_evidence_bindings'='[]'::jsonb
   THEN RAISE EXCEPTION 'MODE_EVIDENCE_INCONCLUSIVE'; END IF;
  ELSE
   IF NEW.transport_manifest ?| ARRAY['credential_binding_id','credential_use_record_id','secret_access_execution_record_id'] THEN RAISE EXCEPTION 'NONCREDENTIAL_CREDENTIAL_FIELDS_FORBIDDEN'; END IF;
   IF NEW.transport_manifest->'credential_presentation_observed'='true'::jsonb OR coalesce(NEW.transport_manifest->'credential_categories','[]'::jsonb)<>'[]'::jsonb THEN RAISE EXCEPTION 'PUBLIC_CREDENTIAL_PRESENTATION_FORBIDDEN'; END IF;
   IF NEW.cas_manifest IS DISTINCT FROM '{}'::jsonb OR NEW.transport_manifest->'dispatched' IS DISTINCT FROM 'true'::jsonb OR NEW.transport_manifest->'response_observed' IS DISTINCT FROM 'true'::jsonb OR NEW.transport_manifest->'components_complete' IS DISTINCT FROM 'true'::jsonb OR NEW.transport_manifest->'credential_presentation_observed' IS DISTINCT FROM 'false'::jsonb
   OR NOT (NEW.transport_manifest ?& ARRAY['method','requested_locator','final_locator','redirects','request_fingerprint','status','dispatch_observed_at','response_observed_at','inspected_request_components']) THEN RAISE EXCEPTION 'MODE_EVIDENCE_INCONCLUSIVE'; END IF;
  END IF;
  IF NEW.content_reference IS DISTINCT FROM jsonb_build_object('uri','cas+sha256://'||NEW.artifact_hash||'/'||NEW.byte_size::text,'hash',NEW.artifact_hash,'byte_size',NEW.byte_size)
  OR NEW.component_manifest->'complete' IS DISTINCT FROM 'true'::jsonb OR jsonb_typeof(NEW.component_manifest->'components') IS DISTINCT FROM 'array' OR NEW.component_manifest->'components'='[]'::jsonb
  OR NOT (NEW.execution_proof_binding ?& ARRAY['id','hash']) OR coalesce(NEW.execution_proof_binding->>'hash','') !~ '^[0-9a-f]{64}$' OR jsonb_typeof(NEW.redaction_manifest) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'B02_COMPLETE_COMPONENT_EVIDENCE_REQUIRED'; END IF;
  -- A6 exact material exclusions, including only explicitly excluded metadata.
  material:=public.b02_json_hash(to_jsonb(NEW)-ARRAY['receipt_id','receipt_hash','receipt_created_at','creator','provenance','record_hash']);
  IF NEW.receipt_hash IS NOT NULL AND NEW.receipt_hash IS DISTINCT FROM material THEN RAISE EXCEPTION 'B02_RECEIPT_HASH_DIVERGENCE'; END IF;
  NEW.receipt_hash:=material;
 ELSE
  SELECT * INTO r FROM public.noncredential_acquisition_receipts WHERE receipt_id=NEW.receipt_id AND receipt_hash=NEW.receipt_hash;
  IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_RECEIPT_REQUIRED'; END IF;
  SELECT * INTO b FROM public.acquisition_mode_bindings WHERE mode_binding_id=r.mode_binding_id;
  IF NEW.assigned_txid IS DISTINCT FROM r.assigned_txid OR NEW.sanitization_policy_binding IS DISTINCT FROM r.sanitization_policy_binding OR NEW.verified_at<r.receipt_created_at THEN RAISE EXCEPTION 'B02_VERIFICATION_BINDING_DIVERGENCE'; END IF;
  g:=public.b02_policy_grant(NEW.sanitization_policy_binding,'sanitization',r.source_scope,r.mode,NEW.verified_at);
  IF NEW.verification_outcome='verified_sanitized' THEN
   IF NEW.inspected_component_manifest->'complete' IS DISTINCT FROM 'true'::jsonb OR NEW.inspected_component_manifest->'components' IS DISTINCT FROM r.component_manifest->'components'
   OR NEW.inspected_component_manifest->'execution_proof_binding' IS DISTINCT FROM r.execution_proof_binding OR NEW.violation_manifest IS DISTINCT FROM '[]'::jsonb
   OR g->'verification_engine_binding' IS DISTINCT FROM jsonb_build_object('id',NEW.verification_engine_id,'version',NEW.verification_engine_version,'hash',NEW.verification_engine_hash)
   OR NOT coalesce(g->'verifiers' ? NEW.verifier,false) OR NEW.verifier=r.creator
   OR g->>'independence_evidence_required' IS DISTINCT FROM 'true'
   OR NOT (NEW.inspected_component_manifest ? 'independence_evidence_binding')
   OR coalesce(NEW.inspected_component_manifest->'independence_evidence_binding'->>'hash','') !~ '^[0-9a-f]{64}$'
   THEN RAISE EXCEPTION 'B02_FAVOURABLE_INDEPENDENT_VERIFICATION_REQUIRED'; END IF;
  END IF;
 END IF;
 expected:=public.b02_json_hash(to_jsonb(NEW)-'record_hash');
 IF NEW.record_hash IS NOT NULL AND NEW.record_hash IS DISTINCT FROM expected THEN RAISE EXCEPTION 'B02_RECORD_HASH_DIVERGENCE'; END IF;
 NEW.record_hash:=expected;
 RETURN NEW;
END $$;

CREATE FUNCTION b02_require_complete_unit(execution_id text, attempt integer, terminal_id text, current_transaction_required boolean)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
DECLARE b public.acquisition_mode_bindings%ROWTYPE; r public.noncredential_acquisition_receipts%ROWTYPE;
 v public.noncredential_sanitization_verifications%ROWTYPE; e public.acquisition_executions%ROWTYPE;
 a public.normative_artifacts%ROWTYPE;
BEGIN
 SELECT * INTO b FROM public.acquisition_mode_bindings WHERE acquisition_execution_id=execution_id AND attempt_number=attempt;
 IF NOT FOUND OR b.mode='EXTERNAL_CREDENTIALLED' THEN RETURN; END IF;
 SELECT * INTO r FROM public.noncredential_acquisition_receipts WHERE mode_binding_id=b.mode_binding_id AND acquisition_execution_id=b.acquisition_execution_id AND attempt_number=b.attempt_number;
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_ATOMIC_RECEIPT_REQUIRED'; END IF;
 SELECT * INTO v FROM public.noncredential_sanitization_verifications WHERE receipt_id=r.receipt_id AND receipt_hash=r.receipt_hash AND verification_outcome='verified_sanitized';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_ATOMIC_VERIFICATION_REQUIRED'; END IF;
 SELECT * INTO e FROM public.acquisition_executions WHERE acquisition_execution_id=execution_id AND attempt_number=attempt AND execution_event='conclusao' AND projected_state='concluida' AND (terminal_id IS NULL OR acquisition_execution_record_id=terminal_id);
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_ATOMIC_TERMINAL_REQUIRED'; END IF;
 SELECT * INTO a FROM public.normative_artifacts WHERE acquisition_execution_record_id=e.acquisition_execution_record_id AND acquisition_execution_id=e.acquisition_execution_id AND artifact_reference_id=e.artifact_reference_id AND acquisition_attempt_number=e.attempt_number;
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_ATOMIC_ARTIFACT_REQUIRED'; END IF;
 IF e.previous_acquisition_execution_record_id IS DISTINCT FROM r.start_execution_record_id OR e.artifact_reference_id IS DISTINCT FROM r.artifact_reference_id
 OR e.structured_result->>'noncredential_receipt_id' IS DISTINCT FROM r.receipt_id OR e.structured_result->>'noncredential_receipt_hash' IS DISTINCT FROM r.receipt_hash
 OR e.structured_result->>'noncredential_verification_id' IS DISTINCT FROM v.verification_id OR e.structured_result->>'noncredential_verification_hash' IS DISTINCT FROM v.record_hash
 OR a.artifact_hash IS DISTINCT FROM r.artifact_hash OR a.byte_size IS DISTINCT FROM r.byte_size OR a.media_type IS DISTINCT FROM r.media_type
 OR a.immutable_bytes IS NULL OR encode(public.digest(a.immutable_bytes,'sha256'),'hex') IS DISTINCT FROM r.artifact_hash
 OR a.b02_completion_txid IS DISTINCT FROM b.assigned_txid OR e.b02_completion_txid IS DISTINCT FROM b.assigned_txid
 OR r.assigned_txid IS DISTINCT FROM b.assigned_txid OR v.assigned_txid IS DISTINCT FROM b.assigned_txid
 OR (current_transaction_required AND b.assigned_txid IS DISTINCT FROM pg_current_xact_id()::text)
 THEN RAISE EXCEPTION 'B02_ATOMIC_IDENTITY_OR_TRANSACTION_DIVERGENCE'; END IF;
 IF (r.mode='LOCAL_CAS_INCORPORATION' AND r.acquisition_outcome<>'incorporated') OR (r.mode='EXTERNAL_PUBLIC_NO_CREDENTIALS' AND r.acquisition_outcome<>'acquired') THEN RAISE EXCEPTION 'B02_SUCCESSFUL_BYTES_REQUIRED'; END IF;
 IF EXISTS(SELECT 1 FROM public.secret_access_execution_records WHERE acquisition_execution_id=execution_id) OR EXISTS(SELECT 1 FROM public.credential_use_records WHERE acquisition_execution_id=execution_id) THEN RAISE EXCEPTION 'NONCREDENTIAL_CHAIN_CONTRADICTION'; END IF;
 PERFORM public.b02_policy_grant(r.security_policy_binding,'security',r.source_scope,r.mode);
 PERFORM public.b02_policy_grant(r.sanitization_policy_binding,'sanitization',r.source_scope,r.mode);
END $$;

CREATE FUNCTION b02_deferred_complete_unit() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public AS $$
DECLARE r public.noncredential_acquisition_receipts%ROWTYPE; xid_value text; exec_id text; attempt_value integer; terminal_id text;
BEGIN
 IF TG_TABLE_NAME='noncredential_sanitization_verifications' THEN
  SELECT * INTO r FROM public.noncredential_acquisition_receipts WHERE receipt_id=NEW.receipt_id;
  exec_id:=r.acquisition_execution_id; attempt_value:=r.attempt_number;
 ELSIF TG_TABLE_NAME='normative_artifacts' THEN
  exec_id:=NEW.acquisition_execution_id; attempt_value:=NEW.acquisition_attempt_number; terminal_id:=NEW.acquisition_execution_record_id;
 ELSE exec_id:=NEW.acquisition_execution_id; attempt_value:=NEW.attempt_number;
 END IF;
 PERFORM public.b02_require_complete_unit(exec_id,attempt_value,terminal_id,true);
 RETURN NULL;
END $$;

-- Replace only the defective function prospectively. Existing trigger objects
-- remain installed, active, and never disabled, including all legal gates.
CREATE OR REPLACE FUNCTION adr020_require_sanitized_acquisition() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$
DECLARE e public.acquisition_executions%ROWTYPE; a public.normative_artifacts%ROWTYPE;
 b public.acquisition_mode_bindings%ROWTYPE; r public.noncredential_acquisition_receipts%ROWTYPE;
 v public.noncredential_sanitization_verifications%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='acquisition_executions' THEN
  IF NEW.projected_state<>'concluida' THEN RETURN NEW; END IF;
  e:=NEW;
 ELSIF TG_TABLE_NAME='extraction_runs' THEN
  SELECT * INTO a FROM public.normative_artifacts WHERE normative_artifact_id=NEW.normative_artifact_id AND artifact_hash=NEW.artifact_hash;
  IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_ARTIFACT_REQUIRED_BEFORE_EXTRACTION'; END IF;
  SELECT * INTO e FROM public.acquisition_executions WHERE acquisition_execution_record_id=a.acquisition_execution_record_id AND acquisition_execution_id=a.acquisition_execution_id AND artifact_reference_id=a.artifact_reference_id AND attempt_number=a.acquisition_attempt_number AND execution_event='conclusao' AND projected_state='concluida';
  IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_TERMINAL_REQUIRED_BEFORE_EXTRACTION'; END IF;
 ELSE RAISE EXCEPTION 'B02_UNSUPPORTED_TRIGGER_TABLE';
 END IF;
 SELECT * INTO b FROM public.acquisition_mode_bindings WHERE acquisition_execution_id=e.acquisition_execution_id AND attempt_number=e.attempt_number;
 IF NOT FOUND OR b.mode='EXTERNAL_CREDENTIALLED' THEN
  -- Preserve the credentialled contract; never infer public/CAS from absence.
  IF NOT EXISTS(SELECT 1 FROM public.sanitized_acquisition_receipts receipt JOIN public.sanitization_verification_records verification ON verification.sanitized_acquisition_receipt_id=receipt.sanitized_acquisition_receipt_id AND verification.sanitized_acquisition_receipt_hash=receipt.sanitized_acquisition_receipt_hash WHERE receipt.acquisition_execution_id=e.acquisition_execution_id AND verification.verification_outcome='verified_sanitized') THEN RAISE EXCEPTION 'CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN'; END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO r FROM public.noncredential_acquisition_receipts WHERE mode_binding_id=b.mode_binding_id AND receipt_id=e.structured_result->>'noncredential_receipt_id' AND receipt_hash=e.structured_result->>'noncredential_receipt_hash' AND acquisition_execution_id=e.acquisition_execution_id AND attempt_number=e.attempt_number;
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_TERMINAL_RECEIPT_REQUIRED'; END IF;
 SELECT * INTO v FROM public.noncredential_sanitization_verifications WHERE receipt_id=r.receipt_id AND receipt_hash=r.receipt_hash AND verification_id=e.structured_result->>'noncredential_verification_id' AND record_hash=e.structured_result->>'noncredential_verification_hash' AND verification_outcome='verified_sanitized';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02_EXACT_TERMINAL_VERIFICATION_REQUIRED'; END IF;
 IF TG_TABLE_NAME='acquisition_executions' THEN
  IF b.assigned_txid IS DISTINCT FROM pg_current_xact_id()::text OR r.assigned_txid IS DISTINCT FROM b.assigned_txid OR v.assigned_txid IS DISTINCT FROM b.assigned_txid OR e.b02_completion_txid IS DISTINCT FROM b.assigned_txid OR e.previous_acquisition_execution_record_id IS DISTINCT FROM r.start_execution_record_id THEN RAISE EXCEPTION 'B02_ATOMIC_IDENTITY_OR_TRANSACTION_DIVERGENCE'; END IF;
 ELSE
  PERFORM public.b02_require_complete_unit(e.acquisition_execution_id,e.attempt_number,e.acquisition_execution_record_id,false);
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION b02_reject_credential_contradiction() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM public.acquisition_mode_bindings WHERE acquisition_execution_id=NEW.acquisition_execution_id AND mode<>'EXTERNAL_CREDENTIALLED') THEN RAISE EXCEPTION 'NONCREDENTIAL_CHAIN_CONTRADICTION'; END IF;
 RETURN NEW;
END $$;
''')
    for table in ('acquisition_executions','normative_artifacts'):
        op.execute(f"CREATE TRIGGER a_b02_stamp BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION b02_stamp_existing()")
    for table in ('acquisition_mode_bindings','noncredential_acquisition_receipts','noncredential_sanitization_verifications'):
        op.execute(f"CREATE TRIGGER a_b02_validate BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION b02_validate_new_proof()")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only_mutation BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION adr020_reject_append_only_mutation()")
        op.execute(f"CREATE TRIGGER trg_{table}_append_only_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION adr020_reject_append_only_mutation()")
    for table in ('acquisition_mode_bindings','noncredential_acquisition_receipts','noncredential_sanitization_verifications','acquisition_executions','normative_artifacts'):
        op.execute(f"CREATE CONSTRAINT TRIGGER z_b02_complete_unit AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION b02_deferred_complete_unit()")
    for table in ('secret_access_execution_records','credential_use_records'):
        op.execute(f"CREATE TRIGGER a_b02_no_mode_contradiction BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION b02_reject_credential_contradiction()")

def downgrade():
    raise RuntimeError('B02_APPEND_ONLY_IRREVERSIBLE')
