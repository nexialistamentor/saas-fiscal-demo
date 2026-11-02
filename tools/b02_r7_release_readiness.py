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
    'G5_V3_OWN_INDEPENDENT_AUDIT', 'RCV31_A2_V4_OWN_REVIEW',
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

# Only the G4 successor has been reported physically reconciled. Preserve the
# original historical R7 fence and validate the separately pinned consumption.
POST_G4_PATH = 'B02_R7_G4_V4_CONSUMO_FISICO_POS_JANELA_20261031.json'
V3_PATH = 'POLICY_G5_CANDIDATO_SUCESSOR_V3_PARA_REVISAO.json'
G4_ACTIVATION_ID = 'B02-05ede-activation-v4'
G4_ACTIVATION_HASH = 'cf617e146b3451555898d8253fba8bb13dfa6ff99776b50978e0ba68df4cb482'
G5_V3_FILE_SHA256 = '32068cadf7297fb5958af25650899abffc667c17f3508f9261a165b8dfbd5fc7'


def evaluate_post_g4(result, fence, *, fence_blob, consumption, v3,
                     v3_blob, v3_raw):
    """Consume reported G4 v4 proof; never infer database access or R7 release."""
    import hashlib
    if consumption.get('schema') != 'SOLVERIS_B02_R7_G4_V4_POSTWINDOW_CONSUMPTION_V1':
        stop('G4_CONSUMPTION_SCHEMA')
    original = consumption.get('source_fence', {})
    if original != {'path': FENCE_PATH, 'git_blob': fence_blob, 'immutable': True}:
        stop('G4_CONSUMPTION_FENCE_BINDING')
    if consumption.get('original_missing_predecessor_id') != 'CURRENT_G4_V3_SUCCESSOR':
        stop('G4_CONSUMPTION_WRONG_PREDECESSOR')
    proof = consumption.get('resolution', {})
    if (proof.get('status') != 'RECONCILED_AS_REPORTED_BY_AUTHORIZED_WINDOWS_EXECUTOR'
        or proof.get('observed_result') != 'G4_V4_PHYSICAL_RECONCILED_G5_V3_DRAFT_ONLY'
        or proof.get('g4_activation_id') != G4_ACTIVATION_ID
        or proof.get('g4_activation_record_hash') != G4_ACTIVATION_HASH
        or proof.get('no_automatic_retries') is not True
        or proof.get('independent_postgres_query_by_this_chat') is not False):
        stop('G4_CONSUMPTION_PROOF_CONFLICT')
    p = consumption.get('g5_v3_consumer', {})
    if (p.get('path') != V3_PATH or p.get('git_blob') != v3_blob
        or p.get('sha256_exact') != G5_V3_FILE_SHA256
        or hashlib.sha256(v3_raw).hexdigest() != G5_V3_FILE_SHA256
        or p.get('policy_active') is not False):
        stop('G4_CONSUMPTION_V3_SOURCE_CONFLICT')
    body = v3.get('policy_candidate_body', {})
    release = body.get('rules', {}).get('b02_noncredential', {}).get('security', {}).get('g5_release', {})
    docs = release.get('documents', [])
    if (v3.get('status') != 'V3_PROSPECTIVE_DRAFT_UNISSUED_INCOMPLETE_AUTHORITY'
        or body.get('policy_version') != 3
        or body.get('policy_id') != 'SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE'
        or len(docs) != 2
        or len({x.get('document_id') for x in docs}) != 2
        or any(x.get('g4', {}).get('policy_binding', {}).get('policy_activation_id') != G4_ACTIVATION_ID
               or x.get('g4', {}).get('policy_binding', {}).get('policy_activation_record_hash') != G4_ACTIVATION_HASH
               for x in docs)
        or release.get('capability_root_id') is not None
        or release.get('actor') is not None):
        stop('G4_CONSUMPTION_V3_INCOMPLETE_OR_MISMATCHED')
    remaining = set(REQUIRED_GAPS) - {'CURRENT_G4_V3_SUCCESSOR'}
    if (set(consumption.get('open_predecessors_after_g4', [])) != remaining
        or set(consumption.get('not_dischargeable_by_g4_alone', [])) != remaining
        or len(consumption['open_predecessors_after_g4']) != len(remaining)
        or len(consumption['not_dischargeable_by_g4_alone']) != len(remaining)
        or consumption.get('no_other_gates_promoted') is not True
        or consumption.get('old_fence_preserved') is not True
        or consumption.get('b02_closed') is not False
        or consumption.get('b03_released') is not False):
        stop('G4_CONSUMPTION_REMAINING_GATES')
    return dict(result, result='B02_OPEN_B03_BLOCKED_POST_G4_RECONCILED_AS_REPORTED',
                missing_independently_owned_acts=len(remaining),
                g4_successor='RECONCILED_AS_REPORTED_BY_AUTHORIZED_WINDOWS_EXECUTOR',
                g4_fresh_database_read_this_run=False,
                post_g4_completed_predecessors=['CURRENT_G4_V3_SUCCESSOR'],
                remaining_predecessors=sorted(remaining))


# A later scoped technical review is a completed review of A2 V4 only.
# Do not erase the 31/10 institutional fence or promote it to a real signed root.
A2_FOCAL_PATH = 'evidence/b02/rcv31/a2/SOLVERIS_B02_RCV31_A2_V4_PARECER_PROPRIO_FINAL_20261101.md'
A2_FOCAL_BLOB = '256585a1dedcd3c703f14644f0c6723c1c0742c1'


def consume_a2_v4_focal_review(result, *, report_blob, report_text):
    """Recognize the subsequently issued bounded A2 review, not an operational release."""
    if report_blob != A2_FOCAL_BLOB:
        stop('A2_FOCAL_REVIEW_BLOB_DIVERGENCE')
    required = (
        '**FAVORÁVEL CONDICIONADO, estritamente ao A2 V4 no ensaio descartável/sintético**',
        '**FAVORÁVEL CONDICIONADO ao objeto A2 V4, no seu alcance técnico e sintético; encerrada a revisão focal deste delta.**',
        '**Nenhum novo ficheiro ou ensaio é indispensável para esta conclusão delimitada.**',
        'Não alego identidade verificável da execução revisora original de 25/10',
        'não ratifica política',
    )
    if not all(x in report_text for x in required):
        stop('A2_FOCAL_REVIEW_CONTENT_DIVERGENCE')
    if (result.get('claim_of_b02_release') is not False
        or result.get('claim_of_b03_release') is not False
        or 'RCV31_A2_V4_OWN_REVIEW' not in result.get('remaining_predecessors', ())):
        stop('A2_SCOPED_NOT_AN_INSTITUTIONAL_RELEASE')
    # The 31/10 fence and post-G4 snapshot remain immutable history. Only
    # the effective present-day projection stops listing an accepted focal
    # review as pending. This is NOT institutional origin or real SQL approval.
    current = list(result['remaining_predecessors'])
    completed = list(result.get('post_g4_completed_predecessors', ()))
    if (current.count('RCV31_A2_V4_OWN_REVIEW') != 1
        or 'RCV31_A2_V4_OWN_REVIEW' in completed):
        stop('A2_HISTORICAL_CONSUMPTION_CONFLICT')
    remaining = [p for p in current if p != 'RCV31_A2_V4_OWN_REVIEW']
    return dict(result,
        a2_v4_focal_review='CLOSED_IN_ITS_TECHNICAL_SYNTHETIC_SCOPE_NO_RETEST',
        a2_v4_focal_review_git_blob=A2_FOCAL_BLOB,
        a2_v4_focal_review_reexecution_required=False,
        a2_v4_original_reviewer_identity_not_attested=True,
        post_g4_completed_predecessors=completed + ['RCV31_A2_V4_OWN_REVIEW'],
        remaining_predecessors=remaining,
        missing_independently_owned_acts=len(remaining),
        historic_r7_fence_had_a2_as_pending=True,
        r7_original_fence_preserved=True)


# Only recognize exact acts already issued; these are not origin authentication,
# a new G5 policy, a runtime trust root or permission to install anything.
SUCCESSOR_PROOFS_PATH = 'evidence/b02/successor_v3/proofs.json'
SUCCESSOR_PROOFS_BASE_135_BLOB = 'f07e2f609acad4675fcfa0c3698fb249ef2d493b'
SUCCESSOR_OWN_ACT_PATH = 'evidence/b02/ATO_PROPRIO_AUTOR_INTEGRADOR_SUCESSOR_20261102.json'
SUCCESSOR_MANDATES = {
    'author': ('B02-G4-SUCESSAO-20261101-AUTHOR.body.json',
               '73d77e161747a8f6725fe94cf0f148d41423c09a04b6233c7521bff6990c6849',
               'da14259ebd91584a0c30905719379720d4da4fbf3ace2f7d3ba424fe23db09c0'),
    'integrator': ('B02-G4-SUCESSAO-20261101-INTEGRATOR.body.json',
                   '44698d76a4657804f4f6717cc83fac50697905717335efb8e8c9d8304c31fafe',
                   '8efb6c1a11abbea216692b3e9af6b19cc7ca2c559b7f0a6505206d79a4fe9757'),
    'origin_examiner': ('B02-G4-SUCESSAO-20261101-ORIGIN.body.json',
                        '22ce147864beacc1fa51cf993672eb5a8ee817fa64be3b96e1259306e91e5ba7',
                        None),
}
SUCCESSOR_MANDATE_DIR = 'evidence/b02/successor_v3/mandate_bodies/'
SUCCESSOR_REVIEWER_ACCEPTANCE = '6792209f25f33346cf5d235f2df186e2428679364042337b0c49d2675d66273d'


def consume_issued_successor_acts(result, *, proofs, own, bodies, proofs_blob):
    """Reconcile accepted author/integrator roles without creating an origin act."""
    import hashlib
    from datetime import datetime
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True,
            ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()
    if not isinstance(proofs, dict) or SUCCESSOR_REVIEWER_ACCEPTANCE not in proofs:
        stop('SUCCESSOR_PRIOR_REVIEWER_PROOF_MISSING')
    if (own.get('schema') != 'B02_G4_SUCCESSOR_AUTHOR_INTEGRATOR_OWN_ACCEPTANCES_20261102_V1'
        or not isinstance(own.get('acceptances'), list)
        or len(own['acceptances']) != 2):
        stop('SUCCESSOR_OWN_ACT_INVALID')
    issued = {x.get('role'): x for x in own['acceptances'] if isinstance(x, dict)}
    if set(issued) != {'author', 'integrator'}:
        stop('SUCCESSOR_OWN_ROLES_INVALID')
    add = {}
    for role, (name, mandate_hash, acceptance_hash) in SUCCESSOR_MANDATES.items():
        body = bodies.get(name)
        if not isinstance(body, dict) or digest(body) != mandate_hash:
            stop('SUCCESSOR_MANDATE_HASH_' + role.upper())
        add[mandate_hash] = body
        if role == 'origin_examiner':
            if body.get('execution_id') != 'GPT-6/examinador-origem-sefa-pr-g4-sucessor-20261101':
                stop('SUCCESSOR_ORIGIN_DESIGNATION_DIVERGENCE')
            continue
        current = issued[role]
        acceptance = current.get('own_canonical_acceptance')
        if (not isinstance(acceptance, dict)
            or digest(acceptance) != acceptance_hash
            or current.get('acceptance_sha256') != acceptance_hash
            or acceptance.get('accepted') is not True
            or acceptance.get('mandate_sha256') != mandate_hash
            or acceptance.get('execution_id') != body.get('execution_id')
            or body.get('role') != role):
            stop('SUCCESSOR_OWN_ACCEPTANCE_' + role.upper())
        at = datetime.fromisoformat(acceptance['accepted_at'])
        start = datetime.fromisoformat(body['valid_from'])
        end = datetime.fromisoformat(body['valid_until'])
        if at.tzinfo is None or not start <= at < end:
            stop('SUCCESSOR_OWN_CHRONOLOGY_' + role.upper())
        add[acceptance_hash] = acceptance
    if (result.get('claim_of_b02_release') is not False
        or result.get('claim_of_b03_release') is not False):
        stop('SUCCESSOR_UNSUPPORTED_RELEASE_CLAIM')
    if len(proofs) == 135 and proofs_blob == SUCCESSOR_PROOFS_BASE_135_BLOB:
        if any(key in proofs for key in add):
            stop('SUCCESSOR_135_BASE_ALREADY_MUTATED')
        indexed = False
    elif len(proofs) == 140:
        if any(key not in proofs or proofs[key] != value for key, value in add.items()):
            stop('SUCCESSOR_140_PROOFS_MISMATCH')
        indexed = True
    else:
        stop('SUCCESSOR_PROOFS_BASE_OR_COUNT_INVALID')
    return dict(result,
        g4_author_integrator_current_own_acceptances='TWO_CURRENT_OWN_ACCEPTANCES_ISSUED',
        g4_reviewer_existing_own_acceptance='PRESERVED',
        g4_successor_mandates_issued=3,
        g4_successor_five_issued_proofs_indexed=indexed,
        g4_successor_proofs_count=len(proofs),
        g4_distinct_origin_examiner_own_acceptance='NOT_PRESENT_IN_THIS_EVIDENCE',
        g4_author_integrator_own_acceptance_reissue_required=False,
        claim_of_b02_release=False, claim_of_b03_release=False)


def main():
    if git('branch', '--show-current') != BRANCH:
        stop('WRONG_CHECKOUT_BRANCH')
    if git('status', '--porcelain', '--', FENCE_PATH, MANIFEST_PATH, POST_G4_PATH, V3_PATH):
        stop('UNCOMMITTED_GOVERNANCE_CHANGE')
    for path in (FENCE_PATH, MANIFEST_PATH, POST_G4_PATH, V3_PATH):
        if git('hash-object', path) != git('rev-parse', 'HEAD:' + path):
            stop('UNPINNED_GOVERNANCE_FILE')
    fence = json.loads((REPO / FENCE_PATH).read_text(encoding='utf-8-sig'))
    manifest = json.loads((REPO / MANIFEST_PATH).read_text(encoding='utf-8-sig'))
    result = evaluate(fence, manifest, fence_blob=git('hash-object', FENCE_PATH))
    post = json.loads((REPO / POST_G4_PATH).read_text(encoding='utf-8-sig'))
    v3_raw = (REPO / V3_PATH).read_bytes()
    v3 = json.loads(v3_raw.decode('utf-8-sig'))
    result = evaluate_post_g4(result, fence, fence_blob=git('hash-object', FENCE_PATH),
                              consumption=post, v3=v3,
                              v3_blob=git('hash-object', V3_PATH), v3_raw=v3_raw)
    # Read an independently committed later A2 focal report, without re-running A2.
    if git('status', '--porcelain', '--', A2_FOCAL_PATH):
        stop('A2_FOCAL_REVIEW_UNCOMMITTED')
    if git('hash-object', A2_FOCAL_PATH) != git('rev-parse', 'HEAD:' + A2_FOCAL_PATH):
        stop('A2_FOCAL_REVIEW_WORKTREE_DRIFT')
    report_blob = git('hash-object', A2_FOCAL_PATH)
    report_text = (REPO / A2_FOCAL_PATH).read_text(encoding='utf-8-sig')
    result = consume_a2_v4_focal_review(
        result, report_blob=report_blob, report_text=report_text)
    # Consume the existing two own acceptances and the three exact mandate
    # bodies, without treating a designated origin examiner as accepted.
    paths = [SUCCESSOR_PROOFS_PATH, SUCCESSOR_OWN_ACT_PATH] + [
        SUCCESSOR_MANDATE_DIR + v[0] for v in SUCCESSOR_MANDATES.values()]
    if git('status', '--porcelain', '--', *paths):
        stop('SUCCESSOR_EVIDENCE_UNCOMMITTED')
    if any(git('hash-object', p) != git('rev-parse', 'HEAD:' + p) for p in paths):
        stop('SUCCESSOR_EVIDENCE_WORKTREE_DRIFT')
    proofs = json.loads((REPO / SUCCESSOR_PROOFS_PATH).read_text(encoding='utf-8-sig'))
    own = json.loads((REPO / SUCCESSOR_OWN_ACT_PATH).read_text(encoding='utf-8-sig'))
    bodies = {name: json.loads((REPO / SUCCESSOR_MANDATE_DIR / name)
                .read_text(encoding='utf-8-sig'))
              for name, _, _ in SUCCESSOR_MANDATES.values()}
    result = consume_issued_successor_acts(
        result, proofs=proofs, own=own, bodies=bodies,
        proofs_blob=git('hash-object', SUCCESSOR_PROOFS_PATH))
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))
    print('B02_R7_GATED_NO_RELEASE_SOURCE_ONLY_PASS')

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as error:
        print(str(error)[:250]); sys.exit(2)
