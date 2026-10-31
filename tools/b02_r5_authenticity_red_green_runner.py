#!/usr/bin/env python3
"""B02 R5: 5 focused RED-before/GREEN-after tests; no DB/network/files modified."""
from __future__ import annotations
import re
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RED = "92806515b652b3a757020ac594e670527e73d24d"
SERVICE = "app/services/enterprise_b02_noncredential_acquisition.py"
TEST = "tests/test_b02_r5_authenticity_before_flush_red.py"
FROZEN = "tests/test_enterprise_b02_r4g_contract.py"
RED_SERVICE_BLOB = "723448cb7f23b659f5131c5535d5238c2fcf0fd4"
GREEN_SERVICE_BLOB = "1555fe2be00c6f7e0249bfe83e504a86942a83a9"
TEST_BLOB = "ebfd19184f05017314ed22ed03209fbcf4c3efd7"
FROZEN_BLOB = "09f8778d53eaeda3d2daf6c1e174597c122feac9"


def stop(reason):
    raise RuntimeError("STOP_B02_R5_RED_GREEN_" + reason)


def git(*args):
    proc = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, timeout=30)
    if proc.returncode: stop("GIT_SOURCE")
    return proc.stdout.strip()


def check_ref(ref, path, expected):
    if git("rev-parse", f"{ref}:{path}").decode("ascii") != expected:
        stop("PIN_DIVERGENCE_" + path.replace("/", "_"))


def run_tests(test_root, pattern):
    return subprocess.run(
        [sys.executable, "-B", "-m", "unittest", "discover",
         "-s", str(test_root), "-p", pattern, "-q"],
        cwd=ROOT, capture_output=True, text=True, timeout=100,
    )


def main():
    check_ref(RED, SERVICE, RED_SERVICE_BLOB)
    check_ref(RED, TEST, TEST_BLOB)
    check_ref("HEAD", SERVICE, GREEN_SERVICE_BLOB)
    check_ref("HEAD", TEST, TEST_BLOB)
    check_ref("HEAD", FROZEN, FROZEN_BLOB)
    for path, expected in ((SERVICE, GREEN_SERVICE_BLOB), (TEST, TEST_BLOB),
                           (FROZEN, FROZEN_BLOB)):
        if git("hash-object", path).decode("ascii") != expected:
            stop("LOCAL_TRACKED_SOURCE_CHANGED_" + path.replace("/", "_"))
    if subprocess.run(["git", "diff", "--check", RED, "HEAD", "--", SERVICE, TEST],
                      cwd=ROOT, capture_output=True, timeout=30).returncode:
        stop("DIFF_CHECK")
    with tempfile.TemporaryDirectory(prefix="solveris-r5-red-only-") as temp:
        isolated = Path(temp)
        for name in (SERVICE, TEST):
            destination = isolated / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(git("show", f"{RED}:{name}"))
        red = run_tests(isolated / "tests", Path(TEST).name)
    red_output = red.stderr + red.stdout
    if (red.returncode == 0 or
            re.search(r"Ran 5 tests", red_output) is None or
            "FAILED" not in red_output):
        stop("BASELINE_RED_NOT_REPRODUCED")
    print("R5_AUTHENTICITY_TEST_ONLY_COMMIT_RED_REPRODUCED")
    green = run_tests(ROOT / "tests", Path(TEST).name)
    green_output = green.stderr + green.stdout
    if green.returncode or not re.search(r"Ran 5 tests", green_output):
        print(green_output[-2000:])
        stop("NEW_CONTRACT_NOT_GREEN")
    print("R5_AUTHENTICITY_5_NEW_TESTS_PASS")
    frozen = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", FROZEN],
        cwd=ROOT, capture_output=True, text=True, timeout=150,
    )
    if frozen.returncode:
        print((frozen.stdout + frozen.stderr)[-1500:])
        stop("FROZEN_R4G_CONTRACT_REGRESSION")
    print("R5_FROZEN_R4G_CONTRACT_PASS")
    check_ref("HEAD", FROZEN, FROZEN_BLOB)
    if git("hash-object", FROZEN).decode("ascii") != FROZEN_BLOB:
        stop("FROZEN_CONTRACT_CHANGED_AFTER_TEST")
    print("R5_FROZEN_R4G_CONTRACT_BLOB_UNCHANGED")
    print("R5_FOCUSED_RED_GREEN_SOURCE_ONLY_PASS_NO_POSTGRESQL")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
        print(str(e)[:220])
        sys.exit(2)
