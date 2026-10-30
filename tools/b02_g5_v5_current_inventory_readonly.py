#!/usr/bin/env python3
"""One bounded physical inventory of G5 policy, activation and release, all versions.

Use existing Docker bridge and restricted PostgreSQL reader, no DSN/password.
No DML/DDL, no pg_hba changes, no synthetic fixtures or repeated old tests.
The inventory is evidence, not release eligibility or permission to operate.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

import b02_g5_v5_local_bridge as bridge
import b02_g5_v5_institutional_owner_rollback_probe as owner

ROOT = Path(__file__).resolve().parents[1]
PATH = "tools/b02_g5_v5_current_inventory_readonly.py"
POLICY_ID = "SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE"
HASH_V1 = "57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa"
HASH_V2 = "007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf"
POLICY_RECORD_V2 = "fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9"
SUBMITTED_HASH = "dfa49ca6a05fae13e649a04ba795f6bf9f0576151a0b3751a582b903d4599f2a"
START_HASH = "da26dccf706582ef71868a6523d286e1bfe3aeae7b0272e3b8bd6a89ff8608d3"

# All table references below exist in Alembic 0063 and use a read-only transaction.
# Never use "LIMIT 1" or newest-only selection to conceal competing rows.
SQL = """BEGIN READ ONLY;
SELECT jsonb_build_object(
 'observed_at_utc',timezone('UTC',clock_timestamp()),
 'database',current_database(),
 'session_user',session_user,
 'current_user',current_user,
 'postgres_version',current_setting('server_version'),
 'alembic_revision',(SELECT version_num FROM public.alembic_version),
 'policies',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'version',p.policy_version,'id',p.policy_version_record_id,
   'policy_hash',p.policy_hash,'record_hash',p.record_hash,
   'record_hash_valid',p.record_hash=public.b02_json_hash(to_jsonb(p)-'record_hash'),
   'material_interval',p.declared_material_applicability,
   'created_at',p.created_at) ORDER BY p.policy_version,p.policy_version_record_id)
  FROM public.policy_versions p WHERE p.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'decisions',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',d.decision_id,'version',d.policy_version,'policy_hash',d.policy_hash,
   'event',d.decision_event,'actor',d.actor,'role',d.institutional_role,
   'previous_id',d.previous_decision_id,
   'previous_record_hash',d.evidence->>'previous_decision_record_hash',
   'timestamp',d.timestamp,'hash',d.record_hash,
   'hash_valid',d.record_hash=public.b02_json_hash(to_jsonb(d)-'record_hash'))
   ORDER BY d.policy_version,d.timestamp,d.decision_id)
  FROM public.policy_decisions d WHERE d.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'bootstraps',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',b.bootstrap_authority_record_id,'version',b.policy_version,
   'policy_hash',b.policy_hash,'hash',b.record_hash,'validity',b.validity,
   'audit_result',b.independent_audit_result,'timestamp',b.timestamp)
   ORDER BY b.policy_version,b.bootstrap_authority_record_id)
  FROM public.bootstrap_authority_records b WHERE b.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'activations',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',a.policy_activation_id,'version',a.policy_version,
   'policy_hash',a.policy_hash,'hash',a.record_hash,'state',a.state,
   'activated_at',a.activated_at,'operational_interval',a.operational_interval,
   'decision_id',a.policy_decision_id,
   'decision_record_hash',a.policy_decision_record_hash,
   'execution_id',a.policy_activation_execution_id,
   'technical_actor',a.technical_actor,'domain',a.domain,'modality',a.modality,
   'txid',COALESCE(to_jsonb(a)->>'b02_policy_txid',to_jsonb(a)->>'assigned_txid'),
   'record_hash_valid',a.record_hash=public.b02_json_hash(to_jsonb(a)-'record_hash'))
   ORDER BY a.policy_version,a.policy_activation_id)
  FROM public.policy_activations a WHERE a.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'executions',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',e.policy_activation_execution_id,'version',e.policy_version,
   'policy_hash',e.policy_hash,'hash',e.record_hash,'state',e.state,
   'decision_id',e.policy_decision_id,'decision_hash',e.policy_decision_record_hash,
   'txid',COALESCE(to_jsonb(e)->>'b02_policy_txid',to_jsonb(e)->>'assigned_txid'),
   'completed_at',e.finished_at)
   ORDER BY e.policy_version,e.policy_activation_execution_id)
  FROM public.policy_activation_executions e WHERE e.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'generations',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',g.policy_activation_generation_id,'version',g.policy_version,
   'hash',g.record_hash,'execution_id',g.policy_activation_execution_id,
   'activation_id',g.policy_activation_id,'txid',COALESCE(
    to_jsonb(g)->>'b02_policy_txid',to_jsonb(g)->>'assigned_txid'))
   ORDER BY g.policy_version,g.policy_activation_generation_id)
  FROM public.policy_activation_generations g WHERE g.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'outbox',COALESCE((
  SELECT jsonb_agg(jsonb_build_object(
   'id',o.policy_activation_outbox_event_id,'version',o.policy_version,
   'hash',o.record_hash,'generation_id',o.policy_activation_generation_id,
   'activation_id',o.policy_activation_id,'txid',COALESCE(
    to_jsonb(o)->>'b02_policy_txid',to_jsonb(o)->>'assigned_txid'))
   ORDER BY o.policy_version,o.policy_activation_outbox_event_id)
  FROM public.policy_activation_outbox_events o WHERE o.policy_id='SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
 ),'[]'::jsonb),
 'native_symbols',(SELECT COALESCE(jsonb_agg(n), '[]'::jsonb)
   FROM (SELECT proname AS n FROM pg_catalog.pg_proc
    WHERE proname IN ('b02g5_assert_signature','b02g5_native_profile',
      'b02g5_precommit_validate','b02g5_require_real_release',
      'b02_g5_assert_one_shot','b02_g5_reserve_operational_decision')
    ORDER BY proname) s),
 'one_shot_table',(to_regclass('public.b02_g5_operational_approval_uses') IS NOT NULL),
 'g4_926',(SELECT jsonb_build_object(
   'activation_id',a.policy_activation_id,'activation_hash',a.record_hash,
   'decision_id',a.policy_decision_id,'execution_id',a.policy_activation_execution_id,
   'policy_hash',a.policy_hash,'interval',a.operational_interval,
   'txid',COALESCE(to_jsonb(a)->>'b02_policy_txid',to_jsonb(a)->>'assigned_txid'))
   FROM public.policy_activations a WHERE a.policy_activation_id='B02-05ede-activation-v3')
)::text;
ROLLBACK;"""


def classify(report):
    expected_db = (bridge.DATABASE, bridge.ROLE, bridge.ROLE)
    if tuple(report.get(k) for k in ("database","session_user","current_user")) != expected_db:
        raise RuntimeError("STOP_INVENTORY_WRONG_DB_OR_ROLE")
    version = report.get("alembic_revision")
    if not isinstance(version,str) or not version.startswith("00"):
        raise RuntimeError("STOP_INVENTORY_UNKNOWN_SCHEMA")
    fields = ("policies","decisions","bootstraps","activations","executions","generations","outbox")
    if any(not isinstance(report.get(name),list) or len(report[name])>100 for name in fields):
        raise RuntimeError("STOP_INVENTORY_TOO_MANY_ROWS_OR_SCHEMA")
    policies = report["policies"]
    actual = [p for p in policies if p["version"] == 2]
    if len(actual)!=1 or actual[0]["policy_hash"]!=HASH_V2 or actual[0]["record_hash"]!=POLICY_RECORD_V2 or actual[0]["record_hash_valid"] is not True:
        raise RuntimeError("STOP_INVENTORY_POLICY_V2_CHANGED")
    known = {
        ("B02-G5-V5-GPT6-submetida-v1",SUBMITTED_HASH),
        ("B02-G5-V5-GPT6-auditoria-iniciada-v1",START_HASH)
    }
    for k,h in known:
        rows=[d for d in report["decisions"] if d["id"]==k]
        if len(rows)!=1 or rows[0]["hash"]!=h or rows[0]["hash_valid"] is not True:
            raise RuntimeError("STOP_INVENTORY_KNOWN_DECISION_DRIFT_" + k)
    v1 = [p for p in policies if p["version"]==1]
    if len(v1)!=1 or v1[0]["policy_hash"]!=HASH_V1 or v1[0]["record_hash_valid"] is not True:
        raise RuntimeError("STOP_INVENTORY_V1_DRIFT")
    latest_versions=[p["version"] for p in policies]
    report["version_next_free_candidate"] = max(latest_versions)+1
    report["classification"]={
        str(version):{
          "policy_count":sum(p["version"]==version for p in policies),
          "decision_events":[d["event"] for d in report["decisions"] if d["version"]==version],
          "activation_count":sum(a["version"]==version for a in report["activations"]),
          "activations":[a["id"] for a in report["activations"] if a["version"]==version],
          "complete_unit_claim":"NOT_INFERRED_FROM_COUNTS",
        } for version in latest_versions
    }
    report["eligibility"]="NOT_INFERRED_FROM_RECORD_COUNT_OR_HEADER"
    report["operational_proof"]="REQUIRES_FOUR_RECORD_SAME_TXID_G4_CURRENT_NATIVE_0064_0065_TWO_REAL_UNITS"
    report["database_writes"]=0
    return report


def inspect():
    with bridge.managed_container():
        lines=owner.psql(SQL,bridge.ROLE)
        if len(lines)!=3 or lines[0]!="BEGIN" or lines[2]!="ROLLBACK":
            raise RuntimeError("STOP_INVENTORY_READ_ONLY_PROTOCOL")
        report=json.loads(lines[1])
        if not isinstance(report,dict):raise RuntimeError("STOP_INVENTORY_JSON")
        if report["one_shot_table"]:
            permission=owner.psql("""BEGIN READ ONLY;
SELECT has_table_privilege(current_user,
  'public.b02_g5_operational_approval_uses','SELECT');
ROLLBACK;""",bridge.ROLE)
            if permission != ["BEGIN","t","ROLLBACK"]:
                report["one_shot_reservations"]="NOT_READABLE_BY_RESTRICTED_POLICY_WRITER"
                return classify(report)
            extra=owner.psql("""BEGIN READ ONLY;
SELECT coalesce(jsonb_agg(jsonb_build_object(
  'approval_id',approval_id,'release_id',release_id,'txid',assigned_txid,
  'operator_sha256',operator_sha256,'decision_document_sha256',decision_document_sha256,
  'reserved_at',reserved_at) ORDER BY approval_id),'[]'::jsonb)::text
FROM public.b02_g5_operational_approval_uses;
ROLLBACK;""",bridge.ROLE)
            if len(extra)!=3 or extra[0]!="BEGIN" or extra[2]!="ROLLBACK":
                raise RuntimeError("STOP_ONE_SHOT_READ_ONLY_PROTOCOL")
            report["one_shot_reservations"]=json.loads(extra[1])
        else:
            report["one_shot_reservations"]=None
        return classify(report)


def main():
    bridge.validate_checkout(PATH)
    print(json.dumps(inspect(),ensure_ascii=False,sort_keys=True,default=str))


if __name__=="__main__":
    main()
