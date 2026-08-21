"""Proof that the MEI publication/reachability census is repeatable."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def _census_bytes(seed: str) -> bytes:
    script = (
        "import json; "
        "from app.scripts.mei_publication_reachability_census import build_census; "
        "print(json.dumps(build_census(), sort_keys=True, separators=(',', ':'), "
        "ensure_ascii=False))"
    )
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = seed
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=env,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def test_census_is_byte_identical_across_hash_seeds():
    outputs = [_census_bytes(seed) for seed in ("1", "7", "41")]

    assert outputs[0]
    assert outputs[0] == outputs[1] == outputs[2]

    hashes = [hashlib.sha256(payload).hexdigest() for payload in outputs]
    assert len(set(hashes)) == 1
