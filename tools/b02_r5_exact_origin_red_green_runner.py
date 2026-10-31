#!/usr/bin/env python3
"""B02 R5 exact G4 origin: replay immutable RED, then current GREEN.

No SQL, credentials, user source PDFs, Git mutation or database connection.
The previous five-case RED/GREEN contract is treated as frozen.
"""
from __future__ import annotations
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
RED="3315be5c0386383fc7d20a7e06f7d9ddead223a5"
SERVICE="app/services/enterprise_b02_noncredential_acquisition.py"
TEST="tests/test_b02_r5_exact_origin_guard_red.py"
PREVIOUS="tests/test_b02_r5_authenticity_before_flush_red.py"
FROZEN="tests/test_enterprise_b02_r4g_contract.py"
RED_BLOB="1555fe2be00c6f7e0249bfe83e504a86942a83a9"
GREEN_BLOB="849e95c61e14859ffd24d7c0dcdc228c81b83866"
TEST_BLOB="614cd48e13683bc049d19289c9d7264523ef5dc1"
PREVIOUS_BLOB="ebfd19184f05017314ed22ed03209fbcf4c3efd7"
FROZEN_BLOB="09f8778d53eaeda3d2daf6c1e174597c122feac9"

def stop(msg): raise RuntimeError("STOP_B02_R5_EXACT_ORIGIN_"+msg)

def git(*args):
    r=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,timeout=40)
    if r.returncode:stop("GIT_QUERY")
    return r.stdout.strip()

def pin(ref,path,expected):
    if git("rev-parse",f"{ref}:{path}").decode("ascii")!=expected:
        stop("REF_PIN_DIVERGED_"+path.replace("/","_"))

def tests(root,name):
    return subprocess.run(
        [sys.executable,"-B","-m","unittest","discover",
         "-s",str(root/"tests"),"-p",name,"-q"],
        cwd=ROOT,text=True,capture_output=True,timeout=120)

def main():
    for path,ref_hash,head_hash in [
        (SERVICE,RED_BLOB,GREEN_BLOB),
        (TEST,TEST_BLOB,TEST_BLOB),
        (PREVIOUS,PREVIOUS_BLOB,PREVIOUS_BLOB),
        (FROZEN,FROZEN_BLOB,FROZEN_BLOB)]:
        pin(RED,path,ref_hash);pin("HEAD",path,head_hash)
        if git("hash-object",path).decode("ascii")!=head_hash:
            stop("LOCAL_SOURCE_CHANGED_"+path.replace("/","_"))
    r=subprocess.run(["git","diff","--check",RED,"HEAD","--",SERVICE,TEST,PREVIOUS,FROZEN],
                     cwd=ROOT,capture_output=True,timeout=30)
    if r.returncode:stop("DIFF_CHECK")
    with tempfile.TemporaryDirectory(prefix="solveris-r5-g4-exact-red-") as d:
        tmp=Path(d)
        for path in (SERVICE,TEST,PREVIOUS):
            destination=tmp/path
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(git("show",f"{RED}:{path}"))
        red=tests(tmp,Path(TEST).name)
    out=red.stdout+red.stderr
    if red.returncode==0 or "Ran 4 tests" not in out or "FAILED" not in out:
        print(out[-900:]);stop("RED_NOT_REPRODUCED")
    print("R5_G4_EXACT_NEGATIVE_BASELINE_RED_REPRODUCED")
    green=tests(ROOT,Path(TEST).name)
    if green.returncode or "Ran 4 tests" not in green.stdout+green.stderr:
        print((green.stdout+green.stderr)[-1800:]);stop("FOUR_NEGATIVE_GUARDS_NOT_GREEN")
    print("R5_G4_EXACT_FOUR_NEGATIVE_GUARDS_PASS")
    prior=tests(ROOT,Path(PREVIOUS).name)
    if prior.returncode or "Ran 5 tests" not in prior.stdout+prior.stderr:
        print((prior.stdout+prior.stderr)[-1800:]);stop("PRIOR_FIVE_CONTRACT_REGRESSION")
    print("R5_PRIOR_FIVE_CONTRACTS_REMAIN_PASS")
    frozen=subprocess.run([sys.executable,"-B","-m","pytest","-q",FROZEN],
                          cwd=ROOT,capture_output=True,text=True,timeout=180)
    if frozen.returncode:
        print((frozen.stdout+frozen.stderr)[-1800:]);stop("ORIGINAL_R4G_REGRESSION")
    print("R5_ORIGINAL_R4G_CONTRACT_PASS")
    for path,expected in [(SERVICE,GREEN_BLOB),(TEST,TEST_BLOB),
                          (PREVIOUS,PREVIOUS_BLOB),(FROZEN,FROZEN_BLOB)]:
        if git("hash-object",path).decode("ascii")!=expected:stop("POST_TEST_FILE_CHANGED")
    print("R5_G4_EXACT_RED_GREEN_CONTRACTS_UNCHANGED_NO_POSTGRESQL")

if __name__=="__main__":
    try:main()
    except (RuntimeError,subprocess.TimeoutExpired,OSError) as e:
        print(str(e)[:240]);sys.exit(2)
