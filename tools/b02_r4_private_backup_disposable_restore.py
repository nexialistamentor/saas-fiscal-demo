#!/usr/bin/env python3
"""B02 R4: real protected-db logical backup and isolated structural restore.

This is an independent technical gate, NOT full ACL/authority restoration, SQL
0064/0065 installation or operational permission. Writes ONLY a new private
directory in LOCALAPPDATA and an isolated Docker container (no network/ports).
Never alters/restarts/replaces existing volumes, source schema or credentials.
"""
from __future__ import annotations
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
         "--format=custom","--compress=0","--no-password","--lock-wait-timeout=10000",
         "-U",ROLE,"-d",bridge.DATABASE]
    with path.open("xb") as handle:
        p=subprocess.run(cmd,stdout=handle,stderr=subprocess.PIPE,timeout=MAX_TIME)
    if p.returncode or not path.stat().st_size:
        stop("DUMP_FAILED_"+p.stderr.decode("utf8",errors="replace")[-250:])
    with path.open("rb") as handle:
        toc=subprocess.run(["docker","exec","-i",bridge.CONTAINER,
                            "pg_restore","--list","-"],
                           stdin=handle,capture_output=True,timeout=120)
    if toc.returncode or b"TOC Entries:" not in toc.stdout:
        stop("ARCHIVE_TOC_INVALID")
    return {"backup_sha256":sha_file(path),"backup_bytes":path.stat().st_size,
            "toc_sha256":hashlib.sha256(toc.stdout).hexdigest()}


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
            subprocess.run(["docker","rm","-f","-v",name],capture_output=True,timeout=60)


def main():
    bridge.validate_checkout(PATH)
    if os.name!="nt":stop("WINDOWS_REQUIRED")
    token=uuid4().hex
    base=Path(os.environ["LOCALAPPDATA"])/"SOLVERIS"/"B02R4Privado"/token
    verify_private_directory(base,token)
    backup=base/"protected_pg1710.dump"
    report=base/"evidence.json"
    with bridge.managed_container():
        info=bridge.container_info()
        image=info.get("Image","")
        version=invoke(["docker","exec",bridge.CONTAINER,"postgres","--version"])
        if "PostgreSQL) 17.10" not in version:
            stop("SOURCE_NOT_PG1710")
        before=snapshot(ROLE)
        metadata=dump_to_private(backup)
        result=disposable_restore(backup,image,token)
        if before!=result["counts"]:
            stop("DISPOSABLE_RESTORE_COUNTS_DIVERGE")
    output={"status":"R4_DISPOSABLE_STRUCTURAL_RESTORE_MATCHED",
        "scope":"NOT_FULL_R4_ACL_OR_NATIVE_OR_CAS_APPROVAL",
        "source_database":bridge.DATABASE,"source_role":ROLE,
        "source_postgres_version":version,"source_image":image,
        "protected_database_writes":0,"protected_volume_mutations":0,
        "source_count_snapshot":before,
        "backup_location_private":str(backup),
        "private_acl":"CURRENT_USER_AND_SYSTEM_ONLY",
        **metadata,**result}
    report.write_text(json.dumps(output,indent=2,sort_keys=True)+"\n",encoding="utf8")
    print(json.dumps(output,ensure_ascii=False,sort_keys=True))


if __name__=="__main__":
    try:main()
    except Exception as e:
        print(str(e),file=sys.stderr)
        raise SystemExit(2)
