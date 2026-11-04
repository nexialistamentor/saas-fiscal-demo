#!/usr/bin/env python3
"""B02: prospective ROOT V2 issuance, separate from CAS and owner adoption.

INSPECT only computes an exact authorization contract from the actual emitted
snapshot. ISSUE is allowed solely after the owner authorizes that contract's
SHA-256; ROOT issuance and ROOT_ADOPTION are different decisions. SQL untouched.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from app.services import enterprise_b02_founder_review_profile as profile
from tools import b02_v2_custody_root_preflight_windows as pre

ROOT_REPO = Path(__file__).resolve().parents[1]
CUSTODY = Path(os.environ.get("LOCALAPPDATA",str(Path.home()/"AppData/Local"))) / "SOLVERIS/B02Trust/SUCCESSOR_V3"
SIGNED_BUNDLE = Path.home()/"Downloads/SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022/BUNDLE_SUCESSOR_V2_24H_20261103_1800UTC"
PUBLIC_DER = Path(os.environ.get("LOCALAPPDATA",str(Path.home()/"AppData/Local"))) / "SOLVERIS/CustodiaB02/Chave_ceee5bb6f2a740a58cf4dbaa66565698/miguel-public.der"
DECISION_END = datetime.fromisoformat("2026-11-04T18:00:00+00:00")
_SUBJECT = {
  "policy_type":"activation_authority",
  "policy_id":"SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY",
  "policy_version":1,
  "policy_hash":"05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a",
}


def stop(reason):
    raise RuntimeError("STOP_B02_ROOT_V2_" + reason)


def load(*, plan_path, plan_sha):
    if len(plan_sha)!=64 or any(c not in "0123456789abcdef" for c in plan_sha):
        stop("SPECIFIC_PLAN_SHA_REQUIRED")
    raw,plan=pre.read(plan_path,plan_sha)
    if (plan.get("schema")!="SOLVERIS-B02-STORE-V2-EMISSION-PLAN-V1"
        or plan.get("status")!="PLAN_NOT_AUTHORITY"
        or plan.get("postgresql_writes")!=0
        or plan.get("root_issued") is not False
        or plan.get("runtime_trust_provisioned") is not False
        or plan.get("custody_root")!=str(pre.safe(CUSTODY))):
        stop("PLAN_AUTHORITY_OR_DESTINATION_INVALID")
    # Verify the already-completed custody stage by physically checking all
    # original signed bytes and adoptions. This check never writes.
    original_raw, original_plan=pre.read(
        Path.home()/"Downloads/B02_STORE_V2_PLANO_REVALIDADO_20261104.json",pre.PLAN_SHA)
    observed,signer_sha,adoption,review=pre.root_inputs(
        ROOT_REPO,original_plan,CUSTODY,SIGNED_BUNDLE,PUBLIC_DER)
    if any((observed.get(name)!="PRESENT_MATCH") for name in (
        "CONTINUITY_ADOPTION.json","SIGNER_AUTHORITY.json","SIGNER_REVIEW.json")):
        stop("SIGNED_CUSTODY_INPUTS_INCOMPLETE")
    if observed["BUNDLE_ASSINADO"]["status"]!="PRESENT_MATCH":
        stop("SIGNED_BUNDLE_CUSTODY_MISSING")
    if any(observed.get(name)!="NOT_ISSUED" for name in ("ROOT.json","ROOT_ADOPTION.json")):
        stop("ROOT_ALREADY_EXISTS")
    if plan["signed_bundle_hashes"]!=pre.SIGNED:
        stop("NEW_PLAN_SIGNED_BYTES_DIVERGENCE")
    if plan["db"].get("database")!="solveris_b02_r4g_test":
        stop("PG_SOURCE_CHANGED")
    if plan.get("source_git_head") is None:
        stop("GIT_SOURCE_MISSING")
    # The new plan may be on a later commit, but it must refer to this
    # unchanged emitter and the same signed institutional source.
    git = pre.git
    if git(ROOT_REPO,"branch","--show-current")!=b"candidate/g5-v5-publicacao-local":
        stop("BRANCH_INVALID")
    sha=git(ROOT_REPO,"rev-parse","HEAD").decode()
    if git(ROOT_REPO,"merge-base","--is-ancestor",plan["source_git_head"],sha)!=b"":
        stop("PLAN_GIT_NOT_ANCESTOR")
    src="tools/b02_store_emission_v2_windows.py"
    if (git(ROOT_REPO,"rev-parse","HEAD:"+src)!=
        git(ROOT_REPO,"rev-parse",plan["source_git_head"]+":"+src)):
        stop("CAS_EMITTER_CHANGED")
    pins=plan.get("pins",{})
    names={"head_genesis","writer","origin_mandate",
           "origin_report_1","origin_report_2","snapshot"}
    if set(pins)!=names or set(plan.get("objects",{}))!=names:
        stop("SIX_OBJECTS_REQUIRED")
    for name,pin in pins.items():
        if set(pin)!={"id","sha256"}:
            stop("CAS_PIN_FORMAT")
        raw,obj=pre.read(
            CUSTODY/"STORE"/"sha256"/pin["sha256"][:2]/(pin["sha256"]+".json"),
            pin["sha256"])
        if obj!=plan["objects"][name] or pin["id"]!=obj.get("id"):
            stop("CAS_PHYSICAL_READBACK:"+name)
    snapshot=plan["objects"]["snapshot"]
    if (snapshot.get("policy_subject")!=_SUBJECT
        or snapshot.get("head_binding")!=pins["head_genesis"]
        or snapshot.get("genesis_binding")!=pins["head_genesis"]
        or snapshot.get("execution_writer_binding")!=pins["writer"]
        or snapshot.get("origin_mandate_binding")!=pins["origin_mandate"]
        or snapshot.get("origin_report_bindings")!=[
            pins["origin_report_1"],pins["origin_report_2"]]):
        stop("SNAPSHOT_DEPENDENT_PINS_DIVERGE")
    start=datetime.fromisoformat(snapshot["valid_from"])
    end=datetime.fromisoformat(snapshot["valid_until"])
    if start.tzinfo is None or end!=DECISION_END:
        stop("SNAPSHOT_WINDOW_INVALID")
    decision=pre.read(CUSTODY/"BUNDLE_ASSINADO"/"decision.json",pre.SIGNED["decision.json"])[1]
    auth=pre.read(CUSTODY/"SIGNER_AUTHORITY.json",signer_sha)[1]
    rev=pre.read(CUSTODY/"SIGNER_REVIEW.json",pre.REVIEW_SHA)[1]
    if (decision.get("profile")!="FOUNDER_SIGNED_REVIEW_BUNDLE_B02_V2"
        or decision.get("policy_subject")!=_SUBJECT
        or auth.get("review",{}).get("review_sha256")!=pre.REVIEW_SHA
        or rev.get("outcome")!="favoravel"
        or rev.get("id") is None
        or auth.get("id")!="SOLVERIS-B02-G4-DOCUMENTARY-LOCAL-SIGNER-V2"):
        stop("OWNER_SIGNER_OR_REVIEW_CHAIN")
    der=pre.read(PUBLIC_DER,pre.PUBLIC_SHA,json_file=False)[0]
    root_static={
        "id":"B02-ROOT-V2-"+pins["snapshot"]["sha256"][:16],
        "schema":"SOLVERIS-B02-RECOGNIZED-SUCCESSOR-ROOT-V2",
        "profile":decision["profile"],
        "policy_subject":_SUBJECT,
        "key_fingerprint":pre.PUBLIC_SHA,
        "public_key_der_hex":der.hex(),
        "decision_sha256":pre.SIGNED["decision.json"],
        "manifest_sha256":pre.SIGNED["manifest.json"],
        "signature_sha256":pre.SIGNED["signature.bin"],
        "origin_document_scope":["101201900571","101202501245"],
        "continuity_adoption_binding":{
            "id":adoption["id"],"sha256":pre.ADOPTION_SHA},
        "signer_adoption_binding":{"id":auth["id"],"sha256":signer_sha},
        "signer_review_binding":{"id":rev["id"],"sha256":pre.REVIEW_SHA},
        "snapshot_binding":pins["snapshot"],
        "no_operational_authority":True,
        "valid_from":snapshot["valid_from"],
        "valid_until":snapshot["valid_until"],
        "revoked":False,
        "synthetic_only":False,
    }
    contract={
        "schema":"SOLVERIS-B02-V2-ROOT-ISSUANCE-CONTRACT-V1",
        "status":"PROPOSAL_NOT_AN_AUTHORIZATION",
        "source_plan_sha256":plan_sha,
        "snapshot_binding":pins["snapshot"],
        "static_root":root_static,
        "issued_at_rule":"UTC_NOW_ONLY_AT_PHYSICAL_ROOT_ISSUANCE",
        "window_rule":"ISSUED_AT_STRICTLY_BEFORE_SNAPSHOT_VALID_FROM",
        "no_root_adoption":True,
        "no_operational_authority":True,
        "sql_writes":0,
    }
    return contract,start,end


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("inspect","issue"),required=True)
    parser.add_argument("--plan",required=True,type=Path)
    parser.add_argument("--plan-sha256",required=True)
    parser.add_argument("--authorized-contract-sha256")
    a=parser.parse_args()
    contract,start,end=load(plan_path=a.plan,plan_sha=a.plan_sha256)
    contract_sha=pre.sha(profile.canonical(contract))
    now=datetime.now(timezone.utc)
    if a.mode=="inspect":
        if a.authorized_contract_sha256:
            stop("INSPECT_IS_NOT_ROOT_AUTHORIZATION")
        print(json.dumps({
            "status":"ROOT_V2_CONTRACT_INSPECTED_NOT_ISSUED",
            "contract_sha256":contract_sha,
            "snapshot_sha256":contract["snapshot_binding"]["sha256"],
            "root_valid_from_utc":start.isoformat(),
            "root_valid_until_utc":end.isoformat(),
            "root_issuance_still_prospective":now<start,
            "root_issued":False,"root_adopted":False,
            "sql_writes":0,"custody_writes":0},sort_keys=True))
        return
    if a.authorized_contract_sha256!=contract_sha:
        stop("MIGUEL_EXACT_CONTRACT_RATIFICATION_REQUIRED")
    # Time must be checked immediately before taking the immutable write.
    now=datetime.now(timezone.utc)
    if not now<start<end:
        stop("ROOT_PROSPECTIVE_WINDOW_EXPIRED")
    root=dict(contract["static_root"],issued_at=now.isoformat())
    raw=profile.canonical(root)
    dest=pre.safe(CUSTODY/"ROOT.json")
    if dest.exists():
        stop("ROOT_ALREADY_ISSUED_NO_OVERWRITE")
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_BINARY",0),0o600)
    with os.fdopen(fd,"wb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    if dest.read_bytes()!=raw:
        stop("ROOT_PHYSICAL_READBACK_DIVERGENCE")
    print(json.dumps({
        "status":"ROOT_V2_ISSUED_READBACK_PASS_ADOPTION_REQUIRED",
        "root_sha256":pre.sha(raw),
        "snapshot_sha256":contract["snapshot_binding"]["sha256"],
        "issued_at_utc":root["issued_at"],
        "valid_from_utc":root["valid_from"],
        "valid_until_utc":root["valid_until"],
        "root_adopted":False,"runtime_provisioned":False,"sql_writes":0},
        sort_keys=True))


if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(str(exc)[:400],file=__import__("sys").stderr)
        raise SystemExit(2) from None
