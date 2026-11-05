BEGIN;
-- B02 G5 one-shot reservation, PROTECTED profile. Candidate only, never installed.
-- Reuses the accepted V30 disposable design (table + reserve + assert),
-- swapping ONLY the profile guard (SYNTHETIC -> REAL_PROFILE_COMPILED_APPROVED_ROOTS).
-- b02g5_capability_manifest() and b02g5_precommit_validate() are replaced
-- directly via CREATE OR REPLACE with the exact 0064 body plus the
-- one-shot call -- no _v28-style rename, because this is the FIRST
-- installation of these functions under the real profile, not a patch.

DO $$ BEGIN
 IF to_regclass('public.b02_g5_operational_approval_uses') IS NOT NULL
 THEN RAISE EXCEPTION 'STOP:B02_G5_ONE_SHOT_ALREADY_INSTALLED'; END IF;
END $$;

CREATE TABLE public.b02_g5_operational_approval_uses (
 approval_id varchar(128) PRIMARY KEY,
 release_id varchar(128) NOT NULL UNIQUE,
 assigned_txid text NOT NULL UNIQUE,
 decision_document_sha256 char(64) NOT NULL
   CHECK (decision_document_sha256 ~ '^[0-9a-f]{64}$'),
 operator_sha256 char(64) NOT NULL
   CHECK (operator_sha256 ~ '^[0-9a-f]{64}$'),
 writer_name name NOT NULL,
 database_name name NOT NULL,
 reserved_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
 CONSTRAINT ck_b02_g5_one_shot_ids CHECK (
   length(approval_id) BETWEEN 1 AND 128 AND length(release_id) BETWEEN 1 AND 128),
 CONSTRAINT ck_b02_g5_one_shot_txid CHECK (assigned_txid ~ '^[1-9][0-9]*$')
);
-- Fail closed on direct INSERT, including default privilege grants.
-- Reserve only through the narrowly scoped SECURITY DEFINER function below.
REVOKE ALL ON public.b02_g5_operational_approval_uses FROM PUBLIC;
REVOKE ALL ON public.b02_g5_operational_approval_uses FROM solveris_b02_writer;
GRANT SELECT ON public.b02_g5_operational_approval_uses TO solveris_b02_writer;

CREATE FUNCTION public.b02_g5_reserve_operational_decision(
 p_approval varchar(128), p_release varchar(128),
 p_operator_sha char(64), p_decision_sha char(64))
-- Function owner must be the separately authorised installer solveris_test;
-- SQL role writer has SELECT but no direct INSERT on the reservation relation.
RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,pg_temp AS $fn$
DECLARE recorded text;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
 OR session_user<>'solveris_b02_writer' OR current_user<>'solveris_test'
 OR current_setting('transaction_isolation')<>'read committed'
 OR public.b02g5_native_profile()<>'REAL_PROFILE_COMPILED_APPROVED_ROOTS'
 THEN RAISE EXCEPTION 'G5_ONESHOT_PROTECTED_WRITER_ONLY'; END IF;
 IF p_approval IS NULL OR p_release IS NULL OR p_operator_sha IS NULL OR p_decision_sha IS NULL
 OR length(p_approval)=0 OR length(p_release)=0
 THEN RAISE EXCEPTION 'G5_ONESHOT_BINDING_INCOMPLETE'; END IF;
 recorded:=pg_current_xact_id()::text;
 -- A unique-index conflict between 2 transactions waits for the first commit/rollback.
 -- No ON CONFLICT/UPSERT and no autonomous reservation commit.
 INSERT INTO public.b02_g5_operational_approval_uses
  (approval_id,release_id,assigned_txid,operator_sha256,
   decision_document_sha256,writer_name,database_name)
 VALUES(p_approval,p_release,recorded,p_operator_sha,p_decision_sha,
        session_user,current_database());
 RETURN recorded;
END;
$fn$;
REVOKE ALL ON FUNCTION public.b02_g5_reserve_operational_decision(varchar,varchar,char,char) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02_g5_reserve_operational_decision(varchar,varchar,char,char) TO solveris_b02_writer;

CREATE FUNCTION public.b02_g5_assert_one_shot() RETURNS jsonb
LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE r public.b02_g5_operational_approval_uses%ROWTYPE;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test'
 OR session_user<>'solveris_b02_writer' OR current_user<>session_user
 OR current_setting('transaction_isolation')<>'read committed'
 OR public.b02g5_native_profile()<>'REAL_PROFILE_COMPILED_APPROVED_ROOTS'
 THEN RAISE EXCEPTION 'G5_ONESHOT_RESTRICTED_PRECOMMIT'; END IF;
 SELECT * INTO STRICT r FROM public.b02_g5_operational_approval_uses
 WHERE assigned_txid=pg_current_xact_id()::text;
 IF r.writer_name<>session_user OR r.database_name<>current_database()
 OR r.assigned_txid<>pg_current_xact_id()::text
 THEN RAISE EXCEPTION 'G5_ONESHOT_TX_IDENTITY_MISMATCH'; END IF;
 RETURN jsonb_build_object('schema','B02_G5_ONE_SHOT_REAL_V1',
   'approval_id',r.approval_id,'release_id',r.release_id,
   'assigned_txid',r.assigned_txid,
   'operator_sha256',trim(r.operator_sha256),
   'decision_document_sha256',trim(r.decision_document_sha256));
EXCEPTION WHEN no_data_found THEN
 RAISE EXCEPTION 'G5_ONESHOT_RESERVATION_REQUIRED';
END;
$fn$;
REVOKE ALL ON FUNCTION public.b02_g5_assert_one_shot() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.b02_g5_assert_one_shot() TO solveris_b02_writer;

CREATE OR REPLACE FUNCTION public.b02g5_capability_manifest() RETURNS text
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE b public.acquisition_mode_bindings%ROWTYPE; p public.policy_versions%ROWTYPE;
 r public.noncredential_acquisition_receipts%ROWTYPE; v public.noncredential_sanitization_verifications%ROWTYPE;
 e public.acquisition_executions%ROWTYPE; a public.normative_artifacts%ROWTYPE;
 avr public.artifact_verification_records%ROWTYPE; units jsonb:='[]'; docs jsonb:='[]';
 binding jsonb; release jsonb; grants jsonb; authority jsonb:='{}'; values_hash jsonb; t text;
 cnt integer; manifest jsonb; release_scope jsonb; release_mode text; reservation jsonb;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer' OR current_user<>session_user OR current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'G5_CAPABILITY_RESTRICTED_WRITER_REQUIRED'; END IF;
 reservation:=public.b02_g5_assert_one_shot();
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
 IF (manifest->'server'->>'txid') IS DISTINCT FROM reservation->>'assigned_txid' THEN RAISE EXCEPTION 'G5_ONESHOT_MANIFEST_TX_MISMATCH'; END IF;
 RETURN public.b02_canonical_json(manifest || jsonb_build_object('g5_one_shot',reservation));
END;
$$;

CREATE OR REPLACE FUNCTION public.b02g5_precommit_validate() RETURNS void
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE t text; b public.acquisition_mode_bindings%ROWTYPE;
BEGIN
 IF current_database()<>'solveris_b02_r4g_test' OR session_user<>'solveris_b02_writer' OR current_user<>session_user OR current_setting('transaction_isolation')<>'read committed' THEN RAISE EXCEPTION 'G5_PRECOMMIT_RESTRICTED_IDENTITY_REQUIRED'; END IF;
 IF NOT EXISTS(SELECT 1 FROM public.acquisition_mode_bindings WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) AND NOT EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) AND NOT EXISTS(SELECT 1 FROM public.noncredential_sanitization_verifications WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb) THEN RETURN; END IF;
 PERFORM public.b02_g5_assert_one_shot();
 FOREACH t IN ARRAY ARRAY['policy_versions','policy_decisions','policy_activations','policy_activation_executions','policy_activation_generations','policy_activation_outbox_events','bootstrap_authority_records'] LOOP
  IF NOT EXISTS(SELECT 1 FROM pg_catalog.pg_locks WHERE pid=pg_backend_pid() AND relation=to_regclass('public.'||t) AND granted AND mode IN ('ShareLock','ShareRowExclusiveLock','ExclusiveLock','AccessExclusiveLock')) THEN RAISE EXCEPTION 'G5_AUTHORITY_LOCK_NOT_HELD'; END IF;
 END LOOP;
 IF EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts r WHERE r.assigned_txid=pg_current_xact_id()::text AND r.provenance->'synthetic_only'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM public.acquisition_mode_bindings q WHERE q.mode_binding_id=r.mode_binding_id AND q.record_hash=r.mode_binding_hash AND q.assigned_txid=r.assigned_txid AND q.provenance->'synthetic_only'='false'::jsonb)) OR EXISTS(SELECT 1 FROM public.noncredential_sanitization_verifications v WHERE v.assigned_txid=pg_current_xact_id()::text AND v.provenance->'synthetic_only'='false'::jsonb AND NOT EXISTS(SELECT 1 FROM public.noncredential_acquisition_receipts r JOIN public.acquisition_mode_bindings q ON q.mode_binding_id=r.mode_binding_id AND q.record_hash=r.mode_binding_hash AND q.assigned_txid=r.assigned_txid WHERE r.receipt_id=v.receipt_id AND r.receipt_hash=v.receipt_hash AND r.assigned_txid=v.assigned_txid AND r.provenance->'synthetic_only'='false'::jsonb AND q.provenance->'synthetic_only'='false'::jsonb)) THEN RAISE EXCEPTION 'G5_PRECOMMIT_EXACT_PREDECESSOR_REQUIRED'; END IF;
 PERFORM public.b02g5_assert_transaction_capability();
 FOR b IN SELECT * FROM public.acquisition_mode_bindings WHERE assigned_txid=pg_current_xact_id()::text AND provenance->'synthetic_only'='false'::jsonb LOOP
  PERFORM public.b02_require_complete_unit(b.acquisition_execution_id,b.attempt_number,NULL,true);
 END LOOP;
END;
$$;

-- Two documents + reservation enforced together, deferred so stage_completion
-- can still issue SET CONSTRAINTS ALL IMMEDIATE before the signature exists.
CREATE FUNCTION public.b02_g5_assert_reserved_two_units() RETURNS trigger
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE n integer;
BEGIN
 PERFORM public.b02_g5_assert_one_shot();
 SELECT count(DISTINCT acquisition_execution_id) INTO n
 FROM public.acquisition_mode_bindings
 WHERE assigned_txid=pg_current_xact_id()::text
   AND provenance->'synthetic_only'='false'::jsonb;
 IF n<>2 THEN RAISE EXCEPTION 'G5_ONESHOT_TWO_DOCUMENTS_REQUIRED'; END IF;
 RETURN NULL;
END;
$fn$;
REVOKE ALL ON FUNCTION public.b02_g5_assert_reserved_two_units() FROM PUBLIC;
CREATE CONSTRAINT TRIGGER trg_b02_g5_one_shot_requires_two_units
AFTER INSERT ON public.b02_g5_operational_approval_uses
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.b02_g5_assert_reserved_two_units();

DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('0065_b02_g5_one_shot_real');
COMMIT;
