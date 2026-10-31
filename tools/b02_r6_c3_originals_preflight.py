#!/usr/bin/env python3
"""B02 R6: inspect two pre-existing C3 PDFs, read-only; no CAS import or authority."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / 'POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json'
POLICY_ID = 'SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
EXPECTED = {
    '101201900571': ('af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d', 1944929),
    '101202501245': ('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832', 258302),
}
MAX_BYTES = 16 * 1024 * 1024


def stop(message):
    raise RuntimeError('STOP_B02_R6_C3_' + message)


def check_components(path: Path):
    # Inspect each existing path component, including Windows junction/reparse points.
    if not path.is_absolute() or '..' in path.parts:
        stop('ABSOLUTE_UNTRAVERSABLE_PATH_REQUIRED')
    for part in (*reversed(path.parents), path):
        try:
            st = part.lstat()
        except OSError:
            stop('SOURCE_PATH_MISSING_OR_UNREADABLE')
        if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & 0x400:
            stop('SOURCE_REPARSE_OR_SYMLINK_DENIED')


def read_once(path: Path, wanted_size: int):
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        stop('SOURCE_OPEN_FAILED')
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size != wanted_size or before.st_nlink != 1:
            stop('SOURCE_TYPE_SIZE_OR_HARDLINK_DIVERGENCE')
        with os.fdopen(fd, 'rb', closefd=False) as src:
            data = src.read(MAX_BYTES + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, k) != getattr(after, k) for k in fields):
            stop('SOURCE_CHANGED_DURING_READ')
        if len(data) != wanted_size or not data.startswith(b'%PDF-'):
            stop('SOURCE_BYTES_INVALID')
        return hashlib.sha256(data).hexdigest(), (before.st_dev, before.st_ino)
    finally:
        os.close(fd)


def check_policy(policy_path=POLICY, expected=None):
    if expected is None:
        expected = EXPECTED
    policy = json.loads(policy_path.read_text(encoding='utf-8-sig'))
    body = policy['policy_candidate_body']
    if body['policy_id'] != POLICY_ID or body['policy_version'] != 2:
        stop('SOURCE_POLICY_NOT_HISTORIC_V2')
    release = body['rules']['b02_noncredential']['security']['g5_release']
    actual = release['documents']
    if len(actual) != 2 or len({d['document_id'] for d in actual}) != 2:
        stop('POLICY_DOCUMENT_SET_INVALID')
    for doc in actual:
        docid = doc['document_id']
        if docid not in expected or (doc['sha256'], doc['byte_size']) != expected[docid]:
            stop('POLICY_DOCUMENT_CONTENT_MISMATCH')
    if not (body['declared_material_applicability']['until'] == '2026-10-30T13:00:00+00:00'
            and release['until'] == '2026-10-30T13:00:00+00:00'
            and all(d['g4']['valid_until'] == '2026-10-30T13:00:00+00:00' for d in actual)):
        stop('HISTORICAL_POLICY_INTERVAL_DIVERGENCE')


def verify(base: Path, *, policy_path=POLICY, expected=None):
    if expected is None:
        expected = EXPECTED
    check_components(base)
    if not base.is_dir():
        stop('BASE_NOT_DIRECTORY')
    check_policy(policy_path, expected)
    for docid, (digest, size) in expected.items():
        path = base / docid / 'DOCUMENT.pdf'
        check_components(path)
        a, id_a = read_once(path, size)
        check_components(path)
        b, id_b = read_once(path, size)
        if a != digest or b != digest or a != b or id_a != id_b:
            stop('SOURCE_HASH_OR_FILE_IDENTITY_CHANGED')
    return {'status': 'B02_R6_C3_TWO_ORIGINALS_BYTES_READ_ONLY_PASS',
            'files': len(expected), 'sha256_and_size': 'MATCHED_BOTH',
            'policy_v2_document_bindings': 'MATCHED_HISTORIC_ONLY',
            'policy_v2_window': 'EXPIRED_2026_10_30_13_00_UTC',
            'protected_database_writes': 0, 'pdf_writes': 0,
            'authority_for_release': False, 'normative_link_persisted': False}


def main(argv=None):
    ap = argparse.ArgumentParser(description='C3 two-PDF read-only provenance check')
    ap.add_argument('--base', type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(verify(args.base), sort_keys=True))
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as exc:
        print('STOP_B02_R6_C3_' + str(exc)[:170])
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
