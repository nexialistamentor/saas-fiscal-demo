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
def dt(v):
    try:r=datetime.fromisoformat(v)
    except Exception:stop('TIME_INVALID')
    if r.tzinfo is None:stop('TIME_WITHOUT_OFFSET')
    return r.astimezone(timezone.utc)
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--evidencias',type=Path,required=True,help='Sete JSON CANONICOS de atos reais ja emitidos pela execucao competente')
    p.add_argument('--der-publico',type=Path,required=True,help='Chave DER publica existente; nunca privada')
    p.add_argument('--valid-from',required=True,help='Inicio real decidido pelo custódio, com offset')
    p.add_argument('--valid-until',required=True,help='Fim real decidido pelo custódio, com offset')
    p.add_argument('--aceitacao-risco-explicita',action='store_true',help='Somente se existir aceite competente especifico, nao inferido pelo empacotador')
    p.add_argument('--out',type=Path,required=True,help='Nova pasta de PRE-ASSINATURA; nao deve existir')
    a=p.parse_args()
    if not a.aceitacao_risco_explicita:stop('RESIDUAL_RISK_ACCEPTANCE_NOT_EXPRESS')
    if a.out.exists():stop('OUTPUT_EXISTS_PRESERVE')
    if not a.evidencias.is_dir():stop('EVIDENCE_FOLDER_MISSING')
    actual={x.name for x in a.evidencias.iterdir() if x.is_file()}
    if actual!=set(FILES) or any(x.is_symlink() for x in a.evidencias.iterdir()):stop('REQUIRED_7_FILES_EXACT')
    keybytes=a.der_publico.read_bytes()
    if sha(keybytes)!=FP:stop('HISTORICAL_PUBLIC_KEY_FINGERPRINT_DIVERGENCE')
    key=load_der_public_key(keybytes)
    if not isinstance(key,Ed25519PublicKey) or key.public_bytes(Encoding.DER,PublicFormat.SubjectPublicKeyInfo)!=keybytes:stop('ED25519_DER_INVALID')
    start,end=dt(a.valid_from),dt(a.valid_until)
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
