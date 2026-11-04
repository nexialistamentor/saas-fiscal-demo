#!/usr/bin/env python3
"""B02 V2: real PG read-only projection and gated local CAS emission, not authority.

PREVIEW writes a complete plan outside custody; EMIT requires that exact plan's
separately authorized SHA-256. Never creates ROOT/adoption, SQL rows, identities,
signatures or operational admission. A historical revision is projected, never
retimestamped as a historical event.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from app.services import enterprise_b02_founder_review_profile as profile
from app.services import enterprise_b02_founder_runtime as runtime

SUBJECT = dict(policy_type="activation_authority",
               policy_id="SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY",
               policy_version=1,
               policy_hash="05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a")
SEVEN = {
 "execution.json":"5cdc4e6fca726edbc14aeb7cf253739cca9dc6067d7895096211ee89c0b6e903",
 "history.json":"8c585bdb3ec42d2ebc100f96013ff7be5144d78a1b29435f4025670c6bcd36c1",
 "institutional.json":"c3c894710010c9ffa508e8c7d73ecafefcf02962c38a65f06e50ae4164fcd505",
 "mandates.json":"89630a184206bbb606544151e0925efed29f618125cd3c0099dc9f72854504d6",
 "object.json":"615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906",
 "proofs.json":"9bc79ef8f1cc39d857a41fbfb0e74f0cf4deda274998db23c524c448c88ca004",
 "review.json":"9949a7cca164f9ed50f2b92aa2a1f348fdddfc1c4c3a5cced56b292112a86d21",
}
DECISION_SHA = "d3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520"
MANIFEST_SHA = "99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1"
SIGNATURE_SHA = "479c9304724e0a92a5d02145e74d99485792b6e8e54b6c098590d3e0c3ca2c8c"
ADOPTION_SHA = "d0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8"
BRANCH = "candidate/g5-v5-publicacao-local"
ACTIVATION_ID = "B02-05ede-activation-v4"


def stop(code):
    raise RuntimeError("STOP_B02_STORE_" + code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(obj):
    return profile.canonical(obj)


def read(path, pin=None, binary=False):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        stop("INPUT_MISSING_OR_SYMLINK:" + str(path))
    raw = path.read_bytes()
    if pin and sha(raw) != pin:
        stop("INPUT_HASH_DIVERGENCE:" + str(path))
    if binary:
        return raw
    obj = profile.parse(raw)
    if canonical(obj) != raw:
        stop("INPUT_NOT_CANONICAL:" + str(path))
    return obj


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, timeout=30)
    if p.returncode:
        stop("GIT_QUERY_FAILED:" + str(args))
    return p.stdout.strip()


def pin(obj):
    return dict(id=obj["id"], sha256=sha(canonical(obj)))


def sources(repo, bundle):
    if git(repo, "branch", "--show-current") != BRANCH:
        stop("WRONG_CHECKOUT")
    remote = git(repo, "remote", "get-url", "origin")
    if "nexialistamentor/saas-fiscal-demo" not in remote:
        stop("REMOTE_MISMATCH")
    source = repo / "evidence/b02/successor_v3"
    for name, digest in SEVEN.items():
        path = "evidence/b02/successor_v3/" + name
        if git(repo, "status", "--porcelain", "--", path):
            stop("DIRTY_SIGNED_SOURCE:" + name)
        if git(repo, "hash-object", path) != git(repo, "rev-parse", "HEAD:" + path):
            stop("UNCOMMITTED_SIGNED_SOURCE:" + name)
        if read(source / name, digest) != read(bundle / name, digest):
            stop("SIGNED_SOURCE_DIVERGENCE:" + name)
    decision = read(bundle / "decision.json", DECISION_SHA)
    manifest = read(bundle / "manifest.json", MANIFEST_SHA)
    signature = read(bundle / "signature.bin", SIGNATURE_SHA, binary=True)
    if len((bundle / "decision.json").read_bytes()) != 1118 or len(signature) != 64:
        stop("DECISION_OR_SIGNATURE_SIZE")
    if decision.get("schema_version") != 2 or decision.get("policy_subject") != SUBJECT:
        stop("DECISION_SUBJECT")
    if (len(manifest.get("entries", [])) != 7
        or {e["path"]:e["sha256"] for e in manifest["entries"]} != SEVEN):
        stop("SIGNED_MANIFEST")
    adoption = read(repo / "evidence/b02/B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json", ADOPTION_SHA)
    history = read(source / "history.json", SEVEN["history.json"])
    review = read(source / "review.json", SEVEN["review.json"])
    proofs = read(source / "proofs.json", SEVEN["proofs.json"])
    institutional = read(source / "institutional.json", SEVEN["institutional.json"])
    if (history.get("revision") != 1 or history.get("previous_revision") is not None
        or history.get("prior_reviews") != [] or not history.get("reviews")
        or SEVEN["review.json"] not in history["reviews"]
        or history.get("object_sha256") != SEVEN["object.json"]
        or review.get("accepted") is not True or len(proofs) < 149
        or len(institutional.get("decisions", [])) != 4):
        stop("HISTORICAL_REVISION_OR_PROOF_CHAIN")
    return source, decision, adoption, history, review, proofs, institutional


def origin(proofs, adoption, review):
    origin_pins = adoption.get("origin_reports")
    if not isinstance(origin_pins, list) or len(origin_pins) != 2:
        stop("ORIGIN_REPORT_COUNT")
    reports, mandates = [], []
    for ref in origin_pins:
        obj = proofs.get(ref["sha256"])
        if (not isinstance(obj, dict) or obj.get("id") != ref["id"]
            or sha(canonical(obj)) != ref["sha256"]
            or ref["sha256"] not in review["inputs_sha256"]):
            stop("ORIGIN_REPORT_UNRESOLVED")
        mref = obj.get("mandate_binding")
        if not isinstance(mref, dict) or set(mref) != {"id", "sha256"}:
            stop("ORIGIN_MANDATE_PIN")
        mandate = proofs.get(mref["sha256"])
        if (not isinstance(mandate, dict) or mandate.get("id") != mref["id"]
            or sha(canonical(mandate)) != mref["sha256"]
            or mandate.get("revoked") is not False):
            stop("ORIGIN_MANDATE_UNRESOLVED")
        reports.append(obj)
        mandates.append(mandate)
    if (pin(mandates[0]) != pin(mandates[1])
        or len({pin(r)["sha256"] for r in reports}) != 2):
        stop("ORIGIN_MANDATE_OR_REPORT_DIVERGENCE")
    return reports, mandates[0]


def pg_read(dsn, signed):
    from sqlalchemy import create_engine, text
    engine = create_engine(dsn, pool_pre_ping=False)
    try:
        with engine.connect() as con:
            con.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            runtime._read_identity(con)
            row = con.execute(text(
                "SELECT transaction_timestamp(), current_database(), current_user,"
                "current_setting('transaction_read_only'),current_setting('transaction_isolation')")).one()
            observed = row[0].astimezone(timezone.utc)
            activation = con.execute(text(
                "SELECT * FROM public.policy_activations WHERE policy_activation_id=:id"),
                {"id": ACTIVATION_ID}).mappings().one_or_none()
            if activation is None:
                stop("G4_V4_ACTIVATION_MISSING")
            activation = runtime._plain(dict(activation))
            binding = {k:activation[k] for k in SUBJECT}
            binding.update(policy_activation_id=ACTIVATION_ID,
                           policy_activation_record_hash=activation["record_hash"])
            if (binding["policy_version"] != SUBJECT["policy_version"]
                or {k:activation[k] for k in SUBJECT} != SUBJECT
                or activation.get("state") != "activa"):
                stop("G4_V4_NOT_ACTIVE")
            interval = activation.get("operational_interval")
            if not isinstance(interval, dict) or not (
                    datetime.fromisoformat(interval["from"].replace("Z","+00:00")) <= observed <
                    datetime.fromisoformat(interval["until"].replace("Z","+00:00"))):
                stop("G4_V4_OPERATIONAL_INTERVAL_NOT_CURRENT")
            decisions, a, e = runtime._read_snapshot(con, SUBJECT, binding)
            db_sha = sha(canonical(sorted(decisions,key=lambda d:d["decision_id"])))
            signed_sha = sha(canonical(sorted(signed["decisions"],key=lambda d:d["decision_id"])))
            if db_sha != signed_sha or len(decisions) != 4:
                stop("PG_ALL_DECISIONS_VS_SIGNED_DIVERGENCE")
            if (a != activation or e.get("state") != "concluida"
                or e.get("policy_activation_execution_id") != ACTIVATION_ID
                   and e.get("policy_activation_execution_id") != a.get("policy_activation_execution_id")):
                stop("PG_EXECUTION_NOT_BOUND")
            if a.get("policy_activation_execution_id") != e.get("policy_activation_execution_id"):
                stop("PG_EXECUTION_DIVERGENCE")
            receipt = dict(database=row[1],reader_role=row[2],read_only=row[3],
                           isolation=row[4],canonical_decisions_sha256=db_sha,
                           activation_id=a["policy_activation_id"],
                           activation_hash=a["record_hash"],
                           execution_id=e["policy_activation_execution_id"],
                           execution_hash=e["record_hash"])
            con.rollback()
            return observed, a, e, receipt
    finally:
        engine.dispose()


def projection(history, review, proofs, institutional, adoption, decision,
               observed, activation, execution, pg_receipt, valid_from):
    if valid_from.tzinfo is None or not (observed < valid_from):
        stop("PROSPECTIVE_START_REQUIRED")
    start = datetime.fromisoformat(decision["valid_from"].replace("Z","+00:00"))
    end = datetime.fromisoformat(decision["valid_until"].replace("Z","+00:00"))
    if not start <= observed < valid_from < end:
        stop("SIGNED_DECISION_WINDOW_EXPIRED")
    reports, mandate = origin(proofs, adoption, review)
    window = dict(valid_from=valid_from.isoformat(),valid_until=end.isoformat(),
                  revoked=False,synthetic_only=False)
    head = dict(
        id="B02-PRESERVED-REV1-" + history["object_sha256"][:16],
        schema="SOLVERIS-B02-PRESERVED-REVIEW-PROJECTION-V1",
        policy_subject=SUBJECT,sequence=1,previous=None,supersedes=None,
        history_sha256=SEVEN["history.json"],review_hashes=history["reviews"],
        object_sha256=history["object_sha256"],
        current_review_sha256=SEVEN["review.json"],**window)
    writer = dict(
        id="B02-PG-WRITER-PROJECTION-" + activation["record_hash"][:16],
        schema="SOLVERIS-B02-EXECUTION-WRITER-BINDING-V1",
        writer_role=execution["actor_or_worker"],
        activation_binding=dict(id=activation["policy_activation_id"],sha256=activation["record_hash"]),
        execution_record_binding=dict(id=execution["policy_activation_execution_id"],sha256=execution["record_hash"]),
        **window)
    context = dict(history_sha256=SEVEN["history.json"],
                   current_object_sha256=SEVEN["object.json"],
                   current_review_sha256=SEVEN["review.json"])
    runtime._binding(dict(context),writer,activation,execution,institutional["expected"],now=valid_from)
    snapshot = dict(
        id="B02-READ-SNAPSHOT-G4V4-" + activation["record_hash"][:16],
        schema="SOLVERIS-B02-AUTHORIZED-READ-SNAPSHOT-V1",
        policy_subject=SUBJECT,canonical_decisions_sha256=pg_receipt["canonical_decisions_sha256"],
        head_binding=pin(head),genesis_binding=pin(head),context=context,
        execution_writer_binding=pin(writer),
        origin_report_bindings=[pin(x) for x in reports],
        origin_mandate_binding=pin(mandate),**window)
    objects = {"head_genesis":head,"writer":writer,"origin_mandate":mandate,
               "origin_report_1":reports[0],"origin_report_2":reports[1],
               "snapshot":snapshot}
    return objects,{k:pin(v) for k,v in objects.items()}


def rootpath(p):
    p = Path(p).absolute()
    if any(x.is_symlink() for x in (p,*p.parents)):
        stop("CUSTODY_LINK")
    return p


def emit_object(root,obj):
    raw = canonical(obj)
    h = sha(raw)
    dest = root/"STORE"/"sha256"/h[:2]/(h+".json")
    if any(p.is_symlink() for p in (dest,*dest.parents)):
        stop("CAS_LINK")
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists():
        try:
            with os.fdopen(os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_BINARY",0),0o600),"wb") as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            pass
    if dest.read_bytes() != raw:
        stop("CAS_READBACK_MISMATCH")
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode",choices=("preview","emit"),required=True)
    ap.add_argument("--repo",type=Path,required=True)
    ap.add_argument("--signed-bundle",type=Path,required=True)
    ap.add_argument("--plan-file",type=Path,required=True)
    ap.add_argument("--custody-root",type=Path,required=True)
    ap.add_argument("--dsn-env",default="SOLVERIS_B02_READER_DSN")
    ap.add_argument("--authorized-plan-sha256")
    a = ap.parse_args()
    dsn = os.environ.get(a.dsn_env)
    if not dsn:
        stop("RESTRICTED_POSTGRES_DSN_UNAVAILABLE")
    repo = a.repo.resolve()
    source,decision,adoption,history,review,proofs,institutional = sources(repo,a.signed_bundle.resolve())
    observed,activation,execution,db = pg_read(dsn,institutional)
    plan_previous = None
    if a.mode == "emit":
        if not a.authorized_plan_sha256 or re.fullmatch("[a-f0-9]{64}",a.authorized_plan_sha256) is None:
            stop("EXACT_MIGUEL_PLAN_AUTHORIZATION_REQUIRED")
        plan_previous = profile.parse(read(a.plan_file,a.authorized_plan_sha256,binary=True))
        valid_from = datetime.fromisoformat(plan_previous["snapshot_valid_from"])
    else:
        if a.authorized_plan_sha256:
            stop("PREVIEW_CANNOT_AUTHORIZE")
        valid_from = observed+timedelta(minutes=15)
    objects,pins = projection(history,review,proofs,institutional,adoption,
                              decision,observed,activation,execution,db,valid_from)
    plan = dict(schema="SOLVERIS-B02-STORE-V2-EMISSION-PLAN-V1",
                status="PLAN_NOT_AUTHORITY",
                source_git_head=git(repo,"rev-parse","HEAD"),
                signed_bundle_hashes={**SEVEN,"decision.json":DECISION_SHA,
                                      "manifest.json":MANIFEST_SHA,
                                      "signature.bin":SIGNATURE_SHA},
                db=db,snapshot_valid_from=valid_from.isoformat(),
                custody_root=str(rootpath(a.custody_root)),
                objects=objects,pins=pins,postgresql_writes=0,
                root_issued=False,runtime_trust_provisioned=False)
    if a.mode == "preview":
        if a.plan_file.exists():
            stop("PLAN_EXISTS_NO_OVERWRITE")
        a.plan_file.parent.mkdir(parents=True,exist_ok=True)
        with a.plan_file.open("xb") as f:
            f.write(canonical(plan))
        if read(a.plan_file,binary=True) != canonical(plan):
            stop("PLAN_PHYSICAL_READBACK_FAILED")
        print(json.dumps(dict(status="PREVIEW_ONLY",plan_file=str(a.plan_file),
                              plan_sha256=sha(canonical(plan)),pins=pins,
                              db_read_only=True,custody_writes=0,
                              no_root_no_trust=True),sort_keys=True))
        return
    if (plan["source_git_head"] != plan_previous["source_git_head"]
        or plan["signed_bundle_hashes"] != plan_previous["signed_bundle_hashes"]
        or plan["db"] != plan_previous["db"]
        or plan["custody_root"] != plan_previous["custody_root"]
        or plan["objects"] != plan_previous["objects"]
        or plan["pins"] != plan_previous["pins"]):
        stop("PLAN_STALE_DB_OR_SOURCE_DIVERGENCE")
    root = rootpath(a.custody_root)
    hashes = {k:emit_object(root,v) for k,v in objects.items()}
    if hashes != {k:v["sha256"] for k,v in pins.items()}:
        stop("EMITTED_HASH_DIVERGENCE")
    print(json.dumps(dict(status="LOCAL_CAS_READBACK_PASS_NO_ROOT_NO_TRUST",
                          plan_sha256=a.authorized_plan_sha256,
                          emitted_sha256=hashes,pg_read_only=True,
                          sql_writes=0,r7_closed=False),sort_keys=True))


if __name__ == "__main__":
    try:main()
    except Exception as exc:
        print(str(exc)[:450],file=sys.stderr)
        raise SystemExit(2) from None
