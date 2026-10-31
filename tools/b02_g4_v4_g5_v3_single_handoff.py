#!/usr/bin/env python3
"""B02: one-way G4 v4 -> G5 V3 DRAFT handoff after a real four-record readback.

This is an operator convenience guard, not an authorization, retry policy,
SQL executor, institutional auditor, migration installer or G5 activation.
It always stops at the first failure. Never rerun after an ambiguous COMMIT.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "B02_G5_V5_SUCESSOR_TEMPORAL_PLANO_CONDICIONAL_20261030.json"
DECISION = "decisao_unica_temporal_antecipada_g4_g5_20261031"
REFERENCE = "B02-G4-G5-TEMP-SUCCESSOR-20261031-01"
WINDOW_START = datetime.fromisoformat("2026-11-01T00:00:00+00:00")
WINDOW_END = datetime.fromisoformat("2026-11-15T00:00:00+00:00")
BRIDGE = ROOT / "tools/b02_g5_v5_local_bridge.py"
G4 = "tools/b02_g4_g5_temporal_successor_runner.py"
G5 = "tools/b02_g5_v3_temporal_materialize_candidate.py"
G4_BLOB = "604fce993b755c7d9d9427ef9b874fa9858fec6f"
G5_BLOB = "e658a51bd9f4876cd2ffa2ec2b233b092f86f60b"


def stop(code):
    raise RuntimeError("STOP_B02_HANDOFF_" + code)


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       text=True, timeout=25)
    if p.returncode:
        stop("GIT_UNAVAILABLE")
    return p.stdout.strip()


def verify():
    if git("branch", "--show-current") != "candidate/g5-v5-publicacao-local":
        stop("WRONG_BRANCH")
    if git("status", "--porcelain", "--untracked-files=no"):
        stop("TRACKED_DIRTY")
    if git("hash-object", str(PLAN.relative_to(ROOT))) != git(
        "rev-parse", "HEAD:" + str(PLAN.relative_to(ROOT))
    ):
        stop("RATIFICATION_FILE_CHANGED")
    q = json.loads(PLAN.read_text(encoding="utf-8-sig"))[DECISION]
    if (q.get("reference") != REFERENCE or q.get("approved") is not True
        or q.get("status") != "RATIFICADA_PROSPECTIVAMENTE"
        or q.get("approved_by") != "Miguel"
        or not q.get("ratification_source")):
        stop("RATIFICATION_NOT_RECONCILED")
    if (q.get("window_utc", {}).get("from") != WINDOW_START.isoformat()
        or q.get("window_utc", {}).get("until") != WINDOW_END.isoformat()
        or q.get("g4", {}).get("successor_runner_git_blob") != G4_BLOB
        or q.get("g5", {}).get("materializer_git_blob") != G5_BLOB):
        stop("SOURCE_PIN_OR_WINDOW_CHANGED")
    for name, expected in ((G4, G4_BLOB), (G5, G5_BLOB)):
        if git("rev-parse", "HEAD:" + name) != expected or git(
            "hash-object", name
        ) != expected:
            stop("SOURCE_CHANGED_" + name.rsplit("/", 1)[-1])
    approved = datetime.fromisoformat(q["approved_at_utc"])
    now = datetime.now(timezone.utc)
    if approved.tzinfo is None or not approved <= now:
        stop("INVALID_PROSPECTIVE_RATIFICATION_TIME")
    if not WINDOW_START <= now < WINDOW_END:
        stop("OUTSIDE_RATIFIED_G4_WINDOW")
    return q


def invoke(target, *args):
    p = subprocess.run([sys.executable, str(BRIDGE), target, *args],
                       cwd=ROOT, capture_output=True, text=True)
    if p.returncode:
        # Explicit failure, including unknown COMMIT ACK: NEVER auto-retry.
        print(p.stderr[-1100:], file=sys.stderr)
        stop("CHILD_FAILURE_NO_RETRY_" + target.rsplit("/", 1)[-1])
    rows = []
    for line in p.stdout.splitlines():
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                stop("INVALID_CHILD_JSON")
    return rows


def main():
    verify()
    if (ROOT / "POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json").exists():
        stop("V3_CANDIDATE_ALREADY_EXISTS_PRESERVE_NO_RETRY")
    g4 = invoke(G4, "--execute", "--approval-reference", REFERENCE)
    units = [r for r in g4 if r.get("status") == "FOUR_RECORDS_RECONCILED"]
    if len(units) != 1:
        stop("G4_FOUR_RECORD_READBACK_NOT_REPORTED_NO_G5")
    unit = units[0]
    exact = ("execution", "activation", "generation", "outbox")
    for name in exact:
        if unit.get(name + "_id") != "B02-05ede-" + name + "-v4":
            stop("G4_RECORD_ID_MISMATCH_" + name)
        value = unit.get(name + "_hash")
        if not isinstance(value, str) or len(value) != 64 or any(
            c not in "0123456789abcdef" for c in value
        ):
            stop("G4_RECORD_HASH_MISSING_" + name)
    g5 = invoke(G5)
    drafts = [r for r in g5 if r.get("status") == "G5_V3_DRAFT_READY_FOR_NEW_OWN_AUDIT_ONLY"]
    if len(drafts) != 1 or drafts[0].get("g4_activation_hash") != unit["activation_hash"]:
        stop("G5_DRAFT_NOT_LINKED_TO_RECONCILED_G4")
    print(json.dumps({
        "status": "G4_V4_PHYSICAL_RECONCILED_G5_V3_DRAFT_ONLY",
        "g4_activation_id": unit["activation_id"],
        "g4_activation_hash": unit["activation_hash"],
        "g5_v3_draft_sha256": drafts[0]["draft_file_sha256"],
        "g5_installed": False, "institutional_review_complete": False,
        "b02_closed": False, "automatic_retries": 0,
        "next": "OWN_G5_V3_INDEPENDENT_REVIEW_AND_REAL_SEPARATE_GATES"
    }, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError,
            subprocess.TimeoutExpired) as exc:
        print(str(exc)[:1100], file=sys.stderr)
        sys.exit(2)
