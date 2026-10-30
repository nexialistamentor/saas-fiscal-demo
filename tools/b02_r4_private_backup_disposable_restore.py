#!/usr/bin/env python3
"""B02 R4: real protected-db logical backup and isolated structural restore.

This is an independent technical gate, NOT full ACL/authority restoration, SQL
0064/0065 installation or operational permission. Writes ONLY a new private
directory in LOCALAPPDATA and an isolated Docker container (no network/ports).
Never alters/restarts/replaces existing volumes, source schema or credentials.
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
import time
from uuid import uuid4

import b02_g5_v5_local_bridge as bridge
import b02_g5_v5_institutional_owner_rollback_probe as owner

PATH="tools/b02_r4_private_backup_disposable_restore.py"
ROLE=owner.OWNER
TABLES=("policy_versions","policy_decisions","policy_activations",
        "policy_activation_executions","policy_activation_generations",
        "policy_activation_outbox_events","bootstrap_authority_records",
        "normative_artifacts","extraction_results")
MAX_TIME=900


def stop(reason):
    raise RuntimeError("STOP_B02_R4_"+reason)


def invoke(argv, *, timeout=60, stdin=None):
    p=subprocess.run(argv, input=stdin, capture_output=True, timeout=timeout)
    if p.returncode:
        stop("COMMAND_"+Path(argv[0]).name+"_"+
             p.stderr.decode("utf8",errors="replace")[-250:])
    return p.stdout.decode("utf8",errors="replace").strip()


def verify_private_directory(base:Path, token:str):
    if os.name!="nt" or not re.fullmatch("[a-f0-9]{32}",token):
        stop("NTFS_WINDOWS_AND_UNIQUE_TOKEN_REQUIRED")
    expected=Path(os.environ["LOCALAPPDATA"]).resolve()
    if expected not in base.resolve().parents:
        stop("PRIVATE_PATH_NOT_UNDER_LOCALAPPDATA")
    base.mkdir(parents=True,exist_ok=False)
    sid=invoke(["whoami","/user","/fo","csv","/nh"]).strip()
    m=re.search("S-1-[0-9-]+",sid)
    if not m:stop("WINDOWS_SID_UNAVAILABLE")
    invoke(["icacls",str(base),"/inheritance:r","/grant:r",
            "*"+m.group(0)+":(OI)(CI)F","*S-1-5-18:(OI)(CI)F"])
    return base


def snapshot(role,table_list=TABLES):
    if role != ROLE:
        stop("SNAPSHOT_ROLE")
    prefix="BEGIN READ ONLY;\nSELECT current_database()||'|'||current_user;\n"
    query="SELECT jsonb_build_object(" + ",".join(
      "'"+t+"',(SELECT count(*) FROM public."+t+")" for t in table_list
    ) + ")::text;\nROLLBACK;"
    reply=owner.psql(prefix+query,ROLE)
    if len(reply)!=4 or reply[0]!="BEGIN" or reply[1]!=bridge.DATABASE+"|"+ROLE or reply[3]!="ROLLBACK":
        stop("SOURCE_SNAPSHOT_IDENTITY")
    return json.loads(reply[2])


def sha_file(path:Path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def dump_to_private(path:Path):
    cmd=["docker","exec","-i",bridge.CONTAINER,"pg_dump",
         "--format=custom","--compress=6","--no-password","--lock-wait-timeout=10000",
         "-U",ROLE,"-d",bridge.DATABASE]
    with path.open("xb") as handle:
        p=subprocess.run(cmd,stdout=handle,stderr=subprocess.PIPE,timeout=MAX_TIME)
    if p.returncode or not path.stat().st_size:
        path.unlink(missing_ok=True)
        stop("DUMP_FAILED_"+p.stderr.decode("utf8",errors="replace")[-250:])
    return inspect_private_archive(path)


def inspect_private_archive(path:Path):
    """Validate an existing custom-format archive without creating another dump."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size<6:
        stop("PRIVATE_ARCHIVE_MISSING_OR_UNSAFE")
    with path.open("rb") as handle:
        if handle.read(5)!=b"PGDMP":
            stop("PRIVATE_ARCHIVE_NOT_CUSTOM_FORMAT")
    # pg_restore reads the archive from stdin only when no filename is supplied.
    # Passing '-' as a positional filename was the original TOC failure candidate.
    with path.open("rb") as handle:
        toc=subprocess.run(["docker","exec","-i",bridge.CONTAINER,
                            "pg_restore","--list"],
                           stdin=handle,capture_output=True,timeout=120)
    if toc.returncode:
        stop("ARCHIVE_TOC_COMMAND_FAILED_"+toc.stderr.decode(
             "utf8",errors="replace")[-300:])
    if b"TOC Entries:" not in toc.stdout:
        stop("ARCHIVE_TOC_LIST_MISSING")
    listing=toc.stdout.decode("utf8",errors="replace")
    source_db=re.search(r"(?mi)^;\s*dbname:\s*(\S+)\s*$",listing)
    source_ver=re.search(
        r"(?mi)^;\s*Dumped from database version:\s*(17\.10)(?:\s|$)",listing)
    if not source_db or source_db.group(1)!=bridge.DATABASE:
        stop("ARCHIVE_SOURCE_DATABASE_MISMATCH")
    if not source_ver:
        stop("ARCHIVE_SOURCE_PG1710_NOT_PROVED")
    return {"backup_sha256":sha_file(path),"backup_bytes":path.stat().st_size,
            "toc_sha256":hashlib.sha256(toc.stdout).hexdigest()}


def find_unique_incomplete_private_backup(*,latest_validated=False):
    """Select a preserved backup; multiple candidates require explicit verified-latest opt-in."""
    if os.name!="nt":stop("WINDOWS_REQUIRED")
    root=Path(os.environ["LOCALAPPDATA"])/"SOLVERIS"/"B02R4Privado"
    if not root.is_dir() or root.is_symlink():
        stop("PRIVATE_BACKUP_ROOT_MISSING")
    candidates=[]
    for p in root.iterdir():
        if not re.fullmatch(r"[0-9a-f]{32}",p.name) or not p.is_dir() or p.is_symlink():
            continue
        archive=p/"protected_pg1710.dump"
        if (archive.is_file() and not archive.is_symlink()
            and not (p/"evidence.json").exists()):
            candidates.append(p)
    if not candidates:
        stop("RESUME_NO_INCOMPLETE_PRIVATE_ARCHIVE")
    if len(candidates)==1:
        base=candidates[0]
    elif not latest_validated:
        stop("RESUME_REQUIRES_EXACTLY_ONE_INCOMPLETE_ARCHIVE_FOUND_"+str(len(candidates)))
    else:
        valid=[]
        for candidate in candidates:
            try:
                inspected=inspect_private_archive(candidate/"protected_pg1710.dump")
                valid.append(((candidate/"protected_pg1710.dump").stat().st_mtime_ns,candidate,inspected))
            except (OSError,RuntimeError,subprocess.TimeoutExpired):
                # Preserve and skip invalid candidates. Nothing is unlinked.
                continue
        if not valid:
            stop("RESUME_NO_ARCHIVE_WITH_VERIFIED_PG1710_TOC")
        valid.sort(key=lambda item:item[0],reverse=True)
        if len(valid)>1 and valid[0][0]==valid[1][0]:
            stop("RESUME_VALID_ARCHIVE_TIMESTAMP_AMBIGUOUS")
        base=valid[0][1]
        print(json.dumps({
            "r4_private_resume":"LATEST_VALIDATED_ARCHIVE_SELECTED",
            "selected_token":base.name,
            "validated_archive_sha256":valid[0][2]["backup_sha256"],
            "candidates_found":len(candidates),
            "candidates_valid":len(valid),
            "other_archives_deleted":0,
            "new_pg_dump":False},sort_keys=True),file=sys.stderr)
    if base.resolve().parent != root.resolve():
        stop("RESUME_PRIVATE_PATH_ESCAPE")
    # Check ACL structural integrity; not a claim of full OWNER/ACL restoration.
    invoke(["icacls",str(base),"/verify"])
    return base


def wait_ready(container):
    for _ in range(40):
        p=subprocess.run(["docker","exec",container,"pg_isready","-q",
                          "-U","postgres","-d","postgres"],
                         capture_output=True,timeout=10)
        if p.returncode==0:return
        time.sleep(0.5)
    stop("DISPOSABLE_POSTGRES_NOT_READY")


def disposable_restore(path:Path,image:str,token:str):
    if not re.fullmatch("sha256:[a-f0-9]{64}",image):
        stop("SOURCE_IMAGE_UNPINNED")
    name="solveris-b02-r4-disposable-"+token[:18]
    created=False
    try:
        invoke(["docker","run","-d","--name",name,"--network","none",
                "-e","POSTGRES_HOST_AUTH_METHOD=trust",image],timeout=90)
        created=True
        wait_ready(name)
        invoke(["docker","cp",str(path),name+":/tmp/b02_r4.dump"],timeout=120)
        invoke(["docker","exec",name,"createdb","-U","postgres","b02_r4_restored"],timeout=40)
        invoke(["docker","exec",name,"pg_restore","--exit-on-error",
                "--single-transaction","--no-owner","--no-acl",
                "-U","postgres","-d","b02_r4_restored","/tmp/b02_r4.dump"],timeout=MAX_TIME)
        sql="SELECT jsonb_build_object("+",".join(
            "'"+t+"',(SELECT count(*) FROM public."+t+")" for t in TABLES
        )+")::text;"
        result=invoke(["docker","exec",name,"psql","-X","-At","-w","-v",
                       "ON_ERROR_STOP=1","-U","postgres","-d","b02_r4_restored",
                       "-c",sql],timeout=90)
        counts=json.loads(result)
        return {"counts":counts,"restore_mode":"NO_OWNER_NO_ACL_STRUCTURAL_ONLY",
                "network":"none","host_ports":[],"installed_to_protected":False}
    finally:
        if created:
            cleanup=subprocess.run(["docker","rm","-f","-v",name],
                                   capture_output=True,timeout=60)
            if cleanup.returncode:
                stop("DISPOSABLE_CLEANUP_FAILED")


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--resume-existing",action="store_true",
                    help="Validate and restore an existing private backup; no new pg_dump")
    ap.add_argument("--resume-latest-validated",action="store_true",
                    help="When multiple incomplete backups exist, select latest unique TOC-validated PG17.10 backup")
    opts=ap.parse_args(argv)
    if opts.resume_latest_validated and not opts.resume_existing:
        ap.error("--resume-latest-validated requires --resume-existing")
    bridge.validate_checkout(PATH)
    if os.name!="nt":stop("WINDOWS_REQUIRED")
    base=None
    token=None
    if not opts.resume_existing:
        token=uuid4().hex
        base=Path(os.environ["LOCALAPPDATA"])/"SOLVERIS"/"B02R4Privado"/token
        verify_private_directory(base,token)
    with bridge.managed_container():
        if opts.resume_existing:
            base=find_unique_incomplete_private_backup(
                latest_validated=opts.resume_latest_validated)
            token=base.name
        backup=base/"protected_pg1710.dump"
        report=base/"evidence.json"
        if report.exists():
            stop("R4_EVIDENCE_ALREADY_PRESENT_NO_REPEAT")
        info=bridge.container_info()
        image=info.get("Image","")
        version=invoke(["docker","exec",bridge.CONTAINER,"postgres","--version"])
        if "PostgreSQL) 17.10" not in version:
            stop("SOURCE_NOT_PG1710")
        before=snapshot(ROLE)
        size_reply=owner.psql("""BEGIN READ ONLY;
SELECT pg_database_size(current_database())::text;
ROLLBACK;""",ROLE)
        if len(size_reply)!=3 or size_reply[0]!="BEGIN" or size_reply[2]!="ROLLBACK":
            stop("SOURCE_DATABASE_SIZE_PROTOCOL")
        size_bytes=int(size_reply[1])
        free_bytes=__import__("shutil").disk_usage(base).free
        if size_bytes<0 or (not opts.resume_existing and
                             free_bytes < max(2147483648,2*size_bytes)):
            stop("INSUFFICIENT_PRIVATE_BACKUP_DISK_SPACE")
        metadata=(inspect_private_archive(backup) if opts.resume_existing
                  else dump_to_private(backup))
        result=disposable_restore(backup,image,token)
        if before!=result["counts"]:
            stop("DISPOSABLE_RESTORE_COUNTS_DIVERGE")
    output={"status":"R4_DISPOSABLE_STRUCTURAL_RESTORE_MATCHED",
        "scope":"NOT_FULL_R4_ACL_OR_NATIVE_OR_CAS_APPROVAL",
        "source_database":bridge.DATABASE,"source_role":ROLE,
        "source_postgres_version":version,"source_image":image,
        "protected_database_writes":0,"protected_volume_mutations":0,
        "source_count_snapshot":before,
        "source_database_size_bytes":size_bytes,
        "private_disk_free_prebackup":None if opts.resume_existing else free_bytes,
        "private_disk_free_at_validation":free_bytes,
        "reused_existing_private_archive":bool(opts.resume_existing),
        "backup_location_private":str(backup),
        "private_acl":"ICACLS_APPLIED_NOT_INDEPENDENTLY_RECONCILED",
        **metadata,**result}
    report.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    try:main()
    except Exception as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
