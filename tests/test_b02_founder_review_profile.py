"""Synthetic-only candidates. No real key, authority, database or network."""
import copy
from datetime import datetime,timezone
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
from app.services import enterprise_b02_founder_review_profile as p
from app.services import enterprise_b02_institutional_verifier as legacy
from app.services.sefa_pr_policy_projection import validate_institutional_chain,verify_institutional_evidence,PolicyProofError
NOW=datetime(2026,10,21,12,tzinfo=timezone.utc)
START='2026-10-21T00:00:00+00:00';END='2026-10-22T00:00:00+00:00'
SUBJECT={'policy_type':'activation_authority','policy_id':'synthetic-sefa','policy_version':1,'policy_hash':'a'*64}
def digest(v):return p.sha(p.canonical(v))
def seal(s):
    root=s['root'];files=s['files'];d=s['decision'];entries=[]
    d['object_sha256']=digest(files['object.json']);d['review_sha256']=digest(files['review.json'])
    for n,v in sorted(files.items()):
        raw=p.canonical(v);(root/n).write_bytes(raw);entries.append({'path':n,'size':len(raw),'sha256':p.sha(raw)})
    raw=p.canonical({'entries':entries});(root/'manifest.json').write_bytes(raw);d['manifest_sha256']=p.sha(raw)
    raw=p.canonical(d);(root/'decision.json').write_bytes(raw);(root/'signature.bin').write_bytes(s['key'].sign(raw))
def repin(s):
    f=s['files'];s['context'].update(history_sha256=digest(f['history.json']),execution_records_sha256=digest(f['execution.json']),mandates_sha256=digest(f['mandates.json']),current_object_sha256=digest(f['object.json']),current_review_sha256=digest(f['review.json']))
def build(tmp_path,shared=False):
    key=Ed25519PrivateKey.generate();der=key.public_key().public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)
    author='exec-author';auditor='exec-review';integrator=author if shared else 'exec-integrator'
    obj={'policy_subject':SUBJECT,'documents':dict(p._DOCUMENTS),'use':'autenticar_documento_sefa_pr'};oh=digest(obj)
    review={'id':'audit','object_sha256':oh,'outcome':'favoravel','reviewer_execution':auditor,'author_execution':author,'integrator_execution':integrator,'inputs_sha256':[oh],'findings':['independent synthetic examination'],'limitations':['synthetic; shared infrastructure; material independence not proven'],'conflicts':[],'participation':'review_only','mandate_id':'m-reviewer','accepted':True,'addressed_reviews':[],'completed_at':START}
    proofs={}
    def proof(v):h=digest(v);proofs[h]=v;return h
    def pin(v):return {'id':v['id'],'sha256':proof(v)}
    def identity(x):return {'actor_id':x,'binding':pin({'id':'identity-'+x,'actor_id':x,'description':'synthetic execution record, not model identity'})}
    rows=[]
    fields=('decision_id','policy_type','policy_id','policy_version','policy_hash','decision_event','institutional_role','actor','previous_decision_id','timestamp')
    actors=(author,auditor,auditor,'Miguel');events=('submetida','auditoria_iniciada','auditada_favoravelmente','ratificada');roles=('proponente_institucional','auditor_independente','auditor_independente','autoridade_constitucional_final')
    for i,(actor,event,role) in enumerate(zip(actors,events,roles)):
        row=dict(SUBJECT,decision_id='d'+str(i),record_hash=str(i+1)*64,actor=actor,decision_event=event,institutional_role=role,previous_decision_id=rows[-1]['decision_id'] if rows else None,timestamp=START)
        previous_hash=rows[-1]['record_hash'] if rows else None
        record_pin=pin({'id':'record-'+str(i),'decision':{k:row[k] for k in fields},'previous_decision_record_hash':previous_hash})
        e={'policy_subject':SUBJECT,'previous_decision_record_hash':previous_hash,'actor_identity':identity(actor),'record_evidence':record_pin}
        if i==0:e['technical_author']=identity(author)
        if i==2:e['audit_report']={'policy_subject':SUBJECT,'auditor_id':auditor,'outcome':'favoravel','binding':{'id':'audit','sha256':digest(review)}}
        row['evidence']=e;rows.append(row)
    structural=validate_institutional_chain(rows,dict(SUBJECT,decision_id='d3',decision_hash='4'*64),now=NOW,technical_actor=integrator,activated_at=NOW)
    expected={k:v for k,v in structural.items() if k!='institutional_evidence_verified'}
    records=[];mandates=[]
    for who,role in ((auditor,'reviewer'),(author,'author'),(integrator,'integrator')):
        mid='m-'+role;ops={'reviewer':['review','reprove'],'author':['prepare','submit'],'integrator':['integrate_candidate','test']}[role]
        body={'id':mid,'issuer':'Miguel','execution_id':who,'role':role,'object_sha256':oh,'valid_from':START,'valid_until':END,'revoked':False,'operations':ops}
        m=dict(body,accepted=True,acceptance_sha256=proof({'execution_id':who,'mandate_sha256':digest(body),'accepted':True,'accepted_at':START}));mandates.append(m)
        participation='review_only' if role=='reviewer' else role
        ctx={'execution_id':who,'role':role,'instructions':'synthetic mandate instructions','provided_context':'synthetic object and adverse risks','participation':participation,'limitations':['provider/model not institutionally attested']}
        records.append({'id':who,'role':role,'mandate_id':mid,'context_sha256':proof(ctx),'inputs_sha256':[oh],'outputs_sha256':[digest(review)] if role=='reviewer' else [oh],'participation':participation,'provider':'synthetic-test','model_observation':'NOT_DEMONSTRATED','occurred_at':START})
    files={'object.json':obj,'review.json':review,'execution.json':{'executions':records},'mandates.json':{'mandates':mandates},'institutional.json':{'expected':expected,'decisions':rows},'history.json':{'object_sha256':oh,'revision':1,'previous_revision':None,'reviews':[digest(review)],'prior_reviews':[],'delta_sha256':None},'proofs.json':proofs}
    context={'synthetic_only':True,'profile':p.PROFILE,'adoption_sha256':p.ADOPTION,'scope':p.SCOPE,'policy_subject':SUBJECT,'enabled':True,'channel_authorized':True,'bootstrap_binding':{'id':'synthetic-bootstrap','sha256':'b'*64},'authorization_binding':{'id':'synthetic-authorization','sha256':'c'*64},'valid_from':START,'valid_until':END,'revoked':False,'public_key_der_hex':der.hex(),'key_fingerprint':p.sha(der),'history_complete':True,'history_branched':False,'unresolved_adverse_reviews':[]}
    decision={'domain':p.DOMAIN,'schema_version':1,'profile':p.PROFILE,'algorithm':'Ed25519','key_fingerprint':p.sha(der),'adoption_sha256':p.ADOPTION,'manifest_sha256':'','policy_subject':SUBJECT,'object_sha256':oh,'review_sha256':digest(review),'scope':p.SCOPE,'valid_from':START,'valid_until':END,'synthetic_only':True,'residual_risk_accepted':True}
    s={'root':tmp_path,'files':files,'context':context,'decision':decision,'key':key,'expected':expected,'rows':rows};repin(s);seal(s);return s
@pytest.fixture
def case(tmp_path):return build(tmp_path)
def check(s,synthetic=True):return p._verify_bundle(s['root'],expected=s['expected'],decisions=s['rows'],context=s['context'],now=NOW,synthetic=synthetic)
def test_complete_signed_bundle_positive_synthetic_only(case):assert check(case)['status']=='verified_synthetic'
def test_author_can_integrate_but_cannot_review(tmp_path):assert check(build(tmp_path,True))['status']=='verified_synthetic'
def test_r2_rejects_synthetic_status(case):
    class A:
        def verify_exact_chain(self,**kw):return check(case)
    with pytest.raises(PolicyProofError,match='NOT_VERIFIED'):verify_institutional_evidence(A(),case['expected'],connection=None)
def test_default_roots_closed():assert not p._AUTHORIZED_CONTEXTS and not legacy._TRUST_ROOTS
def test_no_public_payload_root(case):
    with pytest.raises(TypeError):p.admit_with_founder_review_bundle({},connection=None,evidence_directory=case['root'],now=NOW,context=case['context'])
def test_synthetic_cannot_be_real(case):
    with pytest.raises(PolicyProofError,match='TRUST_DOMAIN'):check(case,False)
@pytest.mark.parametrize('field,value',[('enabled',False),('channel_authorized',False),('bootstrap_binding',None),('authorization_binding',None),('adoption_sha256','0'*64),('revoked',True),('valid_until',START),('history_complete',False),('history_branched',True),('unresolved_adverse_reviews',['negative']),('history_sha256','0'*64),('current_review_sha256','0'*64)])
def test_authority_and_history_reject(case,field,value):
    case['context'][field]=value
    with pytest.raises(PolicyProofError):check(case)
@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{ "x": 1 }',b'{"x":1.5}',b'{"x":NaN}',b'\xef\xbb\xbf{}','{"x":"e\u0301"}'.encode()])
def test_strict_json(raw):
    with pytest.raises(PolicyProofError):p.parse(raw)
@pytest.mark.parametrize('name',['../escape','/absolute','a//b','a/./b','a/../b','a\\b','C:drive',''])
def test_invalid_paths(name):
    with pytest.raises(PolicyProofError):p._path(name)
@pytest.mark.parametrize('file',['review.json','object.json','proofs.json','mandates.json'])
def test_tampered_bytes(case,file):
    path=case['root']/file;path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(PolicyProofError,match='ALTERED'):check(case)
def test_signature_reject(case):
    (case['root']/'signature.bin').write_bytes(b'0'*64)
    with pytest.raises(PolicyProofError,match='SIGNATURE'):check(case)
def test_extra_file_reject(case):
    (case['root']/'extra').write_text('untrusted')
    with pytest.raises(PolicyProofError,match='UNDECLARED'):check(case)
def test_symlink_reject(case):
    q=case['root']/'review.json';outside=case['root'].parent/'outside.json';outside.write_bytes(q.read_bytes());q.unlink();q.symlink_to(outside)
    with pytest.raises(PolicyProofError,match='SYMLINK'):check(case)
@pytest.mark.parametrize('field,value',[('outcome','desfavoravel'),('outcome','inconclusivo'),('reviewer_execution','exec-author'),('accepted',False),('participation','author'),('limitations',[])])
def test_adverse_review_cannot_be_laundered(case,field,value):
    case['files']['review.json'][field]=value;repin(case);seal(case)
    with pytest.raises(PolicyProofError):check(case)
def test_missing_context_proof(case):
    h=case['files']['execution.json']['executions'][0]['context_sha256'];case['files']['proofs.json'].pop(h);seal(case)
    with pytest.raises(PolicyProofError,match='UNAVAILABLE'):check(case)
def test_exact_mandate_acceptance(case):
    case['files']['mandates.json']['mandates'][0]['operations']=['anything'];repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='OPERATIONS'):check(case)
def test_acceptance_cannot_transfer(case):
    case['files']['mandates.json']['mandates'][0]['acceptance_sha256']=digest(case['files']['object.json']);repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='ACCEPTANCE'):check(case)
def test_exact_review_binding(case):
    case['expected']['audit_report_binding']['sha256']='0'*64;seal(case)
    with pytest.raises(PolicyProofError,match='REPORT_BINDING'):check(case)
def test_history_previous_revision_required(case):
    case['files']['history.json']['revision']=2;repin(case);seal(case)
    with pytest.raises(PolicyProofError):check(case)
def test_hidden_prior_report_not_accepted(case):
    case['files']['history.json']['prior_reviews']=['0'*64];repin(case);seal(case)
    with pytest.raises(PolicyProofError):check(case)
def test_document_divergence(case):
    case['files']['object.json']['documents']['101201900571']='0'*64;repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='OBJECT'):check(case)
def test_fiscal_scope_denied(case):
    case['files']['object.json']['use']='fundamentacao_fiscal';repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='OBJECT'):check(case)
def test_missing_report(case):
    (case['root']/'review.json').unlink()
    with pytest.raises(PolicyProofError,match='MISSING'):check(case)
def test_canonical_row_divergence(case):
    case['rows'][1]['record_hash']='0'*64;seal(case)
    with pytest.raises(PolicyProofError):check(case)
def test_no_legacy_fallback(case):
    with pytest.raises(PolicyProofError,match='READ_TRANSACTION_REQUIRED'):p._FounderAdapter(case['root'],NOW).verify_exact_chain(connection=None,expected=case['expected'])

def test_mandate_must_cover_full_decision_interval(case):
    m=case['files']['mandates.json']['mandates'][0];m['valid_from']='2026-10-21T10:00:00+00:00'
    body={k:v for k,v in m.items() if k not in ('acceptance_sha256','accepted')}
    a={'execution_id':m['execution_id'],'mandate_sha256':digest(body),'accepted':True,'accepted_at':m['valid_from']}
    h=digest(a);case['files']['proofs.json'][h]=a;m['acceptance_sha256']=h;repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='CHRONOLOGY'):check(case)

def test_review_cannot_precede_acceptance(case):
    m=case['files']['mandates.json']['mandates'][0]
    a=copy.deepcopy(case['files']['proofs.json'][m['acceptance_sha256']]);a['accepted_at']='2026-10-21T01:00:00+00:00'
    h=digest(a);case['files']['proofs.json'][h]=a;m['acceptance_sha256']=h;repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='CHRONOLOGY'):check(case)

def revised_case(s):
    f=s['files'];proofs=f['proofs.json']
    old_object=copy.deepcopy(f['object.json']);old_object['policy_subject']['policy_hash']='b'*64;old_hash=digest(old_object);proofs[old_hash]=old_object
    old_review=copy.deepcopy(f['review.json']);old_review.update(object_sha256=old_hash,outcome='inconclusivo',inputs_sha256=[old_hash]);old_report_hash=digest(old_review);proofs[old_report_hash]=old_review
    previous={'object_sha256':old_hash,'revision':1,'previous_revision':None,'reviews':[old_report_hash],'prior_reviews':[],'delta_sha256':None}
    previous_hash=digest(previous);proofs[previous_hash]=previous
    delta={'from':old_hash,'to':digest(f['object.json']),'changes':['Corrected documentary binding'],'responses':{old_report_hash:'Corrected hash and linked exact evidence; reviewed again'}};delta_hash=digest(delta);proofs[delta_hash]=delta
    f['review.json']['addressed_reviews']=[old_report_hash];report_hash=digest(f['review.json'])
    s['expected']['audit_report_binding']['sha256']=report_hash
    s['rows'][2]['evidence']['audit_report']['binding']['sha256']=report_hash
    f['execution.json']['executions'][0]['outputs_sha256']=[report_hash]
    f['history.json'].update(revision=2,previous_revision=previous_hash,reviews=[report_hash],prior_reviews=[old_report_hash],delta_sha256=delta_hash)
    repin(s);seal(s);return old_report_hash

def test_material_correction_preserves_and_resolves_prior_inconclusive(case):
    revised_case(case);assert check(case)['status']=='verified_synthetic'

def test_missing_prior_report_bytes_abstain(case):
    old=revised_case(case);case['files']['proofs.json'].pop(old);seal(case)
    with pytest.raises(PolicyProofError,match='UNAVAILABLE'):check(case)

def test_prior_review_cannot_be_omitted(case):
    revised_case(case);case['files']['history.json']['prior_reviews']=[];repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='OMITTED'):check(case)

def test_adverse_same_object_cannot_be_answered_away(case):
    old=copy.deepcopy(case['files']['review.json']);old['outcome']='inconclusivo';h=digest(old);case['files']['proofs.json'][h]=old
    case['files']['history.json']['reviews'].append(h);case['files']['review.json']['addressed_reviews']=[h]
    # Keep the current report binding exact; reject the actual adverse report.
    rh=digest(case['files']['review.json']);case['files']['history.json']['reviews'][0]=rh
    case['expected']['audit_report_binding']['sha256']=rh;case['rows'][2]['evidence']['audit_report']['binding']['sha256']=rh
    case['files']['execution.json']['executions'][0]['outputs_sha256']=[rh];repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='SAME_OBJECT_ADVERSE'):check(case)

def test_malformed_historical_report_is_not_a_response(case):
    old=revised_case(case);bad={'outcome':'desfavoravel'};h=digest(bad);case['files']['proofs.json'][h]=bad
    case['files']['history.json']['reviews'].append(h);repin(case);seal(case)
    with pytest.raises(PolicyProofError):check(case)

def test_audit_report_cannot_precede_audit_opening(case):
    for row in case['rows'][1:]:row['timestamp']='2026-10-21T01:00:00+00:00'
    fields=('decision_id','policy_type','policy_id','policy_version','policy_hash','decision_event','institutional_role','actor','previous_decision_id','timestamp')
    for i,row in enumerate(case['rows']):
        proof={'id':'record-'+str(i),'decision':{k:row[k] for k in fields},'previous_decision_record_hash':row['evidence']['previous_decision_record_hash']}
        h=digest(proof);case['files']['proofs.json'][h]=proof
        row['evidence']['record_evidence']={'id':proof['id'],'sha256':h};case['expected']['record_evidence_bindings'][i]={'id':proof['id'],'sha256':h}
    case['decision']['valid_from']='2026-10-21T01:00:00+00:00';repin(case);seal(case)
    with pytest.raises(PolicyProofError,match='INSTITUTIONAL_CHRONOLOGY'):check(case)

class ReadConnection:
    def __init__(self,identity):self.identity=identity;self.queries=[]
    def in_transaction(self):return True
    def execute(self,query,*args):
        self.queries.append(str(query));return self
    def one(self):return self.identity

def test_explicit_entry_reads_identity_then_remains_closed(case):
    c=ReadConnection(('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on','repeatable read'))
    with pytest.raises(PolicyProofError,match='NOT_OPERATIONALLY_AUTHORIZED'):
        p._FounderAdapter(case['root'],NOW).verify_exact_chain(connection=c,expected=case['expected'])
    assert len(c.queries)==1 and c.queries[0].startswith('SELECT')

@pytest.mark.parametrize('identity',[
    ('protected_db','solveris_b02_writer','solveris_b02_writer','on','repeatable read'),
    ('solveris_b02_r4g_test','admin','admin','on','repeatable read'),
    ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','off','repeatable read'),
    ('solveris_b02_r4g_test','solveris_b02_writer','solveris_b02_writer','on','read committed')])
def test_wrong_read_identity_is_denied_before_evidence(case,identity):
    with pytest.raises(PolicyProofError,match='RESTRICTED_CONSISTENT_READ'):
        p._FounderAdapter(case['root'],NOW).verify_exact_chain(connection=ReadConnection(identity),expected=case['expected'])
