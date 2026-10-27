"""NEW verifier tests only. All positive specimens are explicitly synthetic."""
import base64
import copy
import hashlib
from datetime import datetime, timezone
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from app.services import enterprise_b02_institutional_verifier as iv
from app.services import enterprise_b02_sefa_pr_authenticity as av
from app.services.sefa_pr_policy_projection import verify_institutional_evidence, PolicyProofError

NOW=datetime(2026,10,21,tzinfo=timezone.utc)
FROM='2026-10-20T00:00:00+00:00';UNTIL='2026-10-22T00:00:00+00:00'
SUBJECT={'policy_type':'activation_authority','policy_id':'synthetic-sefa','policy_version':1,'policy_hash':'a'*64}
ROLES=['proponente_institucional','auditor_independente','auditor_independente','autoridade_constitucional_final']

def public(key):return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
def signed(payload,key):
    p=dict(payload,synthetic_only=True,valid_from=FROM,valid_until=UNTIL)
    return {'payload':p,'signature':{'algorithm':'Ed25519','key_sha256':iv.digest(public(key)),
        'value':base64.b64encode(key.sign(iv.canonical_bytes(p))).decode()}}
def put(root,envelope,identifier):
    raw=iv.canonical_bytes(envelope);h=iv.digest(raw);p=root/'sha256'/h[:2]/(h+'.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return {'id':identifier,'sha256':h}

@pytest.fixture
def specimen(tmp_path):
    issuer=Ed25519PrivateKey.generate();keys={a:Ed25519PrivateKey.generate() for a in ('proponent','auditor','ratifier','author','origin')}
    roles={'proponent':[ROLES[0]],'auditor':[ROLES[1]],'ratifier':[ROLES[3]],'author':['technical_author'],'origin':['documentary_origin_verifier']}
    identities={}
    for actor,key in keys.items():
        p=signed({'id':'identity-'+actor,'kind':'institutional_identity','policy_subject':SUBJECT,'actor_id':actor,'roles':roles[actor],'public_key_hex':public(key).hex()},issuer)
        identities[actor]={'actor_id':actor,'binding':put(tmp_path,p,'identity-'+actor)}
    bindings=[{'id':'decision-'+str(i),'sha256':str(i+1)*64} for i in range(4)]
    rows=[];recordpins=[]
    for i,actor in enumerate(('proponent','auditor','auditor','ratifier')):
        row=dict(SUBJECT,decision_id=bindings[i]['id'],record_hash=bindings[i]['sha256'],decision_event=('submetida','auditoria_iniciada','auditada_favoravelmente','ratificada')[i],institutional_role=ROLES[i],actor=actor,previous_decision_id=bindings[i-1]['id'] if i else None,timestamp=FROM,evidence={'previous_decision_record_hash':bindings[i-1]['sha256'] if i else None})
        fields=('decision_id','policy_type','policy_id','policy_version','policy_hash','decision_event','institutional_role','actor','previous_decision_id')
        payload={'id':'record-'+str(i),'kind':'policy_decision_evidence','decision':{k:row.get(k) for k in fields},'decision_timestamp':FROM,'previous_decision_record_hash':row['evidence']['previous_decision_record_hash']}
        pin=put(tmp_path,signed(payload,keys[actor]),payload['id']);rows.append(row);recordpins.append(pin)
    report={'id':'audit','kind':'independent_policy_audit','policy_subject':SUBJECT,'auditor_id':'auditor','outcome':'favoravel','decision_bindings':bindings[:2],'technical_author_id':'author','scope':'SEFA_PR_B02_DOCUMENTAL_AUTHENTICATION_ONLY'}
    expected={'policy_subject':SUBJECT,'decision_bindings':bindings,'actor_identity_bindings':[identities[x] for x in ('proponent','auditor','auditor','ratifier')],'technical_author':identities['author'],'technical_actor':'executor','record_evidence_bindings':recordpins,'audit_report_binding':put(tmp_path,signed(report,keys['auditor']),'audit')}
    root={'synthetic_only':True,'policy_subject':SUBJECT,'identity_issuer_public_key_hex':public(issuer).hex(),'ratification_binding':bindings[-1]}
    return {'store':iv.PreservedEvidenceStore(tmp_path),'rootpath':tmp_path,'root':root,'expected':expected,'rows':rows,'keys':keys,'issuer':issuer,'identities':identities}

def verify(s):return iv._verify_chain_bytes(s['store'],s['expected'],s['rows'],root=s['root'],now=NOW,synthetic=True)

def test_01_intact_signed_proof_is_synthetic_only(specimen):
    assert verify(specimen)['status']=='verified_synthetic'

def test_02_altered_bytes_rejected(specimen):
    p=specimen['expected']['audit_report_binding'];path=specimen['rootpath']/'sha256'/p['sha256'][:2]/(p['sha256']+'.json');path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(PolicyProofError,match='EVIDENCE_BYTES_ALTERED'):verify(specimen)

def test_03_wrong_signer_even_rehashed_rejected(specimen):
    old=specimen['expected']['audit_report_binding'];env=specimen['store'].resolve(old)
    env['signature']['key_sha256']='0'*64
    specimen['expected']['audit_report_binding']=put(specimen['rootpath'],env,'audit')
    with pytest.raises(PolicyProofError,match='SIGNER_NOT_AUTHORIZED'):verify(specimen)

def test_04_missing_decision_rejected(specimen):
    specimen['rows'].pop()
    with pytest.raises(PolicyProofError,match='DECISION_MISSING'):verify(specimen)

def test_05_missing_evidence_rejected(specimen):
    specimen['expected']['audit_report_binding']['sha256']='f'*64
    with pytest.raises(PolicyProofError,match='IMMUTABLE_EVIDENCE_MISSING'):verify(specimen)

def test_06_signature_tamper_cannot_be_hidden_by_new_hash(specimen):
    env=specimen['store'].resolve(specimen['expected']['audit_report_binding']);env['payload']['outcome']='forged'
    specimen['expected']['audit_report_binding']=put(specimen['rootpath'],env,'audit')
    with pytest.raises(PolicyProofError,match='SIGNATURE_INVALID'):verify(specimen)

def test_07_real_root_absent_is_safe_abstention():
    with pytest.raises(PolicyProofError,match='REAL_INSTITUTIONAL_TRUST_ANCHOR_MISSING'):iv._root_for(SUBJECT,NOW)

def test_08_synthetic_cannot_enter_real_verification(specimen):
    with pytest.raises(PolicyProofError,match='TRUST_ANCHOR_SUBJECT_DIVERGENCE'):
        iv._verify_chain_bytes(specimen['store'],specimen['expected'],specimen['rows'],root=specimen['root'],now=NOW,synthetic=False)

def test_09_trusted_entrypoint_has_no_callback_parameter():
    import inspect
    assert 'institutional_proof_verifier' not in inspect.signature(iv.admit_with_preserved_institutional_proofs).parameters
    assert 'root' not in inspect.signature(iv.admit_with_preserved_institutional_proofs).parameters

def test_10_duplicate_json_key_rejected(specimen):
    raw=b'{"payload":{},"payload":{}}';h=iv.digest(raw);p=specimen['rootpath']/'sha256'/h[:2]/(h+'.json');p.parent.mkdir(exist_ok=True);p.write_bytes(raw)
    with pytest.raises(PolicyProofError,match='DUPLICATE_KEY'):specimen['store'].resolve({'id':'x','sha256':h})

def origin_specimen(s):
    data=b'SYNTHETIC DOCUMENT BYTES ONLY';document=('https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/synthetic.pdf',iv.digest(data),len(data))
    binding=dict(SUBJECT,policy_activation_id='synthetic-active',policy_activation_record_hash='d'*64,decision_id='decision-3',decision_hash='4'*64)
    context={'document_id':'synthetic-document','policy_binding':binding,'verifier_id':av.VERIFIER_ID,'verifier_version':av.VERIFIER_VERSION,'verifier_hash':'e'*64,'session_id':'synthetic-session','received_at':FROM}
    receipt={'requested_url':document[0],'resolved_url':document[0],'http_status':200,'session_id':context['session_id'],'received_at':FROM,'artifact_hash':document[1],'byte_size':document[2]}
    pin=put(s['rootpath'],receipt,'synthetic-receipt');context.update(receipt_id=pin['id'],receipt_hash=pin['sha256'])
    tls={'payload':{'id':'tls','session_id':context['session_id'],'hostname':'www.sefanet.pr.gov.br','url':document[0],'chain_validation':'verified','hostname_validation':'verified','certificate_chain_sha256':['a'*64],'validation_transcript':{'synthetic_only':True,'result':'valid'},'validated_at':FROM}}
    tp=put(s['rootpath'],tls,'tls')
    report={'id':'origin-report','kind':'independent_document_origin','document':{'id':context['document_id'],'url':document[0],'sha256':document[1],'byte_size':document[2]},'policy_binding':binding,'verifier':{'id':av.VERIFIER_ID,'version':av.VERIFIER_VERSION,'hash':'e'*64},'actor_id':'origin','mechanism':av.MECHANISM,'criteria_id':av.CRITERIA,'outcome':'favoravel','receipt_binding':pin,'receipt_projection':{k:[k] for k in receipt},'tls_evidence_binding':tp,'official_identifier':context['document_id'],'doe_references':['SYNTHETIC DOE'],'mechanism_assessment':'SYNTHETIC independent assessment'}
    context['independent_origin_report']=put(s['rootpath'],signed(report,s['keys']['origin']),'origin-report')
    context['origin_verifier_identity']=s['identities']['origin']['binding']
    root=dict(s['root'],origin_mechanism=av.MECHANISM,origin_verifier=report['verifier'],origin_verifier_actor='origin')
    return context,document,root,report

def origin(s,c,d,r):return av._verify_origin(s['store'],c,root=r,now=NOW,synthetic=True,document=d)

def test_11_intact_origin_signature_receipt_tls_synthetic(specimen):
    c,d,r,_=origin_specimen(specimen);assert origin(specimen,c,d,r)['status']=='verified_synthetic'

def test_12_document_divergence_despite_valid_signature(specimen):
    c,d,r,_=origin_specimen(specimen)
    with pytest.raises(PolicyProofError,match='ORIGIN_DOCUMENT_DIVERGENCE'):origin(specimen,c,(d[0],'f'*64,d[2]),r)

def test_13_origin_verifier_not_enabled(specimen):
    c,d,r,_=origin_specimen(specimen);c['verifier_hash']='0'*64
    with pytest.raises(PolicyProofError,match='VERIFIER_NOT_ENABLED'):origin(specimen,c,d,r)

def test_14_missing_tls_abstains(specimen):
    c,d,r,report=origin_specimen(specimen);report['tls_evidence_binding']={'id':'missing','sha256':'f'*64}
    c['independent_origin_report']=put(specimen['rootpath'],signed(report,specimen['keys']['origin']),'origin-report')
    with pytest.raises(PolicyProofError,match='IMMUTABLE_EVIDENCE_MISSING'):origin(specimen,c,d,r)

def test_15_unapproved_mechanism_rejected(specimen):
    c,d,r,_=origin_specimen(specimen);r['origin_mechanism']='hash_and_tls_only'
    with pytest.raises(PolicyProofError,match='ORIGIN_MECHANISM_NOT_AUTHORIZED'):origin(specimen,c,d,r)

@pytest.mark.parametrize('doc',['101202501245','101201900571'])
def test_16_real_documents_never_accept_synthetic_bytes(tmp_path,doc):
    result=av.verify_document_authenticity(normative_artifact_id='synthetic-artifact',document_id=doc,artifact_bytes=b'synthetic',context={'document_id':doc},connection=None,evidence_directory=tmp_path,now=NOW)
    assert result['outcome']=='inconclusivo' and not result['origin_authenticated'] and not result['fiscal_authority'] and not result['persisted']
    assert result['reason']=='DOCUMENT_BYTES_DIVERGENCE'

def test_17_safe_abstention_invalid_context(tmp_path):
    result=av.verify_document_authenticity(normative_artifact_id='x',document_id='unknown',artifact_bytes=b'',context={},connection=None,evidence_directory=tmp_path,now=NOW)
    assert result['outcome']=='inconclusivo' and result['reason']=='DOCUMENT_DIVERGENCE'


def test_18_echo_object_is_not_an_accepted_dependency(tmp_path):
    class Echo:
        def verify_exact_chain(self, **kw):return {'status':'verified','verified_bindings':kw['expected']}
    with pytest.raises(TypeError):
        iv.admit_with_preserved_institutional_proofs({},connection=None,evidence_directory=tmp_path,institutional_proof_verifier=Echo())

def test_19_synthetic_success_is_rejected_by_r2_boundary(specimen):
    class SyntheticAdapter:
        def verify_exact_chain(self, **kw):return verify(specimen)
    with pytest.raises(PolicyProofError,match='INSTITUTIONAL_EVIDENCE_NOT_VERIFIED'):
        verify_institutional_evidence(SyntheticAdapter(),specimen['expected'],connection=None)

def test_20_no_connection_cannot_verify_real_chain(specimen):
    adapter=iv._InstitutionalAdapter(specimen['store'],NOW)
    with pytest.raises(PolicyProofError,match='READ_TRANSACTION_REQUIRED'):
        adapter.verify_exact_chain(connection=None,expected=specimen['expected'])

def test_21_divergent_identity_policy_rejected(specimen):
    pin=specimen['expected']['technical_author']['binding'];env=specimen['store'].resolve(pin)
    env['payload']['policy_subject']=dict(SUBJECT,policy_version=2)
    env=signed({k:v for k,v in env['payload'].items() if k not in ('synthetic_only','valid_from','valid_until')},specimen['issuer'])
    specimen['expected']['technical_author']['binding']=put(specimen['rootpath'],env,env['payload']['id'])
    with pytest.raises(PolicyProofError,match='IDENTITY_POLICY_DIVERGENCE'):verify(specimen)
