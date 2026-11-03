"""Only the B02 supplementary continuity contract V2. Synthetic, not authority."""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import pytest
from app.services import enterprise_b02_documentary_continuity_v2 as v

OLD='2026-10-21T22:19:28+00:00'
RAT='2026-10-21T22:46:35+00:00'
NEW='2026-11-02T23:41:10+00:00'
START='2026-11-03T10:00:00+00:00'
END='2026-11-10T00:00:00+00:00'
NOW='2026-11-03T11:00:00+00:00'
WINDOW_START='2026-11-01T00:00:00+00:00'
WINDOW_END='2026-11-15T00:00:00+00:00'
ACTORS={'reviewer':'reviewer-v2','author':'author-v2','integrator':'author-v2','origin_examiner':'origin-v2'}
DOCS={'101202501245':'a'*64,'101201900571':'b'*64}
SUB={'policy_type':'activation_authority','policy_id':'SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY','policy_version':1,'policy_hash':'c'*64}

def add(proofs,obj):
    h=v._digest(obj);proofs[h]=obj;return h

def fixture():
    p={}
    obj={'policy_subject':SUB,'documents':DOCS,'use':'autenticar_documento_sefa_pr'};oh=v._digest(obj)
    hist={'id':'historical','outcome':'favoravel','reviewer_execution':'review-old','completed_at':OLD}
    hist_hash=add(p,hist)
    review={'id':'review-new','object_sha256':oh,'outcome':'favoravel','accepted':True,
            'participation':'review_only','conflicts':[],'findings':['limited historical provenance'],
            'limitations':['not operational authority'],**{role+'_execution':ACTORS[role] for role in ('reviewer','author','integrator')},
            'completed_at':NEW,'mandate_id':'mandate-reviewer','inputs_sha256':[oh]}
    mandates=[];executions=[]
    for role in ('reviewer','author','integrator'):
        who=ACTORS[role]
        m={'id':'mandate-'+role,'issuer':'Miguel','execution_id':who,'role':role,
           'object_sha256':oh,'valid_from':WINDOW_START,'valid_until':WINDOW_END,
           'revoked':False,'operations':{'reviewer':['review','reprove'],'author':['prepare','submit'],'integrator':['integrate_candidate','test']}[role]}
        accepted={'execution_id':who,'mandate_sha256':v._digest(m),'accepted':True,'accepted_at':'2026-11-02T00:00:00+00:00'}
        m.update(accepted=True,acceptance_sha256=add(p,accepted));mandates.append(m)
        ctx={'execution_id':who,'role':role,'instructions':'synthetic evidence only',
             'provided_context':'synthetic context', 'participation':'review_only' if role=='reviewer' else role,
             'limitations':['not authenticated']}
        executions.append({'id':who,'role':role,'mandate_id':m['id'],'context_sha256':add(p,ctx),
                           'inputs_sha256':[oh],'outputs_sha256':[oh],
                           'occurred_at':NEW if role=='reviewer' else '2026-11-02T12:00:00+00:00'})
    origin_m={'id':'origin-m','issuer':'Miguel','execution_id':ACTORS['origin_examiner'],
              'operations':['examine_document_origin','report','abstain'],'valid_from':WINDOW_START,
              'valid_until':WINDOW_END,'revoked':False,'policy_subject':SUB,'synthetic_only':True};origin_pin={'id':'origin-m','sha256':add(p,origin_m)}
    a={'execution_id':ACTORS['origin_examiner'],'mandate_sha256':v._digest(origin_m),'accepted':True,
       'accepted_at':'2026-11-02T08:00:00+00:00'};ah=add(p,a)
    pins=[]
    for doc,digest in DOCS.items():
        document={'id':doc,'sha256':digest,'url':'https://example.test/'+doc,'byte_size':120}
        exam={'actor_execution':ACTORS['origin_examiner'],'document':document,'mandate_binding':origin_pin,
              'examined_at':'2026-11-02T18:00:00+00:00','own_findings':['synthetic examined'],
              'limitations':['synthetic only']}
        report={'id':'origin-'+doc,'kind':v.ORIGIN_KIND,'document':document,'actor_execution':ACTORS['origin_examiner'],
                'policy_subject':SUB,'synthetic_only':True,'revoked':False,
                'mechanism':v.MECHANISM,'criteria_id':'SEFA_PR_DOCUMENTARY_ADMISSION_V1',
                'verifier':{'id':'synthetic-test'},'receipt_projection':{'id':'synthetic-test'},
                'official_identifier':doc,
                'technical_author_execution':ACTORS['author'],'technical_integrator_execution':ACTORS['integrator'],
                'mandate_binding':origin_pin,'mandate_acceptance_sha256':ah,'examination_record_sha256':add(p,exam),
                'examined_at':exam['examined_at'],'valid_from':'2026-11-02T19:00:00+00:00',
                'valid_until':WINDOW_END,'outcome':'favoravel','limitations':['not operational'],
                'mechanism_assessment':['historic channel only'],'receipt_binding':{'id':'receipt-'+doc,'sha256':'d'*64},
                'tls_evidence_binding':{'id':'tls-'+doc,'sha256':'e'*64}}
        pin={'id':report['id'],'sha256':add(p,report)};pins.append(pin);review['inputs_sha256'].append(pin['sha256'])
    revhash=add(p,review)
    history={'object_sha256':oh,'revision':1,'previous_revision':None,
             'reviews':[hist_hash,revhash],'prior_reviews':[],'delta_sha256':None}
    decisions=[{'decision_id':f'd{i}','record_hash':str(i+1)*64,
                'actor':actor,'timestamp':time,'evidence':{}}
               for i,(actor,time) in enumerate((('author-old','2026-10-21T22:14:56+00:00'),
                   ('review-old','2026-10-21T22:17:02+00:00'),('review-old',OLD),('Miguel',RAT)))]
    audit={'id':'historical','sha256':hist_hash};rat_pin={'id':'d3','sha256':'4'*64}
    decisions[2]['evidence']['audit_report']={'binding':audit}
    expected={'policy_subject':SUB,'decision_bindings':[{'id':f'd{i}','sha256':str(i+1)*64} for i in range(4)],
              'audit_report_binding':audit}
    evidence={'institutional.json':{'expected':expected,'decisions':decisions},'object.json':obj,
              'review.json':review,'history.json':history,'proofs.json':p,
              'mandates.json':{'mandates':mandates},'execution.json':{'executions':executions}}
    adoption={'schema':v.SCHEMA,'scope':v.SCOPE,'id':'adoption-v2-synthetic',
              'policy_subject':SUB,'object_sha256':oh,'historical_ratification':rat_pin,
              'historical_audit':audit,'successor_review':{'id':'review-new','sha256':revhash},
              'origin_reports':pins,'actors':dict(ACTORS),'synthetic_only':True,
              'evidence_hashes':{n:v._digest(evidence[n]) for n in ('history.json','mandates.json','execution.json','proofs.json')},
              'decision':{'issuer':'Miguel','status':'adopted','approved':True,'issued_at':NEW,
                          'valid_from':START,'valid_until':END,'revoked':False,'risk_accepted':False,
                          'signing_authorized':False,'new_events_authorized':False,'reactivate_g4_v4':False}}
    return {'adoption':adoption,'trusted_pin':{'id':adoption['id'],'sha256':v._digest(adoption)},
            'evidence':evidence,'expected':expected,'decisions':decisions,
            'now':NOW,'valid_from':START,'valid_until':END,'synthetic':True}

def check(s):
    return v.verify_supplemental_continuity(**s)

def repin(s,*,adoption=False,evidence=False,report=None):
    # Simulate fully rehashed unsigned payloads to reach SEMANTIC checks.
    if report is not None:
        reviews=s['evidence']['review.json'];proof=s['evidence']['proofs.json']
        for i,entry in enumerate(s['adoption']['origin_reports']):
            if entry['id']==report['id']:
                old=entry['sha256'];proof.pop(old);entry['sha256']=add(proof,report)
                reviews['inputs_sha256']=[entry['sha256'] if x==old else x for x in reviews['inputs_sha256']]
        s['adoption']['successor_review']['sha256']=v._digest(reviews)
        s['evidence']['history.json']['reviews'][1]=v._digest(reviews)
    if evidence or report is not None:
        for name in s['adoption']['evidence_hashes']:
            s['adoption']['evidence_hashes'][name]=v._digest(s['evidence'][name])
    if adoption or evidence or report is not None:
        s['trusted_pin']['sha256']=v._digest(s['adoption'])


def test_synthetic_positive_only():
    assert check(fixture())['status']=='verified_synthetic_continuity_v2'

def test_no_trusted_pin_default_fails():
    s=fixture();s['trusted_pin']={'id':s['trusted_pin']['id'],'sha256':'0'*64}
    with pytest.raises(ValueError,match='UNRECOGNIZED_ADOPTION'):check(s)

@pytest.mark.parametrize('field,value',[('status','draft'),('approved',False),('issuer','another'),('risk_accepted',True),
  ('signing_authorized',True),('new_events_authorized',True),('reactivate_g4_v4',True),('revoked',True)])
def test_decision_never_self_promotes(field,value):
    s=fixture();s['adoption']['decision'][field]=value;repin(s,adoption=True)
    with pytest.raises(ValueError,match='DECISION_NOT_ELIGIBLE'):check(s)

@pytest.mark.parametrize('field,value',[('issued_at','2026-10-20T00:00:00+00:00'),('issued_at','2026-12-01T00:00:00+00:00'),
    ('valid_until','2026-11-12T00:00:00+00:00')])
def test_adoption_chronology_protected(field,value):
    s=fixture();s['adoption']['decision'][field]=value;repin(s,adoption=True)
    with pytest.raises(ValueError):check(s)

def test_historical_audit_hash_not_rewritten():
    s=fixture();s['adoption']['historical_audit']={'id':'historical','sha256':'0'*64};repin(s,adoption=True)
    with pytest.raises(ValueError,match='HISTORICAL_AUDIT_CHANGED'):check(s)

def test_historical_decision_row_cannot_be_swapped():
    s=fixture();s['decisions'][2]['actor']='reviewer-v2';s['evidence']['institutional.json']['decisions']=s['decisions']
    with pytest.raises(ValueError,match='HISTORICAL_REVIEW_INVALID'):check(s)

def test_history_omitted_previous_review():
    s=fixture();s['evidence']['history.json']['reviews']=s['evidence']['history.json']['reviews'][1:]
    repin(s,evidence=True)
    with pytest.raises(ValueError,match='HISTORY_CHANGED_OR_OMITTED'):check(s)

def test_forged_successor_review_hash():
    s=fixture();s['evidence']['review.json']['outcome']='desfavoravel';repin(s,evidence=True)
    with pytest.raises(ValueError,match='SUCCESSOR_REVIEW_INVALID'):check(s)

def test_reviewer_cannot_be_origin_examiner():
    s=fixture();s['adoption']['actors']['origin_examiner']='reviewer-v2';repin(s,adoption=True)
    with pytest.raises(ValueError,match='ACTOR_SEGREGATION'):check(s)

def test_changed_mandate_acceptance_rejected_even_if_all_pins_updated():
    s=fixture();m=s['evidence']['mandates.json']['mandates'][0];m['id']='fake-reviewer';repin(s,evidence=True)
    with pytest.raises(ValueError,match='ROLE_BINDING_INVALID'):check(s)

def test_expired_own_mandate_disallows_decision():
    s=fixture();m=s['evidence']['mandates.json']['mandates'][0]
    m['valid_until']='2026-11-05T00:00:00+00:00'
    old=m['acceptance_sha256'];accept=s['evidence']['proofs.json'].pop(old)
    body={k:v for k,v in m.items() if k not in ('acceptance_sha256','accepted')}
    accept['mandate_sha256']=v._digest(body)
    m['acceptance_sha256']=add(s['evidence']['proofs.json'],accept)
    repin(s,evidence=True)
    with pytest.raises(ValueError,match='MANDATE_DECISION_WINDOW'):check(s)

def test_origin_report_not_pinned_in_own_review():
    s=fixture();review=s['evidence']['review.json'];review['inputs_sha256'].pop();repin(s,evidence=True)
    with pytest.raises(ValueError,match='SUCCESSOR_REVIEW_INVALID'):check(s)

def test_report_outcome_cannot_launder_to_authority():
    s=fixture();pin=s['adoption']['origin_reports'][0];report=copy.deepcopy(s['evidence']['proofs.json'][pin['sha256']]);report['outcome']='inconclusivo'
    repin(s,report=report)
    with pytest.raises(ValueError,match='ORIGIN_REPORT_INVALID'):check(s)

def test_wrong_origin_acceptance_cannot_be_repinned():
    s=fixture();pin=s['adoption']['origin_reports'][0];report=copy.deepcopy(s['evidence']['proofs.json'][pin['sha256']]);report['mandate_acceptance_sha256']='0'*64
    repin(s,report=report)
    with pytest.raises(ValueError,match='ORIGIN_EVIDENCE_INVALID'):check(s)

def test_scope_unchanged_when_signer_pins_wrong_contract():
    s=fixture();s['adoption']['scope']='FISCAL_AUTHORITY';repin(s,adoption=True)
    with pytest.raises(ValueError,match='SCOPE_OR_DOMAIN'):check(s)

def test_unsigned_payload_and_founder_signature_alone_are_not_an_adoption():
    s=fixture();s['adoption']['decision']['approved']=False;repin(s,adoption=True)
    with pytest.raises(ValueError,match='DECISION_NOT_ELIGIBLE'):check(s)

def test_no_v1_fallback_on_untrusted_continuity():
    s=fixture();s['adoption']['synthetic_only']=False;repin(s,adoption=True)
    with pytest.raises(ValueError,match='SCOPE_OR_DOMAIN'):check(s)

def test_profile_passes_offset_aware_datetime_to_v2():
    s=fixture();s['now']=datetime(2026,11,3,11,tzinfo=timezone.utc)
    assert check(s)['status']=='verified_synthetic_continuity_v2'

def test_naive_datetime_rejected_fail_closed():
    s=fixture();s['now']=datetime(2026,11,3,11)
    with pytest.raises(ValueError,match='TIME_INVALID'):check(s)
