"""PolicyActivationExecution atomic generation/outbox: review candidate only.
No grants, policy data, backfill, historical edits or production side effects.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision='0063_adr020_policy_activation_atomicity'
down_revision='0062_adr020_noncredential_acquisition'
branch_labels=None
depends_on=None

def upgrade():
    if op.get_bind().dialect.name!='postgresql':raise RuntimeError('POLICY_POSTGRESQL_REQUIRED')
    for table in ('policy_activation_executions','policy_activations'):
        op.add_column(table,sa.Column('b02_policy_txid',sa.Text(),nullable=True))
        op.add_column(table,sa.Column('policy_decision_record_hash',sa.String(64),nullable=True))
    op.add_column('policy_activations',sa.Column('policy_activation_execution_record_hash',sa.String(64),nullable=True))
    op.create_unique_constraint('uq_b02p_decision_exact','policy_decisions',['decision_id', 'record_hash', 'policy_id', 'policy_version', 'policy_hash'])
    op.create_unique_constraint('uq_b02p_exec_exact','policy_activation_executions',['policy_activation_execution_id', 'record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'])
    op.create_unique_constraint('uq_b02p_activation_exact','policy_activations',['policy_activation_id', 'record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'])
    op.execute('ALTER TABLE policy_activation_executions ADD CONSTRAINT fk_b02p_exec_decision FOREIGN KEY (policy_decision_id,policy_decision_record_hash,policy_id,policy_version,policy_hash) REFERENCES policy_decisions (decision_id,record_hash,policy_id,policy_version,policy_hash) ON DELETE RESTRICT NOT VALID')
    op.execute('ALTER TABLE policy_activations ADD CONSTRAINT fk_b02p_activation_exec FOREIGN KEY (policy_activation_execution_id,policy_activation_execution_record_hash,policy_decision_id,policy_decision_record_hash,policy_id,policy_version,policy_hash) REFERENCES policy_activation_executions (policy_activation_execution_id,record_hash,policy_decision_id,policy_decision_record_hash,policy_id,policy_version,policy_hash) ON DELETE RESTRICT NOT VALID')
    op.create_table('policy_activation_generations',
        sa.Column('policy_activation_generation_id',sa.String(64),nullable=False,primary_key=True),
        sa.Column('policy_activation_id',sa.String(64),nullable=False),
        sa.Column('policy_activation_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_activation_execution_id',sa.String(64),nullable=False),
        sa.Column('policy_activation_execution_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_decision_id',sa.String(64),nullable=False),
        sa.Column('policy_decision_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_id',sa.String(64),nullable=False),
        sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('policy_hash',sa.String(64),nullable=False),
        sa.Column('schema_version',sa.Integer(),nullable=False),
        sa.Column('domain',sa.String(255),nullable=False),
        sa.Column('modality',sa.String(64),nullable=False),
        sa.Column('scope_descriptor',postgresql.JSONB(),nullable=False),
        sa.Column('scope_hash',sa.String(64),nullable=False),
        sa.Column('operational_interval',postgresql.JSONB(),nullable=False),
        sa.Column('completion_manifest',postgresql.JSONB(),nullable=False),
        sa.Column('is_complete',sa.Boolean(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('provenance',postgresql.JSONB(),nullable=False),
        sa.Column('assigned_txid',sa.Text(),nullable=False),
        sa.Column('record_hash',sa.String(64),nullable=False),
        sa.UniqueConstraint('policy_activation_generation_id','record_hash',name='uq_b02p_0_0'),
        sa.UniqueConstraint('policy_activation_execution_id',name='uq_b02p_0_1'),
        sa.UniqueConstraint('policy_activation_id',name='uq_b02p_0_2'),
        sa.UniqueConstraint('record_hash',name='uq_b02p_0_3'),
        sa.UniqueConstraint('policy_activation_generation_id','policy_activation_id','policy_activation_record_hash',name='uq_b02p_0_4'),
        sa.UniqueConstraint('policy_activation_generation_id','record_hash','policy_activation_id','policy_activation_record_hash','policy_activation_execution_id','policy_activation_execution_record_hash','policy_decision_id','policy_decision_record_hash','policy_id','policy_version','policy_hash',name='uq_b02p_0_5'),
        sa.ForeignKeyConstraint(['policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_executions.policy_activation_execution_id', 'policy_activation_executions.record_hash', 'policy_activation_executions.policy_decision_id', 'policy_activation_executions.policy_decision_record_hash', 'policy_activation_executions.policy_id', 'policy_activation_executions.policy_version', 'policy_activation_executions.policy_hash'],name='fk_b02p_0_0',ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activations.policy_activation_id', 'policy_activations.record_hash', 'policy_activations.policy_activation_execution_id', 'policy_activations.policy_activation_execution_record_hash', 'policy_activations.policy_decision_id', 'policy_activations.policy_decision_record_hash', 'policy_activations.policy_id', 'policy_activations.policy_version', 'policy_activations.policy_hash'],name='fk_b02p_0_1',ondelete='RESTRICT'),
        sa.CheckConstraint('schema_version=1',name='ck_b02p_0_0'),
        sa.CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'",name='ck_b02p_0_1'),
        sa.CheckConstraint('policy_version>0',name='ck_b02p_0_2'),
        sa.CheckConstraint("policy_activation_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_3'),
        sa.CheckConstraint("policy_activation_execution_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_4'),
        sa.CheckConstraint("policy_decision_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_5'),
        sa.CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_6'),
        sa.CheckConstraint("scope_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_7'),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_0_8'),
        sa.CheckConstraint('is_complete',name='ck_b02p_0_9'),
        sa.CheckConstraint("jsonb_typeof(completion_manifest)='object'",name='ck_b02p_0_10'),
        sa.CheckConstraint("jsonb_typeof(provenance)='object'",name='ck_b02p_0_11'),
    )
    op.create_table('policy_activation_outbox_events',
        sa.Column('policy_activation_outbox_event_id',sa.String(64),nullable=False,primary_key=True),
        sa.Column('policy_activation_generation_id',sa.String(64),nullable=False),
        sa.Column('policy_activation_generation_hash',sa.String(64),nullable=False),
        sa.Column('policy_activation_id',sa.String(64),nullable=False),
        sa.Column('policy_activation_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_activation_execution_id',sa.String(64),nullable=False),
        sa.Column('policy_activation_execution_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_decision_id',sa.String(64),nullable=False),
        sa.Column('policy_decision_record_hash',sa.String(64),nullable=False),
        sa.Column('policy_id',sa.String(64),nullable=False),
        sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('policy_hash',sa.String(64),nullable=False),
        sa.Column('schema_version',sa.Integer(),nullable=False),
        sa.Column('event_type',sa.String(64),nullable=False),
        sa.Column('payload',postgresql.JSONB(),nullable=False),
        sa.Column('payload_hash',sa.String(64),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('provenance',postgresql.JSONB(),nullable=False),
        sa.Column('assigned_txid',sa.Text(),nullable=False),
        sa.Column('record_hash',sa.String(64),nullable=False),
        sa.UniqueConstraint('policy_activation_outbox_event_id','record_hash',name='uq_b02p_1_0'),
        sa.UniqueConstraint('policy_activation_execution_id',name='uq_b02p_1_1'),
        sa.UniqueConstraint('policy_activation_id',name='uq_b02p_1_2'),
        sa.UniqueConstraint('policy_activation_generation_id',name='uq_b02p_1_3'),
        sa.UniqueConstraint('record_hash',name='uq_b02p_1_4'),
        sa.ForeignKeyConstraint(['policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_executions.policy_activation_execution_id', 'policy_activation_executions.record_hash', 'policy_activation_executions.policy_decision_id', 'policy_activation_executions.policy_decision_record_hash', 'policy_activation_executions.policy_id', 'policy_activation_executions.policy_version', 'policy_activation_executions.policy_hash'],name='fk_b02p_1_0',ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activations.policy_activation_id', 'policy_activations.record_hash', 'policy_activations.policy_activation_execution_id', 'policy_activations.policy_activation_execution_record_hash', 'policy_activations.policy_decision_id', 'policy_activations.policy_decision_record_hash', 'policy_activations.policy_id', 'policy_activations.policy_version', 'policy_activations.policy_hash'],name='fk_b02p_1_1',ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['policy_activation_generation_id', 'policy_activation_generation_hash', 'policy_activation_id', 'policy_activation_record_hash', 'policy_activation_execution_id', 'policy_activation_execution_record_hash', 'policy_decision_id', 'policy_decision_record_hash', 'policy_id', 'policy_version', 'policy_hash'],['policy_activation_generations.policy_activation_generation_id', 'policy_activation_generations.record_hash', 'policy_activation_generations.policy_activation_id', 'policy_activation_generations.policy_activation_record_hash', 'policy_activation_generations.policy_activation_execution_id', 'policy_activation_generations.policy_activation_execution_record_hash', 'policy_activation_generations.policy_decision_id', 'policy_activation_generations.policy_decision_record_hash', 'policy_activation_generations.policy_id', 'policy_activation_generations.policy_version', 'policy_activation_generations.policy_hash'],name='fk_b02p_1_2',ondelete='RESTRICT'),
        sa.CheckConstraint('schema_version=1',name='ck_b02p_1_0'),
        sa.CheckConstraint("assigned_txid ~ '^[1-9][0-9]*$'",name='ck_b02p_1_1'),
        sa.CheckConstraint('policy_version>0',name='ck_b02p_1_2'),
        sa.CheckConstraint("policy_activation_generation_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_3'),
        sa.CheckConstraint("policy_activation_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_4'),
        sa.CheckConstraint("policy_activation_execution_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_5'),
        sa.CheckConstraint("policy_decision_record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_6'),
        sa.CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_7'),
        sa.CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_8'),
        sa.CheckConstraint("record_hash ~ '^[0-9a-f]{64}$'",name='ck_b02p_1_9'),
        sa.CheckConstraint("event_type='policy_activation_completed'",name='ck_b02p_1_10'),
        sa.CheckConstraint("jsonb_typeof(payload)='object'",name='ck_b02p_1_11'),
        sa.CheckConstraint("jsonb_typeof(provenance)='object'",name='ck_b02p_1_12'),
    )
    op.execute('ALTER TABLE policy_activations ADD CONSTRAINT fk_b02p_activation_generation FOREIGN KEY (activation_generation_id,policy_activation_id,record_hash) REFERENCES policy_activation_generations (policy_activation_generation_id,policy_activation_id,policy_activation_record_hash) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED NOT VALID')
    op.execute(r'''
-- All functions are SECURITY INVOKER. Privileges are a separate reviewed gate.
CREATE FUNCTION b02p_check_authority(e public.policy_activation_executions) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,public SET timezone='UTC' AS $$
DECLARE p public.policy_versions%ROWTYPE; d public.policy_decisions%ROWTYPE;
 b public.bootstrap_authority_records%ROWTYPE; superior public.policy_activations%ROWTYPE;
 envelope public.policy_activations%ROWTYPE; pv public.policy_versions%ROWTYPE;
BEGIN
 SELECT * INTO p FROM public.policy_versions WHERE policy_id=e.policy_id AND policy_version=e.policy_version AND policy_hash=e.policy_hash AND policy_type=e.policy_type;
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_EXACT_POLICY_REQUIRED'; END IF;
 SELECT * INTO d FROM public.policy_decisions WHERE decision_id=e.policy_decision_id AND record_hash=e.policy_decision_record_hash AND policy_id=e.policy_id AND policy_version=e.policy_version AND policy_hash=e.policy_hash AND policy_type=e.policy_type AND decision_event='ratificada' AND institutional_role='autoridade_constitucional_final';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_EXACT_RATIFIED_DECISION_REQUIRED'; END IF;
 IF e.actor_or_worker=d.actor OR NOT coalesce(p.roles->'technical_policy_activation_writers' ? e.actor_or_worker,false)
 OR NOT coalesce(p.permitted_execution_modes ? e.execution_mode,false)
 OR NOT coalesce(p.permitted_authorization_classes ? e.authorization_class,false)
 THEN RAISE EXCEPTION 'B02P_TECHNICAL_AUTHORITY_OR_SEGREGATION_REQUIRED'; END IF;
 IF e.started_at IS NULL OR e.finished_at IS NULL OR e.started_at<d.timestamp OR e.finished_at<e.started_at OR e.finished_at>statement_timestamp()
 THEN RAISE EXCEPTION 'B02P_EXECUTION_CHRONOLOGY_INVALID'; END IF;
 IF jsonb_typeof(e.structured_result) IS DISTINCT FROM 'object'
 OR e.structured_result->>'schema' IS DISTINCT FROM 'ADR020_POLICY_ACTIVATION_UNIT_V1'
 OR NOT (e.structured_result ?& ARRAY['policy_activation_id','policy_activation_generation_id','policy_activation_outbox_event_id','domain','modality','scope_hash'])
 OR e.structured_result->>'domain' IS DISTINCT FROM p.domain
 OR e.structured_result->>'scope_hash' IS DISTINCT FROM public.b02_json_hash(p.scope)
 OR NOT coalesce(p.modalities ? (e.structured_result->>'modality'),false)
 THEN RAISE EXCEPTION 'B02P_EXACT_COMPLETION_MANIFEST_REQUIRED'; END IF;
 IF coalesce(e.structured_result->>'policy_activation_id','') !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$'
 OR coalesce(e.structured_result->>'policy_activation_generation_id','') !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$'
 OR coalesce(e.structured_result->>'policy_activation_outbox_event_id','') !~ '^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$'
 THEN RAISE EXCEPTION 'B02P_EXACT_UNIT_IDS_REQUIRED'; END IF;
 IF e.authorization_basis_type='bootstrap_authority_record' THEN
  SELECT * INTO b FROM public.bootstrap_authority_records WHERE bootstrap_authority_record_id=e.bootstrap_authority_record_id AND record_hash=e.bootstrap_authority_record_hash AND policy_id=e.policy_id AND policy_version=e.policy_version AND policy_hash=e.policy_hash AND policy_type='activation_authority' AND validity='valida' AND independent_audit_result='favoravel';
  IF NOT FOUND OR e.policy_type<>'activation_authority' OR e.execution_mode<>'manual' OR e.authorization_class<>'constitucional_reservada' OR b.scope IS DISTINCT FROM p.scope OR b.domain IS DISTINCT FROM p.domain OR b.timestamp>e.started_at
  THEN RAISE EXCEPTION 'B02P_EXACT_MANUAL_BOOTSTRAP_REQUIRED'; END IF;
 ELSE
  IF e.authorization_basis_type<>'active_policy_chain' THEN RAISE EXCEPTION 'B02P_AUTHORITY_BASIS_INVALID'; END IF;
  SELECT a.* INTO superior FROM public.policy_activations a JOIN public.policy_versions v USING(policy_id,policy_version,policy_hash)
   WHERE a.policy_activation_id=e.activation_authority_policy_activation_id AND a.policy_id=e.activation_authority_policy_id AND a.policy_version=e.activation_authority_policy_version AND a.policy_hash=e.activation_authority_policy_hash AND a.policy_type='activation_authority' AND v.policy_type='activation_authority' AND a.state='activa' AND a.domain=p.domain AND a.modality=e.structured_result->>'modality' AND v.scope=p.scope;
  IF NOT FOUND THEN RAISE EXCEPTION 'B02P_EXACT_ACTIVE_SUPERIOR_REQUIRED'; END IF;
  SELECT * INTO pv FROM public.policy_versions WHERE policy_id=superior.policy_id AND policy_version=superior.policy_version AND policy_hash=superior.policy_hash;
  IF NOT coalesce(pv.roles->'technical_policy_activation_writers' ? e.actor_or_worker,false)
  OR NOT coalesce(pv.permitted_execution_modes ? e.execution_mode,false) OR NOT coalesce(pv.permitted_authorization_classes ? e.authorization_class,false) THEN RAISE EXCEPTION 'B02P_SUPERIOR_DELEGATION_RESTRICTED'; END IF;
  IF e.policy_type='automation_envelope' AND NOT coalesce(p.exact_references @> jsonb_build_array(jsonb_build_object('activation_authority_policy_id',superior.policy_id,'activation_authority_policy_version',superior.policy_version,'activation_authority_policy_hash',superior.policy_hash,'activation_authority_policy_activation_id',superior.policy_activation_id)),false) THEN RAISE EXCEPTION 'B02P_ENVELOPE_SUPERIOR_REFERENCE_REQUIRED'; END IF;
  IF superior.activated_at>e.started_at OR NOT (superior.operational_interval ?& ARRAY['from','until'])
  OR superior.operational_interval->>'from' IS NULL OR superior.operational_interval->>'until' IS NULL
  OR statement_timestamp()<(superior.operational_interval->>'from')::timestamptz OR statement_timestamp()>=(superior.operational_interval->>'until')::timestamptz
  THEN RAISE EXCEPTION 'B02P_SUPERIOR_INTERVAL_INVALID'; END IF;
  PERFORM public.b02p_require_complete(superior.policy_activation_execution_id,false);
 END IF;
 IF e.execution_mode='automatico' THEN
  SELECT a.* INTO envelope FROM public.policy_activations a JOIN public.policy_versions v USING(policy_id,policy_version,policy_hash)
   WHERE a.policy_activation_id=e.automation_envelope_activation_id AND a.policy_id=e.automation_envelope_id AND a.policy_version=e.automation_envelope_version AND a.policy_hash=e.automation_envelope_hash AND a.policy_type='automation_envelope' AND v.policy_type='automation_envelope' AND a.state='activa' AND a.domain=p.domain AND a.modality=e.structured_result->>'modality' AND v.scope=p.scope;
  IF NOT FOUND OR e.authorization_class<>'automatica_delegada' THEN RAISE EXCEPTION 'B02P_EXACT_AUTOMATION_ENVELOPE_REQUIRED'; END IF;
  SELECT * INTO pv FROM public.policy_versions WHERE policy_id=envelope.policy_id AND policy_version=envelope.policy_version AND policy_hash=envelope.policy_hash;
  IF NOT coalesce(pv.roles->'technical_policy_activation_writers' ? e.actor_or_worker,false) OR NOT coalesce(pv.permitted_execution_modes ? e.execution_mode,false) OR NOT coalesce(pv.permitted_authorization_classes ? e.authorization_class,false)
  OR NOT coalesce(pv.exact_references @> jsonb_build_array(jsonb_build_object('activation_authority_policy_id',e.activation_authority_policy_id,'activation_authority_policy_version',e.activation_authority_policy_version,'activation_authority_policy_hash',e.activation_authority_policy_hash,'activation_authority_policy_activation_id',e.activation_authority_policy_activation_id)),false)
  THEN RAISE EXCEPTION 'B02P_ENVELOPE_DELEGATION_RESTRICTED'; END IF;
  IF envelope.activated_at>e.started_at OR NOT (envelope.operational_interval ?& ARRAY['from','until'])
  OR envelope.operational_interval->>'from' IS NULL OR envelope.operational_interval->>'until' IS NULL
  OR statement_timestamp()<(envelope.operational_interval->>'from')::timestamptz OR statement_timestamp()>=(envelope.operational_interval->>'until')::timestamptz
  THEN RAISE EXCEPTION 'B02P_ENVELOPE_INTERVAL_INVALID'; END IF;
  PERFORM public.b02p_require_complete(envelope.policy_activation_execution_id,false);
 END IF;
END $$;

CREATE FUNCTION b02p_outbox_payload(g public.policy_activation_generations) RETURNS jsonb
LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,public AS $$
 SELECT jsonb_build_object('schema','ADR020_POLICY_ACTIVATION_OUTBOX_V1',
 'policy_activation_execution_id',(g).policy_activation_execution_id,'policy_activation_execution_record_hash',(g).policy_activation_execution_record_hash,
 'policy_activation_id',(g).policy_activation_id,'policy_activation_record_hash',(g).policy_activation_record_hash,
 'policy_activation_generation_id',(g).policy_activation_generation_id,'policy_activation_generation_hash',(g).record_hash,
 'policy_id',(g).policy_id,'policy_version',(g).policy_version,'policy_hash',(g).policy_hash,
 'domain',(g).domain,'modality',(g).modality,'scope_hash',(g).scope_hash)
$$;

CREATE FUNCTION b02p_stamp_and_validate() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public SET timezone='UTC' AS $$
DECLARE e public.policy_activation_executions%ROWTYPE; a public.policy_activations%ROWTYPE;
 g public.policy_activation_generations%ROWTYPE; p public.policy_versions%ROWTYPE;
 superior public.policy_activations%ROWTYPE; expected text; expected_payload jsonb; xid_value text:=pg_current_xact_id()::text;
BEGIN
 IF TG_TABLE_NAME IN ('policy_activation_executions','policy_activations') THEN
  IF NEW.b02_policy_txid IS NOT NULL THEN RAISE EXCEPTION 'B02P_SERVER_TXID_ONLY'; END IF;
  NEW.b02_policy_txid:=xid_value;
 ELSE
  IF NEW.assigned_txid IS NOT NULL THEN RAISE EXCEPTION 'B02P_SERVER_TXID_ONLY'; END IF;
  NEW.assigned_txid:=xid_value;
 END IF;
 IF TG_TABLE_NAME='policy_activation_executions' THEN
  IF NEW.actor_or_worker IS DISTINCT FROM session_user OR current_user IS DISTINCT FROM session_user THEN RAISE EXCEPTION 'B02P_DIRECT_TECHNICAL_IDENTITY_REQUIRED'; END IF;
  IF NEW.policy_decision_record_hash IS NULL THEN RAISE EXCEPTION 'B02P_EXACT_DECISION_HASH_REQUIRED'; END IF;
  IF NEW.state='concluida' THEN PERFORM public.b02p_check_authority(NEW); END IF;
 ELSIF TG_TABLE_NAME='policy_activations' THEN
  SELECT * INTO e FROM public.policy_activation_executions WHERE policy_activation_execution_id=NEW.policy_activation_execution_id AND record_hash=NEW.policy_activation_execution_record_hash AND policy_decision_id=NEW.policy_decision_id AND policy_decision_record_hash=NEW.policy_decision_record_hash AND policy_id=NEW.policy_id AND policy_version=NEW.policy_version AND policy_hash=NEW.policy_hash AND policy_type=NEW.policy_type AND state='concluida';
  IF NOT FOUND OR e.b02_policy_txid IS DISTINCT FROM xid_value THEN RAISE EXCEPTION 'B02P_EXACT_CURRENT_COMPLETED_EXECUTION_REQUIRED'; END IF;
  SELECT * INTO p FROM public.policy_versions WHERE policy_id=e.policy_id AND policy_version=e.policy_version AND policy_hash=e.policy_hash;
  IF NEW.policy_activation_id IS DISTINCT FROM e.structured_result->>'policy_activation_id' OR NEW.activation_generation_id IS DISTINCT FROM e.structured_result->>'policy_activation_generation_id'
  OR NEW.domain IS DISTINCT FROM p.domain OR NEW.modality IS DISTINCT FROM e.structured_result->>'modality'
  OR NEW.technical_actor IS DISTINCT FROM e.actor_or_worker OR NEW.technical_actor IS DISTINCT FROM session_user
  OR NEW.activated_at<e.finished_at OR NEW.activated_at>statement_timestamp()
  OR NOT (NEW.operational_interval ?& ARRAY['from','until']) OR NEW.operational_interval->>'from' IS NULL OR NEW.operational_interval->>'until' IS NULL
  OR (NEW.operational_interval->>'from')::timestamptz>NEW.activated_at OR (NEW.operational_interval->>'until')::timestamptz<=statement_timestamp()
  THEN RAISE EXCEPTION 'B02P_ACTIVATION_IDENTITY_OR_INTERVAL_INVALID'; END IF;
  IF e.authorization_basis_type='active_policy_chain' THEN
   SELECT * INTO superior FROM public.policy_activations WHERE policy_activation_id=e.activation_authority_policy_activation_id;
   IF (NEW.operational_interval->>'from')::timestamptz<(superior.operational_interval->>'from')::timestamptz OR (NEW.operational_interval->>'until')::timestamptz>(superior.operational_interval->>'until')::timestamptz THEN RAISE EXCEPTION 'B02P_AUTHORITY_INTERVAL_EXPANSION'; END IF;
  END IF;
  IF e.execution_mode='automatico' THEN
   SELECT * INTO superior FROM public.policy_activations WHERE policy_activation_id=e.automation_envelope_activation_id;
   IF (NEW.operational_interval->>'from')::timestamptz<(superior.operational_interval->>'from')::timestamptz OR (NEW.operational_interval->>'until')::timestamptz>(superior.operational_interval->>'until')::timestamptz THEN RAISE EXCEPTION 'B02P_ENVELOPE_INTERVAL_EXPANSION'; END IF;
  END IF;
 ELSIF TG_TABLE_NAME='policy_activation_generations' THEN
  SELECT * INTO a FROM public.policy_activations WHERE policy_activation_id=NEW.policy_activation_id AND record_hash=NEW.policy_activation_record_hash AND policy_activation_execution_id=NEW.policy_activation_execution_id AND policy_activation_execution_record_hash=NEW.policy_activation_execution_record_hash;
  IF NOT FOUND OR a.b02_policy_txid IS DISTINCT FROM xid_value THEN RAISE EXCEPTION 'B02P_EXACT_CURRENT_ACTIVATION_REQUIRED'; END IF;
  SELECT * INTO e FROM public.policy_activation_executions WHERE policy_activation_execution_id=a.policy_activation_execution_id;
  SELECT * INTO p FROM public.policy_versions WHERE policy_id=a.policy_id AND policy_version=a.policy_version AND policy_hash=a.policy_hash;
  IF NEW.policy_activation_generation_id IS DISTINCT FROM a.activation_generation_id OR NEW.completion_manifest IS DISTINCT FROM e.structured_result
  OR NEW.domain IS DISTINCT FROM a.domain OR NEW.modality IS DISTINCT FROM a.modality OR NEW.operational_interval IS DISTINCT FROM a.operational_interval
  OR NEW.scope_descriptor IS DISTINCT FROM p.scope OR NEW.scope_hash IS DISTINCT FROM public.b02_json_hash(p.scope)
  OR NEW.is_complete IS DISTINCT FROM true OR NEW.created_at<a.activated_at OR NEW.created_at>statement_timestamp()
  THEN RAISE EXCEPTION 'B02P_COMPLETE_EXACT_GENERATION_REQUIRED'; END IF;
 ELSE
  SELECT * INTO g FROM public.policy_activation_generations WHERE policy_activation_generation_id=NEW.policy_activation_generation_id AND record_hash=NEW.policy_activation_generation_hash;
  IF NOT FOUND OR g.assigned_txid IS DISTINCT FROM xid_value OR NEW.policy_activation_outbox_event_id IS DISTINCT FROM g.completion_manifest->>'policy_activation_outbox_event_id'
  OR NEW.created_at<g.created_at OR NEW.created_at>statement_timestamp()
  THEN RAISE EXCEPTION 'B02P_EXACT_CURRENT_GENERATION_REQUIRED'; END IF;
  expected_payload:=public.b02p_outbox_payload(g);
  IF NEW.payload IS NOT NULL AND NEW.payload IS DISTINCT FROM expected_payload THEN RAISE EXCEPTION 'B02P_OUTBOX_PAYLOAD_DIVERGENCE'; END IF;
  NEW.payload:=expected_payload;
  expected:=public.b02_json_hash(expected_payload);
  IF NEW.payload_hash IS NOT NULL AND NEW.payload_hash IS DISTINCT FROM expected THEN RAISE EXCEPTION 'B02P_OUTBOX_PAYLOAD_HASH_DIVERGENCE'; END IF;
  NEW.payload_hash:=expected;
 END IF;
 IF jsonb_typeof(NEW.provenance) IS DISTINCT FROM 'object' THEN RAISE EXCEPTION 'B02P_PROVENANCE_REQUIRED'; END IF;
 expected:=public.b02_json_hash(to_jsonb(NEW)-'record_hash');
 IF NEW.record_hash IS NOT NULL AND NEW.record_hash IS DISTINCT FROM expected THEN RAISE EXCEPTION 'B02P_RECORD_HASH_DIVERGENCE'; END IF;
 NEW.record_hash:=expected;
 RETURN NEW;
END $$;

CREATE FUNCTION b02p_require_complete(execution_id text,current_transaction_required boolean) RETURNS void
LANGUAGE plpgsql SET search_path=pg_catalog,public SET timezone='UTC' AS $$
DECLARE e public.policy_activation_executions%ROWTYPE; a public.policy_activations%ROWTYPE;
 g public.policy_activation_generations%ROWTYPE; o public.policy_activation_outbox_events%ROWTYPE;
BEGIN
 SELECT * INTO e FROM public.policy_activation_executions WHERE policy_activation_execution_id=execution_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_EXECUTION_MISSING'; END IF;
 IF e.state<>'concluida' THEN
  IF EXISTS(SELECT 1 FROM public.policy_activations WHERE policy_activation_execution_id=execution_id)
  OR EXISTS(SELECT 1 FROM public.policy_activation_generations WHERE policy_activation_execution_id=execution_id)
  OR EXISTS(SELECT 1 FROM public.policy_activation_outbox_events WHERE policy_activation_execution_id=execution_id)
  THEN RAISE EXCEPTION 'B02P_PARTIAL_EXECUTION_CANNOT_ACTIVATE'; END IF;
  RETURN;
 END IF;
 SELECT * INTO a FROM public.policy_activations WHERE policy_activation_execution_id=execution_id AND policy_activation_id=e.structured_result->>'policy_activation_id';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_ACTIVATION_MISSING'; END IF;
 SELECT * INTO g FROM public.policy_activation_generations WHERE policy_activation_execution_id=execution_id AND policy_activation_generation_id=e.structured_result->>'policy_activation_generation_id';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_GENERATION_MISSING'; END IF;
 SELECT * INTO o FROM public.policy_activation_outbox_events WHERE policy_activation_execution_id=execution_id AND policy_activation_outbox_event_id=e.structured_result->>'policy_activation_outbox_event_id';
 IF NOT FOUND THEN RAISE EXCEPTION 'B02P_OUTBOX_MISSING'; END IF;
 IF e.b02_policy_txid IS NULL OR a.b02_policy_txid IS DISTINCT FROM e.b02_policy_txid OR g.assigned_txid IS DISTINCT FROM e.b02_policy_txid OR o.assigned_txid IS DISTINCT FROM e.b02_policy_txid
 OR (current_transaction_required AND e.b02_policy_txid IS DISTINCT FROM pg_current_xact_id()::text)
 THEN RAISE EXCEPTION 'B02P_ATOMIC_TRANSACTION_DIVERGENCE'; END IF;
 IF a.policy_activation_execution_record_hash IS DISTINCT FROM e.record_hash
 OR g.policy_activation_execution_record_hash IS DISTINCT FROM e.record_hash OR o.policy_activation_execution_record_hash IS DISTINCT FROM e.record_hash
 OR a.activation_generation_id IS DISTINCT FROM g.policy_activation_generation_id OR o.policy_activation_generation_id IS DISTINCT FROM g.policy_activation_generation_id OR o.policy_activation_generation_hash IS DISTINCT FROM g.record_hash
 OR g.policy_activation_id IS DISTINCT FROM a.policy_activation_id OR o.policy_activation_id IS DISTINCT FROM a.policy_activation_id
 OR g.policy_activation_record_hash IS DISTINCT FROM a.record_hash OR o.policy_activation_record_hash IS DISTINCT FROM a.record_hash
 OR g.completion_manifest IS DISTINCT FROM e.structured_result OR o.payload IS DISTINCT FROM public.b02p_outbox_payload(g)
 THEN RAISE EXCEPTION 'B02P_ATOMIC_IDENTITY_DIVERGENCE'; END IF;
 IF e.record_hash IS DISTINCT FROM public.b02_json_hash(to_jsonb(e)-'record_hash')
 OR a.record_hash IS DISTINCT FROM public.b02_json_hash(to_jsonb(a)-'record_hash')
 OR g.record_hash IS DISTINCT FROM public.b02_json_hash(to_jsonb(g)-'record_hash')
 OR o.record_hash IS DISTINCT FROM public.b02_json_hash(to_jsonb(o)-'record_hash')
 OR o.payload_hash IS DISTINCT FROM public.b02_json_hash(o.payload)
 THEN RAISE EXCEPTION 'B02P_ATOMIC_HASH_DIVERGENCE'; END IF;
 PERFORM public.b02p_check_authority(e);
END $$;

CREATE FUNCTION b02p_deferred_complete() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public AS $$
BEGIN
 PERFORM public.b02p_require_complete(NEW.policy_activation_execution_id,true);
 RETURN NULL;
END $$;

-- B02 consumes committed policies only after checking their exact full unit.
-- No changes to the source or functions of 0062 are needed.
CREATE FUNCTION b02p_guard_consumed_policy() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public AS $$
DECLARE binding jsonb; a public.policy_activations%ROWTYPE;
BEGIN
 FOR binding IN SELECT value FROM jsonb_array_elements(jsonb_build_array(NEW.security_policy_binding,NEW.sanitization_policy_binding)) LOOP
  SELECT * INTO a FROM public.policy_activations WHERE policy_activation_id=binding->>'policy_activation_id' AND record_hash=binding->>'policy_activation_record_hash' AND policy_id=binding->>'policy_id' AND policy_version=(binding->>'policy_version')::integer AND policy_hash=binding->>'policy_hash' AND policy_type=binding->>'policy_type' AND state='activa';
  IF NOT FOUND THEN RAISE EXCEPTION 'B02P_EXACT_COMPLETE_POLICY_REQUIRED'; END IF;
  PERFORM public.b02p_require_complete(a.policy_activation_execution_id,false);
 END LOOP;
 RETURN NEW;
END $$;
''')
    for table,suffix in (('policy_activation_executions','exec'),('policy_activations','act'),('policy_activation_generations','gen'),('policy_activation_outbox_events','outbox')):
        op.execute(f"CREATE TRIGGER a_b02p_validate BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION b02p_stamp_and_validate()")
        op.execute(f"CREATE CONSTRAINT TRIGGER b02p_unit_{suffix} AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION b02p_deferred_complete()")
    for table in ('policy_activation_generations','policy_activation_outbox_events'):
        op.execute(f"CREATE TRIGGER b02p_no_mutation BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION adr020_reject_append_only_mutation()")
        op.execute(f"CREATE TRIGGER b02p_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION adr020_reject_append_only_mutation()")
    op.execute("CREATE TRIGGER a_b02p_consumed_policy BEFORE INSERT ON acquisition_mode_bindings FOR EACH ROW EXECUTE FUNCTION b02p_guard_consumed_policy()")

def downgrade():
    raise RuntimeError('POLICY_ATOMICITY_APPEND_ONLY_IRREVERSIBLE')
