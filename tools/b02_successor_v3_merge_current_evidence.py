#!/usr/bin/env python3
"""B02 successor V3: append five already-issued proofs, never reissue an act.

Only the 135-entry canonical proofs.json is eligible as input. No historical
record is rewritten; no authority, release, SQL, signature or new review is
created. --apply writes one file atomically in the designated local checkout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "candidate/g5-v5-publicacao-local"
BASE = "f07e2f609acad4675fcfa0c3698fb249ef2d493b"
PROOFS = "evidence/b02/successor_v3/proofs.json"
BODIES = "evidence/b02/successor_v3/mandate_bodies/"
OWN_ACT = "evidence/b02/ATO_PROPRIO_AUTOR_INTEGRADOR_SUCESSOR_20261102.json"
EXPECTED = {
 "author": ("B02-G4-SUCESSAO-20261101-AUTHOR.body.json",
            "73d77e161747a8f6725fe94cf0f148d41423c09a04b6233c7521bff6990c6849",
            "da14259ebd91584a0c30905719379720d4da4fbf3ace2f7d3ba424fe23db09c0"),
 "integrator": ("B02-G4-SUCESSAO-20261101-INTEGRATOR.body.json",
                "44698d76a4657804f4f6717cc83fac50697905717335efb8e8c9d8304c31fafe",
                "8efb6c1a11abbea216692b3e9af6b19cc7ca2c559b7f0a6505206d79a4fe9757"),
 "origin_examiner": ("B02-G4-SUCESSAO-20261101-ORIGIN.body.json",
                     "22ce147864beacc1fa51cf993672eb5a8ee817fa64be3b96e1259306e91e5ba7", None),
}
AUTHOR_ID = "GPT-6/executor-documental-g4-continuidade-sucessora-20261101"
REVIEWER_ACCEPTANCE = "6792209f25f33346cf5d235f2df186e2428679364042337b0c49d2675d66273d"


def stop(reason):
    raise RuntimeError("STOP_B02_SUCCESSOR_EVIDENCE_" + reason)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=25)
    if p.returncode:
        stop("GIT_QUERY_FAILED")
    return p.stdout.strip()


def load(path):
    file = ROOT / path
    if file.is_symlink() or not file.is_file():
        stop("SOURCE_UNSAFE_OR_ABSENT")
    raw = file.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    if type(obj) is not dict:
        stop("SOURCE_SCHEMA_INVALID")
    return obj


def planned():
    if git("branch", "--show-current") != BRANCH:
        stop("WRONG_BRANCH")
    if git("status", "--porcelain", "--", PROOFS, OWN_ACT, BODIES):
        stop("SOURCE_DIRTY")
    if git("hash-object", PROOFS) != BASE or git("rev-parse", "HEAD:" + PROOFS) != BASE:
        stop("PROOFS_135_BASE_CHANGED")
    old = load(PROOFS)
    if len(old) != 135 or REVIEWER_ACCEPTANCE not in old:
        stop("BASE_COUNT_OR_REVIEWER_ACCEPTANCE_INVALID")
    act = load(OWN_ACT)
    if act.get("schema") != "B02_G4_SUCCESSOR_AUTHOR_INTEGRATOR_OWN_ACCEPTANCES_20261102_V1":
        stop("OWN_ACT_SCHEMA")
    issued = act.get("acceptances")
    if type(issued) is not list or len(issued) != 2:
        stop("TWO_OWN_ACCEPTANCES_REQUIRED")
    by_role = {i.get("role"): i for i in issued if type(i) is dict}
    if set(by_role) != {"author", "integrator"}:
        stop("TWO_DISTINCT_ROLES_REQUIRED")
    extras = {}
    for role, (name, mandate_hash, acceptance_hash) in EXPECTED.items():
        body = load(BODIES + name)
        if digest(body) != mandate_hash:
            stop("MANDATE_HASH_" + role.upper())
        if body.get("issuer") != "Miguel" or body.get("revoked") is not False:
            stop("MANDATE_AUTHORITY_" + role.upper())
        if role == "origin_examiner":
            if body.get("execution_id") != "GPT-6/examinador-origem-sefa-pr-g4-sucessor-20261101":
                stop("ORIGIN_ROLE_ID")
        else:
            if body.get("execution_id") != AUTHOR_ID or body.get("role") != role:
                stop("AUTHOR_INTEGRATOR_ROLE_MISMATCH")
        extras[mandate_hash] = body
        if acceptance_hash is None:
            continue  # A mandated examiner has NOT accepted; do not imply acceptance.
        own = by_role[role]
        acceptance = own.get("own_canonical_acceptance")
        if (type(acceptance) is not dict
            or set(acceptance) != {"accepted", "accepted_at", "execution_id", "mandate_sha256"}
            or digest(acceptance) != acceptance_hash
            or own.get("acceptance_sha256") != acceptance_hash
            or acceptance["accepted"] is not True
            or acceptance["execution_id"] != AUTHOR_ID
            or acceptance["mandate_sha256"] != mandate_hash):
            stop("OWN_ACCEPTANCE_" + role.upper())
        moment = datetime.fromisoformat(acceptance["accepted_at"])
        start, until = (datetime.fromisoformat(body[k])
                        for k in ("valid_from", "valid_until"))
        if moment.tzinfo is None or not start <= moment < until:
            stop("OWN_ACCEPTANCE_CHRONOLOGY")
        extras[acceptance_hash] = acceptance
    if len(extras) != 5 or any(k in old for k in extras):
        stop("EXACT_FIVE_NEW_HASHES_REQUIRED")
    if any(digest(value) != key for key, value in extras.items()):
        stop("CANONICAL_PROOF_HASH_DIVERGENCE")
    new = dict(old)
    new.update(extras)
    if len(new) != 140 or any(new[k] != v for k, v in old.items()):
        stop("HISTORICAL_ENTRY_CHANGED")
    data = canonical(new)
    return data, {"source_records": len(old), "added_records": len(extras),
                  "result_records": len(new),
                  "new_proofs_sha256": hashlib.sha256(data).hexdigest(),
                  "origin_acceptance": "NOT_RECEIVED_OR_INSERTED",
                  "status": "SOURCE_ONLY_PROOF_INDEX_RECONCILED_NOT_AUTHORITY",
                  "protected_writes": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    data, result = planned()
    if args.apply:
        path = ROOT / PROOFS
        fd, temp_name = tempfile.mkstemp(prefix=".b02_proofs_", suffix=".tmp",
                                         dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        if path.read_bytes() != data:
            stop("WRITE_READBACK_MISMATCH")
        result["local_proofs_file_written"] = True
        result["git_commit_created"] = False
    else:
        result["local_proofs_file_written"] = False
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        print(str(exc)[:300], file=__import__("sys").stderr)
        raise SystemExit(2)
