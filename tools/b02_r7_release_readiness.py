#!/usr/bin/env python3
"""Read-only, fail-closed B02 R7 release readiness assertion.

This does not approve a release. It verifies that the existing institutional
release fence is coherently BLOCKED. It never authenticates original sources,
signs, executes SQL, issues institutional acts, or publishes B03.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
BRANCH = 'candidate/g5-v5-publicacao-local'
FENCE_PATH = 'B02_R7_RELEASE_FENCE_20261031.json'
MANIFEST_PATH = 'B02_G5_V5_AUTHORIZATION_MANIFEST_DRAFT.json'
REQUIRED_GAPS = frozenset({
    'G5_AUDITOR_OWN_FINAL', 'RCV31_A2_V4_OWN_REVIEW',
    'CURRENT_G4_V3_SUCCESSOR', 'G5_NEW_TEMPORAL_POLICY',
    'R1_NATIVE_ROOT_SUCCESSOR', 'R5_FULL_0064_0065_PHYSICAL',
    'R6_NORMATIVE_TO_FISCAL', 'R7_COMPETENT_B02_FINAL',
})
COMPLETED_SCOPES = {
    'R4': 'SCOPED_PASS',
    'R6_C3': 'SCOPED_PASS_NOT_AUTHENTICITY',
    'R5_PREPARATION': 'SCOPED_PASS_NOT_REAL_0064_0065',
    'R1_NATIVE_PREPARATION': 'SOURCE_AND_FOCAL_TEST_PASS_NO_SUCCESSOR_ELF',
}

def stop(code):
    raise RuntimeError('STOP_B02_R7_READINESS_' + code)

def git(*args):
    result = subprocess.run(['git', *args], cwd=REPO, capture_output=True,
                            text=True, timeout=25)
    if result.returncode:
        stop('GIT_QUERY_FAILED')
    return result.stdout.strip()

def evaluate(fence, manifest, *, fence_blob):
    if not isinstance(fence, dict) or not isinstance(manifest, dict):
        stop('INVALID_JSON_OBJECT')
    if fence.get('schema') != 'SOLVERIS_B02_R7_CLOSEOUT_RELEASE_FENCE_V1':
        stop('UNRECOGNIZED_FENCE')
    if fence.get('status') != 'B02_NOT_CLOSED_B03_NOT_RELEASED':
        stop('FENCE_RELEASE_CLAIM_NOT_ACCEPTED')
    if fence.get('read_only_origin', {}).get('branch') != BRANCH:
        stop('FENCE_BRANCH_DIVERGENCE')
    rules = fence.get('strict_release_rules', {})
    guards = ('no_backdated_authority', 'no_reuse_expired_g4_g5_or_native_roots',
              'no_synthetic_to_real_promotion',
              'no_production_ddl_dml_without_explicit_new_prospective_authority',
              'no_auto_retry_after_uncertain_commit_ack',
              'no_mei_or_historical_b02_mutation',
              'no_unnecessary_repetition_of_accepted_r4_c3_r5_tests',
              'technical_signoff_not_institutional_signoff')
    if any(rules.get(g) is not True for g in guards):
        stop('MISSING_SECURITY_GUARD')
    if (rules.get('final_b02_closed_allowed') is not False or
            rules.get('b03_release_allowed') is not False):
        stop('UNAUTHORIZED_RELEASE_FLAG')
    raw = fence.get('exact_missing_predecessors')
    if not isinstance(raw, list) or len(raw) != len(REQUIRED_GAPS):
        stop('INCOMPLETE_GAP_INVENTORY')
    ids = [x.get('id') for x in raw if isinstance(x, dict)]
    if len(ids) != len(REQUIRED_GAPS) or set(ids) != REQUIRED_GAPS:
        stop('GAP_ID_SET_DIVERGENCE')
    if any(not x.get('observed') or x['observed'] in ('PASS', 'CLOSED', 'ISSUED')
           for x in raw):
        stop('UNSUPPORTED_OWNED_ACT_CLAIM')
    scopes = fence.get('technically_completed_not_to_repeat')
    if not isinstance(scopes, list) or len(scopes) != len(COMPLETED_SCOPES):
        stop('COMPLETED_SCOPE_SET_DIVERGENCE')
    actual = {x.get('gate'): x.get('status') for x in scopes if isinstance(x, dict)}
    if actual != COMPLETED_SCOPES:
        stop('TECHNICAL_SCOPE_PROMOTED_OR_CHANGED')
    m = manifest.get('r1_r7_continuity_matrix', {})
    if m.get('status') != 'B02_OPEN_B03_BLOCKED':
        stop('MANIFEST_CLAIMS_COMPLETION')
    link = m.get('R7_release_fence_20261031', {})
    if (link.get('file') != FENCE_PATH or link.get('git_blob') != fence_blob
            or link.get('b02_closed') is not False
            or link.get('b03_released') is not False):
        stop('MANIFEST_FENCE_LINK_DIVERGENCE')
    if link.get('protected_database_writes_in_this_reconciliation') != 0:
        stop('PROTECTED_WRITE_ASSERTION')
    if set(link.get('missing_predecessors', ())) != REQUIRED_GAPS:
        stop('MANIFEST_GAP_SET_DIVERGENCE')
    if (manifest.get('reviewer_documentary_evidence', {})
            .get('sql_auditada_favoravelmente') != 'NOT_ISSUED'):
        stop('INSTITUTIONAL_AUDIT_STATUS_DIVERGENCE')
    if (m.get('R5_disposable_two_unit_candidate', {}).get('status') !=
            'R5_TWO_UNIT_SOURCE_RED_GREEN_AND_PG17_DISPOSABLE_CAUSAL_PASS_WAITING_ORIGINAL_INDEPENDENT_REVIEW'):
        stop('R5_PHYSICAL_SCOPE_DIVERGENCE')
    return {
        'schema': 'SOLVERIS_B02_R7_READONLY_GATE_RESULT_V1',
        'result': 'B02_OPEN_B03_BLOCKED_CORROBORATED',
        'missing_independently_owned_acts': len(REQUIRED_GAPS),
        'completed_technical_scopes_preserved': len(COMPLETED_SCOPES),
        'claim_of_b02_release': False,
        'claim_of_b03_release': False,
        'database_writes': 0,
    }

def main():
    if git('branch', '--show-current') != BRANCH:
        stop('WRONG_CHECKOUT_BRANCH')
    if git('status', '--porcelain', '--', FENCE_PATH, MANIFEST_PATH):
        stop('UNCOMMITTED_GOVERNANCE_CHANGE')
    for path in (FENCE_PATH, MANIFEST_PATH):
        if git('hash-object', path) != git('rev-parse', 'HEAD:' + path):
            stop('UNPINNED_GOVERNANCE_FILE')
    fence = json.loads((REPO / FENCE_PATH).read_text(encoding='utf-8-sig'))
    manifest = json.loads((REPO / MANIFEST_PATH).read_text(encoding='utf-8-sig'))
    result = evaluate(fence, manifest, fence_blob=git('hash-object', FENCE_PATH))
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    print('B02_R7_GATED_NO_RELEASE_SOURCE_ONLY_PASS')

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as error:
        print(str(error)[:250]); sys.exit(2)
