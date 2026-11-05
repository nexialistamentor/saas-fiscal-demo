"""B02 R5 V3 installer→source→transaction bridge (preparation only).

This is NOT an installer or SQL-privileged operation. 0064/0065 stay in
migrations/candidates until an independently authorised installer applies them.
It never grants authority, issues signatures, produces synthetic G4 origin, or
changes the V5 harness.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from collections.abc import Mapping

from sqlalchemy import text

from app.services.enterprise_b02_g5_two_unit_stage import C3_DOCUMENTS
from tools.b02_r5_g5_v3_authorized_transaction import (
    execute_authorized_r5, validate_approval,
)

CANDIDATES = (
    ("migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py",
     "968c092e70e91b6be3d55bfab7a2dd4fc5256669",
     "7a42f583a4ca604a697a2e9a11cda7ffdb88d92c40bfbd181e408da736293074",
     "0064_b02_g5_controlled_real_cas", "0063_adr020_policy_activation_atomicity"),
    ("migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py",
     "7f3fbf53217aecfe045280f343982ece5a72d60c",
     "fbe2c12119572df4e835f0144b7ea25ca4bb92f22471e57dd6e616d179f2f507",
     "0065_b02_g5_one_shot_real", "0064_b02_g5_controlled_real_cas"),
)
V5_HARNESS = ("tools/b02_g5_v5_atomic_transaction_harness.py",
              "2b195ee3fd3de0040f813af03e10733953f84b7d")
_SQL_0064 = "a9a76c47f6426666ee17094537cb66451623bafe17dc15a961458ef58c43e787"
_SQL_0065 = "d1d359f0be1828fbd8c81fffc0698172931f47c5b4e6d2e53c2c35c1b479d662"
SHA = re.compile(r"[0-9a-f]{64}\Z")

def stop(code):
    raise ValueError("STOP_B02_R5_INSTALL_BRIDGE_" + code)

def _git(root: Path, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                       text=True, timeout=30)
    if p.returncode:
        stop("PIN_GIT_READ_FAILED")
    return p.stdout.strip()

def pinned_install_plan(root: Path):
    """Offline immutable source inventory for a separate approved installer."""
    if not root.is_dir() or root.is_symlink():
        stop("ROOT_MISSING_OR_SYMLINK")
    files = []
    for path, blob, digest, revision, down_revision in CANDIDATES:
        p = root / path
        if not p.is_file() or p.is_symlink():
            stop("CANDIDATE_FILE_MISSING")
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            stop("CANDIDATE_BYTES_DIVERGENT")
        if _git(root, "hash-object", "--", path) != blob or _git(root, "rev-parse", "HEAD:" + path) != blob:
            stop("CANDIDATE_GIT_BLOB_DIVERGENT")
        tree = ast.parse(raw)
        declarations = {}
        sql = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("revision", "down_revision", "_SQL"):
                    declarations[node.targets[0].id] = ast.literal_eval(node.value)
        if declarations.get("revision") != revision or declarations.get("down_revision") != down_revision:
            stop("MIGRATION_CHAIN_DIVERGENT")
        sql = declarations.get("_SQL")
        sql_digest = hashlib.sha256(sql.encode("utf-8")).hexdigest() if isinstance(sql,str) else None
        if sql_digest != (_SQL_0064 if revision.startswith("0064") else _SQL_0065):
            stop("SQL_CANDIDATE_DIVERGENT")
        files.append({"path": path, "git_blob": blob, "file_sha256": digest,
                      "sql_sha256": sql_digest, "revision": revision, "down_revision": down_revision})
    guard_path, guard_blob = V5_HARNESS
    if _git(root, "hash-object", "--", guard_path) != guard_blob or (
        _git(root, "rev-parse", "HEAD:" + guard_path) != guard_blob
    ):
        stop("V5_HARNESS_GUARD_CHANGED")
    return {
        "schema": "SOLVERIS_B02_R5_G5_V3_INSTALL_PREVIEW_V1",
        "status": "PREPARATION_ONLY_NOT_INSTALLATION",
        "files": files,
        "v5_guard_git_blob": guard_blob,
        "database": "solveris_b02_r4g_test", "writer": "solveris_b02_writer",
        "pg_server_version_num": 170010,
        "initial_alembic": "0063_adr020_policy_activation_atomicity",
        "target_alembic": "0065_b02_g5_one_shot_real",
        "installer_must_separately_verify": [
            "reviewer_own_eligible_act", "final_g5_policy_sha256",
            "g5_ratification", "prospective_native_root_and_elf",
            "installer_identity_owner_acls", "migration_0063_to_0064_to_0065",
            "independent_0065_schema_native_precommit_readback",
            "specific_one_shot_commit_authority",
        ],
        "safe_to_run_alembic_upgrade_head_now": False,
        "protected_writes": 0,
    }

def inspect_physical_revision_readonly(conn):
    """On an existing read-only transaction; never execute migrations."""
    ident = tuple(conn.execute(text("""
        SELECT current_database(), current_setting('server_version_num')::integer,
               current_setting('transaction_read_only')
    """)).one())
    if ident != ("solveris_b02_r4g_test", 170010, "on"):
        stop("EXACT_READONLY_PG1710_DATABASE_REQUIRED")
    revision = conn.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one()
    if revision not in ("0063_adr020_policy_activation_atomicity",
                        "0064_b02_g5_controlled_real_cas",
                        "0065_b02_g5_one_shot_real"):
        stop("UNKNOWN_PHYSICAL_ALEMBIC_REVISION")
    reserve_table = conn.execute(text(
        "SELECT to_regclass('public.b02_g5_operational_approval_uses')::text")).scalar_one()
    functions = {
        "reserve": conn.execute(text("SELECT to_regprocedure("
                "'public.b02_g5_reserve_operational_decision(character varying,character varying,character,character)')::text"
            )).scalar_one(),
        "capability": conn.execute(text("SELECT to_regprocedure("
                "'public.b02g5_assert_transaction_capability()')::text"
            )).scalar_one(),
    }
    if revision == "0063_adr020_policy_activation_atomicity" and reserve_table is not None:
        stop("PARTIAL_OR_UNEXPECTED_INSTALLED_ONE_SHOT_STOP")
    if revision == "0065_b02_g5_one_shot_real" and (
            reserve_table is None or any(v is None for v in functions.values())):
        stop("0065_INSTALLED_BUT_STRUCTURES_MISSING_STOP")
    return {
        "status": "REVISION_READONLY_OBSERVED_NO_INSTALLATION",
        "alembic_revision": revision,
        "reserve_table_present": reserve_table is not None,
        "required_functions_present": {k: bool(v) for k, v in functions.items()},
        "commit_authorized": False, "writes": 0,
    }

def real_units_from_custody(custody_root: Path, sources: Mapping, *, approved_policy_hash: str):
    """Read exact CAS only from private custody, without copying or generating bytes.

    sources maps TWO document IDs to exact caller-supplied fields:
      cas_relpath, binding, start, build_evidence, stage_authenticity
    The last two are real independently supplied callables, not this tool's
    declarations or synthetic fixtures.
    """
    if not isinstance(approved_policy_hash, str) or not SHA.fullmatch(approved_policy_hash):
        stop("APPROVED_POLICY_HASH_REQUIRED")
    if not isinstance(sources, Mapping) or set(sources) != set(C3_DOCUMENTS):
        stop("EXACT_TWO_C3_SOURCE_ITEMS_REQUIRED")
    if custody_root.is_symlink() or not custody_root.is_dir():
        stop("PRIVATE_CUSTODY_DIRECTORY_REQUIRED")
    root = custody_root.resolve(strict=True)
    units = []
    required = {"cas_relpath", "binding", "start", "build_evidence", "stage_authenticity"}
    for doc_id in sorted(C3_DOCUMENTS):
        s = sources[doc_id]
        if not isinstance(s, Mapping) or set(s) != required:
            stop("EXACT_SOURCE_FIELDS_REQUIRED")
        b = s["binding"]
        if not isinstance(b, Mapping) or b.get("mode") != "LOCAL_CAS_INCORPORATION":
            stop("CURRENT_REAL_BINDING_REQUIRED")
        if not isinstance(b.get("provenance"), Mapping) or b["provenance"].get("synthetic_only") is not False:
            stop("SYNTHETIC_INPUT_FORBIDDEN")
        if (not isinstance(b.get("security_policy_binding"), Mapping)
                or b["security_policy_binding"].get("policy_hash") != approved_policy_hash
                or b.get("sanitization_policy_binding") != b["security_policy_binding"]):
            stop("FINAL_POLICY_BINDING_NOT_APPLICABLE")
        if not callable(s["build_evidence"]) or not callable(s["stage_authenticity"]):
            stop("REAL_EXTERNAL_EVIDENCE_CALLBACKS_REQUIRED")
        relative = s["cas_relpath"]
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            stop("PRIVATE_CAS_RELATIVE_PATH_REQUIRED")
        path = root / relative
        if path.is_symlink() or not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
            stop("CAS_OUTSIDE_PRIVATE_CUSTODY")
        digest, size = C3_DOCUMENTS[doc_id]
        def read_cas(path=path, digest=digest, size=size):
            # Every call re-opens and recomputes: no cached or fabricated bytes.
            if path.is_symlink() or not path.is_file() or not path.resolve(strict=True).is_relative_to(root):
                stop("CAS_INTEGRITY_AT_READ")
            raw = path.read_bytes()
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                stop("CAS_BYTES_NOT_AUTHENTIC")
            return raw
        # Immediate preparation check, then the stage helper calls it once more.
        read_cas()
        units.append({"document_id": doc_id, "binding": b, "start": s["start"],
                      "read_cas": read_cas, "build_evidence": s["build_evidence"],
                      "stage_authenticity": s["stage_authenticity"]})
    return units

def execute_after_authorised_installation(engine, *, installation_receipt: Mapping,
                                           approval: Mapping, units,
                                           independently_verify_acts,
                                           competent_sign_manifest,
                                           specifically_authorized_commit=False):
    """Bridge an independently verified installer receipt to the existing R5 runner.

    No receipt is self-certifying: independently_verify_acts MUST validate the
    institutional chain and installer/root/ELF, then the runner and native
    PostgreSQL guards independently enforce the actual DB state and signature.
    """
    validate_approval(approval)
    if not isinstance(installation_receipt, Mapping) or (
        installation_receipt.get("target_revision") != "0065_b02_g5_one_shot_real"
        or installation_receipt.get("database") != "solveris_b02_r4g_test"
        or installation_receipt.get("root_sha256") != approval["native_root_sha256"]
        or installation_receipt.get("elf_sha256") != approval["native_elf_sha256"]
        or installation_receipt.get("install_act_sha256") != approval["install_act_sha256"]
        or installation_receipt.get("sql_0064_sha256") != _SQL_0064
        or installation_receipt.get("sql_0065_sha256") != _SQL_0065
        or installation_receipt.get("independent_readback") is not True
    ):
        stop("PHYSICAL_INSTALLER_RECEIPT_MISSING_OR_INCONGRUENT")
    return execute_authorized_r5(
        engine, units=units, approval=approval,
        independently_verify_acts=independently_verify_acts,
        competent_sign_manifest=competent_sign_manifest,
        specifically_authorized_commit=specifically_authorized_commit,
    )

def main():
    import argparse
    p = argparse.ArgumentParser(description="Read-only/offline 0064-0065 source preflight")
    p.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = p.parse_args()
    print(json.dumps(pinned_install_plan(args.repo), sort_keys=True, ensure_ascii=False))

if __name__ == "__main__":
    main()
