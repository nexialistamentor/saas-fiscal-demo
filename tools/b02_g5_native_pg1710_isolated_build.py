#!/usr/bin/env python3
"""B02/G5 reproducible PG17.10 *isolated* native build, never installation.

Requires an independently approved successor root header with exact 64-hex
SHA and exact G5 successor policy hash. Neither legacy V1 root, key, protected
Docker volume nor live DB is read by this utility. Produces ELF and its audit
summary only after actual ABI/version, dynamic symbol and hash checks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCES=[
 ROOT/"native/g5/historical_20261022/b02_precommit_guard.c",
 ROOT/"native/g5/historical_20261022/b02_g5_native_signature.c",
]
LEGACY_HEADER=ROOT/"native/g5/historical_20261022/b02_g5_approved_roots.h"
ELF_NAME="b02_g5_native_REAL_CLOSED.so"
REQUIRED_SYMBOLS=("_PG_init","b02g5_register_real_precommit",
                  "b02g5_assert_signature","b02g5_native_profile")
DOCKERFILE="""FROM postgres:17.10-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc libc6-dev make binutils file libssl-dev postgresql-server-dev-17 \\
 && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY b02_precommit_guard.c b02_g5_native_signature.c b02_g5_approved_roots.h ./
RUN set -eu; \\
    test "$(pg_config --version)" = "PostgreSQL 17.10"; \\
    case "$(dpkg-query -W -f='${Version}' postgresql-server-dev-17)" in 17.10*) ;; *) echo STOP_PG1710_SERVER_HEADERS_MISMATCH >&2; exit 33;; esac; \\
    gcc -shared -fPIC -O2 -Wall -Wextra -Wno-unused-parameter \\
        -I"$(pg_config --includedir-server)" \\
        b02_precommit_guard.c b02_g5_native_signature.c \\
        -o b02_g5_native_REAL_CLOSED.so -lcrypto; \\
    file b02_g5_native_REAL_CLOSED.so | grep -q 'ELF 64-bit'; \\
    readelf -Ws b02_g5_native_REAL_CLOSED.so | grep -q b02g5_assert_signature; \\
    readelf -Ws b02_g5_native_REAL_CLOSED.so | grep -q b02g5_register_real_precommit; \\
    sha256sum b02_g5_native_REAL_CLOSED.so
"""


def stop(reason):
    raise RuntimeError("STOP_G5_PG1710_NATIVE_"+reason)


def check_sha_file(path:Path,sha:str):
    if not re.fullmatch("[a-f0-9]{64}",sha):
        stop("INVALID_HASH_ARGUMENT")
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=sha:stop("SOURCE_SHA_MISMATCH_"+path.name)
    return actual


def check_input(header:Path,sha:str,policy_hash:str):
    if not header.is_file() or not re.fullmatch("[0-9a-f]{64}",policy_hash):
        stop("EXACT_HEADER_OR_POLICY_HASH_REQUIRED")
    if header.resolve()==LEGACY_HEADER.resolve():
        stop("EXPIRED_V1_ROOT_FORBIDDEN")
    if not header.name.endswith(".h"):
        stop("ROOT_MUST_BE_C_HEADER")
    if policy_hash in ("57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa",
                       "007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf"):
        stop("EXPIRED_G5_V1_OR_V2_POLICY_FORBIDDEN")
    check_sha_file(header,sha)
    source=header.read_text(encoding="utf8")
    if ("SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE" not in source
       or policy_hash not in source
       or "57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa" in source):
        stop("ROOT_SUBJECT_NOT_SUCCESSOR")
    if not all(p.is_file() for p in SOURCES):
        stop("NATIVE_SOURCES_MISSING")
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in SOURCES}


def command(*args,timeout=600):
    p=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if p.returncode:
        stop("COMMAND_FAILED_"+Path(args[0]).name+":"+p.stderr[-400:])
    return p.stdout


def build(header:Path,header_sha:str,policy_hash:str,out:Path):
    source_hashes=check_input(header,header_sha,policy_hash)
    if not shutil.which("docker"):stop("DOCKER_MISSING")
    if out.exists():stop("OUTPUT_ALREADY_EXISTS_PRESERVE")
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="solveris-g5-pg1710-") as temp:
        tmp=Path(temp)
        for p in SOURCES: shutil.copyfile(p,tmp/p.name)
        shutil.copyfile(header,tmp/"b02_g5_approved_roots.h")
        (tmp/"Dockerfile").write_text(DOCKERFILE,encoding="utf8")
        tag="solveris-b02-g5-pg1710-isolated:"+hashlib.sha256(
            (policy_hash+header_sha).encode()).hexdigest()[:12]
        ident=None
        try:
            command("docker","build","--pull","--no-cache","-q","-t",tag,str(tmp),timeout=1200)
            # Docker build contains NO private volume mount, docker run is network-isolated.
            verify=command("docker","run","--rm","--network","none",
                "--entrypoint","sh",tag,"-ceu",
                "test \"$(pg_config --version)\" = 'PostgreSQL 17.10'; "
                "readelf -Ws /work/"+ELF_NAME+"; sha256sum /work/"+ELF_NAME)
            if not all(x in verify for x in REQUIRED_SYMBOLS):
                stop("REQUIRED_ELF_SYMBOLS_MISSING")
            ident=command("docker","create","--network","none",
                          "--entrypoint","sh",tag,"-c","true").strip()
            command("docker","cp",ident+":/work/"+ELF_NAME,str(out))
            elf_hash=hashlib.sha256(out.read_bytes()).hexdigest()
            report={
                "status":"PG1710_NATIVE_ELF_COMPILED_ISOLATED_NOT_INSTALLED",
                "pg_config":"PostgreSQL 17.10",
                "policy_hash":policy_hash,
                "successor_header_sha256":header_sha,
                "source_sha256":source_hashes,
                "elf_path":str(out),
                "elf_sha256":elf_hash,
                "required_symbols":list(REQUIRED_SYMBOLS),
                "has_real_key_signature_validation":False,
                "approved_for_protected_installation":False,
                "protected_db_access":False,
            }
            return report
        finally:
            if ident is not None:
                subprocess.run(["docker","rm","-f",ident],capture_output=True)
            subprocess.run(["docker","image","rm","-f",tag],capture_output=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--header",type=Path,required=True)
    ap.add_argument("--header-sha256",required=True)
    ap.add_argument("--policy-hash",required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    print(json.dumps(build(a.header,a.header_sha256,a.policy_hash,a.out),
        sort_keys=True,ensure_ascii=False))


if __name__=="__main__":
    try: main()
    except Exception as e:
        print(str(e),file=__import__("sys").stderr)
        raise SystemExit(2)
