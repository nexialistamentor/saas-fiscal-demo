"""B02 RCV31-R3: independent read-only observer, DISPOSABLE ONLY.

Inputs are selectors, a read-only DB connection and separately pinned public
trust. No writer Operation, SignedProofPorts, expected_units, or private keys.
Never writes SQL; checks documentary graph and signed exact manifest.
"""
from __future__ import annotations
import argparse, base64, hashlib, hmac, json, os, re, sqlite3, sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

HEX=re.compile(r'^[0-9a-f]{64}$')
IDENT=re.compile(r'^[A-Za-z0-9_.:-]{1,128}$')
DOCS={
 '101201900571':('af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d',1944929),
 '101202501245':('e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832',258302)
}
SCHEMA_DECISION='SOLVERIS_B02_G5_SIGNED_OPERATIONAL_DECISION_V1'
SCHEMA_UNIT='SOLVERIS_B02_G5_SIGNED_INSPECTION_UNIT_V1'
SCHEMA_TX='SOLVERIS_B02_G5_SIGNED_MANIFEST_ATTESTATION_V1'
class Rejected(RuntimeError):pass
def insist(p,why):
 if not p:raise Rejected('STOP:'+why)
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def pairs(p):
 x={}
 for k,v in p:
  insist(k not in x,'JSON_DUPLICATE_KEY');x[k]=v
 return x
def parse(raw,canonical=False):
 insist(isinstance(raw,bytes) and len(raw)<=1048576,'DOCUMENT_INVALID_BYTES')
 v=json.loads(raw.decode('utf8'),object_pairs_hook=pairs)
 insist(type(v) is dict,'DOCUMENT_NOT_OBJECT')
 if canonical:insist(canon(v)==raw,'SIGNED_RECORD_NOT_CANONICAL')
 return v
def blob(x):
 if isinstance(x,memoryview):return x.tobytes()
 if isinstance(x,bytearray):return bytes(x)
 return x
def as_jsonb(v):
 if isinstance(v,dict):return v
 if isinstance(v,str):return parse(v.encode())
 insist(False,'JSONB_INVALID')
def key(data,field):
 root=Path(data[field+'_path'])
 insist(root.is_file() and root.is_absolute() and not root.is_symlink(),'TRUST_ROOT_MISSING')
 raw=root.read_bytes();p=data[field+'_sha256']
 insist(HEX.fullmatch(p) and hmac.compare_digest(sha(raw),p),'TRUST_ROOT_DIVERGENT')
 obj=serialization.load_der_public_key(raw)
 insist(isinstance(obj,Ed25519PublicKey),'TRUST_ROOT_NOT_ED25519')
 return obj
def record(raw,signer,kind,expected,when):
 e=parse(raw,canonical=True)
 insist(set(e)=={'payload','signature_base64'} and type(e['payload']) is dict,'EVIDENCE_ENVELOPE_INVALID')
 p=e['payload']; insist(p.get('schema')==kind,'EVIDENCE_SCHEMA_DIVERGENT')
 for k,v in expected.items():insist(p.get(k)==v,'EVIDENCE_SCOPE_DIVERGENT_'+k)
 try:
  vf=datetime.fromisoformat(p['valid_from']);vu=datetime.fromisoformat(p['valid_until'])
  insist(vf.tzinfo is not None and vu.tzinfo is not None and vf<=when<vu,'EVIDENCE_NOT_VALID_AT_COMMIT')
  sig=base64.b64decode(e['signature_base64'],validate=True)
  insist(len(sig)==64,'EVIDENCE_SIGNATURE_LENGTH')
  signer.verify(sig,canon(p))
 except (ValueError,KeyError,TypeError) as ex:raise Rejected('STOP:EVIDENCE_INVALID') from ex
 return p

def rows(db,stmt,args=()):
 # Statements are static; ONLY selector values are parameters.
 cur=db.cursor()
 try:
  mod=type(db).__module__
  if mod.startswith('sqlite3'):stmt=stmt.replace('%s','?')
  cur.execute(stmt,args)
  names=[c[0] for c in cur.description]
  return [dict(zip(names,r)) for r in cur.fetchall()]
 finally:cur.close()
def one(db,stmt,args=(),code='EXPECTED_EXACTLY_ONE_ROW'):
 res=rows(db,stmt,args);insist(len(res)==1,code);return res[0]

def observe(db,approval_id,release_id,txid,trust):
 for x in (approval_id,release_id,txid):insist(IDENT.fullmatch(x),'SELECTOR_INVALID')
 decision_root=key(trust,'decision');reviewer_root=key(trust,'reviewer');signer_root=key(trust,'signer')
 insist(len({trust['decision_sha256'],trust['reviewer_sha256'],trust['signer_sha256']})==3,
        'ROOTS_NOT_SEPARATED')
 reservation=one(db,'''SELECT * FROM public.b02_g5_operational_approval_uses
                    WHERE approval_id=%s AND release_id=%s AND assigned_txid=%s''',
                    (approval_id,release_id,txid),'RESERVATION_MISSING_OR_MULTIPLE')
 evidence=one(db,'''SELECT * FROM public.b02_g5_committed_chain_evidence
                     WHERE approval_id=%s AND release_id=%s AND assigned_txid=%s''',
                   (approval_id,release_id,txid),'CHAIN_EVIDENCE_MISSING_OR_MULTIPLE')
 manifest=blob(evidence['manifest_utf8']);signature=blob(evidence['signature']);decision=blob(evidence['decision_bytes'])
 insist(type(manifest) is bytes and type(signature) is bytes and len(signature)==64,
        'PERSISTED_SIGNER_SHAPE')
 signer_root.verify(signature,manifest)
 m=parse(manifest)
 one_shot=m.get('g5_one_shot',{});server=m.get('server',{})
 insist(m.get('synthetic_only') is True,'NOT_DISPOSABLE_OBSERVER_SCOPE')
 for k,v in {'approval_id':approval_id,'release_id':release_id,'assigned_txid':txid}.items():
  insist(one_shot.get(k)==v,'MANIFEST_ONE_SHOT_DIVERGENT_'+k)
 insist(server.get('txid')==txid,'MANIFEST_TXID_DIVERGENT')
 insist(server.get('database_name')==trust['database_name'] and
        server.get('system_identifier')==trust['system_identifier'],'SERVER_IDENTITY_DIVERGENT')
 insist(str(server.get('database_oid'))==str(trust['database_oid']) and
        str(server.get('writer_oid'))==str(trust['writer_oid']),'SERVER_OIDS_DIVERGENT')
 insist(str(reservation['operator_sha256']).strip()==one_shot.get('operator_sha256'),
        'RESERVATION_OPERATOR_DIVERGENT')
 dec_digest=sha(decision)
 insist(dec_digest==one_shot.get('decision_document_sha256')==str(reservation['decision_document_sha256']).strip(),
        'DECISION_BYTES_NOT_SIGNED_IN_MANIFEST')
 # Exact original transaction timestamp is server-owned; not a date supplied
 # by the writer. The SQL disallows INSERT to written_at for the writer.
 stamp=evidence.get('written_at')
 if isinstance(stamp,str):stamp=datetime.fromisoformat(stamp)
 insist(isinstance(stamp,datetime) and stamp.tzinfo is not None,
        'SERVER_TRANSACTION_TIMESTAMP_MISSING')
 when=stamp.astimezone(timezone.utc)
 docpins=DOCS
 if os.environ.get('B02_TEST_ONLY_SQLITE_OBSERVER')=='1' and 'synthetic_docs' in trust:
  candidate=trust['synthetic_docs']
  insist(set(candidate)==set(DOCS) and all(isinstance(v,list) and len(v)==2 and
    HEX.fullmatch(v[0]) and isinstance(v[1],int) for v in candidate.values()),
    'SYNTHETIC_DOCS_INVALID')
  docpins={k:tuple(v) for k,v in candidate.items()}
 decision_payload=record(decision,decision_root,SCHEMA_DECISION,{
   'object_sha256':trust['approved_object_sha256'],
   'institutional_scope_sha256':trust['institutional_scope_sha256'],
   'approval_id':approval_id,'release_id':release_id,
   'operator_sha256':one_shot['operator_sha256'],
   'system_identifier':trust['system_identifier'],
   'database_oid':int(trust['database_oid']),'writer_oid':int(trust['writer_oid'])},when)
 insist(decision_payload.get('document_sha256_set')==sorted(v[0] for v in docpins.values()) and
        decision_payload.get('use')=='one_shot_b02_g5_two_documents',
        'DECISION_DOCUMENT_SET_NOT_APPROVED')
 docs=m.get('documents');insist(type(docs) is list and len(docs)==2,'MANIFEST_TWO_DOCUMENTS_REQUIRED')
 insist({(x['id'],x['sha256'],x['byte_size']) for x in docs}==
        {(k,v[0],v[1]) for k,v in docpins.items()},'MANIFEST_PRESERVED_BYTES_DIVERGENT')
 witnesses=as_jsonb(evidence['unit_witnesses'])
 insist(set(witnesses)==set(DOCS),'SIGNED_UNIT_SET_INCOMPLETE')
 # Existing archive uses array of server-generated record hashes. Those are
 # reconstructed from persisted rows, not from writer Operation.
 manifest_graph=m.get('units')
 insist(type(manifest_graph) is list and len(manifest_graph)==2,'MANIFEST_CHAIN_UNITS_MISSING')
 # Rebuild the policy root from persisted policy_versions, not from an
 # operator-supplied trusted status or a writer-produced screenshot.
 release_policy=m.get('release_policy_hash')
 if release_policy is not None:
  policy=one(db,'SELECT * FROM public.policy_versions WHERE policy_hash=%s',
             (release_policy,),'SIGNED_POLICY_VERSION_NOT_UNIQUE')
  insist(policy['domain']=='SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE' and
         policy['policy_type']=='activation_authority',
         'SIGNED_POLICY_NOT_G5_AUTHORITY_DOMAIN')
  expected_binding=as_jsonb(m.get('g5_policy_binding'))
  insist(expected_binding.get('policy_hash')==release_policy and
         expected_binding.get('policy_id')==policy['policy_id'] and
         expected_binding.get('policy_version')==policy['policy_version'],
         'G5_POLICY_NOT_IN_SIGNED_RELEASE_MANIFEST')
  insist(type(m.get('authority_snapshot_hash')) is str and
         HEX.fullmatch(m['authority_snapshot_hash']),
         'SIGNED_AUTHORITY_SNAPSHOT_HASH_MISSING')
 else:
  insist(os.environ.get('B02_TEST_ONLY_SQLITE_OBSERVER')=='1',
         'SIGNED_RELEASE_POLICY_HASH_MISSING')
 observed_graph=[]
 for docid,(expected_sha,expected_size) in docpins.items():
  b64=witnesses[docid]
  insist(type(b64) is str,'WITNESS_BAD_STORAGE')
  unit_raw=base64.b64decode(b64,validate=True)
  p=record(unit_raw,reviewer_root,SCHEMA_UNIT,
     {'document_id':docid,'document_sha256':expected_sha,
      'document_byte_size':expected_size,'txid':txid},when)
  for k in ('receipt_id','receipt_hash','verification_id','approved_review_sha256','review_record_id'):
   insist(type(p.get(k)) is str,'WITNESS_IDENTIFIER_OR_REVIEW_MISSING_'+k)
  receipt=one(db,'SELECT * FROM public.noncredential_acquisition_receipts WHERE receipt_id=%s',
           (p['receipt_id'],),'RECEIPT_NOT_UNIQUE')
  insist(receipt['assigned_txid']==txid and receipt['receipt_hash']==p['receipt_hash'] and
         receipt['artifact_hash']==expected_sha and receipt['byte_size']==expected_size,
         'RECEIPT_NOT_BOUND_TO_WITNESS')
  bind=one(db,'SELECT * FROM public.acquisition_mode_bindings WHERE mode_binding_id=%s',
           (receipt['mode_binding_id'],),'BINDING_NOT_UNIQUE')
  insist(bind['assigned_txid']==txid and bind['record_hash']==receipt['mode_binding_hash'] and
         bind['acquisition_execution_id']==receipt['acquisition_execution_id'] and
         bind['mode']=='LOCAL_CAS_INCORPORATION','BINDING_NOT_BOUND_TO_RECEIPT')
  if release_policy is not None:
   security=as_jsonb(bind['security_policy_binding'])
   sanitation=as_jsonb(bind['sanitization_policy_binding'])
   insist(security==sanitation and security.get('policy_hash')==release_policy and
          security.get('policy_id')==policy['policy_id'] and
          security.get('policy_version')==policy['policy_version'],
          'BINDING_POLICY_NOT_PRESENT_IN_SIGNED_RELEASE')
  verification=one(db,'SELECT * FROM public.noncredential_sanitization_verifications WHERE verification_id=%s',
                   (p['verification_id'],),'VERIFICATION_NOT_UNIQUE')
  insist(verification['receipt_id']==p['receipt_id'] and
         verification['receipt_hash']==p['receipt_hash'] and
         verification['assigned_txid']==txid and
         verification['verification_outcome']=='verified_sanitized',
         'SANITIZATION_NOT_BOUND_TO_RECEIPT')
  artifact=one(db,'SELECT * FROM public.normative_artifacts WHERE acquisition_execution_id=%s',
               (receipt['acquisition_execution_id'],),'ARTIFACT_NOT_UNIQUE')
  raw=blob(artifact['immutable_bytes'])
  insist(type(raw) is bytes and sha(raw)==expected_sha and len(raw)==expected_size,
         'ARTIFACT_BYTES_DIVERGENT')
  reference=one(db,'SELECT * FROM public.artifact_references WHERE artifact_reference_id=%s',
                (artifact['artifact_reference_id'],),'REFERENCE_NOT_UNIQUE')
  insist(bind['artifact_reference_id']==reference['artifact_reference_id'] and
         artifact['artifact_reference_id']==reference['artifact_reference_id'],
         'REFERENCE_LINK_DIVERGENT')
  auths=rows(db,'''SELECT * FROM public.artifact_verification_records
                  WHERE normative_artifact_id=%s AND verification_type='authenticity'
                  AND outcome='conclusivo_favoravel' ''',(artifact['normative_artifact_id'],))
  insist(len(auths)==1 and auths[0]['verified_artifact_hash']==expected_sha,
         'AUTHENTICITY_NOT_INDEPENDENTLY_BOUND')
  executions=rows(db,'''SELECT * FROM public.acquisition_executions
        WHERE acquisition_execution_id=%s AND attempt_number=%s''',
       (receipt['acquisition_execution_id'],receipt['attempt_number']))
  events={r['execution_event'] for r in executions}
  insist(len(executions)==3 and events=={'criacao','inicio','conclusao'},
         'THREE_EXECUTION_EVENTS_NOT_RECONSTRUCTED')
  terminal=next(e for e in executions if e['execution_event']=='conclusao')
  insist(terminal['artifact_reference_id']==reference['artifact_reference_id'] and
         terminal['projected_state']=='concluida',
         'TERMINAL_EVENT_NOT_BOUND')
  graph={'binding':bind['record_hash'],'receipt':receipt['record_hash'],
         'receipt_material':receipt['receipt_hash'],
         'verification':verification['record_hash'],
         'terminal':terminal['record_hash'],'artifact':artifact['record_hash'],
         'authenticity':auths[0]['record_hash']}
  observed_graph.append(graph)
 insist(sorted(map(canon,observed_graph))==sorted(map(canon,manifest_graph)),
        'MANIFEST_PERSISTED_CHAIN_HASHES_DIVERGENT')
 reviewer_witness=base64.b64decode(evidence['manifest_witness'],validate=True)
 record(reviewer_witness,reviewer_root,SCHEMA_TX,
        {'manifest_sha256':sha(manifest),'txid':txid,
         'operator_sha256':one_shot['operator_sha256']},when)
 # PRE_COMMIT evidence bindings must match the final signed manifest.
 bindings=one_shot.get('authenticated_evidence_sha256')
 insist(type(bindings) is dict and bindings.get('decision')==dec_digest and
        bindings.get('unit_witnesses')=={d:sha(base64.b64decode(witnesses[d],validate=True)) for d in docpins},
        'SIGNED_AUTHENTICATION_COMMITMENT_DIVERGENT')
 return {'status':'PASS_INDEPENDENT_READ_ONLY_DISPOSABLE',
         'approval_id':approval_id,'txid_sha256':sha(txid.encode()),
         'manifest_sha256':sha(manifest),'units':2,'record_hash_chains':2,
         'decision_signature_reverified':True,'unit_signatures_reverified':True,
         'manifest_signatures_reverified':True,'separate_process':True}

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--approval-id',required=True);p.add_argument('--release-id',required=True)
 p.add_argument('--txid',required=True)
 p.add_argument('--trust-profile',type=Path,required=True)
 p.add_argument('--trust-profile-sha256',required=True)
 p.add_argument('--fixture-sqlite',type=Path,help='Local unit tests ONLY; never PostgreSQL proof')
 a=p.parse_args()
 try:
  insist(HEX.fullmatch(a.trust_profile_sha256),'TRUST_PROFILE_PIN_INVALID')
  content=a.trust_profile.read_bytes()
  insist(hmac.compare_digest(sha(content),a.trust_profile_sha256),'TRUST_PROFILE_SHA256_DIVERGENT')
  trust=parse(content,canonical=True)
  if a.fixture_sqlite is None:
   # R3 acceptance: the writer MAY NOT choose fresh trusted public roots
   # by supplying a new trust file and its own digest.  Exactly the roots
   # sealed in this reviewed, hash-verified DISPOSABLE unit are accepted.
   rootpins=Path(__file__).with_name('RCV31_R3_TRUST_ROOTS_PINNED_SINTETICO.json')
   insist(rootpins.is_file() and
          hmac.compare_digest(sha(rootpins.read_bytes()),
            'aaeab63ef5ad3d636d80bbe58bb59c84996cc7b8920919d126daae1bcc72ec86'),
          'EXTERNAL_DISPOSABLE_TRUST_PIN_FILE_DIVERGENT')
   pins=json.loads(rootpins.read_text(encoding='utf8'))
   insist(pins['institutional_authority'] is False,
          'INSTITUTIONAL_ROOT_NOT_PROVEN')
   for name in ('decision','reviewer','signer'):
    insist(trust.get(name+'_sha256')==pins[name+'_sha256'],
           'OBSERVER_EXTERNAL_ROOT_DIVERGENT_'+name)
   insist(trust.get('institutional_scope_sha256')==pins['scope_sha256'] and
          trust.get('approved_object_sha256')==pins['object_sha256'],
          'OBSERVER_EXTERNAL_SCOPE_DIVERGENT')
  if a.fixture_sqlite is not None:
   insist(os.environ.get('B02_TEST_ONLY_SQLITE_OBSERVER')=='1','SQLITE_FIXTURE_FORBIDDEN')
   db=sqlite3.connect('file:'+str(a.fixture_sqlite)+'?mode=ro',uri=True)
   db.execute("ATTACH DATABASE 'file:"+str(a.fixture_sqlite)+"?mode=ro' AS public")
  else:
   import psycopg2
   dsn=os.environ['B02_OBSERVER_DSN']
   db=psycopg2.connect(dsn,connect_timeout=8)
   db.set_session(readonly=True,autocommit=False)
   with db.cursor() as c:
    c.execute("SELECT current_database(),current_user")
    name,role=c.fetchone()
    insist(name==trust['database_name'] and role==trust['observer_role'],
           'OBSERVER_DB_OR_ROLE_DIVERGENT')
    c.execute("SELECT has_table_privilege(current_user,'public.b02_g5_committed_chain_evidence','INSERT,UPDATE,DELETE')")
    insist(c.fetchone()[0] is False,'OBSERVER_ROLE_NOT_READ_ONLY')
  try:result=observe(db,a.approval_id,a.release_id,a.txid,trust)
  finally:db.rollback();db.close()
  print(json.dumps(result,sort_keys=True));return 0
 except Exception as exc:
  print(json.dumps({'status':'STOP_OBSERVER','error':type(exc).__name__+':'+str(exc)[:150]}));return 2
if __name__=='__main__':sys.exit(main())
