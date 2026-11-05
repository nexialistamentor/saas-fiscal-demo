BEGIN;
-- INTEGRATED CANDIDATE ONLY. No operational authorization.
-- CANDIDATE ONLY: pure assertion, no tables, roots, institutional decisions,
-- policies or DML. Root library path is reviewed, never provided by payload.
-- Replace $libdir/b02_g5_native_REAL_CLOSED only in the separately approved disposable installer.
CREATE FUNCTION public.b02g5_assert_signature(bytea,bytea,bytea,text)
RETURNS void AS '$libdir/b02_g5_native_REAL_CLOSED','b02g5_assert_signature'
LANGUAGE C VOLATILE PARALLEL UNSAFE SECURITY INVOKER;
REVOKE ALL ON FUNCTION public.b02g5_assert_signature(bytea,bytea,bytea,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_assert_signature(bytea,bytea,bytea,text) TO solveris_b02_writer;
CREATE FUNCTION public.b02g5_native_profile()
RETURNS text AS '$libdir/b02_g5_native_REAL_CLOSED','b02g5_native_profile'
LANGUAGE C STABLE PARALLEL UNSAFE SECURITY INVOKER;
REVOKE ALL ON FUNCTION public.b02g5_native_profile() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_native_profile() TO solveris_b02_writer;
CREATE OR REPLACE FUNCTION b02_policy_grant(b jsonb, purpose text, scope_value jsonb, mode_value text, effective_at timestamptz DEFAULT statement_timestamp())
RETURNS jsonb LANGUAGE plpgsql VOLATILE SET search_path=pg_catalog,public,pg_temp AS $$
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
 OR effective_at>clock_timestamp()
 OR effective_at < (a.operational_interval->>'from')::timestamptz
 OR effective_at >= (a.operational_interval->>'until')::timestamptz
 OR clock_timestamp() < (a.operational_interval->>'from')::timestamptz
 OR clock_timestamp() >= (a.operational_interval->>'until')::timestamptz
 THEN RAISE EXCEPTION 'STOP_REAL_POLICY_OR_EVIDENCE_MISSING'; END IF;
 RETURN g;
END $$;

-- Fixed-scope privileged LOCK only; no DML, no caller SQL and no new authority.
-- Candidate requires explicit review of owner/ACL before any installation.
CREATE FUNCTION public.b02g5_lock_authority_snapshot()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp SET lock_timeout='3s' AS $$
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer'
 OR current_setting('transaction_isolation')<>'read committed'
 THEN RAISE EXCEPTION 'G5_LOCK_IDENTITY_OR_ISOLATION_REQUIRED'; END IF;
 LOCK TABLE public.policy_versions,public.policy_decisions,public.policy_activations,
 public.policy_activation_executions,public.policy_activation_generations,
 public.policy_activation_outbox_events,public.bootstrap_authority_records IN SHARE MODE;
END $$;
REVOKE ALL ON FUNCTION public.b02g5_lock_authority_snapshot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_lock_authority_snapshot() TO solveris_b02_writer;

-- New veto only. A real document cannot be relabelled as synthetic.
CREATE FUNCTION public.b02g5_require_unit_class(j jsonb,table_name text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE classification jsonb; parent_class jsonb; h text;
BEGIN
 classification:=j->'provenance'->'synthetic_only';
 IF classification IS NULL OR classification NOT IN ('true'::jsonb,'false'::jsonb) THEN RAISE EXCEPTION 'G5_EXPLICIT_BOOLEAN_CLASS_REQUIRED'; END IF;
 IF table_name='acquisition_mode_bindings' THEN RETURN;
 ELSIF table_name='noncredential_acquisition_receipts' THEN
  SELECT b.provenance->'synthetic_only' INTO parent_class FROM public.acquisition_mode_bindings b
  WHERE b.mode_binding_id=j->>'mode_binding_id' AND b.record_hash=j->>'mode_binding_hash';
  h:=j->>'artifact_hash';
 ELSIF table_name='noncredential_sanitization_verifications' THEN
  SELECT r.provenance->'synthetic_only',r.artifact_hash INTO parent_class,h FROM public.noncredential_acquisition_receipts r
  WHERE r.receipt_id=j->>'receipt_id' AND r.receipt_hash=j->>'receipt_hash';
 ELSE RAISE EXCEPTION 'G5_UNIT_TABLE_UNKNOWN'; END IF;
 IF parent_class IS DISTINCT FROM classification THEN RAISE EXCEPTION 'G5_MIXED_REAL_SYNTHETIC_UNIT_FORBIDDEN'; END IF;
 IF classification='true'::jsonb AND h IN ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832','af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d') THEN RAISE EXCEPTION 'G5_REAL_C3_CANNOT_BE_SYNTHETIC'; END IF;
END $$;

-- CANDIDATE ONLY. Do not run: no G4 real attestation or G5 authority yet.
-- No table, policy type, key or role is created. SECURITY INVOKER is deliberate.
CREATE FUNCTION public.b02g5_require_real_release(j jsonb, table_name text)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE b public.acquisition_mode_bindings%ROWTYPE;
 r public.noncredential_acquisition_receipts%ROWTYPE;
 p public.policy_versions%ROWTYPE; a public.policy_activations%ROWTYPE;
 gp public.policy_versions%ROWTYPE; ga public.policy_activations%ROWTYPE; gd public.policy_decisions%ROWTYPE; gb jsonb;
 d public.policy_decisions%ROWTYPE; g jsonb; release jsonb; doc jsonb;
 chain_count integer; ancestor_ids text[]; actors text[]; events text[]; roles text[];
 hashes text[]; bad boolean; document_hash text; size_bytes bigint; role_info record;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer'
 OR current_user<>session_user OR j->'provenance'->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR j->>'assigned_txid' IS DISTINCT FROM pg_current_xact_id()::text
 THEN RAISE EXCEPTION 'G5_REAL_IDENTITY_OR_TRANSACTION_REQUIRED'; END IF;
 SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolinherit INTO role_info FROM pg_catalog.pg_roles WHERE rolname=current_user;
 IF role_info.rolsuper OR role_info.rolcreatedb OR role_info.rolcreaterole OR role_info.rolreplication OR role_info.rolbypassrls OR role_info.rolinherit
 OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user))
 THEN RAISE EXCEPTION 'G5_RESTRICTED_WRITER_REQUIRED'; END IF;
 IF public.b02g5_native_profile() IS DISTINCT FROM 'REAL_PROFILE_COMPILED_APPROVED_ROOTS' THEN RAISE EXCEPTION 'G5_TRUSTED_FINALIZATION_NOT_IMPLEMENTED_OR_APPROVED'; END IF;
 -- Prospective predicates below are prepared, never an active opening.
 PERFORM public.b02g5_lock_authority_snapshot();
 -- The trust bridge is the EXISTING immutable, separately governed policy chain.
 -- An acquisition writer must be physically unable to manufacture that chain.
 IF has_table_privilege(current_user,'public.policy_versions','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'public.policy_decisions','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'public.bootstrap_authority_records','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_any_column_privilege(current_user,'public.policy_versions','INSERT,UPDATE')
 OR has_any_column_privilege(current_user,'public.policy_decisions','INSERT,UPDATE')
 OR has_any_column_privilege(current_user,'public.bootstrap_authority_records','INSERT,UPDATE')
 OR has_table_privilege(current_user,'public.policy_activations','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_any_column_privilege(current_user,'public.policy_activations','INSERT,UPDATE')
 OR has_table_privilege(current_user,'public.policy_activation_executions','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_any_column_privilege(current_user,'public.policy_activation_executions','INSERT,UPDATE')
 OR has_table_privilege(current_user,'public.policy_activation_generations','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_any_column_privilege(current_user,'public.policy_activation_generations','INSERT,UPDATE')
 OR has_table_privilege(current_user,'public.policy_activation_outbox_events','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_any_column_privilege(current_user,'public.policy_activation_outbox_events','INSERT,UPDATE')
 THEN RAISE EXCEPTION 'G5_WRITER_CANNOT_ISSUE_AUTHORITY'; END IF;
 IF table_name='acquisition_mode_bindings' THEN
  b:=jsonb_populate_record(NULL::public.acquisition_mode_bindings,j);
 ELSIF table_name='noncredential_acquisition_receipts' THEN
  SELECT * INTO b FROM public.acquisition_mode_bindings WHERE mode_binding_id=j->>'mode_binding_id' AND record_hash=j->>'mode_binding_hash';
  IF NOT FOUND THEN RAISE EXCEPTION 'G5_BINDING_MISSING'; END IF;
  document_hash:=j->>'artifact_hash'; size_bytes:=(j->>'byte_size')::bigint;
 ELSIF table_name='noncredential_sanitization_verifications' THEN
  SELECT * INTO r FROM public.noncredential_acquisition_receipts WHERE receipt_id=j->>'receipt_id' AND receipt_hash=j->>'receipt_hash';
  IF NOT FOUND THEN RAISE EXCEPTION 'G5_RECEIPT_MISSING'; END IF;
  SELECT * INTO b FROM public.acquisition_mode_bindings WHERE mode_binding_id=r.mode_binding_id AND record_hash=r.mode_binding_hash;
  IF NOT FOUND THEN RAISE EXCEPTION 'G5_BINDING_MISSING'; END IF;
  document_hash:=r.artifact_hash; size_bytes:=r.byte_size;
 ELSE RAISE EXCEPTION 'G5_TABLE_NOT_AUTHORIZED'; END IF;
 IF b.sanitization_policy_binding IS DISTINCT FROM b.security_policy_binding THEN RAISE EXCEPTION 'G5_ONE_EXACT_REAL_RELEASE_POLICY_REQUIRED'; END IF;
 IF b.mode<>'LOCAL_CAS_INCORPORATION' OR b.provenance->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR b.assigned_txid IS DISTINCT FROM pg_current_xact_id()::text
 THEN RAISE EXCEPTION 'G5_LOCAL_CAS_REAL_UNIT_ONLY'; END IF;
 g:=public.b02_policy_grant(b.security_policy_binding,'security',b.source_scope,b.mode,b.bound_at);
 SELECT * INTO p FROM public.policy_versions WHERE policy_type=b.security_policy_binding->>'policy_type'
 AND policy_id=b.security_policy_binding->>'policy_id' AND policy_version=(b.security_policy_binding->>'policy_version')::integer AND policy_hash=b.security_policy_binding->>'policy_hash';
 SELECT * INTO a FROM public.policy_activations WHERE policy_activation_id=b.security_policy_binding->>'policy_activation_id'
 AND record_hash=b.security_policy_binding->>'policy_activation_record_hash';
 IF p.policy_type IS DISTINCT FROM 'activation_authority' OR p.domain IS DISTINCT FROM 'SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE'
 OR p.origin_evidence->'synthetic_only' IS DISTINCT FROM 'false'::jsonb OR a.provenance->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 THEN RAISE EXCEPTION 'G5_REAL_AUTHORITY_REQUIRED'; END IF;
 SELECT * INTO d FROM public.policy_decisions WHERE decision_id=a.policy_decision_id AND policy_type=p.policy_type
 AND policy_id=p.policy_id AND policy_version=p.policy_version AND policy_hash=p.policy_hash;
 IF NOT FOUND OR d.decision_event<>'ratificada' OR d.institutional_role<>'autoridade_constitucional_final'
 OR d.actor=a.technical_actor OR d.timestamp>a.activated_at OR a.activated_at>clock_timestamp()
 THEN RAISE EXCEPTION 'G5_RATIFICATION_REQUIRED'; END IF;
 WITH RECURSIVE chain AS (
  SELECT q.*,0 AS depth FROM public.policy_decisions q WHERE q.decision_id=d.decision_id
  UNION ALL
  SELECT q.*,c.depth+1 FROM public.policy_decisions q JOIN chain c ON q.decision_id=c.previous_decision_id WHERE c.depth<4
 ) SELECT count(*),array_agg(decision_id ORDER BY depth DESC),array_agg(actor ORDER BY depth DESC),
 array_agg(decision_event ORDER BY depth DESC),array_agg(institutional_role ORDER BY depth DESC),array_agg(record_hash ORDER BY depth DESC),
 bool_or(policy_type IS DISTINCT FROM p.policy_type OR policy_id IS DISTINCT FROM p.policy_id OR policy_version IS DISTINCT FROM p.policy_version OR policy_hash IS DISTINCT FROM p.policy_hash OR timestamp>clock_timestamp())
 INTO chain_count,ancestor_ids,actors,events,roles,hashes,bad FROM chain;
 IF chain_count<>4 OR bad OR events<>ARRAY['submetida','auditoria_iniciada','auditada_favoravelmente','ratificada']::text[]
 OR roles<>ARRAY['proponente_institucional','auditor_independente','auditor_independente','autoridade_constitucional_final']::text[]
 OR actors[2]<>actors[3] OR actors[1]=actors[2] OR actors[1]=actors[4] OR actors[2]=actors[4] OR actors[2]=a.technical_actor
 THEN RAISE EXCEPTION 'G5_EXACT_SEGREGATED_CHAIN_REQUIRED'; END IF;
 IF EXISTS(SELECT 1 FROM public.policy_decisions q WHERE q.policy_type=p.policy_type AND q.policy_id=p.policy_id
 AND q.policy_version=p.policy_version
 AND (q.policy_hash IS DISTINCT FROM p.policy_hash OR NOT(q.decision_id=ANY(ancestor_ids)) OR q.decision_event IN ('auditada_desfavoravelmente','rejeitada','cancelada')))
 THEN RAISE EXCEPTION 'G5_CURRENT_DECISION_AMBIGUOUS'; END IF;
 IF EXISTS(SELECT 1 FROM public.policy_decisions q WHERE q.decision_id=ancestor_ids[1] AND (q.previous_decision_id IS NOT NULL OR q.evidence->'previous_decision_record_hash' IS DISTINCT FROM 'null'::jsonb))
 OR EXISTS(SELECT 1 FROM generate_series(2,4) n JOIN public.policy_decisions q ON q.decision_id=ancestor_ids[n]
 JOIN public.policy_decisions prev ON prev.decision_id=ancestor_ids[n-1]
 WHERE q.previous_decision_id IS DISTINCT FROM prev.decision_id OR q.evidence->>'previous_decision_record_hash' IS DISTINCT FROM prev.record_hash OR q.timestamp<prev.timestamp)
 THEN RAISE EXCEPTION 'G5_PREDECESSOR_DIVERGENCE'; END IF;
 IF EXISTS(SELECT 1 FROM public.policy_activations q WHERE q.policy_type=p.policy_type AND q.domain=a.domain AND q.modality=a.modality
 AND q.policy_activation_id<>a.policy_activation_id
 AND (NOT(q.operational_interval ?& ARRAY['from','until']) OR q.operational_interval->>'from' IS NULL OR q.operational_interval->>'until' IS NULL OR q.state NOT IN ('activa','suspensa','desactivada','expirada','revogada') OR q.activated_at>clock_timestamp()
 OR q.policy_id=p.policy_id AND q.policy_version=p.policy_version AND q.state<>'activa'
 OR q.state='activa' AND (q.operational_interval->>'from')::timestamptz<(a.operational_interval->>'until')::timestamptz
 AND (a.operational_interval->>'from')::timestamptz<(q.operational_interval->>'until')::timestamptz))
 THEN RAISE EXCEPTION 'G5_CURRENT_ACTIVATION_AMBIGUOUS'; END IF;
 PERFORM public.b02p_require_complete(a.policy_activation_execution_id,false);
 release:=g->'g5_release';
 IF release->>'schema' IS DISTINCT FROM 'B02_G5_SEFA_PR_REAL_RELEASE_V1'
 OR release->>'mode' IS DISTINCT FROM 'LOCAL_CAS_INCORPORATION' OR release->>'actor' IS DISTINCT FROM b.actor
 OR release->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR clock_timestamp()<(release->>'from')::timestamptz OR clock_timestamp()>=(release->>'until')::timestamptz
 OR release->>'from' IS NULL OR release->>'until' IS NULL
 OR jsonb_typeof(release->'documents') IS DISTINCT FROM 'array' OR jsonb_array_length(release->'documents')<>2
 OR (SELECT count(DISTINCT x->>'sha256') FROM jsonb_array_elements(release->'documents') x)<>2
 THEN RAISE EXCEPTION 'G5_EXACT_REAL_RELEASE_REQUIRED'; END IF;
 -- Ratification is resolved from the actual activation above, not embedded
 -- inside its own immutable policy (which would create a hash cycle).
 SELECT item INTO doc FROM jsonb_array_elements(release->'documents') item
 WHERE item->>'acquisition_execution_id'=b.acquisition_execution_id;
 IF NOT FOUND OR (SELECT count(*) FROM jsonb_array_elements(release->'documents') x WHERE x->>'acquisition_execution_id'=b.acquisition_execution_id)<>1
 OR EXISTS(SELECT 1 FROM unnest(ARRAY['acquisition_execution_id','mode_binding_id','artifact_reference_id','receipt_id','verification_id','normative_artifact_id']) k WHERE coalesce(doc->>k,'')='')
 OR doc->>'mode_binding_id' IS DISTINCT FROM b.mode_binding_id OR doc->>'artifact_reference_id' IS DISTINCT FROM b.artifact_reference_id
 OR b.source_identity_binding->>'source_id' IS DISTINCT FROM 'SEFA-PR-B02-DOCUMENTAL'
 OR doc->>'url' IS DISTINCT FROM b.source_identity_binding->>'exact_locator'
 OR NOT coalesce(((doc->>'sha256'='e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832' AND doc->>'byte_size'='258302' AND doc->>'url'='https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101202501245.pdf')
 OR (doc->>'sha256'='af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d' AND doc->>'byte_size'='1944929' AND doc->>'url'='https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf')),false)
 OR (document_hash IS NOT NULL AND (document_hash IS DISTINCT FROM doc->>'sha256' OR size_bytes::text IS DISTINCT FROM doc->>'byte_size'))
 OR doc->'g4'->>'valid_from' IS NULL OR doc->'g4'->>'valid_until' IS NULL
 OR clock_timestamp()<(doc->'g4'->>'valid_from')::timestamptz OR clock_timestamp()>=(doc->'g4'->>'valid_until')::timestamptz
 OR doc->'g4'->>'outcome' IS DISTINCT FROM 'conclusivo_favoravel' OR doc->'g4'->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR coalesce(doc->'g4'->'origin_report_binding'->>'sha256','') !~ '^[0-9a-f]{64}$'
 OR coalesce(doc->'g4'->'verifier'->>'hash','') !~ '^[0-9a-f]{64}$'
 OR doc->'g4'->'verifier' IS DISTINCT FROM jsonb_build_object('id','SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN','version','1','hash','fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472')
 OR (doc->>'sha256'='e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832' AND doc->>'document_id' IS DISTINCT FROM '101202501245')
 OR (doc->>'sha256'='af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d' AND doc->>'document_id' IS DISTINCT FROM '101201900571')
 OR doc->'sanitization'->>'outcome' IS DISTINCT FROM 'verified_sanitized'
 OR doc->'sanitization'->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR (CASE WHEN doc->'sanitization'->>'proof_binding_mode'='B02_G5_SIGNED_TRANSACTION_PROOFS_V1' THEN
    coalesce(doc->'sanitization'->'institutional_method_review_binding'->>'sha256','') !~ '^[0-9a-f]{64}$'
    OR doc->'sanitization'->'institutional_method_review_binding' IS DISTINCT FROM p.origin_evidence->'institutional_evidence_bindings'->'method_review'
    ELSE coalesce(doc->'sanitization'->'signed_evidence_binding'->>'sha256','') !~ '^[0-9a-f]{64}$' END)
 THEN RAISE EXCEPTION 'G5_EXACT_DOCUMENT_OR_G4_MISSING'; END IF;
 -- Recheck the ORIGINAL G4 authority as well as the G5 release. The fixed
 -- SHARE locks prevent competing policy/decision/activation INSERTs through
 -- commit. READ COMMITTED ensures post-lock checks observe prior commits.
 gb:=doc->'g4'->'policy_binding';
 SELECT * INTO gp FROM public.policy_versions WHERE policy_type=gb->>'policy_type' AND policy_id=gb->>'policy_id' AND policy_version=(gb->>'policy_version')::integer AND policy_hash=gb->>'policy_hash';
 SELECT * INTO ga FROM public.policy_activations WHERE policy_activation_id=gb->>'policy_activation_id' AND record_hash=gb->>'policy_activation_record_hash' AND policy_type=gp.policy_type AND policy_id=gp.policy_id AND policy_version=gp.policy_version AND policy_hash=gp.policy_hash;
 SELECT * INTO gd FROM public.policy_decisions WHERE decision_id=gb->>'decision_id' AND record_hash=gb->>'decision_hash' AND decision_id=ga.policy_decision_id AND policy_type=gp.policy_type AND policy_id=gp.policy_id AND policy_version=gp.policy_version AND policy_hash=gp.policy_hash;
 IF gp.policy_type IS DISTINCT FROM 'activation_authority' OR gp.domain IS DISTINCT FROM 'SEFA_PR_B02_DOCUMENTAL'
 OR gp.origin_evidence->'synthetic_only' IS DISTINCT FROM 'false'::jsonb OR ga.provenance->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
 OR ga.modality IS DISTINCT FROM b.mode OR gp.scope->>'source_id' IS DISTINCT FROM 'SEFA-PR-B02-DOCUMENTAL'
 OR NOT coalesce(gp.scope->'document_hashes' ? (doc->>'sha256'),false)
 OR ga.state IS DISTINCT FROM 'activa' OR gd.decision_event IS DISTINCT FROM 'ratificada'
 OR ga.activated_at>clock_timestamp() OR clock_timestamp()<(ga.operational_interval->>'from')::timestamptz OR clock_timestamp()>=(ga.operational_interval->>'until')::timestamptz
 OR ga.operational_interval->>'from' IS NULL OR ga.operational_interval->>'until' IS NULL
 THEN RAISE EXCEPTION 'G5_ORIGINAL_G4_AUTHORITY_NOT_CURRENT'; END IF;
 WITH RECURSIVE ancestors AS (
 SELECT decision_id,previous_decision_id,0 AS depth FROM public.policy_decisions WHERE decision_id=gd.decision_id
 UNION ALL SELECT q.decision_id,q.previous_decision_id,x.depth+1 FROM public.policy_decisions q JOIN ancestors x ON q.decision_id=x.previous_decision_id WHERE x.depth<4
 ) SELECT array_agg(decision_id) INTO ancestor_ids FROM ancestors;
 IF cardinality(ancestor_ids)<>4 OR EXISTS(SELECT 1 FROM public.policy_decisions q WHERE q.policy_type=gp.policy_type AND q.policy_id=gp.policy_id
 AND q.policy_version=gp.policy_version
 AND (q.policy_hash IS DISTINCT FROM gp.policy_hash OR NOT(q.decision_id=ANY(ancestor_ids))))
 OR EXISTS(SELECT 1 FROM public.policy_activations q WHERE q.policy_type=gp.policy_type AND q.domain=ga.domain AND q.modality=ga.modality AND q.policy_activation_id<>ga.policy_activation_id
 AND (q.state NOT IN ('activa','suspensa','desactivada','expirada','revogada') OR q.activated_at>clock_timestamp()
 OR NOT(q.operational_interval ?& ARRAY['from','until']) OR q.operational_interval->>'from' IS NULL OR q.operational_interval->>'until' IS NULL
 OR q.policy_id=gp.policy_id AND q.policy_version=gp.policy_version AND q.state<>'activa'
 OR q.state='activa' AND (q.operational_interval->>'from')::timestamptz<(ga.operational_interval->>'until')::timestamptz AND (ga.operational_interval->>'from')::timestamptz<(q.operational_interval->>'until')::timestamptz))
 THEN RAISE EXCEPTION 'G5_ORIGINAL_G4_AUTHORITY_AMBIGUOUS'; END IF;
 PERFORM public.b02p_require_complete(ga.policy_activation_execution_id,false);
 -- Explicit opt-in: policies without this selector retain the original exact guards.
 IF doc->'sanitization'->>'proof_binding_mode' = 'B02_G5_SIGNED_TRANSACTION_PROOFS_V1' THEN
  IF doc->'sanitization'->'verification_method_binding' IS DISTINCT FROM g->'verification_engine_binding'
  OR coalesce(doc->'sanitization'->'verification_method_binding'->>'hash','') !~ '^[0-9a-f]{64}$'
  OR coalesce(doc->'sanitization'->>'execution_proof_id','')=''
  OR coalesce(doc->'sanitization'->>'independence_evidence_id','')=''
  OR coalesce(doc->'sanitization'->'verifier_acceptance_binding'->>'hash','') !~ '^[0-9a-f]{64}$'
  OR coalesce(doc->'sanitization'->'mandate_binding'->>'hash','') !~ '^[0-9a-f]{64}$'
  THEN RAISE EXCEPTION 'G5_EXPLICIT_DYNAMIC_METHOD_MANDATE_REQUIRED'; END IF;
  IF table_name='noncredential_acquisition_receipts' THEN
   IF j->>'receipt_id' IS DISTINCT FROM doc->>'receipt_id'
   OR j->'component_manifest' IS DISTINCT FROM doc->'sanitization'->'component_manifest'
   OR j->'execution_proof_binding'->>'id' IS DISTINCT FROM doc->'sanitization'->>'execution_proof_id'
   THEN RAISE EXCEPTION 'G5_APPROVED_COMPONENT_PROOF_REQUIRED'; END IF;
  ELSIF table_name='noncredential_sanitization_verifications' THEN
   DECLARE ep jsonb; ie jsonb; im jsonb;
   BEGIN
    im:=j->'inspected_component_manifest'; ep:=im->'execution_proof'; ie:=im->'independence_evidence';
    IF j->>'verification_id' IS DISTINCT FROM doc->>'verification_id'
    OR j->>'verification_outcome' IS DISTINCT FROM 'verified_sanitized'
    OR j->'violation_manifest' IS DISTINCT FROM '[]'::jsonb
    OR j->>'verifier' IS DISTINCT FROM doc->'sanitization'->>'verifier'
    OR (im-ARRAY['execution_proof_binding','independence_evidence_binding','execution_proof','independence_evidence']) IS DISTINCT FROM doc->'sanitization'->'inspected_component_manifest'
    OR jsonb_typeof(ep) IS DISTINCT FROM 'object' OR jsonb_typeof(ie) IS DISTINCT FROM 'object'
    OR r.execution_proof_binding IS DISTINCT FROM im->'execution_proof_binding'
    OR im->'execution_proof_binding' IS DISTINCT FROM jsonb_build_object('id',doc->'sanitization'->>'execution_proof_id','hash',public.b02_json_hash(ep))
    OR im->'independence_evidence_binding' IS DISTINCT FROM jsonb_build_object('id',doc->'sanitization'->>'independence_evidence_id','hash',public.b02_json_hash(ie))
    THEN RAISE EXCEPTION 'G5_CURRENT_DYNAMIC_PROOF_BINDINGS_REQUIRED'; END IF;
    IF ep IS DISTINCT FROM jsonb_build_object('schema','B02_G5_LOCAL_CAS_EXECUTION_PROOF_V1',
      'acquisition_execution_id',b.acquisition_execution_id,'attempt_number',b.attempt_number,
      'mode_binding_id',b.mode_binding_id,'mode_binding_hash',b.record_hash,'assigned_txid',b.assigned_txid,
      'artifact_hash',r.artifact_hash,'byte_size',r.byte_size,'observer',r.creator,
      'read_observed_at',r.cas_manifest->>'read_observed_at',
      'verification_method_binding',doc->'sanitization'->'verification_method_binding')
    OR coalesce(ep->>'read_observed_at','')=''
    OR (ep->>'read_observed_at')::timestamptz<b.bound_at
    OR NOT EXISTS (SELECT 1 FROM public.acquisition_executions exact_start
      WHERE exact_start.acquisition_execution_record_id=r.start_execution_record_id
      AND exact_start.record_hash=r.start_execution_record_hash
      AND exact_start.acquisition_execution_id=r.acquisition_execution_id
      AND exact_start.attempt_number=r.attempt_number
      AND exact_start.execution_event='inicio'
      AND exact_start.projected_state='em_execucao'
      AND exact_start.started_at<=(ep->>'read_observed_at')::timestamptz)
    OR (ep->>'read_observed_at')::timestamptz>r.observed_at
    THEN RAISE EXCEPTION 'G5_CURRENT_EXECUTION_PROOF_REQUIRED'; END IF;
    IF ie IS DISTINCT FROM jsonb_build_object('schema','B02_G5_SEGREGATED_INSPECTION_EVIDENCE_V1',
      'verification_id',j->>'verification_id','receipt_id',r.receipt_id,'receipt_hash',r.receipt_hash,
      'execution_proof_hash',public.b02_json_hash(ep),'creator',r.creator,'verifier',j->>'verifier',
      'reviewed_at',j->>'verified_at','outcome','verified_sanitized',
      'verification_method_binding',doc->'sanitization'->'verification_method_binding',
      'mandate_binding',doc->'sanitization'->'mandate_binding',
      'verifier_acceptance_binding',doc->'sanitization'->'verifier_acceptance_binding',
      'independent_review_record_binding',ie->'independent_review_record_binding')
    OR coalesce(ie->'independent_review_record_binding'->>'id','')=''
    OR coalesce(ie->'independent_review_record_binding'->>'hash','') !~ '^[0-9a-f]{64}$'
    THEN RAISE EXCEPTION 'G5_OWN_SEGREGATED_INSPECTION_RECORD_REQUIRED'; END IF;
    -- This binds bytes, not model identity. The trusted COMMIT issuer must
    -- independently resolve the own-review record and its documentary trail.
    -- Receipt+verification record hashes cover both bodies in the signed units.
   END;
  END IF;
 ELSIF doc->'sanitization'->>'proof_binding_mode' IS NULL THEN
  IF table_name='noncredential_acquisition_receipts' AND (j->>'receipt_id' IS DISTINCT FROM doc->>'receipt_id' OR j->'component_manifest' IS DISTINCT FROM doc->'sanitization'->'component_manifest' OR j->'execution_proof_binding' IS DISTINCT FROM doc->'sanitization'->'execution_proof_binding') THEN RAISE EXCEPTION 'G5_APPROVED_COMPONENT_PROOF_REQUIRED'; END IF;
  IF table_name='noncredential_sanitization_verifications' AND (j->>'verification_id' IS DISTINCT FROM doc->>'verification_id' OR j->'inspected_component_manifest' IS DISTINCT FROM doc->'sanitization'->'inspected_component_manifest' OR j->'violation_manifest' IS DISTINCT FROM '[]'::jsonb OR j->>'verification_outcome' IS DISTINCT FROM 'verified_sanitized' OR j->>'verifier' IS DISTINCT FROM doc->'sanitization'->>'verifier') THEN RAISE EXCEPTION 'G5_APPROVED_REAL_SANITIZATION_REQUIRED'; END IF;
 ELSE RAISE EXCEPTION 'G5_UNKNOWN_PROOF_BINDING_MODE'; END IF;
END $$;

CREATE FUNCTION public.b02g5_require_authenticity_in_unit(b jsonb,r jsonb,a jsonb)
RETURNS void LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE g jsonb; doc jsonb; matches integer;
BEGIN
 g:=public.b02_policy_grant(b->'security_policy_binding','security',b->'source_scope',b->>'mode');
 SELECT x INTO doc FROM jsonb_array_elements(g->'g5_release'->'documents') x WHERE x->>'acquisition_execution_id'=b->>'acquisition_execution_id';
 IF NOT FOUND OR a->>'normative_artifact_id' IS DISTINCT FROM doc->>'normative_artifact_id' THEN RAISE EXCEPTION 'G5_RELEASE_DOCUMENT_MISSING_AT_COMMIT'; END IF;
 SELECT count(*) INTO matches FROM public.artifact_verification_records v
 WHERE v.normative_artifact_id=a->>'normative_artifact_id' AND v.verified_artifact_hash=r->>'artifact_hash'
 AND v.verification_type='authenticity' AND v.outcome='conclusivo_favoravel'
 AND v.verifier=doc->'g4'->'verifier'->>'id' AND v.verifier_version=doc->'g4'->'verifier'->>'version'
 AND v.evidence::jsonb->'synthetic_only'='false'::jsonb
 AND v.evidence::jsonb->'g4_origin_report_binding'=doc->'g4'->'origin_report_binding'
 AND v.evidence->>'authorized_verifier_hash'=doc->'g4'->'verifier'->>'hash';
 IF matches<>1 THEN RAISE EXCEPTION 'G5_ONE_EXACT_AUTHENTICITY_RECORD_REQUIRED'; END IF;
END $$;

CREATE OR REPLACE FUNCTION b02_validate_new_proof() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public,pg_temp SET timezone='UTC' AS $$
DECLARE j jsonb; expected text; material text; b public.acquisition_mode_bindings%ROWTYPE;
 r public.noncredential_acquisition_receipts%ROWTYPE; e public.acquisition_executions%ROWTYPE;
 ref public.artifact_references%ROWTYPE; g jsonb; s jsonb; p jsonb;
BEGIN
 IF NEW.assigned_txid IS NOT NULL THEN RAISE EXCEPTION 'B02_SERVER_TXID_ONLY'; END IF;
 NEW.assigned_txid:=pg_current_xact_id()::text;
 -- This reviewed local candidate admits synthetic proofs only; real evidence
 -- requires its own implementation/authority gate, never two asserted names.
 PERFORM public.b02g5_require_unit_class(to_jsonb(NEW),TG_TABLE_NAME);
 IF NEW.provenance->'synthetic_only' IS DISTINCT FROM 'true'::jsonb THEN
  PERFORM public.b02g5_require_real_release(to_jsonb(NEW),TG_TABLE_NAME);
 END IF;
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
CREATE OR REPLACE FUNCTION b02_require_complete_unit(execution_id text, attempt integer, terminal_id text, current_transaction_required boolean)
RETURNS void LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$
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
 PERFORM public.b02g5_require_unit_class(to_jsonb(b),'acquisition_mode_bindings');
 PERFORM public.b02g5_require_unit_class(to_jsonb(r),'noncredential_acquisition_receipts');
 PERFORM public.b02g5_require_unit_class(to_jsonb(v),'noncredential_sanitization_verifications');
 IF b.provenance->'synthetic_only'='false'::jsonb AND current_transaction_required THEN
  IF a.provenance->'synthetic_only' IS DISTINCT FROM 'false'::jsonb
  OR EXISTS(SELECT 1 FROM public.acquisition_executions q WHERE q.acquisition_execution_id=b.acquisition_execution_id AND q.attempt_number=b.attempt_number AND q.provenance->'synthetic_only' IS DISTINCT FROM 'false'::jsonb)
  OR EXISTS(SELECT 1 FROM public.artifact_references q WHERE q.artifact_reference_id=b.artifact_reference_id AND q.evidence->'synthetic_only' IS DISTINCT FROM 'false'::jsonb)
  THEN RAISE EXCEPTION 'G5_MIXED_REAL_SYNTHETIC_PREDECESSORS_FORBIDDEN'; END IF;
  PERFORM public.b02g5_require_real_release(to_jsonb(b),'acquisition_mode_bindings');
  PERFORM public.b02g5_require_real_release(to_jsonb(r),'noncredential_acquisition_receipts');
  PERFORM public.b02g5_require_real_release(to_jsonb(v),'noncredential_sanitization_verifications');
  PERFORM public.b02g5_require_authenticity_in_unit(to_jsonb(b),to_jsonb(r),to_jsonb(a));
 END IF;
END $$;
-- CANDIDATE ONLY. No installation, authority provisioning or real opening.
-- Existing 0064 real STOP must remain until full physical integration passes.
CREATE FUNCTION public.b02g5_server_identity() RETURNS jsonb
LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT jsonb_build_object('system_identifier',(SELECT system_identifier::text FROM pg_control_system()),
  'database_oid',(SELECT oid::bigint FROM pg_catalog.pg_database WHERE datname=current_database()),
  'database_name',current_database(),'writer_oid',(SELECT oid::bigint FROM pg_catalog.pg_roles WHERE rolname=session_user),
  'writer_name',session_user,'txid',pg_current_xact_id()::text)
$$;
REVOKE ALL ON FUNCTION public.b02g5_server_identity() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_server_identity() TO solveris_b02_writer;

CREATE FUNCTION public.b02g5_capability_manifest() RETURNS text
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE b public.acquisition_mode_bindings%ROWTYPE; p public.policy_versions%ROWTYPE;
 r public.noncredential_acquisition_receipts%ROWTYPE; v public.noncredential_sanitization_verifications%ROWTYPE;
 e public.acquisition_executions%ROWTYPE; a public.normative_artifacts%ROWTYPE;
 avr public.artifact_verification_records%ROWTYPE; units jsonb:='[]'; docs jsonb:='[]';
 binding jsonb; release jsonb; grants jsonb; authority jsonb:='{}'; values_hash jsonb; t text;
 cnt integer; manifest jsonb; release_scope jsonb; release_mode text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer' OR current_user<>session_user OR current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'G5_CAPABILITY_RESTRICTED_WRITER_REQUIRED'; END IF;
 -- These are the locks already acquired by the mandatory real-row registrar.
 -- PRE_COMMIT never manufactures a new authority snapshot after releasing locks.
 FOREACH t IN ARRAY ARRAY['policy_versions','policy_decisions','policy_activations','policy_activation_executions','policy_activation_generations','policy_activation_outbox_events','bootstrap_authority_records'] LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE pid=pg_backend_pid() AND relation=to_regclass('public.'||t) AND granted AND mode IN ('ShareLock','ShareRowExclusiveLock','ExclusiveLock','AccessExclusiveLock')) THEN RAISE EXCEPTION 'G5_AUTHORITY_LOCK_NOT_HELD'; END IF;
  IF has_table_privilege(current_user,'public.'||t,'INSERT,UPDATE,DELETE,TRUNCATE') OR has_any_column_privilege(current_user,'public.'||t,'INSERT,UPDATE') THEN RAISE EXCEPTION 'G5_WRITER_CANNOT_ISSUE_AUTHORITY'; END IF;
  EXECUTE format('SELECT coalesce(jsonb_agg(record_hash ORDER BY record_hash),''[]''::jsonb) FROM public.%I',t) INTO values_hash;
  authority:=authority||jsonb_build_object(t,values_hash);
 END LOOP;
 FOR b IN SELECT * FROM public.acquisition_mode_bindings WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb ORDER BY acquisition_execution_id,attempt_number LOOP
  IF binding IS NOT NULL AND binding IS DISTINCT FROM b.security_policy_binding THEN RAISE EXCEPTION 'G5_CAPABILITY_SINGLE_EXACT_RELEASE_REQUIRED'; END IF;
  IF b.mode<>'LOCAL_CAS_INCORPORATION' OR b.sanitization_policy_binding IS DISTINCT FROM b.security_policy_binding THEN RAISE EXCEPTION 'G5_CAPABILITY_LOCAL_EXACT_MODE_REQUIRED'; END IF;
  binding:=b.security_policy_binding; release_scope:=b.source_scope; release_mode:=b.mode;
  SELECT * INTO STRICT r FROM public.noncredential_acquisition_receipts WHERE mode_binding_id=b.mode_binding_id AND mode_binding_hash=b.record_hash AND assigned_txid=b.assigned_txid;
  SELECT * INTO STRICT v FROM public.noncredential_sanitization_verifications WHERE receipt_id=r.receipt_id AND receipt_hash=r.receipt_hash AND assigned_txid=b.assigned_txid AND verification_outcome='verified_sanitized';
  SELECT * INTO STRICT e FROM public.acquisition_executions WHERE acquisition_execution_id=b.acquisition_execution_id AND attempt_number=b.attempt_number AND execution_event='conclusao' AND projected_state='concluida';
  SELECT * INTO STRICT a FROM public.normative_artifacts WHERE acquisition_execution_record_id=e.acquisition_execution_record_id AND acquisition_execution_id=e.acquisition_execution_id AND acquisition_attempt_number=e.attempt_number AND artifact_reference_id=e.artifact_reference_id;
  SELECT * INTO STRICT avr FROM public.artifact_verification_records WHERE normative_artifact_id=a.normative_artifact_id AND verified_artifact_hash=r.artifact_hash AND verification_type='authenticity' AND outcome='conclusivo_favoravel';
  units:=units||jsonb_build_array(jsonb_build_object('binding',b.record_hash,'receipt',r.record_hash,'receipt_material',r.receipt_hash,'verification',v.record_hash,'terminal',e.record_hash,'artifact',a.record_hash,'authenticity',avr.record_hash));
  docs:=docs||jsonb_build_array(jsonb_build_object('id',CASE r.artifact_hash WHEN 'e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832' THEN '101202501245' WHEN 'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d' THEN '101201900571' ELSE NULL END,'sha256',r.artifact_hash,'byte_size',r.byte_size));
 END LOOP;
 cnt:=jsonb_array_length(docs);
 IF cnt<>2 OR (SELECT count(DISTINCT x->>'id') FROM jsonb_array_elements(docs) x)<>cnt OR EXISTS(SELECT 1 FROM jsonb_array_elements(docs) x WHERE x->>'id' IS NULL) THEN RAISE EXCEPTION 'G5_CAPABILITY_EXACT_DOCUMENT_SET_REQUIRED'; END IF;
 SELECT jsonb_agg(x ORDER BY x->>'id') INTO docs FROM jsonb_array_elements(docs) x;
 SELECT * INTO STRICT p FROM public.policy_versions WHERE policy_type=binding->>'policy_type' AND policy_id=binding->>'policy_id' AND policy_version=(binding->>'policy_version')::integer AND policy_hash=binding->>'policy_hash';
 IF p.policy_type<>'activation_authority' OR p.domain<>'SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE' OR p.origin_evidence->'synthetic_only' IS DISTINCT FROM 'false'::jsonb THEN RAISE EXCEPTION 'G5_CAPABILITY_REAL_POLICY_REQUIRED'; END IF;
 grants:=public.b02_policy_grant(binding,'security',release_scope,release_mode,clock_timestamp());
 release:=grants->'g5_release';
 IF coalesce(release->>'capability_root_id','')='' OR jsonb_typeof(p.origin_evidence->'institutional_evidence_bindings') IS DISTINCT FROM 'object' OR (p.origin_evidence->'institutional_evidence_bindings')='{}'::jsonb OR release->>'from' IS NULL OR release->>'until' IS NULL OR NOT ((release->>'from')::timestamptz<=clock_timestamp() AND clock_timestamp()<(release->>'until')::timestamptz) THEN RAISE EXCEPTION 'G5_CAPABILITY_MANDATE_OR_WINDOW_MISSING'; END IF;
 manifest:=jsonb_build_object('schema','B02_G5_TX_RELEASE_V1','audit_scope','SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE','synthetic_only',false,'capability_root_id',release->>'capability_root_id','release_policy_hash',p.policy_hash,'server',public.b02g5_server_identity(),'g5_policy_binding',binding,'g4_verifier',jsonb_build_object('id','SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN','version','1','hash','fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472'),'authority_snapshot_hash',public.b02_json_hash(authority),'institutional_proofs_hash',public.b02_json_hash(p.origin_evidence->'institutional_evidence_bindings'),'units_manifest_hash',public.b02_json_hash(units),'documents',docs,'valid_from',release->>'from','valid_until',release->>'until');
 RETURN public.b02_canonical_json(manifest);
END $$;
REVOKE ALL ON FUNCTION public.b02g5_capability_manifest() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_capability_manifest() TO solveris_b02_writer;

CREATE FUNCTION public.b02g5_assert_transaction_capability() RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE envelope jsonb; expected bytea; raw text;
BEGIN
 raw:=current_setting('solveris.g5_signed_capability',true);
 IF raw IS NULL OR octet_length(raw)>131072 THEN RAISE EXCEPTION 'G5_SIGNED_CAPABILITY_MISSING'; END IF;
 -- The GUC is UNTRUSTED transport only. No flag/status in it grants authority.
 envelope:=raw::jsonb;
 IF jsonb_typeof(envelope) IS DISTINCT FROM 'object' OR NOT(envelope ?& ARRAY['key_id','signed_message_base64','signature_base64']) OR (SELECT count(*) FROM jsonb_object_keys(envelope))<>3 OR jsonb_typeof(envelope->'key_id') IS DISTINCT FROM 'string' OR jsonb_typeof(envelope->'signed_message_base64') IS DISTINCT FROM 'string' OR jsonb_typeof(envelope->'signature_base64') IS DISTINCT FROM 'string' THEN RAISE EXCEPTION 'G5_SIGNED_CAPABILITY_INVALID'; END IF;
 expected:=convert_to(public.b02g5_capability_manifest(),'UTF8');
 PERFORM public.b02g5_assert_signature(expected,decode(envelope->>'signed_message_base64','base64'),decode(envelope->>'signature_base64','base64'),envelope->>'key_id');
END $$;
REVOKE ALL ON FUNCTION public.b02g5_assert_transaction_capability() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_assert_transaction_capability() TO solveris_b02_writer;
-- Integration delta NOT applied: mandatory native PRE_COMMIT validator must call
-- b02g5_assert_transaction_capability(), then full b02_require_complete_unit().
-- Main0064 realSTOP remains until this bridge AND full25+7 are physically proved.
-- CANDIDATE ONLY; not installed; no new authority, no DML.
-- The real STOP in 0064 must stay until cryptographic capability->SQL bridge
-- AND this callback's complete physical integration pass independent review.
CREATE FUNCTION public.b02g5_precommit_validate() RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE t text; b public.acquisition_mode_bindings%ROWTYPE;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer' OR current_user<>session_user OR current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'G5_PRECOMMIT_RESTRICTED_IDENTITY_REQUIRED'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.acquisition_mode_bindings WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) AND NOT EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) AND NOT EXISTS(SELECT 1 FROM public.noncredential_sanitization_verifications WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) THEN RETURN; END IF;
 FOREACH t IN ARRAY ARRAY['policy_versions','policy_decisions','policy_activations','policy_activation_executions','policy_activation_generations','policy_activation_outbox_events','bootstrap_authority_records'] LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE pid=pg_backend_pid() AND relation=to_regclass('public.'||t) AND granted AND mode IN ('ShareLock','ShareRowExclusiveLock','ExclusiveLock','AccessExclusiveLock')) THEN RAISE EXCEPTION 'G5_AUTHORITY_LOCK_NOT_HELD'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts r WHERE r.assigned_txid=pg_current_xact_id()::text AND r.provenance->'synthetic_only'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM public.acquisition_mode_bindings q WHERE q.mode_binding_id=r.mode_binding_id AND q.record_hash=r.mode_binding_hash AND q.assigned_txid=r.assigned_txid AND q.provenance->'synthetic_only'='false'::jsonb)) OR EXISTS(SELECT 1 FROM public.noncredential_sanitization_verifications v WHERE v.assigned_txid=pg_current_xact_id()::text AND v.provenance->'synthetic_only'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts r JOIN public.acquisition_mode_bindings q ON q.mode_binding_id=r.mode_binding_id AND q.record_hash=r.mode_binding_hash AND q.assigned_txid=r.assigned_txid WHERE r.receipt_id=v.receipt_id AND r.receipt_hash=v.receipt_hash AND r.assigned_txid=v.assigned_txid AND r.provenance->'synthetic_only'='false'::jsonb AND q.provenance->'synthetic_only'='false'::jsonb)) THEN RAISE EXCEPTION 'G5_PRECOMMIT_EXACT_PREDECESSOR_REQUIRED'; END IF;
 PERFORM public.b02g5_assert_transaction_capability();
 FOR b IN SELECT * FROM public.acquisition_mode_bindings WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb LOOP
  PERFORM public.b02_require_complete_unit(b.acquisition_execution_id,b.attempt_number,NULL,true);
 END LOOP;
END $$;
REVOKE ALL ON FUNCTION public.b02g5_precommit_validate() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02g5_precommit_validate() TO solveris_b02_writer;
-- CANDIDATE ONLY. Owner/admin installs only in the authorized disposable test DB.
-- Production deployment requires separate authority and exact artifact approval.
CREATE FUNCTION public.b02g5_register_real_precommit()
RETURNS trigger
AS '$libdir/b02_g5_native_REAL_CLOSED', 'b02g5_register_real_precommit'
LANGUAGE C VOLATILE PARALLEL UNSAFE SECURITY INVOKER;
REVOKE ALL ON FUNCTION public.b02g5_register_real_precommit() FROM PUBLIC;
-- Trigger invocation does not require client EXECUTE; writer cannot call as SQL.
-- Alphabetical trigger order is not relied on: this registrar only arms a
-- backend callback; original physical validators remain mandatory and intact.
CREATE TRIGGER trg_b02g5_real_binding_precommit
BEFORE INSERT ON public.acquisition_mode_bindings
FOR EACH ROW WHEN (NEW.provenance->'synthetic_only' = 'false'::jsonb)
EXECUTE FUNCTION public.b02g5_register_real_precommit();
CREATE TRIGGER trg_b02g5_real_receipt_precommit
BEFORE INSERT ON public.noncredential_acquisition_receipts
FOR EACH ROW WHEN (NEW.provenance->'synthetic_only' = 'false'::jsonb)
EXECUTE FUNCTION public.b02g5_register_real_precommit();
CREATE TRIGGER trg_b02g5_real_verification_precommit
BEFORE INSERT ON public.noncredential_sanitization_verifications
FOR EACH ROW WHEN (NEW.provenance->'synthetic_only' = 'false'::jsonb)
EXECUTE FUNCTION public.b02g5_register_real_precommit();

INSERT INTO alembic_version (version_num) VALUES ('0064_b02_g5_controlled_real_cas') ON CONFLICT DO NOTHING;
COMMIT;
