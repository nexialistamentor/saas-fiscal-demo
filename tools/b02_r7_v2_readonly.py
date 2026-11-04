#!/usr/bin/env python3
"""B02 R7 prospective status overlay; read-only, no authority creation or release.

Preserves the 2026-10-31 fence and its recorded historic gaps. Reuses the
existing R7 pure readers for G4 V4 and A2 V4 and verifies November V2 pins.
An absent external operational receipt remains UNKNOWN, never proof of nonexecution.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from typing import Any

BASE = Path(__file__).resolve().parents[1]
BRANCH = 'candidate/g5-v5-publicacao-local'
ADOPTION = 'evidence/b02/B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json'
ADOPTION_SHA = 'd0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8'
DECISION_SHA = 'd3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520'
MANIFEST_SHA = '99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1'
PUBLIC_DER_SHA = '6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'
SIGNER_BLOB = 'f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2'
OBJECT_SHA = '615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906'
REVIEW_SHA = '9949a7cca164f9ed50f2b92aa2a1f348fdddfc1c4c3a5cced56b292112a86d21'
HISTORIC_G5_V3_BLOB = '895b277634c50fd17c0f20514fe69ccc40d40a88'
HISTORIC_G5_V3_SHA256 = '32068cadf7297fb5958af25650899abffc667c17f3508f9261a165b8dfbd5fc7'
CURRENT_G5_V3_BLOB = 'fa88b2f98c7f5d24e0c092f0ea02afce22efb2e2'
CURRENT_G5_V3_SHA256 = '29ec3504f7f6c6d4b4dca23484ef3de283768573b5b02095cf53e896350063a5'
CURRENT_G5_V3_BODY_SHA256 = '1011f3f6ba4ab9ee6085aa1d7959f9f87d6880b9384243423bf3686ff0845577'
CURRENT_G4_NOTICE = (
    'G4 V4 activation and two existing historical ORIGIN reports linked by exact '
    'hashes; this does NOT establish G5 V3 operational origin, current inspection '
    'or ratification.'
)
G4_HISTORICAL_ORIGIN = {
 '101202501245': ('B02-G4-SUCESSOR-ORIGIN-REPORT-101202501245-20261102',
                 'a281c48d6107817aca97331e5425f81616847e66853a3e179ca66d3353f23fa8'),
 '101201900571': ('B02-G4-SUCESSOR-ORIGIN-REPORT-101201900571-20261102',
                 '9250fc933c41dab84e186019f01ed1f2b29828de1d5e1b879568a96e3ef1a6d4'),
}
SEVEN = {
 'execution.json': '5cdc4e6fca726edbc14aeb7cf253739cca9dc6067d7895096211ee89c0b6e903',
 'history.json': '8c585bdb3ec42d2ebc100f96013ff7be5144d78a1b29435f4025670c6bcd36c1',
 'institutional.json': 'c3c894710010c9ffa508e8c7d73ecafefcf02962c38a65f06e50ae4164fcd505',
 'mandates.json': '89630a184206bbb606544151e0925efed29f618125cd3c0099dc9f72854504d6',
 'object.json': OBJECT_SHA,
 'proofs.json': '9bc79ef8f1cc39d857a41fbfb0e74f0cf4deda274998db23c524c448c88ca004',
 'review.json': REVIEW_SHA,
}


def reject(code: str) -> None:
    raise ValueError('STOP_B02_R7_V2_' + code)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(repo: Path, path: str, *, expected_sha: str | None = None) -> tuple[bytes, Any]:
    file = repo / path
    if not file.is_file() or file.is_symlink(): reject('FILE_MISSING_OR_SYMLINK_' + path)
    raw = file.read_bytes()
    if expected_sha is not None and sha(raw) != expected_sha:
        reject('PIN_DIVERGENCE_' + path)
    try:
        data = json.loads(raw, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        reject('JSON_' + path)
    return raw, data


def unique(pairs):
    d = {}
    for k, v in pairs:
        if k in d: reject('DUPLICATE_JSON_KEY')
        d[k] = v
    return d


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(['git', '-C', str(repo), *args], text=True,
                       capture_output=True, timeout=35)
    if p.returncode: reject('GIT_QUERY_' + p.stderr[-90:])
    return p.stdout.strip()


def clean_pinned(repo: Path, paths: list[str]) -> None:
    if git(repo, 'branch', '--show-current') != BRANCH: reject('WRONG_BRANCH')
    for path in paths:
        if git(repo, 'status', '--porcelain', '--', path): reject('DIRTY_' + path)
        if git(repo, 'hash-object', path) != git(repo, 'rev-parse', 'HEAD:' + path):
            reject('WORKTREE_GIT_BLOB_' + path)


def reconstruct_current_v3_from_historic(historic: dict) -> dict:
    """Allow only the two G4 historical references, notice and draft-body pin."""
    if not isinstance(historic, dict) or historic.get('status') != (
            'V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY'):
        reject('V3_HISTORIC_DOCUMENT_INVALID')
    expected = copy.deepcopy(historic)
    body = expected.get('policy_candidate_body')
    try:
        release = body['rules']['b02_noncredential']['security']['g5_release']
        docs = release['documents']
        if (len(docs) != 2 or
                {d['document_id'] for d in docs} != set(G4_HISTORICAL_ORIGIN)):
            reject('V3_HISTORIC_TWO_SOURCES_INVALID')
        if release['capability_root_id'] is not None or release['actor'] is not None:
            reject('V3_HISTORIC_AUTHORITY_NOT_CLOSED')
        if expected['__V3_DRAFT_PROVENANCE__']['not_signed_or_authorized'] is not True:
            reject('V3_HISTORIC_NOT_DRAFT')
        for doc in docs:
            g4 = doc['g4']
            if (g4['origin_report_binding'] is not None
                    or g4['verifier'] is not None
                    or g4['outcome'] != 'AWAITING_OWN_CURRENT_FOUNDER_ORIGIN'
                    or doc['sanitization']['outcome'] !=
                    'AWAITING_CURRENT_REAL_INDEPENDENT_INSPECTION'):
                reject('V3_HISTORIC_G4_ALREADY_PROMOTED')
            report_id, report_sha = G4_HISTORICAL_ORIGIN[doc['document_id']]
            g4['origin_report_binding'] = {'id': report_id, 'sha256': report_sha}
    except (KeyError, TypeError, AttributeError):
        reject('V3_HISTORIC_STRUCTURE_INVALID')
    expected['__AVISO_G4_PREENCHIDO__'] = CURRENT_G4_NOTICE
    expected['__V3_DRAFT_PROVENANCE__']['policy_body_sha256_is_draft_only'] = (
        CURRENT_G5_V3_BODY_SHA256)
    return expected


def resolve_v3_snapshots(repo: Path, old, consumption: dict,
                         current_raw: bytes, current_v3: dict) -> tuple[bytes, dict]:
    """Consume old G4 report against its frozen blob; exact-check current delta."""
    pin = consumption.get('g5_v3_consumer', {})
    if (old.V3_PATH != 'POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json'
            or old.G5_V3_FILE_SHA256 != HISTORIC_G5_V3_SHA256
            or not isinstance(pin, dict)
            or pin.get('path') != old.V3_PATH
            or pin.get('git_blob') != HISTORIC_G5_V3_BLOB
            or pin.get('sha256_exact') != HISTORIC_G5_V3_SHA256
            or pin.get('policy_active') is not False):
        reject('HISTORIC_V3_PIN_CONFLICT')
    p = subprocess.run(
        ['git', '-C', str(repo), 'cat-file', 'blob', HISTORIC_G5_V3_BLOB],
        capture_output=True, timeout=35)
    if p.returncode != 0 or sha(p.stdout) != HISTORIC_G5_V3_SHA256:
        reject('HISTORIC_V3_BLOB_DIVERGENCE')
    try:
        historic = json.loads(p.stdout, object_pairs_hook=unique)
    except (ValueError, UnicodeDecodeError):
        reject('HISTORIC_V3_JSON_INVALID')
    if (git(repo, 'rev-parse', 'HEAD:' + old.V3_PATH) != CURRENT_G5_V3_BLOB
            or sha(current_raw) != CURRENT_G5_V3_SHA256):
        reject('CURRENT_V3_PIN_DIVERGENCE')
    expected = reconstruct_current_v3_from_historic(historic)
    if current_v3 != expected:
        reject('CURRENT_V3_UNSCOPED_CHANGE')
    canonical_body = json.dumps(
        current_v3['policy_candidate_body'], sort_keys=True,
        ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if sha(canonical_body) != CURRENT_G5_V3_BODY_SHA256:
        reject('CURRENT_V3_CANONICAL_BODY_DIVERGENCE')
    return p.stdout, historic


def load_old(repo: Path):
    file = repo / 'tools/b02_r7_release_readiness.py'
    spec = importlib.util.spec_from_file_location('historic_b02_r7_readonly', file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def baseline(repo: Path) -> dict:
    old = load_old(repo)
    paths = [old.FENCE_PATH, old.MANIFEST_PATH, old.POST_G4_PATH,
             old.V3_PATH, old.A2_FOCAL_PATH, ADOPTION] + [
             'evidence/b02/successor_v3/' + name for name in SEVEN]
    clean_pinned(repo, paths)
    _,fence = read(repo, old.FENCE_PATH)
    _,manifest = read(repo, old.MANIFEST_PATH)
    current = old.evaluate(fence, manifest, fence_blob=git(repo, 'hash-object', old.FENCE_PATH))
    _,post = read(repo, old.POST_G4_PATH)
    current_raw,current_v3 = read(repo, old.V3_PATH)
    v3raw,v3 = resolve_v3_snapshots(repo, old, post, current_raw, current_v3)
    current = old.evaluate_post_g4(current, fence,
        fence_blob=git(repo,'hash-object',old.FENCE_PATH),
        consumption=post, v3=v3, v3_blob=HISTORIC_G5_V3_BLOB, v3_raw=v3raw)
    a2txt = (repo/old.A2_FOCAL_PATH).read_text(encoding='utf-8-sig')
    current = old.consume_a2_v4_focal_review(current,
        report_blob=git(repo,'hash-object',old.A2_FOCAL_PATH), report_text=a2txt)
    raw,adoption = read(repo, ADOPTION, expected_sha=ADOPTION_SHA)
    if adoption.get('schema') != 'SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2':
        reject('V2_ADOPTION_SCHEMA')
    if adoption.get('decision',{}).get('signing_authorized') is not False:
        reject('DOCUMENTARY_ADOPTION_SELF_GRANTED_SIGNING')
    if adoption.get('successor_review',{}).get('sha256') != REVIEW_SHA:
        reject('V2_REVIEW_NOT_PINNED')
    if adoption.get('object_sha256') != OBJECT_SHA:
        reject('V2_OBJECT_NOT_PINNED')
    evidence = {}
    for name, pin in SEVEN.items():
        _,obj = read(repo, 'evidence/b02/successor_v3/' + name, expected_sha=pin)
        evidence[name] = obj
    if evidence['object.json'].get('policy_subject') != adoption.get('policy_subject'):
        reject('V2_SUBJECT_CONFLICT')
    if len(evidence['proofs.json']) < 149:
        reject('PROOFS_BELOW_REPORTED_149')
    closed = current['post_g4_completed_predecessors']
    if set(closed) != {'CURRENT_G4_V3_SUCCESSOR', 'RCV31_A2_V4_OWN_REVIEW'}:
        reject('G4_A2_NOT_RECONCILED')
    return {
      'schema': 'SOLVERIS_B02_R7_SUCCESSOR_V2_READONLY_PROJECTION_V1',
      'status': 'B02_OPEN_B03_BLOCKED',
      'head_sha': git(repo,'rev-parse','HEAD'),
      'historic_r7_fence_preserved': True,
      'closed_gates_only_in_scope': sorted(closed),
      'documentary_v2_adoption_sha256': sha(raw),
      'documentary_v2_only_no_signing_authority': True,
      'successor_v3_seven_sha256': SEVEN,
      'successor_proofs_count': len(evidence['proofs.json']),
      'current_unproved_r7_predecessors': sorted(current['remaining_predecessors']),
      'signer_v2_approved_decision_sha256': DECISION_SHA,
      'signer_v2_reviewed_source_git_blob': SIGNER_BLOB,
      'signer_v2_signature': 'NOT_OBSERVED_BY_SOURCE_ONLY_RUN',
      'r1_runtime_trust': 'NOT_INFERRED_FROM_DOCUMENTARY_ADOPTION',
      'r5_real_0064_0065_two_units': 'REQUIRES_CURRENT_INDEPENDENT_REAL_RECEIPT',
      'r6_real_normative_rule_item': 'REQUIRES_CURRENT_INDEPENDENT_REAL_RECEIPT',
      'r7_closed': False, 'b03_released': False,
      'protected_writes': 0,
    }


def mathematical_signature(bundle: Path, public_der: Path) -> dict:
    """Optional read-only mathematical check; never grants institutional trust."""
    from cryptography.hazmat.primitives import serialization
    if not bundle.is_dir() or bundle.is_symlink(): reject('SIGNED_BUNDLE_NOT_FOUND')
    manifest = bundle / 'manifest.json'
    decision = bundle / 'decision.json'
    signature = bundle / 'signature.bin'
    if any(not x.is_file() or x.is_symlink() for x in (manifest, decision, signature, public_der)):
        reject('SIGNATURE_INPUT_MISSING_OR_SYMLINK')
    mr, dr, sr, der = manifest.read_bytes(), decision.read_bytes(), signature.read_bytes(), public_der.read_bytes()
    if sha(mr) != MANIFEST_SHA or len(dr) != 1118 or sha(dr) != DECISION_SHA:
        reject('SIGNED_BYTES_WRONG')
    if sha(der) != PUBLIC_DER_SHA or len(sr) != 64:
        reject('PUBLIC_OR_SIGNATURE_INVALID')
    try:
        key = serialization.load_der_public_key(der)
        key.verify(sr, dr)
    except Exception:
        reject('ED25519_MATHEMATICAL_FAILURE')
    return {'mathematical_verification': 'B02_V2_ED25519_MATHEMATICAL_VERIFY_PASS',
            'decision_sha256': sha(dr), 'signature_sha256': sha(sr),
            'operational_trust': 'NOT_GRANTED_BY_MATH_VERIFICATION'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--repo', default=str(BASE))
    p.add_argument('--signed-bundle')
    p.add_argument('--public-der')
    a=p.parse_args()
    result=baseline(Path(a.repo))
    if (a.signed_bundle is None) != (a.public_der is None): reject('SIGNATURE_INPUTS_INCOMPLETE')
    if a.signed_bundle:
        result['signature_math']=mathematical_signature(Path(a.signed_bundle),Path(a.public_der))
        result['signer_v2_signature']='MATH_CHECKED_NOT_ADOPTION_ATTESTED'
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',',':')))
    print('B02_R7_V2_READONLY_RECONCILED_NO_RELEASE')


if __name__ == '__main__':
    try: main()
    except Exception as ex:
        raise SystemExit(str(ex)[:360]) from None
