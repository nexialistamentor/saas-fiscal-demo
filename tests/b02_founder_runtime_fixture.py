# Reused fixture builder only; historical tests not executed.
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

