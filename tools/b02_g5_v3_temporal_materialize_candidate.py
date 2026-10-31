"""B02 G5 V3: materialize ONLY a fail-closed draft from real G4 v4.

Requires independent readback of the four new G4 records. A candidate is
NOT an approved PolicyVersion, signer, institutional origin, fiscal authority,
migrations installation or COMMIT. Historical G5 V1/V2 remain unmodified.
"""
from __future__ import annotations
import importlib.util
import json
import hashlib
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OLD="POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json"
OLD_BLOB="87dd0560d842f8b9f20d808363496fa60786710c"
PLAN="B02_G5_V5_SUCESSOR_TEMPORAL_PLANO_CONDICIONAL_20261030.json"
KEY="decisao_unica_temporal_antecipada_g4_g5_20261031"
NEW="POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json"


def stop(reason):
    raise RuntimeError("STOP_G5_V3_DRAFT_"+reason)


def git(*a):
    p=subprocess.run(["git",*a],cwd=ROOT,stdout=subprocess.PIPE,
                     stderr=subprocess.DEVNULL,timeout=25)
    if p.returncode:stop("GIT_OBJECT_NOT_AVAILABLE")
    return p.stdout.strip().decode("utf-8")


def check():
    if git("branch","--show-current")!="candidate/g5-v5-publicacao-local":
        stop("WRONG_BRANCH")
    if git("rev-parse","HEAD:"+OLD)!=OLD_BLOB:
        stop("IMMUTABLE_V2_SOURCE_CHANGED")
    for path in (OLD,PLAN):
        if git("hash-object",path)!=git("rev-parse","HEAD:"+path):
            stop("TRACKED_INPUT_DIRTY")
    q=json.loads((ROOT/PLAN).read_text(encoding="utf-8-sig"))[KEY]
    if (q["status"]!="RATIFICADA_PROSPECTIVAMENTE"
        or q.get("approved") is not True or q.get("approved_by")!="Miguel"
        or not q.get("approved_at_utc") or not q.get("ratification_source")):
        stop("TEMPORAL_APPROVAL_NOT_RATIFIED")
    if q["g5"].get("materializer_git_blob")!=git("rev-parse","HEAD:tools/b02_g5_v3_temporal_materialize_candidate.py"):
        stop("MATERIALIZER_SOURCE_NOT_PINNED")
    at=datetime.fromisoformat(q["approved_at_utc"])
    end=datetime.fromisoformat(q["window_utc"]["until"])
    if at.tzinfo is None or at>=end or at>datetime.now(timezone.utc):
        stop("APPROVAL_TIME_INVALID")
    return q


def new_policy(q,physical):
    if physical.get("status")!="FOUR_RECORDS_RECONCILED":
        stop("G4_FOUR_RECORDS_NOT_RECONCILED")
    if physical.get("activation_id")!="B02-05ede-activation-v4":
        stop("WRONG_G4_ACTIVATION_ID")
    ah=physical.get("activation_hash")
    if not isinstance(ah,str) or len(ah)!=64 or any(c not in "0123456789abcdef" for c in ah):
        stop("G4_ACTIVATION_HASH_INVALID")
    base=json.loads((ROOT/OLD).read_text(encoding="utf-8-sig"))
    b=base["policy_candidate_body"]
    if b["policy_version"]!=2 or b["policy_id"]!=q["g5"]["policy_id"]:
        stop("UNEXPECTED_V2_POLICY")
    old=b["rules"]["b02_noncredential"]["security"]["g5_release"]
    if len(old["documents"])!=2:
        stop("SOURCE_DOCUMENT_COUNT_INVALID")
    if {d["sha256"] for d in old["documents"]}!={
        "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
        "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d"}:
        stop("ORIGINAL_TWO_DOC_HASHES_NOT_PRESERVED")
    start=q["window_utc"]["from"]
    end=q["window_utc"]["until"]
    b["policy_version"]=3
    b["declared_material_applicability"].update({"from":start,"until":end})
    old["from"]=start
    old["until"]=end
    # The old G5 V2 root and institutional acceptance cannot be inherited.
    old["capability_root_id"]=None
    old["actor"]=None
    b["origin_evidence"]["institutional_evidence_bindings"]={}
    limits=b["origin_evidence"]["known_limitations"]
    for notice in ("NEW_V3_INDEPENDENT_REVIEW_AND_RATIFICATION_PENDING",
                   "CURRENT_G4_FOUNDER_ORIGIN_FOR_EACH_DOCUMENT_NOT_ISSUED",
                   "V3_NATIVE_APPROVED_ROOT_OR_SIGNING_CUSTODY_NOT_ATTESTED",
                   "THIS_DRAFT_MUST_NOT_BE_PERSISTED_AS_ACTIVE_POLICY"):
        if notice not in limits:limits.append(notice)
    for doc in old["documents"]:
        g4=doc["g4"]
        binding=g4["policy_binding"]
        if binding["policy_activation_id"]!="B02-05ede-activation-v3":
            stop("HISTORICAL_V2_DOC_BINDING_DRIFT")
        binding["policy_activation_id"]=physical["activation_id"]
        binding["policy_activation_record_hash"]=ah
        g4["valid_from"]=start
        g4["valid_until"]=end
        # Do not transplant October's own G4 origin proof to the new activation.
        g4["origin_report_binding"]=None
        g4["outcome"]="AWAITING_OWN_CURRENT_FOUNDER_ORIGIN"
    base["status"]="V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY"
    base["predecessor_policy_hash"]=json.loads((ROOT/PLAN).read_text(encoding="utf-8-sig"))["base"]["policy_hash"]
    base["__AVISO_G4_PREENCHIDO__"]="New G4 activation ID and hash physically read, but own G4 origin reports NOT established."
    base["__AVISO_CAMPOS_INSTITUCIONAIS__"]="V3 has no new own audit, ratification, root, signature or release. Old V2 acts are historical only."
    base["__V3_DRAFT_PROVENANCE__"]={
        "temporal_decision_reference":q["reference"],
        "source_v2_blob":OLD_BLOB,
        "g4_reconciled_activation_hash":ah,
        "g4_reconciled_four_record_ids":q["g4"]["fresh_four_record_ids"],
        "not_signed_or_authorized":True,
        "policy_body_sha256_is_draft_only":hashlib.sha256(json.dumps(
            b,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode("utf8")).hexdigest(),
    }
    return base


def main():
    q=check()
    if (ROOT/NEW).exists():
        stop("CANDIDATE_ALREADY_EXISTS_PRESERVE")
    import os
    if not os.environ.get("SOLVERIS_B02_POLICY_WRITER_DSN"):
        stop("READONLY_ISOLATED_BRIDGE_REQUIRED")
    runner=ROOT/"tools/b02_g4_g5_temporal_successor_runner.py"
    spec=importlib.util.spec_from_file_location("g4_v4_runner",runner)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.verify_plan(True)
    source=mod.pinned_code()
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool
    e=create_engine(os.environ["SOLVERIS_B02_POLICY_WRITER_DSN"],
                    poolclass=NullPool)
    try:
        physical=source["independent_read"](e)
        if physical is None:stop("G4_V4_NOT_YET_PERSISTED")
        mod.reconcile_older_path(e)
    finally:e.dispose()
    body=new_policy(q,physical)
    # Existence check plus exclusive create: no rewrite or overwrite.
    encoded=(json.dumps(body,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf8")
    with (ROOT/NEW).open("xb") as file:file.write(encoded)
    print(json.dumps({"status":"G5_V3_DRAFT_READY_FOR_NEW_OWN_AUDIT_ONLY",
        "output":NEW,"draft_file_sha256":hashlib.sha256(encoded).hexdigest(),
        "g4_activation_id":physical["activation_id"],
        "g4_activation_hash":physical["activation_hash"],
        "policy_version":3,
        "g5_institutional_approvals":0,"native_elf_compiled":False,
        "protected_writes":0},sort_keys=True))


if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(str(exc) if isinstance(exc,RuntimeError)
              else "STOP_G5_V3_DRAFT_INTERNAL",file=sys.stderr)
        sys.exit(2)
