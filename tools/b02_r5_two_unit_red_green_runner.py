#!/usr/bin/env python3
"""B02 R5 two-C3-unit contract, immutable RED / GREEN, read-only local sources.

No user PDFs, PostgreSQL, Docker, authentication, SQL execution or Git writes.
"""
from __future__ import annotations
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
RED="d4bb7df1480be5dbc0fe179aa30933ad8ae931b2"
NEW="app/services/enterprise_b02_g5_two_unit_stage.py"
TEST="tests/test_b02_r5_two_unit_stage_red.py"
FROZEN_SOURCE="app/services/enterprise_b02_noncredential_acquisition.py"
OLDER_TEST="tests/test_b02_r5_exact_origin_guard_red.py"
ORIGINAL_TEST="tests/test_b02_r5_authenticity_before_flush_red.py"
PIN_NEW="f538cb5665f86e455d1ff57e24174947384602e7"
PIN_TEST="756f78582369925e66898d5becdc8b5fc7927ce9"
PIN_FROZEN="849e95c61e14859ffd24d7c0dcdc228c81b83866"
PIN_OLDER="614cd48e13683bc049d19289c9d7264523ef5dc1"
PIN_ORIGINAL="ebfd19184f05017314ed22ed03209fbcf4c3efd7"

def halt(reason):raise RuntimeError("STOP_B02_R5_TWO_UNIT_"+reason)

def git(*args):
    z=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,timeout=40)
    if z.returncode:halt("GIT_READ")
    return z.stdout.strip()

def pinned(path,sha):
    if git("rev-parse","HEAD:"+path).decode()!=sha or git("hash-object",path).decode()!=sha:
        halt("PIN_DIVERGENCE_"+path.replace("/","_"))

def run_test(testdir):
    return subprocess.run(
        [sys.executable,"-B","-m","unittest","discover",
         "-s",str(testdir),"-p",Path(TEST).name,"-q"],
        cwd=ROOT,text=True,capture_output=True,timeout=120)

def main():
    if git("cat-file","-e",f"{RED}^{\u007bcommit\u007d}") is None:
        halt("RED_COMMIT_UNAVAILABLE")
    for path,sha in ((NEW,PIN_NEW),(TEST,PIN_TEST),(FROZEN_SOURCE,PIN_FROZEN),
                     (OLDER_TEST,PIN_OLDER),(ORIGINAL_TEST,PIN_ORIGINAL)):
        pinned(path,sha)
    change=subprocess.run(["git","diff","--check",RED,"HEAD","--",NEW,TEST],
                          cwd=ROOT,capture_output=True,timeout=30)
    if change.returncode:halt("DIFF_CHECK")
    with tempfile.TemporaryDirectory(prefix="solveris-b02-r5-2units-red-") as temp:
        target=Path(temp)/TEST
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(git("show",f"HEAD:{TEST}"))  # corrected fixture, absent RED implementation
        before=run_test(target.parent)
    if before.returncode==0 or "Ran 5 tests" not in before.stdout+before.stderr or "FAILED" not in before.stdout+before.stderr:
        print((before.stdout+before.stderr)[-900:]);halt("RED_NOT_REPRODUCED")
    print("B02_R5_TWO_UNIT_TEST_ONLY_RED_REPRODUCED")
    after=run_test(ROOT/"tests")
    if after.returncode or "Ran 5 tests" not in after.stdout+after.stderr:
        print((after.stdout+after.stderr)[-2000:]);halt("FIVE_UNIT_CONTRACTS_NOT_GREEN")
    print("B02_R5_TWO_UNIT_FIVE_CONTRACTS_GREEN")
    for path,sha in ((NEW,PIN_NEW),(TEST,PIN_TEST),(FROZEN_SOURCE,PIN_FROZEN),
                     (OLDER_TEST,PIN_OLDER),(ORIGINAL_TEST,PIN_ORIGINAL)):
        pinned(path,sha)
    print("B02_R5_PRIOR_FROZEN_SERVICE_AND_NINE_CONTRACT_BLOBS_UNCHANGED")
    print("B02_R5_TWO_UNIT_SOURCE_ONLY_RED_GREEN_PASS_NO_POSTGRESQL")

if __name__=="__main__":
    try:main()
    except (RuntimeError,OSError,subprocess.TimeoutExpired) as exc:
        print(str(exc)[:250]);sys.exit(2)
