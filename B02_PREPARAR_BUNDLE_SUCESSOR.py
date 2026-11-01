#!/usr/bin/env python3
"""Empacotador, NAO assinador/verificador de autoridade. Usa o perfil existente.
Recebe APENAS novos atos proprios e evidencia ja custodida pelo emissor.
Nao reutiliza decision/signature/ROOT antigos, nao decide vigencia ou revogacao.
"""
from __future__ import annotations
import argparse, hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.serialization import load_der_public_key, Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from app.services.enterprise_b02_founder_review_profile import canonical, parse, sha, DOMAIN, PROFILE, SCOPE, ADOPTION

FILES=('execution.json','history.json','institutional.json','mandates.json','object.json','proofs.json','review.json')
SUBJECT={'policy_type':'activation_authority','policy_id':'SOLVERIS-B02-SEFA-PR-DOCUMENTARY-AUTHORITY','policy_version':1,'policy_hash':'05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a'}
FP='6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c'
DOCS={'101202501245':'e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832','101201900571':'af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d'}
def stop(x):raise RuntimeError('STOP_B02_PREASSINATURA_'+x)

RECOGNITION_FILE='B02_FOUNDER_ORIGIN_RECONHECIMENTO_CHAVE_MIGUEL_20261101_RETIFICACAO.json'
RECOGNITION_GIT_BLOB='7ec8611d3bbce7db06b7f775b726a93c65393797'

def _recognized_key_scope():
    """Consume the exact ratified document without claiming a new signature."""
    source=Path(__file__).resolve().with_name(RECOGNITION_FILE)
    if source.is_symlink() or not source.is_file():
        stop('RATIFICATION_SOURCE_NOT_PRESENT')
    raw=source.read_bytes()
    git_blob=hashlib.sha1(b'blob '+str(len(raw)).encode('ascii')+bytes([0])+raw).hexdigest()
    if git_blob!=RECOGNITION_GIT_BLOB:
        stop('RATIFICATION_DOCUMENT_CHANGED')
    item=json.loads(raw)
    if (item.get('schema')!='SOLVERIS_B02_FOUNDER_ORIGIN_KEY_RECOGNITION_V3_V1'
        or item.get('status')!='RATIFIED_KEY_ELIGIBILITY_RECOGNITION_CORRECTED_NO_SIGNATURE'
        or item.get('ratifier')!='Miguel' or item.get('policy_subject')!=SUBJECT
        or item.get('public_key',{}).get('public_der_sha256_fingerprint')!=FP
        or item.get('public_key',{}).get('control_of_corresponding_private_key')!='DECLARED_BY_RATIFIER_PERSONALLY'
        or item.get('public_key',{}).get('not_revoked')!='DECLARED_BY_RATIFIER_AFTER_CONSULTING_CUSTODY_RECORDS_NO_KNOWN_COMPETENT_REVOCATION'
        or item.get('g4_reconciled_activation',{}).get('policy_activation_id')!='B02-05ede-activation-v4'
        or item.get('g4_reconciled_activation',{}).get('policy_activation_record_hash')!='cf617e146b3451555898d8253fba8bb13dfa6ff99776b50978e0ba68df4cb482'
        or {x['document_id']:x['sha256'] for x in item.get('exact_document_scope',[])}!=DOCS
        or item.get('approval',{}).get('prepare_new_successor_documentary_decision') is not True
        or item.get('approval',{}).get('authorize_local_signing_now') is not False
        or item.get('approval',{}).get('authorize_pg_protected_migration_or_activation') is not False
        or item.get('approval',{}).get('accept_residual_risk_by_this_recognition_alone') is not False
        or item.get('validity',{}).get('maximum_valid_until_utc_exclusive')!='2026-11-15T00:00:00+00:00'
        or item.get('validity',{}).get('signer_existing_limits')!='MUST_NOT_BE_RELAXED_OR_EXTENDED'
        or item.get('validity',{}).get('no_backdating') is not True
        or item.get('rectification',{}).get('corrected_policy_hash_64_characters')!=SUBJECT['policy_hash']
        or item.get('rectification',{}).get('predecessor_git_blob')!='28dd836199957cc2e64cc96286b4b1fefd9247ff'):
        stop('RECOGNITION_SCOPE_OR_AUTHORITY_MISMATCH')
    return item

def dt(v):
    try:r=datetime.fromisoformat(v)
    except Exception:stop('TIME_INVALID')
    if r.tzinfo is None:stop('TIME_WITHOUT_OFFSET')
    return r.astimezone(timezone.utc)

def _public_key(path):
    """Only a pinned historic ROOT.json or a public DER, never private material."""
    if path.name == 'ROOT.json':
        raw_root = path.read_bytes()
        if sha(raw_root) != '398e3938b11af5694c65fad4412303681651cb906aa5acfff2ef9c1de6caa4ff':
            stop('HISTORICAL_ROOT_NOT_PINNED')
        root = json.loads(raw_root)
        if root.get('key_fingerprint') != FP:
            stop('HISTORICAL_ROOT_KEY_DIVERGENCE')
        raw = bytes.fromhex(root['public_key_der_hex'])
    elif path.suffix.lower() == '.der':
        raw = path.read_bytes()
    else:
        stop('PUBLIC_KEY_INPUT_MUST_BE_DER_OR_HISTORIC_PINNED_ROOT_JSON')
    if sha(raw) != FP:
        stop('HISTORICAL_PUBLIC_KEY_FINGERPRINT_DIVERGENCE')
    key = load_der_public_key(raw)
    if not isinstance(key, Ed25519PublicKey) or key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo) != raw:
        stop('ED25519_DER_INVALID')
    return key


def _verify_signed_bundle(folder, public_path):
    """Offline material/signature preflight ONLY; no trust-root deployment or institutional approval."""
    if folder.is_symlink() or not folder.is_dir():
        stop('SIGNED_BUNDLE_DIRECTORY_INVALID')
    expected = set(FILES) | {'manifest.json', 'decision.json', 'signature.bin'}
    entries = list(folder.iterdir())
    if any(x.is_symlink() or not x.is_file() for x in entries) or {x.name for x in entries} != expected:
        stop('SIGNED_BUNDLE_EXACT_FILE_SET_REQUIRED')
    content = {x.name: x.read_bytes() for x in entries}
    if any(len(x) > 4 * 1024 * 1024 for x in content.values()) or sum(map(len,content.values())) > 16 * 1024 * 1024:
        stop('SIGNED_BUNDLE_SIZE_LIMIT')
    decision_raw = content['decision.json']
    decision = parse(decision_raw)
    fields = {'domain','schema_version','profile','algorithm','key_fingerprint','adoption_sha256',
              'manifest_sha256','policy_subject','object_sha256','review_sha256','scope',
              'valid_from','valid_until','synthetic_only','residual_risk_accepted'}
    if set(decision) != fields or (
        decision['domain'],decision['schema_version'],decision['profile'],decision['algorithm'],
        decision['key_fingerprint'],decision['adoption_sha256'],decision['policy_subject'],
        decision['scope'],decision['synthetic_only'],decision['residual_risk_accepted']
    ) != (DOMAIN,1,PROFILE,'Ed25519',FP,ADOPTION,SUBJECT,SCOPE,False,True):
        stop('SIGNED_DECISION_IDENTITY_DIVERGENCE')
    recognition=_recognized_key_scope()
    if dt(decision['valid_until'])>dt(recognition['validity']['maximum_valid_until_utc_exclusive']):stop('SIGNED_WINDOW_EXCEEDS_RATIFIED_MAXIMUM')
    now = datetime.now(timezone.utc)
    if not dt(decision['valid_from']) <= now < dt(decision['valid_until']):
        stop('SIGNED_DECISION_WINDOW_NOT_CURRENT')
    manifest_raw = content['manifest.json']
    if sha(manifest_raw) != decision['manifest_sha256']:
        stop('SIGNED_MANIFEST_HASH_DIVERGENCE')
    manifest = parse(manifest_raw)
    listed = manifest.get('entries')
    if set(manifest) != {'entries'} or not isinstance(listed,list) or len(listed) != len(FILES):
        stop('SIGNED_MANIFEST_SCHEMA_INVALID')
    paths = [row.get('path') for row in listed if isinstance(row,dict)]
    if paths != sorted(FILES):
        stop('SIGNED_MANIFEST_PATHS_DIVERGENT')
    for entry in listed:
        if set(entry) != {'path','size','sha256'} or entry['size'] != len(content[entry['path']]) or entry['sha256'] != sha(content[entry['path']]):
            stop('SIGNED_EVIDENCE_HASH_DIVERGENCE')
        parse(content[entry['path']])
    objs = {name:parse(content[name]) for name in FILES}
    if decision['object_sha256'] != sha(content['object.json']) or decision['review_sha256'] != sha(content['review.json']):
        stop('SIGNED_OBJECT_REVIEW_HASH_DIVERGENT')
    if objs['object.json'] != {'policy_subject':SUBJECT,'documents':DOCS,'use':'autenticar_documento_sefa_pr'}:
        stop('SIGNED_DOCUMENT_SUBJECT_DIVERGENT')
    review = objs['review.json']
    if not isinstance(review,dict) or review.get('outcome') != 'favoravel' or review.get('accepted') is not True or review.get('participation') != 'review_only' or review.get('conflicts') != [] or review.get('reviewer_execution') in (review.get('author_execution'),review.get('integrator_execution')):
        stop('SIGNED_OWN_REVIEW_NOT_ACCEPTED')
    proofs = objs['proofs.json']
    if not isinstance(proofs,dict) or any(sha(canonical(value)) != key for key,value in proofs.items()):
        stop('SIGNED_PROOFS_CONTENT_HASH_DIVERGENCE')
    own = [v for v in proofs.values() if isinstance(v,dict) and v.get('kind') == 'independent_document_origin_founder_sealed']
    if len(own) != 2 or {x.get('document',{}).get('id') for x in own} != set(DOCS):
        stop('SIGNED_TWO_OWN_ORIGIN_REPORTS_MISSING')
    if any(x.get('outcome') != 'favoravel' or x.get('synthetic_only') is not False for x in own):
        stop('SIGNED_ORIGIN_REPORT_NOT_FAVOURABLE')
    sig = content['signature.bin']
    if len(sig) != 64:stop('SIGNED_SIGNATURE_SIZE_INVALID')
    try:
        _public_key(public_path).verify(sig, decision_raw)
    except Exception:
        stop('SIGNED_ED25519_SIGNATURE_INVALID')
    # Este verificador NAO executa _verify_bundle() com contexto institucional
    # independente; assinatura valida nao basta para admissibilidade FOUNDER_ORIGIN.
    print(json.dumps({'status':'B02_SUCCESSOR_SIGNATURE_AND_BYTES_PREFLIGHT_ONLY',
        'decision_sha256':sha(decision_raw),'manifest_sha256':sha(manifest_raw),
        'public_fingerprint':FP,'signature_sha256':sha(sig),
        'signature_and_bundle_bytes_checked':True,
        'canonical_full_profile_verified':False,
        'independent_history_verified':False,
        'mandate_and_execution_proofs_verified':False,
        'institutional_chain_verified':False,
        'institutional_authority_verified':False,'revocation_verified':False,
        'runtime_root_activated':False,'protected_installation_allowed':False,
        'writes':0},sort_keys=True))

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--verificar-assinado',type=Path,help='Leitura offline de bundle sucessor assinado, sem ativacao')
    p.add_argument('--verificar-reconhecimento',action='store_true',help='Consumir ratificacao da chave; nunca assina, ativa ou escreve DB')
    p.add_argument('--evidencias',type=Path,help='Sete JSON CANONICOS de atos reais ja emitidos pela execucao competente')
    p.add_argument('--der-publico',type=Path,help='Ficheiro .der publico OU ROOT.json historico pinado; nunca chave privada')
    p.add_argument('--valid-from',help='Inicio real decidido pelo custódio, com offset')
    p.add_argument('--valid-until',help='Fim real decidido pelo custódio, com offset')
    p.add_argument('--aceitacao-risco-explicita',action='store_true',help='Somente se existir aceite competente especifico, nao inferido pelo empacotador')
    p.add_argument('--out',type=Path,help='Nova pasta de PRE-ASSINATURA; nao deve existir')
    a=p.parse_args()
    if a.verificar_reconhecimento:
        recognition=_recognized_key_scope()
        print(json.dumps({'status':'B02_RATIFIED_KEY_RECOGNITION_CONSUMED_NOT_SIGNED',
            'ratification_id':recognition['id'],
            'g4_policy_hash':recognition['policy_subject']['policy_hash'],
            'public_fingerprint':FP,
            'maximum_valid_until_utc_exclusive':recognition['validity']['maximum_valid_until_utc_exclusive'],
            'private_key_received':False,'signature_performed':False,'protected_writes':0},sort_keys=True))
        return
    if a.verificar_assinado:
        if a.der_publico is None:stop('PUBLIC_KEY_PATH_REQUIRED')
        _verify_signed_bundle(a.verificar_assinado,a.der_publico)
        return
    if any(x is None for x in (a.evidencias,a.der_publico,a.valid_from,a.valid_until,a.out)):
        stop('EXACT_PRESIGNATURE_INPUTS_REQUIRED')
    if not a.aceitacao_risco_explicita:stop('RESIDUAL_RISK_ACCEPTANCE_NOT_EXPRESS')
    if a.out.exists():stop('OUTPUT_EXISTS_PRESERVE')
    if not a.evidencias.is_dir():stop('EVIDENCE_FOLDER_MISSING')
    actual={x.name for x in a.evidencias.iterdir() if x.is_file()}
    if actual!=set(FILES) or any(x.is_symlink() for x in a.evidencias.iterdir()):stop('REQUIRED_7_FILES_EXACT')
    key=_public_key(a.der_publico)
    start,end=dt(a.valid_from),dt(a.valid_until)
    recognition=_recognized_key_scope()
    if end>dt(recognition['validity']['maximum_valid_until_utc_exclusive']):stop('PREIMAGE_WINDOW_EXCEEDS_RATIFIED_MAXIMUM')
    if end<=start or end<=datetime.now(timezone.utc):stop('NO_CURRENT_VALID_INTERVAL')
    evidence={name:(a.evidencias/name).read_bytes() for name in FILES}
    obj={name:parse(raw) for name,raw in evidence.items()}
    if obj['object.json']!={'policy_subject':SUBJECT,'documents':DOCS,'use':'autenticar_documento_sefa_pr'}:stop('G4_OBJECT_SUBJECT_DIVERGENT')
    own_reports=[v for v in obj['proofs.json'].values() if isinstance(v,dict) and v.get('kind')=='independent_document_origin_founder_sealed']
    if len(own_reports)!=2 or {r.get('document',{}).get('id') for r in own_reports}!=set(DOCS):stop('BOTH_NEW_OWN_ORIGIN_REPORTS_MISSING')
    if any(r.get('outcome')!='favoravel' or r.get('synthetic_only') is not False or not r.get('mandate_acceptance_sha256') or not r.get('tls_evidence_binding') or not r.get('receipt_binding') for r in own_reports):stop('OWN_ORIGIN_REPORTS_NOT_CONCLUSIVE')
    review=obj['review.json']
    if review.get('outcome')!='favoravel' or review.get('accepted') is not True or review.get('participation')!='review_only' or review.get('conflicts')!=[]:stop('NEW_OWN_REVIEW_NOT_FAVOURABLE')
    if review.get('reviewer_execution') in (review.get('author_execution'),review.get('integrator_execution')):stop('REVIEW_NOT_SEGREGATED')
    # Pareceres/mandatos sem formato minimo nao sao preimagens admissiveis.
    fields={'id','object_sha256','outcome','reviewer_execution','author_execution','integrator_execution',
            'inputs_sha256','findings','limitations','conflicts','participation','mandate_id',
            'accepted','addressed_reviews','completed_at'}
    if set(review)!=fields or review['object_sha256']!=sha(evidence['object.json']):
        stop('OWN_REVIEW_SCHEMA_OR_OBJECT_HASH_INVALID')
    if any(not isinstance(review[k],str) or not review[k].strip()
           for k in ('id','reviewer_execution','author_execution','integrator_execution','mandate_id','completed_at')):
        stop('OWN_REVIEW_ACTOR_IDENTITY_MISSING')
    if (not isinstance(review['findings'],list) or not review['findings']
        or not isinstance(review['limitations'],list) or not review['limitations']
        or not isinstance(review['inputs_sha256'],list)):
        stop('OWN_REVIEW_FINDINGS_OR_INPUTS_MISSING')
    if set(obj['history.json']) != {'object_sha256','revision','previous_revision',
                                   'reviews','prior_reviews','delta_sha256'}:
        stop('INSTITUTIONAL_HISTORY_SCHEMA_INVALID')
    if obj['history.json']['object_sha256'] != sha(evidence['object.json']) or sha(evidence['review.json']) not in obj['history.json']['reviews']:
        stop('OWN_REVIEW_NOT_IN_HISTORY')
    if set(obj['execution.json']) != {'executions'} or len(obj['execution.json']['executions']) != 3:
        stop('EXECUTION_SET_NOT_EXACT')
    if set(obj['mandates.json']) != {'mandates'} or len(obj['mandates.json']['mandates']) != 3:
        stop('MANDATES_SET_NOT_EXACT')
    if set(obj['institutional.json']) != {'expected','decisions'}:
        stop('INSTITUTIONAL_CHAIN_ENVELOPE_INVALID')
    manifest={'entries':[{'path':name,'size':len(evidence[name]),'sha256':sha(evidence[name])} for name in sorted(FILES)]}
    manifest_raw=canonical(manifest)
    decision={'domain':DOMAIN,'schema_version':1,'profile':PROFILE,'algorithm':'Ed25519',
        'key_fingerprint':FP,'adoption_sha256':ADOPTION,'manifest_sha256':sha(manifest_raw),
        'policy_subject':SUBJECT,'object_sha256':sha(evidence['object.json']),
        'review_sha256':sha(evidence['review.json']),'scope':SCOPE,
        'valid_from':a.valid_from,'valid_until':a.valid_until,'synthetic_only':False,
        'residual_risk_accepted':True}
    decision_raw=canonical(decision)
    # OUTPUT is a preimage, not authorization; signature.bin must be issued externally.
    a.out.mkdir(parents=True)
    for name,data in evidence.items(): (a.out/name).write_bytes(data)
    (a.out/'manifest.json').write_bytes(manifest_raw)
    (a.out/'decision.json').write_bytes(decision_raw)
    print(json.dumps({'status':'UNSIGNED_PREIMAGE_ONLY_NOT_AUTHORITY',
                      'decision_json_sha256_to_sign_exact_bytes':sha(decision_raw),
                      'manifest_sha256':sha(manifest_raw),
                      'object_sha256':decision['object_sha256'],
                      'review_sha256':decision['review_sha256'],
                      'existing_public_key_fingerprint':FP,
                      'custodian_must_sign_exact_decision_json_and_issue_new_root_and_snapshot':True,
                      'root_and_proofs_elegibility_not_attested_by_packager':True,
                      'signature_bin_present':False},sort_keys=True))
if __name__=='__main__':
    try:main()
    except Exception as ex:
        print(str(ex),file=__import__('sys').stderr)
        raise SystemExit(2)
