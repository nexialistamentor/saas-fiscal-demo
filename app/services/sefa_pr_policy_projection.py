"""R2 read-side validation of canonical institutional events. No writer or authority.

No latest-wins, inferred reactivation, invented lifecycle link, or default proof
verifier. A structural chain is not evidence that its reports/identities are real.
"""
from datetime import datetime,timezone
import re

SUBJECT_KEYS=('policy_type','policy_id','policy_version','policy_hash')
EVENTS=('submetida','auditoria_iniciada','auditada_favoravelmente','ratificada')
ROLES=('proponente_institucional','auditor_independente','auditor_independente','autoridade_constitucional_final')
TERMINAL={'suspensa','desactivada','expirada','revogada'}
class PolicyProofError(ValueError):pass
def fail(code):raise PolicyProofError(code)
def subject(value):
    try:return {k:value[k] for k in SUBJECT_KEYS}
    except (KeyError,TypeError):fail('POLICY_SUBJECT_INCOMPLETE')
def dt(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else value
        if not isinstance(result,datetime) or result.tzinfo is None:fail('EVENT_TIME_INVALID')
        return result.astimezone(timezone.utc)
    except (ValueError,TypeError):fail('EVENT_TIME_INVALID')
def text(value):return isinstance(value,str) and bool(value.strip())
def hash64(value):return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None
def proof(value):
    if not isinstance(value,dict) or set(value)!={'id','sha256'} or not text(value['id']) or not hash64(value['sha256']):fail('INSTITUTIONAL_EVIDENCE_REFERENCE_MISSING')
    return dict(value)
def identity(value,expected=None):
    if not isinstance(value,dict) or not text(value.get('actor_id')) or (expected is not None and value['actor_id']!=expected):fail('INSTITUTIONAL_IDENTITY_BINDING_MISSING')
    return {'actor_id':value['actor_id'],'binding':proof(value.get('binding'))}

def validate_institutional_chain(decisions,binding,*,now,technical_actor,activated_at):
    """Exact four-event chain; branches, blockers and extra events abstain.

    previous_decision_id is canonical. The predecessor hash is an R2 required
    evidence pin in the existing evidence JSON, not a fictional new SQL column.
    """
    target=subject(binding);now=dt(now)
    if not isinstance(decisions,list) or not decisions:fail('INSTITUTIONAL_CHAIN_MISSING')
    by_id={}
    for d in decisions:
        if subject(d)!=target:fail('INSTITUTIONAL_SUBJECT_DIVERGENCE')
        if not text(d.get('decision_id')) or not hash64(d.get('record_hash')) or d['decision_id'] in by_id:fail('INSTITUTIONAL_DECISION_IDENTITY_AMBIGUOUS')
        if dt(d.get('timestamp'))>now:fail('INSTITUTIONAL_FUTURE_EVENT')
        if d.get('decision_event') in ('auditada_desfavoravelmente','rejeitada','cancelada'):fail('INSTITUTIONAL_BLOCKING_DECISION')
        by_id[d['decision_id']]=d
    current=by_id.get(binding.get('decision_id'))
    if current is None or current['record_hash']!=binding.get('decision_hash'):fail('EXACT_RATIFICATION_HASH_MISSING')
    reverse=[];seen=set()
    while current is not None:
        identifier=current['decision_id']
        if identifier in seen:fail('INSTITUTIONAL_CHAIN_CYCLE')
        seen.add(identifier);reverse.append(current)
        prev=current.get('previous_decision_id')
        if prev is None:break
        if prev not in by_id:fail('INSTITUTIONAL_PREDECESSOR_MISSING')
        current=by_id[prev]
    chain=list(reversed(reverse))
    if len(chain)!=4 or len(by_id)!=4 or tuple(d.get('decision_event') for d in chain)!=EVENTS:fail('INSTITUTIONAL_CHAIN_INCOMPLETE_OR_BRANCHED')
    identity_pins=[];last_time=None;previous_hash=None
    for index,d in enumerate(chain):
        if d.get('institutional_role')!=ROLES[index] or not text(d.get('actor')):fail('INSTITUTIONAL_ROLE_DIVERGENCE')
        stamp=dt(d['timestamp'])
        if last_time is not None and stamp<last_time:fail('INSTITUTIONAL_CHRONOLOGY_DIVERGENCE')
        e=d.get('evidence')
        if not isinstance(e,dict) or e.get('policy_subject')!=target:fail('INSTITUTIONAL_EVIDENCE_SUBJECT_DIVERGENCE')
        if 'previous_decision_record_hash' not in e or e['previous_decision_record_hash']!=previous_hash:fail('INSTITUTIONAL_PREDECESSOR_HASH_DIVERGENCE')
        actor_pin=identity(e.get('actor_identity'),d['actor']);proof(e.get('record_evidence'));identity_pins.append(actor_pin)
        last_time=stamp;previous_hash=d['record_hash']
    proponent=chain[0]['actor'];auditor=chain[1]['actor'];ratifier=chain[3]['actor']
    if chain[2]['actor']!=auditor or len({proponent,auditor,ratifier})!=3:fail('INSTITUTIONAL_SEGREGATION_VIOLATION')
    author=identity(chain[0]['evidence'].get('technical_author'))
    if auditor==author['actor_id'] or auditor==technical_actor or ratifier==technical_actor or not text(technical_actor):fail('INSTITUTIONAL_SEGREGATION_VIOLATION')
    report=chain[2]['evidence'].get('audit_report')
    if not isinstance(report,dict) or report.get('policy_subject')!=target or report.get('auditor_id')!=auditor or report.get('outcome')!='favoravel':fail('EXACT_FAVOURABLE_AUDIT_REPORT_MISSING')
    audit_pin=proof(report.get('binding'))
    if dt(activated_at)<dt(chain[3]['timestamp']) or dt(activated_at)>now:fail('ACTIVATION_BEFORE_VALID_RATIFICATION')
    return {'policy_subject':target,'decision_bindings':[{'id':d['decision_id'],'sha256':d['record_hash']} for d in chain],
      'actor_identity_bindings':identity_pins,'technical_author':author,'technical_actor':technical_actor,
      'record_evidence_bindings':[proof(d['evidence']['record_evidence']) for d in chain],'audit_report_binding':audit_pin,
      'institutional_evidence_verified':False}

def project_current_authorization(decisions,activations,binding,*,domain,modality,now):
    """Conservative projection of the complete scoped snapshot, never newest row.

    The current schema has no universally demonstrated terminal-event lineage
    field. Any terminal row of the selected subject blocks, rather than guessing
    which activation it supersedes. Legitimate renewal with unresolved linkage
    also abstains. No new provenance-key lifecycle convention is invented here.
    """
    now=dt(now);target=subject(binding)
    if not isinstance(decisions,list) or not isinstance(activations,list):fail('POLICY_STATE_SNAPSHOT_INCOMPLETE')
    ratifications=[d for d in decisions if d.get('decision_id')==binding.get('decision_id') and d.get('record_hash')==binding.get('decision_hash') and subject(d)==target]
    if len(ratifications)!=1:fail('POLICY_STATE_RATIFICATION_AMBIGUOUS')
    ratified_at=dt(ratifications[0]['timestamp'])
    by_id={d.get('decision_id'):d for d in decisions}
    if len(by_id)!=len(decisions):fail('POLICY_STATE_DECISION_IDENTITY_AMBIGUOUS')
    ancestors=set();cursor=ratifications[0]
    while cursor is not None:
        identifier=cursor['decision_id']
        if identifier in ancestors:fail('POLICY_STATE_DECISION_CYCLE')
        ancestors.add(identifier);previous=cursor.get('previous_decision_id')
        if previous is None:break
        cursor=by_id.get(previous)
        if cursor is None:fail('POLICY_STATE_PREDECESSOR_MISSING')
    for d in decisions:
        if d.get('policy_type')!=target['policy_type'] or d.get('policy_id')!=target['policy_id']:fail('POLICY_STATE_DECISION_SCOPE_DIVERGENCE')
        timestamp=dt(d.get('timestamp'))
        if timestamp>now:fail('POLICY_STATE_FUTURE_DECISION')
        if timestamp>ratified_at or (d.get('previous_decision_id')==binding.get('decision_id') and d.get('decision_id')!=binding.get('decision_id')):fail('POLICY_STATE_LATER_DECISION_REQUIRES_RESOLUTION')
        if timestamp==ratified_at and d.get('decision_id') not in ancestors:fail('POLICY_STATE_UNORDERED_DECISION_TIE')
    selected=[];current=[];ids=set();active_intervals=[]
    for a in activations:
        if a.get('domain')!=domain or a.get('modality')!=modality or a.get('policy_type')!=target['policy_type']:fail('POLICY_STATE_SCOPE_DIVERGENCE')
        aid=a.get('policy_activation_id')
        if not text(aid) or aid in ids or not hash64(a.get('record_hash')):fail('POLICY_STATE_IDENTITY_AMBIGUOUS')
        ids.add(aid)
        state=a.get('state')
        if state not in TERMINAL|{'activa'}:fail('POLICY_STATE_UNKNOWN')
        if dt(a.get('activated_at'))>now:fail('POLICY_STATE_FUTURE_ACTIVATION')
        if subject(a)==target and state in TERMINAL:fail('POLICY_STATE_TERMINAL_OR_UNRESOLVED_LINK')
        interval=a.get('operational_interval')
        try:start=dt(interval['from']);end=dt(interval['until'])
        except (KeyError,TypeError):fail('POLICY_STATE_INTERVAL_UNKNOWN')
        if end<=start:fail('POLICY_STATE_INTERVAL_UNKNOWN')
        if state=='activa':active_intervals.append((aid,start,end))
        if state=='activa' and start<=now<end:current.append(a)
        if aid==binding.get('policy_activation_id'):
            if a['record_hash']!=binding.get('policy_activation_record_hash') or subject(a)!=target or a.get('policy_decision_id')!=binding.get('decision_id'):fail('POLICY_STATE_EXACT_BINDING_DIVERGENCE')
            selected.append(a)
    if len(selected)!=1 or selected[0]['state']!='activa':fail('POLICY_STATE_NOT_ACTIVE')
    chosen_start=dt(selected[0]['operational_interval']['from']);chosen_end=dt(selected[0]['operational_interval']['until'])
    if any(aid!=selected[0]['policy_activation_id'] and start<chosen_end and chosen_start<end for aid,start,end in active_intervals):fail('POLICY_STATE_OVERLAPPING_INTERVALS')
    if len(current)!=1 or current[0]['policy_activation_id']!=selected[0]['policy_activation_id']:fail('POLICY_STATE_OVERLAP_OR_NOT_CURRENT')
    return {'state':'activa','policy_activation_id':selected[0]['policy_activation_id'],'record_hash':selected[0]['record_hash']}

def verify_institutional_evidence(verifier,structural,*,connection):
    """A trusted INTERNAL proof adapter is mandatory. No boolean/JSON fallback.

    No real adapter is shipped or claimed in this preparation. It must resolve
    the actual immutable reports/identity evidence and return their exact pins.
    Never construct this dependency from a client request or environment flag.
    """
    method=getattr(verifier,'verify_exact_chain',None)
    if not callable(method):fail('INSTITUTIONAL_EVIDENCE_VERIFIER_UNAVAILABLE')
    expected={k:v for k,v in structural.items() if k!='institutional_evidence_verified'}
    result=method(connection=connection,expected=expected)
    if not isinstance(result,dict) or set(result)!={'status','verified_bindings'} or result['status']!='verified' or result['verified_bindings']!=expected:fail('INSTITUTIONAL_EVIDENCE_NOT_VERIFIED')

def require_current_authority(connection,binding,selected,*,now,proof_verifier=None):
    from sqlalchemy import text as sql
    isolation=connection.execute(sql("SELECT current_setting('transaction_isolation')")).scalar_one()
    if isolation not in ('repeatable read','serializable'):fail('CONSISTENT_POLICY_SNAPSHOT_REQUIRED')
    decisions=list(connection.execute(sql('''/* R2_POLICY_DECISIONS_SNAPSHOT */
 SELECT d.* FROM public.policy_decisions d WHERE d.policy_type=:policy_type AND d.policy_id=:policy_id'''),
      {'policy_type':binding['policy_type'],'policy_id':binding['policy_id']}).mappings().all())
    # Snapshot includes all versions. No state='activa', ORDER BY/LIMIT, MAX(),
    # or latest timestamp is used to discard potentially impeding events.
    exact=[d for d in decisions if subject(d)==subject(binding)]
    structural=validate_institutional_chain(exact,binding,now=now,technical_actor=selected['technical_actor'],activated_at=selected['activated_at'])
    activations=list(connection.execute(sql('''/* R2_POLICY_ACTIVATIONS_SNAPSHOT */
 SELECT a.* FROM public.policy_activations a
 WHERE a.policy_type=:policy_type AND a.domain=:domain AND a.modality=:modality'''),
      {'policy_type':binding['policy_type'],'domain':selected['domain'],'modality':selected['modality']}).mappings().all())
    project_current_authorization(decisions,activations,binding,domain=selected['domain'],modality=selected['modality'],now=now)
    verify_institutional_evidence(proof_verifier,structural,connection=connection)
