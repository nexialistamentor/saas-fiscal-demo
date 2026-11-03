"""B02 documentary continuity V2; read-only, no grants or fallback.

Only a trust-registry-pinned competent adoption can join a November
supplementary documentary review to the immutable October decision chain.
The adoption is NOT a ratification/activation/signing/risk decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import re

SCHEMA = 'SOLVERIS-B02-DOCUMENTARY-CONTINUITY-ADOPTION-V2'
SCOPE = 'SEFA_PR_B02_HISTORICAL_ORIGIN_ONLY'
REQUIRED_ROLES = ('reviewer', 'author', 'integrator', 'origin_examiner')
ORIGIN_KIND = 'independent_document_origin_founder_sealed'
MECHANISM = 'preserved_official_channel_corroboration'


def _fail(code):
    raise ValueError('B02_CONTINUITY_V2_' + code)


def _digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def _time(value):
    if isinstance(value, datetime):
        when = value
    elif isinstance(value, str):
        try:
            when = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            _fail('TIME_INVALID')
    else:
        _fail('TIME_INVALID')
    if when.tzinfo is None:
        _fail('TIME_INVALID')
    return when.astimezone(timezone.utc)


def _keys(value, keys, code):
    if type(value) is not dict or set(value) != set(keys):
        _fail(code)
    return value


def _pin(value, code):
    _keys(value, ('id', 'sha256'), code)
    if type(value['id']) is not str or not value['id'] or not isinstance(value['sha256'], str) or re.fullmatch(r'[0-9a-f]{64}', value['sha256']) is None:
        _fail(code)
    return value


def verify_supplemental_continuity(*, adoption, trusted_pin, evidence,
                                    expected, decisions, now, valid_from,
                                    valid_until, synthetic):
    """Pure internal V2 gate. Caller must obtain trusted_pin from the trusted ROOT.

    An arbitrary payload may not provide its own trusted pin. The public
    entrypoint has no adoption parameter; synthetic positive is never authority.
    Signature, DB, ROOT, segregation and legacy chain stay separate gates.
    """
    _keys(adoption, ('schema', 'scope', 'id', 'policy_subject', 'object_sha256',
                     'historical_ratification', 'historical_audit',
                     'successor_review', 'origin_reports', 'actors',
                     'evidence_hashes', 'decision', 'synthetic_only'), 'SCHEMA')
    _pin(trusted_pin, 'TRUST_PIN_INVALID')
    if trusted_pin['id'] != adoption['id'] or trusted_pin['sha256'] != _digest(adoption):
        _fail('UNRECOGNIZED_ADOPTION')
    if (adoption['schema'] != SCHEMA or adoption['scope'] != SCOPE
            or adoption['synthetic_only'] is not synthetic
            or adoption['policy_subject'] != expected['policy_subject']):
        _fail('SCOPE_OR_DOMAIN')
    if not isinstance(decisions, list) or len(decisions) != 4:
        _fail('HISTORICAL_CHAIN_INVALID')
    institutional = evidence['institutional.json']
    if institutional != {'expected': expected, 'decisions': decisions}:
        _fail('HISTORICAL_CHAIN_CHANGED')
    if adoption['historical_ratification'] != expected['decision_bindings'][-1]:
        _fail('HISTORICAL_RATIFICATION_CHANGED')
    if adoption['historical_audit'] != expected['audit_report_binding']:
        _fail('HISTORICAL_AUDIT_CHANGED')
    if decisions[2]['evidence']['audit_report']['binding'] != expected['audit_report_binding']:
        _fail('HISTORICAL_AUDIT_CHANGED')
    proofs, review, history = (evidence[x] for x in ('proofs.json', 'review.json', 'history.json'))
    obj, mandates, executions = (evidence[x] for x in ('object.json', 'mandates.json', 'execution.json'))
    if not isinstance(proofs, dict):
        _fail('PROOF_MAP_INVALID')
    original = proofs.get(adoption['historical_audit']['sha256'])
    if (not isinstance(original, dict) or original.get('id') != adoption['historical_audit']['id']
            or original.get('outcome') != 'favoravel'
            or original.get('reviewer_execution') != decisions[2]['actor']
            or _digest(original) != adoption['historical_audit']['sha256']
            or _time(original.get('completed_at')) != _time(decisions[2]['timestamp'])):
        _fail('HISTORICAL_REVIEW_INVALID')
    if (adoption['object_sha256'] != _digest(obj)
            or review.get('object_sha256') != adoption['object_sha256']
            or adoption['successor_review'] != {'id': review.get('id'), 'sha256': _digest(review)}
            or review.get('outcome') != 'favoravel' or review.get('accepted') is not True
            or review.get('participation') != 'review_only' or review.get('conflicts') != []
            or not review.get('findings') or not review.get('limitations')):
        _fail('SUCCESSOR_REVIEW_INVALID')
    if (history.get('object_sha256') != adoption['object_sha256']
            or history.get('revision') != 1 or history.get('previous_revision') is not None
            or history.get('prior_reviews') != [] or history.get('delta_sha256') is not None
            or history.get('reviews') != [adoption['historical_audit']['sha256'],
                                          adoption['successor_review']['sha256']]):
        _fail('HISTORY_CHANGED_OR_OMITTED')
    expected_files = ('history.json', 'mandates.json', 'execution.json', 'proofs.json')
    pins = _keys(adoption['evidence_hashes'], expected_files, 'EVIDENCE_PINS_INVALID')
    if any(pins[name] != _digest(evidence[name]) for name in expected_files):
        _fail('EVIDENCE_PINS_MISMATCH')
    role_map = _keys(adoption['actors'], REQUIRED_ROLES, 'ACTOR_SET_INVALID')
    if (role_map['reviewer'] != review['reviewer_execution']
            or role_map['author'] != review['author_execution']
            or role_map['integrator'] != review['integrator_execution']
            or len({role_map['reviewer'], role_map['author'], role_map['origin_examiner']}) != 3
            or role_map['origin_examiner'] in (role_map['integrator'], role_map['author'])):
        _fail('ACTOR_SEGREGATION')
    if (len(mandates.get('mandates', [])) != 3 or len(executions.get('executions', [])) != 3):
        _fail('ROLE_SET_INVALID')
    role_mandates = {m['role']: m for m in mandates['mandates']}
    role_executions = {e['role']: e for e in executions['executions']}
    if set(role_mandates) != set(REQUIRED_ROLES[:3]) or set(role_executions) != set(REQUIRED_ROLES[:3]):
        _fail('ROLE_SET_INVALID')
    accepted_times = []
    for role in REQUIRED_ROLES[:3]:
        mandate, record = role_mandates[role], role_executions[role]
        actor = role_map[role]
        if (mandate['execution_id'] != actor or record['id'] != actor
                or record['mandate_id'] != mandate['id']
                or record['context_sha256'] not in proofs
                or mandate['accepted'] is not True or mandate['revoked'] is not False):
            _fail('ROLE_BINDING_INVALID')
        accept = proofs.get(mandate['acceptance_sha256'])
        body = {k: v for k, v in mandate.items() if k not in ('accepted', 'acceptance_sha256')}
        if (not isinstance(accept, dict) or _digest(accept) != mandate['acceptance_sha256']
                or accept != {'execution_id': actor, 'mandate_sha256': _digest(body),
                              'accepted': True, 'accepted_at': accept.get('accepted_at')}):
            _fail('ROLE_ACCEPTANCE_INVALID')
        acc = _time(accept['accepted_at'])
        if (not _time(mandate['valid_from']) <= acc <= _time(record['occurred_at'])
                or _time(record['occurred_at']) > _time(review['completed_at'])):
            _fail('ROLE_CHRONOLOGY_INVALID')
        accepted_times.append(acc)
    if _time(role_executions['reviewer']['occurred_at']) != _time(review['completed_at']):
        _fail('REVIEW_CHRONOLOGY_INVALID')
    origins = adoption['origin_reports']
    if (type(origins) is not list or len(origins) != 2
            or any(type(x) is not dict for x in origins)
            or len({x.get('sha256') for x in origins}) != 2):
        _fail('ORIGIN_REPORT_SET_INVALID')
    origin_doc_ids = set()
    for pin in origins:
        _pin(pin, 'ORIGIN_PIN_INVALID')
        report = proofs.get(pin['sha256'])
        if (not isinstance(report, dict) or _digest(report) != pin['sha256'] or report.get('id') != pin['id']
                or report.get('kind') != ORIGIN_KIND or report.get('outcome') != 'favoravel'
                or report.get('policy_subject') != adoption['policy_subject']
                or report.get('synthetic_only') is not synthetic
                or report.get('revoked') is not False
                or report.get('mechanism') != MECHANISM
                or report.get('criteria_id') != 'SEFA_PR_DOCUMENTARY_ADMISSION_V1'
                or not report.get('verifier') or not report.get('receipt_projection')
                or report.get('actor_execution') != role_map['origin_examiner']
                or report.get('technical_author_execution') != role_map['author']
                or report.get('technical_integrator_execution') != role_map['integrator']):
            _fail('ORIGIN_REPORT_INVALID')
        doc = report.get('document', {})
        if (doc.get('id') not in obj['documents'] or doc.get('sha256') != obj['documents'][doc['id']]
                or report.get('official_identifier') != doc['id']):
            _fail('ORIGIN_DOCUMENT_DIVERGENCE')
        origin_doc_ids.add(doc['id'])
        if pin['sha256'] not in review['inputs_sha256']:
            _fail('ORIGIN_NOT_REVIEWED')
        mandate = proofs.get(report['mandate_binding']['sha256'])
        accept = proofs.get(report['mandate_acceptance_sha256'])
        exam = proofs.get(report['examination_record_sha256'])
        if (not isinstance(mandate, dict) or _digest(mandate) != report['mandate_binding']['sha256']
                or mandate.get('id') != report['mandate_binding']['id']
                or mandate.get('execution_id') != role_map['origin_examiner']
                or mandate.get('issuer') != 'Miguel'
                or mandate.get('policy_subject') != adoption['policy_subject']
                or mandate.get('synthetic_only') is not synthetic
                or mandate.get('operations') != ['examine_document_origin', 'report', 'abstain']
                or mandate.get('revoked') is not False
                or not isinstance(accept, dict) or _digest(accept) != report['mandate_acceptance_sha256']
                or accept.get('mandate_sha256') != _digest(mandate)
                or accept.get('execution_id') != role_map['origin_examiner']
                or accept.get('accepted') is not True
                or not isinstance(exam, dict) or _digest(exam) != report['examination_record_sha256']
                or exam.get('actor_execution') != role_map['origin_examiner']
                or exam.get('document') != doc or exam.get('mandate_binding') != report['mandate_binding']
                or exam.get('examined_at') != report['examined_at']
                or not exam.get('own_findings') or not exam.get('limitations')):
            _fail('ORIGIN_EVIDENCE_INVALID')
        if (not _time(mandate['valid_from']) <= _time(accept['accepted_at']) <= _time(report['examined_at'])
                < _time(mandate['valid_until'])
                or _time(report['examined_at']) > _time(review['completed_at'])):
            _fail('ORIGIN_CHRONOLOGY_INVALID')
        if (not report.get('limitations') or not report.get('mechanism_assessment')
                or not report.get('receipt_binding') or not report.get('tls_evidence_binding')):
            _fail('ORIGIN_SCOPE_INSUFFICIENT')
        if (not _time(report['valid_from']) <= _time(valid_from)
                or _time(valid_until) > _time(report['valid_until'])):
            _fail('ORIGIN_DECISION_WINDOW')
    if origin_doc_ids != set(obj['documents']):
        _fail('ORIGIN_DOCUMENT_SET_INVALID')
    decision = _keys(adoption['decision'], ('issuer', 'status', 'approved', 'issued_at', 'valid_from',
                                            'valid_until', 'revoked', 'risk_accepted',
                                            'signing_authorized', 'new_events_authorized',
                                            'reactivate_g4_v4'), 'DECISION_SCHEMA_INVALID')
    if (decision['issuer'] != 'Miguel' or decision['status'] != 'adopted'
            or decision['approved'] is not True or decision['revoked'] is not False
            or decision['risk_accepted'] is not False or decision['signing_authorized'] is not False
            or decision['new_events_authorized'] is not False or decision['reactivate_g4_v4'] is not False):
        _fail('DECISION_NOT_ELIGIBLE')
    now_at = _time(now)
    issued, start, end = _time(decision['issued_at']), _time(valid_from), _time(valid_until)
    if (decision['valid_from'] != valid_from or decision['valid_until'] != valid_until
            or not _time(review['completed_at']) <= issued <= start <= now_at < end):
        _fail('ADOPTION_CHRONOLOGY_INVALID')
    if any(end > _time(m['valid_until']) or start < _time(m['valid_from']) for m in mandates['mandates']):
        _fail('MANDATE_DECISION_WINDOW')
    if _time(decisions[3]['timestamp']) >= _time(review['completed_at']):
        _fail('HISTORICAL_REVIEW_ORDER_INVALID')
    return {'status': 'verified_synthetic_continuity_v2' if synthetic else 'continuity_v2_conditions_met',
            'adoption_binding': trusted_pin, 'historical_ratification': adoption['historical_ratification'],
            'successor_review': adoption['successor_review']}
