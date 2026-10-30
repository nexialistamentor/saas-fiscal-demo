#!/usr/bin/env python3
"""B02 R6: bounded physical catalogue for two documented SEFA/PR sources.

No fiscal applicability inference: PDF hash, rule, item and legal validity are
independent propositions. Never creates a normative relation or selects a rate.
Read-only source database through the existing isolated Docker transport.
"""
from __future__ import annotations
import json
import subprocess
import sys

import b02_g5_v5_local_bridge as bridge

PATH="tools/b02_r6_normative_linkage_readonly.py"
ROLE="solveris_b02_writer"
SOURCE_HASHES={
 "101202501245":"e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
 "101201900571":"af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d",
}
TABLES=("normative_artifacts","extraction_results","rule_versions",
        "normative_relation_versions","tabela_mva")


def fail(reason):raise RuntimeError("STOP_B02_R6_"+reason)


def psql(sql):
    cmd=["docker","exec","-i",bridge.CONTAINER,"psql","-X","-w","-v",
         "ON_ERROR_STOP=1","-U",ROLE,"-d",bridge.DATABASE,"-At"]
    p=subprocess.run(cmd,input=sql.encode("utf8"),capture_output=True,timeout=60)
    if p.returncode:
        fail("SQL_READ_ONLY_"+p.stderr.decode("utf8",errors="replace")[-300:])
    return p.stdout.decode("utf8",errors="strict").strip().splitlines()


def read(sql):
    result=psql(sql)
    if len(result)!=3 or result[0]!="BEGIN" or result[2]!="ROLLBACK":
        fail("TX_READ_ONLY_PROTOCOL")
    try:return json.loads(result[1])
    except (ValueError,TypeError):fail("INVALID_JSON")


PRIVILEGES="""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'database',current_database(),'role',session_user,'current_user',current_user,
 'revision',(SELECT version_num FROM public.alembic_version),
 'select_privileges',(
   SELECT jsonb_object_agg(x.table_name,
     CASE WHEN to_regclass('public.'||x.table_name) IS NOT NULL
      THEN has_table_privilege(current_user,'public.'||x.table_name,'SELECT')
      ELSE false END)
   FROM (VALUES ('normative_artifacts'),('extraction_results'),('rule_versions'),
                ('normative_relation_versions'),('tabela_mva')) x(table_name))
)::text;
ROLLBACK;"""

CATALOGUE="""BEGIN READ ONLY;
SELECT jsonb_build_object(
 'artifacts',(
   SELECT COALESCE(jsonb_agg(jsonb_build_object(
    'source_pdf_hash',a.artifact_hash,'normative_artifact_id',a.normative_artifact_id,
    'record_hash',a.record_hash,
    'record_hash_shape_valid',a.record_hash ~ '^[0-9a-f]{64})
    ORDER BY a.normative_artifact_id),'[]'::jsonb)
   FROM public.normative_artifacts a WHERE a.artifact_hash IN
    ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
     'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d')),
 'rule_candidates',(
   SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'rule_version_record_id',c.rule_version_record_id,
      'rule_hash',c.rule_hash,
      'rule_record_hash',c.record_hash,
      'pdf_artifact_hash',c.artifact_hash,
      'result_id',c.extraction_result_id,
      'result_record_hash',c.extraction_result_record_hash)
      ORDER BY c.rule_version_record_id),'[]'::jsonb)
   FROM (
      SELECT rv.rule_version_record_id,rv.rule_hash,rv.record_hash,
             er.artifact_hash,rv.extraction_result_id,rv.extraction_result_record_hash
      FROM public.rule_versions rv
      JOIN public.extraction_results er
       ON er.extraction_result_id=rv.extraction_result_id
       AND er.record_hash=rv.extraction_result_record_hash
      WHERE er.artifact_hash IN
        ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
         'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d')
      ORDER BY rv.rule_version_record_id LIMIT 30
   ) c),
 'normative_relations_total',
   (SELECT count(*) FROM public.normative_relation_versions),
 'rule_versions_total',(SELECT count(*) FROM public.rule_versions),
 'mva_pr_12119090',
   (SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'id',m.id,'ncm',m.ncm,'vigencia_inicio',m.vigencia_inicio,
      'vigencia_fim',m.vigencia_fim,'fonte_legal',m.fonte_legal)
       ORDER BY m.id),'[]'::jsonb)
      FROM (SELECT * FROM public.tabela_mva
       WHERE estado='PR' AND ncm='12119090'
       ORDER BY id LIMIT 20) m)
)::text;
ROLLBACK;"""


def inspect():
    with bridge.managed_container():
        ident=read(PRIVILEGES)
        if (ident.get("database"),ident.get("role"),ident.get("current_user"))!=(
            bridge.DATABASE,ROLE,ROLE):
            fail("DATABASE_OR_ROLE_MISMATCH")
        acl=ident.get("select_privileges")
        if not isinstance(acl,dict):
            fail("PRIVILEGES_UNKNOWN")
        inaccessible=[table for table in TABLES if acl.get(table) is not True]
        if inaccessible:
            return {"status":"R6_SOURCE_TABLES_INACCESSIBLE_WITH_EXISTING_ROLE",
                "unreadable_tables":inaccessible,"source_identity":ident,
                "writes":0,"new_grants":0,"fiscal_authority":False}
        data=read(CATALOGUE)
        artifacts=data["artifacts"]
        if len(artifacts)>20 or len(data["rule_candidates"])>30:
            fail("RESULT_BOUND_EXCEEDED")
        if any(not a["record_hash_shape_valid"] for a in artifacts):
            fail("ARTIFACT_RECORD_HASH_FORMAT_INVALID")
        return {
            "status":"R6_PHYSICAL_DOCUMENTARY_INVENTORY_ONLY",
            "source_identity":ident,
            "source_sha256":SOURCE_HASHES,
            "catalogue":data,
            "canonical_l2_ruleversion_item_binding_proven":False,
            "external_source_revisions_exhaustively_verified":False,
            "legal_applicability_for_item_proven":False,
            "fiscal_authority":False,
            "checkout":False,
            "writes":0,"new_grants":0}


def main():
    bridge.validate_checkout(PATH)
    print(json.dumps(inspect(),sort_keys=True,ensure_ascii=False,default=str))


if __name__=="__main__":
    try:main()
    except Exception as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
)
    ORDER BY a.normative_artifact_id),'[]'::jsonb)
   FROM public.normative_artifacts a WHERE a.artifact_hash IN
    ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
     'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d')),
 'rule_candidates',(
   SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'rule_version_record_id',c.rule_version_record_id,
      'rule_hash',c.rule_hash,
      'rule_record_hash',c.record_hash,
      'pdf_artifact_hash',c.artifact_hash,
      'result_id',c.extraction_result_id,
      'result_record_hash',c.extraction_result_record_hash)
      ORDER BY c.rule_version_record_id),'[]'::jsonb)
   FROM (
      SELECT rv.rule_version_record_id,rv.rule_hash,rv.record_hash,
             er.artifact_hash,rv.extraction_result_id,rv.extraction_result_record_hash
      FROM public.rule_versions rv
      JOIN public.extraction_results er
       ON er.extraction_result_id=rv.extraction_result_id
       AND er.record_hash=rv.extraction_result_record_hash
      WHERE er.artifact_hash IN
        ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',
         'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d')
      ORDER BY rv.rule_version_record_id LIMIT 30
   ) c),
 'normative_relations_total',
   (SELECT count(*) FROM public.normative_relation_versions),
 'rule_versions_total',(SELECT count(*) FROM public.rule_versions),
 'mva_pr_12119090',
   (SELECT COALESCE(jsonb_agg(jsonb_build_object(
      'id',m.id,'ncm',m.ncm,'vigencia_inicio',m.vigencia_inicio,
      'vigencia_fim',m.vigencia_fim,'fonte_legal',m.fonte_legal)
       ORDER BY m.id),'[]'::jsonb)
      FROM (SELECT * FROM public.tabela_mva
       WHERE estado='PR' AND ncm='12119090'
       ORDER BY id LIMIT 20) m)
)::text;
ROLLBACK;"""


def inspect():
    with bridge.managed_container():
        ident=read(PRIVILEGES)
        if (ident.get("database"),ident.get("role"),ident.get("current_user"))!=(
            bridge.DATABASE,ROLE,ROLE):
            fail("DATABASE_OR_ROLE_MISMATCH")
        acl=ident.get("select_privileges")
        if not isinstance(acl,dict):
            fail("PRIVILEGES_UNKNOWN")
        inaccessible=[table for table in TABLES if acl.get(table) is not True]
        if inaccessible:
            return {"status":"R6_SOURCE_TABLES_INACCESSIBLE_WITH_EXISTING_ROLE",
                "unreadable_tables":inaccessible,"source_identity":ident,
                "writes":0,"new_grants":0,"fiscal_authority":False}
        data=read(CATALOGUE)
        artifacts=data["artifacts"]
        if len(artifacts)>20 or len(data["rule_candidates"])>30:
            fail("RESULT_BOUND_EXCEEDED")
        if any(not a["record_hash_valid"] for a in artifacts):
            fail("EXACT_ARTIFACT_RECORD_HASH_INVALID")
        return {
            "status":"R6_PHYSICAL_DOCUMENTARY_INVENTORY_ONLY",
            "source_identity":ident,
            "source_sha256":SOURCE_HASHES,
            "catalogue":data,
            "canonical_l2_ruleversion_item_binding_proven":False,
            "external_source_revisions_exhaustively_verified":False,
            "legal_applicability_for_item_proven":False,
            "fiscal_authority":False,
            "checkout":False,
            "writes":0,"new_grants":0}


def main():
    bridge.validate_checkout(PATH)
    print(json.dumps(inspect(),sort_keys=True,ensure_ascii=False,default=str))


if __name__=="__main__":
    try:main()
    except Exception as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
