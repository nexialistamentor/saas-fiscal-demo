"""New causal runtime tests. All positive evidence is explicitly synthetic.
No database, network, real key, authority or operational installation.
"""
import copy,inspect
from contextlib import contextmanager
from pathlib import Path
import pytest
from b02_founder_runtime_fixture import build,seal,repin,NOW,START,END,SUBJECT
from app.services import enterprise_b02_founder_runtime as r
from app.services import enterprise_b02_founder_review_profile as p
from app.services.enterprise_b02_institutional_verifier import PreservedEvidenceStore
from app.services.sefa_pr_policy_projection import PolicyProofError,verify_institutional_evidence


@contextmanager
def semantic_rejection():
    with pytest.raises(PolicyProofError) as caught:
        yield
    assert str(caught.value)!='PROFILE_PROOF_BYTES_ALTERED', 'Must reject the semantic defect, not alias-corrupted prior proof bytes'


def put(root,value,ident=None):
    raw=p.canonical(value);h=p.sha(raw);path=root/'sha256'/h[:2]/(h+'.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    return {'id':ident or value['id'],'sha256':h}

def proof(s,value):
    h=r.digest(value);s['files']['proofs.json'][h]=copy.deepcopy(value);return h

def refresh(s):
    repin(s);s['snapshot']['context']=copy.deepcopy(s['context'])
    s['node'].update(history_sha256=r.digest(s['files']['history.json']),object_sha256=r.digest(s['files']['object.json']),current_review_sha256=r.digest(s['files']['review.json']),review_hashes=s['files']['history.json']['reviews'])
    pin=put(s['store_root'],s['node']);s['snapshot'].update(head_binding=pin,genesis_binding=pin,canonical_decisions_sha256=r.digest(sorted(s['rows'],key=lambda x:x['decision_id'])))
    s['runtime_root']['snapshot_binding']=put(s['store_root'],s['snapshot']);seal(s)

@pytest.fixture
def case(tmp_path):
    bundle=tmp_path/'bundle';bundle.mkdir();s=build(bundle);s['store_root']=tmp_path/'store'
    s['expected']['technical_actor']='solveris_b02_policy_writer'
    # The role and execution remain distinct, even inside the signed institutional snapshot.
    s['files']['institutional.json']['expected']=s['expected']
    a=dict(SUBJECT,policy_activation_id='activation',record_hash='5'*64,technical_actor='solveris_b02_policy_writer',state='activa',policy_activation_execution_id='execution',policy_decision_id='d3')
    e=dict(SUBJECT,policy_activation_execution_id='execution',record_hash='6'*64,actor_or_worker='solveris_b02_policy_writer',state='concluida',policy_decision_id='d3',policy_decision_record_hash='4'*64)
    m=next(m for m in s['files']['mandates.json']['mandates'] if m['role']=='integrator')
    binding={'schema':'SOLVERIS-B02-EXECUTION-WRITER-BINDING-V1','policy_subject':SUBJECT,'execution_id':'exec-integrator','writer_role':'solveris_b02_policy_writer','activation_binding':{'id':'activation','sha256':'5'*64},'execution_record_binding':{'id':'execution','sha256':'6'*64},'decision_binding':{'id':'d3','sha256':'4'*64},'mandate_sha256':r.digest(m),'valid_from':START,'valid_until':END,'revoked':False}
    proof(s,binding)
    mandate=dict(id='origin-mandate',issuer='Miguel',policy_subject=SUBJECT,execution_id='exec-origin',operations=['examine_document_origin','report','abstain'],valid_from=START,valid_until=END,revoked=False,synthetic_only=True)
    mp={'id':mandate['id'],'sha256':proof(s,mandate)}
    reports={};contexts={};s['reports']={};s['receipts']={};s['tls']={}
    for doc,(url,h,size) in r.DOCUMENTS.items():
        receipt={'id':'receipt-'+doc,'requested_url':url,'resolved_url':url,'http_status':200,'session_id':'synthetic-session-'+doc,'session_started_at':'2026-10-21T01:00:00+00:00','received_at':'2026-10-21T01:00:02+00:00','artifact_hash':h,'byte_size':size,'synthetic_only':True}
        rp=put(s['store_root'],receipt)
        tls={'payload':{'id':'tls-'+doc,'session_id':receipt['session_id'],'hostname':'www.sefanet.pr.gov.br','url':url,'chain_validation':'verified','hostname_validation':'verified','certificate_chain_sha256':['synthetic-cert-hash'],'validation_transcript':'synthetic fixture, no real TLS','session_started_at':receipt['session_started_at'],'validated_at':'2026-10-21T01:00:01+00:00','synthetic_only':True}}
        tp=put(s['store_root'],tls,'tls-'+doc)
        document={'id':doc,'url':url,'sha256':h,'byte_size':size}
        accepted={'execution_id':'exec-origin','mandate_sha256':r.digest(mandate),'accepted':True,'accepted_at':START}
        examined='2026-10-21T02:00:00+00:00'
        examination={'actor_execution':'exec-origin','document':document,'mandate_binding':mp,'examined_at':examined,'own_findings':['synthetic independent assessment, not real PDF authentication'],'limitations':['synthetic only; no fiscal authority']}
        verifier={'id':r.VERIFIER_ID,'version':r.VERIFIER_VERSION,'hash':p.sha(Path(r.__file__).read_bytes())}
        report={'id':'origin-report-'+doc,'kind':'independent_document_origin_founder_sealed','policy_subject':SUBJECT,'document':document,'actor_execution':'exec-origin','technical_author_execution':'exec-author','technical_integrator_execution':'exec-integrator','mandate_binding':mp,'mandate_acceptance_sha256':proof(s,accepted),'mechanism':r.MECHANISM,'criteria_id':r.CRITERIA,'outcome':'favoravel','verifier':verifier,'receipt_binding':rp,'receipt_projection':{k:[k] for k in ('requested_url','resolved_url','http_status','session_id','received_at','artifact_hash','byte_size','session_started_at')},'tls_evidence_binding':tp,'official_identifier':doc,'doe_references':['synthetic reference; not a real finding'],'mechanism_assessment':['synthetic examiner evaluated channel + receipt + TLS together'],'examination_record_sha256':proof(s,examination),'examined_at':examined,'valid_from':START,'valid_until':END,'revoked':False,'synthetic_only':True}
        reports[doc]={'id':report['id'],'sha256':proof(s,report)};s['reports'][doc]=report;s['receipts'][doc]=receipt;s['tls'][doc]=tls
        contexts[doc]={'document_id':doc,'receipt_id':rp['id'],'receipt_hash':rp['sha256'],'session_id':receipt['session_id'],'received_at':receipt['received_at'],**{'verifier_'+k:v for k,v in verifier.items()}}
    node={'id':'history-node','schema':'SOLVERIS-B02-PRESERVED-REVIEW-PROJECTION-V1','policy_subject':SUBJECT,'sequence':1,'previous':None,'history_sha256':'','review_hashes':[],'object_sha256':'','current_review_sha256':'','supersedes':None,'valid_from':START,'valid_until':END,'revoked':False,'synthetic_only':True}
    snapshot={'id':'snapshot','schema':'SOLVERIS-B02-AUTHORIZED-READ-SNAPSHOT-V1','policy_subject':SUBJECT,'canonical_decisions_sha256':'','head_binding':{},'genesis_binding':{},'context':{},'execution_writer_binding':binding,'origin_report_bindings':reports,'origin_mandate_binding':mp,'valid_from':START,'valid_until':END,'revoked':False,'synthetic_only':True}
    root=dict(s['context'],runtime_profile=r.RUNTIME_PROFILE,recognition_binding=s['context']['authorization_binding'],snapshot_binding={})
    s.update(activation=a,execution=e,node=node,snapshot=snapshot,runtime_root=root,contexts=contexts,store=PreservedEvidenceStore(s['store_root']))
    refresh(s);return s

def check(s,synthetic=True):
    return r._institutional_core(s['store'],s['root'],root=s['runtime_root'],decisions=s['rows'],activation=s['activation'],execution=s['execution'],expected=s['expected'],now=NOW,synthetic=synthetic)

def origin(s,doc=None):
    result,snapshot,context,proofs=check(s);doc=doc or next(iter(r.DOCUMENTS))
    return r._origin_core(s['store'],s['root'],s['contexts'][doc],root=s['runtime_root'],snapshot=snapshot,now=NOW,synthetic=True,verified_proofs=proofs,verified_context=context)

def reseal_report(s,doc):
    report=s['reports'][doc];s['snapshot']['origin_report_bindings'][doc]={'id':report['id'],'sha256':proof(s,report)};refresh(s)

def test_positive_institutional_binding_keeps_execution_distinct_from_role(case):
    assert check(case)[0]['status']=='verified_synthetic'
    b=case['snapshot']['execution_writer_binding'];assert b['execution_id']!=b['writer_role']

@pytest.mark.parametrize('doc',list(r.DOCUMENTS))
def test_positive_each_origin_complete_chain_synthetic_only(case,doc):
    value=origin(case,doc);assert value['status']=='verified_synthetic' and value['temporal_profile']=='ordered_session_events'

def test_database_order_is_not_authority_order(case):
    case['rows'].reverse();assert check(case)[0]['status']=='verified_synthetic'

def test_real_domain_cannot_use_synthetic_bundle(case):
    with semantic_rejection():check(case,False)

def test_default_registries_remain_closed():
    assert not r._RUNTIME_AUTHORIZATIONS and not p._AUTHORIZED_CONTEXTS
    with pytest.raises(PolicyProofError,match='AUTHORIZATION_MISSING'):r._root(SUBJECT,NOW)

def test_entry_does_not_accept_client_root_or_callback(case):
    with pytest.raises(TypeError):r.admit_with_founder_runtime({},connection=None,bundle_directory=case['root'],evidence_directory=case['store_root'],now=NOW,root=case['runtime_root'])
    assert 'institutional_proof_verifier' not in inspect.signature(r.admit_with_founder_runtime).parameters

def test_r2_never_promotes_synthetic_positive(case):
    class Adapter:
        def verify_exact_chain(self,**kw):return check(case)[0]
    with pytest.raises(PolicyProofError,match='NOT_VERIFIED'):verify_institutional_evidence(Adapter(),case['expected'],connection=None)

@pytest.mark.parametrize('field,value',[('writer_role','admin'),('execution_id','exec-author'),('mandate_sha256','0'*64),('decision_binding',{'id':'other','sha256':'4'*64}),('revoked',True),('valid_until',START)])
def test_signed_but_invalid_execution_role_binding_rejected(case,field,value):
    b=case['snapshot']['execution_writer_binding'];b[field]=value;proof(case,b);refresh(case)
    with semantic_rejection():check(case)

@pytest.mark.parametrize('target,field,value',[('execution','actor_or_worker','admin'),('execution','state','pendente'),('activation','technical_actor','exec-integrator'),('execution','policy_hash','0'*64),('activation','record_hash','0'*64)])
def test_actual_canonical_execution_cannot_be_relabelled(case,target,field,value):
    case[target][field]=value
    with semantic_rejection():check(case)

def test_new_decision_cannot_hide_behind_pinned_favourable_chain(case):
    case['rows'].append(dict(case['rows'][-1],decision_id='revoked',decision_event='revogada'))
    with pytest.raises(PolicyProofError,match='STALE_OR_OMITTED'):check(case)

def test_ambiguity_not_fixed_by_refreshing_snapshot(case):
    case['rows'].append(copy.deepcopy(case['rows'][-1]));refresh(case)
    with pytest.raises(PolicyProofError,match='AMBIGUOUS'):check(case)

@pytest.mark.parametrize('field,value',[('current_review_sha256','0'*64),('sequence',2),('review_hashes',['0'*64]),('policy_subject',dict(SUBJECT,policy_hash='b'*64))])
def test_trusted_history_malformed_abstains(case,field,value):
    case['node'][field]=value;pin=put(case['store_root'],case['node']);case['snapshot'].update(head_binding=pin,genesis_binding=pin);case['runtime_root']['snapshot_binding']=put(case['store_root'],case['snapshot'])
    with semantic_rejection():check(case)

def test_resolved_history_byte_tampering(case):
    pin=case['runtime_root']['snapshot_binding'];path=case['store_root']/'sha256'/pin['sha256'][:2]/(pin['sha256']+'.json');path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(PolicyProofError,match='BYTES_ALTERED'):check(case)

def test_offset_intersection_uses_instants_not_lexical_order(case):
    case['runtime_root']['valid_until']='2026-10-21T20:00:00+00:00';case['snapshot']['valid_until']='2026-10-21T19:00:00-02:00';case['runtime_root']['snapshot_binding']=put(case['store_root'],case['snapshot'])
    _,context,_=r._resolve_history(case['store'],case['runtime_root'],case['rows'],now=NOW,synthetic=True)
    assert context['valid_until']=='2026-10-21T20:00:00+00:00'

def test_snapshot_preserves_verified_bytes_after_directory_mutation(case):
    frozen=p._BundleSnapshot(case['root']);before=frozen.read('proofs.json');(case['root']/'proofs.json').write_bytes(b'{}')
    assert frozen.read('proofs.json')==before
    with semantic_rejection():check(case)

@pytest.mark.parametrize('field,value',[('actor_execution','exec-integrator'),('technical_author_execution','invented'),('technical_integrator_execution','invented'),('outcome','inconclusivo'),('official_identifier','other'),('revoked',True),('mechanism','hash_only'),('document',{'id':'other'}),('doe_references',[]),('mechanism_assessment',[])])
def test_origin_signed_declarations_do_not_bypass_exact_context(case,field,value):
    doc=next(iter(r.DOCUMENTS));case['reports'][doc][field]=value;reseal_report(case,doc)
    with semantic_rejection():origin(case,doc)

@pytest.mark.parametrize('mode',['missing','late','wrong_execution','wrong_mandate'])
def test_origin_acceptance_precedes_examination_and_is_exact(case,mode):
    doc=next(iter(r.DOCUMENTS));report=case['reports'][doc];a=copy.deepcopy(case['files']['proofs.json'][report['mandate_acceptance_sha256']])
    if mode=='missing':a.pop('accepted_at')
    if mode=='late':a['accepted_at']='2026-10-21T03:00:00+00:00'
    if mode=='wrong_execution':a['execution_id']='exec-author'
    if mode=='wrong_mandate':a['mandate_sha256']='0'*64
    report['mandate_acceptance_sha256']=proof(case,a);reseal_report(case,doc)
    with semantic_rejection():origin(case,doc)

@pytest.mark.parametrize('mode',['cross_session','inverted_time','no_transcript','wrong_host'])
def test_origin_tls_is_same_verified_session(case,mode):
    doc=next(iter(r.DOCUMENTS));tls=case['tls'][doc];v=tls['payload']
    if mode=='cross_session':v['session_id']='another'
    if mode=='inverted_time':v['validated_at']='2026-10-21T01:00:03+00:00'
    if mode=='no_transcript':v['validation_transcript']=''
    if mode=='wrong_host':v['hostname']='unofficial.invalid'
    case['reports'][doc]['tls_evidence_binding']=put(case['store_root'],tls,'tls-'+doc);reseal_report(case,doc)
    with semantic_rejection():origin(case,doc)

def test_missing_actual_transport_evidence_is_not_echoed_verified(case):
    doc=next(iter(r.DOCUMENTS));pin=case['reports'][doc]['receipt_binding'];(case['store_root']/'sha256'/pin['sha256'][:2]/(pin['sha256']+'.json')).unlink()
    with pytest.raises(PolicyProofError,match='EVIDENCE_MISSING'):origin(case,doc)

def test_origin_requires_founder_signed_report(case):
    doc=next(iter(r.DOCUMENTS));case['files']['proofs.json'].pop(case['snapshot']['origin_report_bindings'][doc]['sha256']);seal(case)
    with pytest.raises(PolicyProofError,match='SIGNED_ORIGIN_REPORT_MISSING'):origin(case,doc)

def test_positive_never_changes_legacy_defaults(case):
    # A role binding is opt-in: old entry does not infer it from proofs.json.
    with semantic_rejection():p._verify_bundle(case['root'],expected=case['expected'],decisions=case['rows'],context=case['context'],now=NOW,synthetic=True)

def test_legacy_fixture_still_works_without_runtime_binding(tmp_path):
    s=build(tmp_path)
    assert p._verify_bundle(s['root'],expected=s['expected'],decisions=s['rows'],context=s['context'],now=NOW,synthetic=True)['status']=='verified_synthetic'

def test_public_real_bytes_divergence_abstains_without_db(case):
    result=r.verify_document_authenticity_with_founder_runtime(normative_artifact_id='a',document_id=next(iter(r.DOCUMENTS)),artifact_bytes=b'synthetic',context={'document_id':next(iter(r.DOCUMENTS))},connection=None,bundle_directory=case['root'],evidence_directory=case['store_root'],now=NOW)
    assert result['outcome']=='inconclusivo' and not result['origin_authenticated'] and not result['write_authorized'] and result['integrity']=='divergent'


def revised_runtime(s):
    from b02_founder_runtime_fixture import revised_case
    revised_case(s)
    history=s['files']['history.json'];previous=s['files']['proofs.json'][history['previous_revision']]
    old=copy.deepcopy(s['node']);old.update(id='history-genesis',history_sha256=r.digest(previous),object_sha256=previous['object_sha256'],current_review_sha256=previous['reviews'][0],review_hashes=previous['reviews'])
    pin=put(s['store_root'],old)
    s['node'].update(sequence=2,previous=pin,supersedes=pin)
    refresh(s);s['snapshot']['genesis_binding']=pin;s['runtime_root']['snapshot_binding']=put(s['store_root'],s['snapshot'])


def test_positive_material_revision_preserves_prior_inconclusive(case):
    revised_runtime(case)
    assert check(case)[0]['status']=='verified_synthetic'


def test_history_node_cannot_reassociate_old_reviews(case):
    revised_runtime(case)
    # Keep the union and current head intact; corrupt only old node association.
    pin=case['snapshot']['genesis_binding'];old=r._resolve(case['store'],pin);old['current_review_sha256']='0'*64
    replacement=put(case['store_root'],old);case['node'].update(previous=replacement,supersedes=replacement)
    head=put(case['store_root'],case['node']);case['snapshot'].update(head_binding=head,genesis_binding=replacement);case['runtime_root']['snapshot_binding']=put(case['store_root'],case['snapshot'])
    with pytest.raises(PolicyProofError,match='NODE_SNAPSHOT'):check(case)


def test_missing_history_predecessor_abstains(case):
    revised_runtime(case)
    pin=case['snapshot']['genesis_binding'];(case['store_root']/'sha256'/pin['sha256'][:2]/(pin['sha256']+'.json')).unlink()
    with pytest.raises(PolicyProofError,match='EVIDENCE_MISSING'):check(case)


def test_origin_after_snapshot_does_not_reread_mutated_directory(case):
    result,snapshot,context,proofs=check(case)
    (case['root']/'proofs.json').write_bytes(b'{}')
    doc=next(iter(r.DOCUMENTS))
    out=r._origin_core(case['store'],case['root'],case['contexts'][doc],root=case['runtime_root'],snapshot=snapshot,now=NOW,synthetic=True,verified_proofs=proofs,verified_context=context)
    assert out['status']=='verified_synthetic'


@pytest.mark.parametrize('flags,memberships',[(tuple([True]+[False]*5),0),((False,)*6,1)])
def test_privileged_reader_rejected(flags,memberships):
    class C:
        query=''
        def in_transaction(self):return True
        def execute(self,q,*a):self.query=str(q);return self
        def one(self):
            if 'current_database' in self.query:return ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on','repeatable read')
            return flags
        def scalar_one(self):return memberships
    with pytest.raises(PolicyProofError,match='PRIVILEGED'):r._read_identity(C())


def test_read_snapshot_queries_exact_canonical_tables_only(case):
    class C:
        query='';queries=[]
        def execute(self,q,params):self.query=str(q);self.queries.append((self.query,params));return self
        def mappings(self):return self
        def all(self):return case['rows']
        def one_or_none(self):return case['activation'] if 'EXACT_ACTIVATION' in self.query else case['execution']
    c=C();rows,a,e=r._read_snapshot(c,SUBJECT,dict(SUBJECT,policy_activation_id='activation',policy_activation_record_hash='5'*64))
    assert rows==case['rows'] and a==case['activation'] and e==case['execution']
    assert len(c.queries)==3 and all('SELECT' in q and not any(x in q.upper() for x in ('INSERT ','UPDATE ','DELETE ','CREATE ','GRANT ')) for q,_ in c.queries)
    assert 'policy_version=:' not in c.queries[0][0] # All versions remain visible.


def test_invalid_context_abstains_on_explicit_new_entry(case):
    answer=r.admit_with_founder_runtime(None,connection=None,bundle_directory=case['root'],evidence_directory=case['store_root'],now=NOW)
    assert not answer.permitido and answer.motivo=='DOCUMENTARY_CONTEXT_REQUIRED'


@pytest.mark.parametrize('keep_synthetic',['receipt','tls'])
def test_real_core_cannot_promote_synthetic_transport(case,keep_synthetic):
    doc=next(iter(r.DOCUMENTS));report=case['reports'][doc];report['synthetic_only']=False
    mp=case['snapshot']['origin_mandate_binding'];mandate=copy.deepcopy(case['files']['proofs.json'][mp['sha256']]);mandate['synthetic_only']=False
    newmp={'id':mandate['id'],'sha256':proof(case,mandate)};case['snapshot']['origin_mandate_binding']=newmp;report['mandate_binding']=newmp
    acceptance={'execution_id':report['actor_execution'],'mandate_sha256':r.digest(mandate),'accepted':True,'accepted_at':START};report['mandate_acceptance_sha256']=proof(case,acceptance)
    exam=copy.deepcopy(case['files']['proofs.json'][report['examination_record_sha256']]);exam['mandate_binding']=newmp;report['examination_record_sha256']=proof(case,exam)
    if keep_synthetic=='tls':
        receipt=case['receipts'][doc];receipt.pop('synthetic_only');rp=put(case['store_root'],receipt);report['receipt_binding']=rp;case['contexts'][doc].update(receipt_id=rp['id'],receipt_hash=rp['sha256'])
    reseal_report(case,doc)
    root=copy.deepcopy(case['runtime_root']);root['synthetic_only']=False
    with pytest.raises(PolicyProofError,match='SYNTHETIC_TRANSPORT_FORBIDDEN'):
        r._origin_core(case['store'],case['root'],case['contexts'][doc],root=root,snapshot=case['snapshot'],now=NOW,synthetic=False,verified_proofs=case['files']['proofs.json'],verified_context={'verified_author_execution':'exec-author','verified_integrator_execution':'exec-integrator'})


@pytest.mark.parametrize('flag',['true',1,None])
def test_malformed_transport_domain_abstains(flag):
    assert r._contains_synthetic({'results':[{'synthetic_only':flag}]})
    assert not r._contains_synthetic({'legacy_receipt_without_domain_field':True})
    assert not r._contains_synthetic({'synthetic_only':False})


@pytest.mark.parametrize('field',['own_findings','limitations','doe_references','mechanism_assessment'])
def test_boolean_is_not_independent_examination_or_reference(case,field):
    doc=next(iter(r.DOCUMENTS));report=case['reports'][doc]
    if field in ('own_findings','limitations'):
        exam=copy.deepcopy(case['files']['proofs.json'][report['examination_record_sha256']]);exam[field]=True;report['examination_record_sha256']=proof(case,exam)
    else:report[field]=True
    reseal_report(case,doc)
    with semantic_rejection():origin(case,doc)


def test_explicit_entry_wires_only_internal_adapter_without_legacy_fallback(case,monkeypatch):
    # Dispatch probe only: sentinel is NOT a successful authentication result.
    from app.services import sefa_pr_documentary_admission as admission
    calls=[];sentinel=object()
    def route(evidence,**kwargs):calls.append((evidence,kwargs));return sentinel
    monkeypatch.setattr(admission,'admit_documentary_verification',route)
    evidence={'policy_binding':{'subject':'synthetic'}}
    assert r.admit_with_founder_runtime(evidence,connection=None,bundle_directory=case['root'],evidence_directory=case['store_root'],now=NOW) is sentinel
    assert len(calls)==1 and type(calls[0][1]['institutional_proof_verifier']) is r._RuntimeAdapter
    assert calls[0][1]['institutional_proof_verifier'].binding==evidence['policy_binding']


def test_adapter_resolves_no_history_when_root_is_missing(case):
    class C:
        q='';queries=[]
        def in_transaction(self):return True
        def execute(self,q,*args):self.q=str(q);self.queries.append(self.q);return self
        def one(self):return ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on','repeatable read') if 'current_database' in self.q else (False,)*6
        def scalar_one(self):return 0
    c=C();adapter=r._RuntimeAdapter(case['root'],case['store_root'],NOW,{})
    with pytest.raises(PolicyProofError,match='AUTHORIZATION_MISSING'):adapter.verify_exact_chain(connection=c,expected=case['expected'])
    assert len(c.queries)==3 and adapter.resolved is None and not any('FOUNDER_RUNTIME_' in q for q in c.queries)
