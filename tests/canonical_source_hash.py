"""Canonical SHA-256 helper for tracked LF source files in test guards."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_ATTRIBUTES = {
    "text": "set",
    "eol": "lf",
    "filter": "unspecified",
    "working-tree-encoding": "unspecified",
}


def canonical_source_sha256(path: str | Path) -> str:
    """Hash current worktree source after the sole permitted CRLF-to-LF fold."""
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = REPO_ROOT / candidate
    try:
        resolved = candidate.resolve(strict=True)
        relative = resolved.relative_to(REPO_ROOT)
    except (OSError, ValueError) as exc:
        raise ValueError("source path must be an existing file inside the repo") from exc
    if not resolved.is_file():
        raise ValueError("source path must identify a file")

    git_path = relative.as_posix()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", git_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0 or tracked.stdout.strip() != git_path:
        raise ValueError("source path must be tracked by git")

    attributes = subprocess.run(
        [
            "git", "check-attr", "-z", "text", "eol", "filter",
            "working-tree-encoding", "--", git_path,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if attributes.returncode != 0:
        raise ValueError("git attributes could not be established")
    fields = attributes.stdout.split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    if len(fields) != 12:
        raise ValueError("git attributes response is ambiguous")
    observed: dict[str, str] = {}
    for index in range(0, len(fields), 3):
        item_path, name, value = fields[index:index + 3]
        if item_path != git_path or name in observed:
            raise ValueError("git attributes response is ambiguous")
        observed[name] = value
    if observed != _EXPECTED_ATTRIBUTES:
        raise ValueError(f"source attributes are not canonical: {observed!r}")

    raw = resolved.read_bytes()
    canonical = raw.replace(b"\r\n", b"\n")
    if b"\r" in canonical:
        raise ValueError("source contains an ambiguous carriage return")
    return hashlib.sha256(canonical).hexdigest().upper()
