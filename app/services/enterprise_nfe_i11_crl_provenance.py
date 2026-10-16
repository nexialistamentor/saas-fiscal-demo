"""I11: manifesto de custódia de LCR, assinado por chave externa, offline.

Assinatura e progressão local NÃO provam origem ITI, status ICP-Brasil,
completude, tempo externo, anti-rollback durável, SEFAZ ou direitos tributários.
Reusa a cadeia I10→I9→I8→I7; nunca lê rede, BD, ficheiros ou certificados do SO.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import re
from uuid import UUID

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.x509.oid import ExtensionOID

from app.services.enterprise_nfe_i10_crl_evidence import verificar_lcr_nfe_i10

SCHEMA = 'ENTERPRISE_I11_SIGNED_CRL_CUSTODY_V1'
_STATE = 'ENTERPRISE_I11_PRIOR_STATE_V1'
_DECLARATION = 'ORIGEM_DECLARADA_PELO_CUSTODIANTE_NAO_COMPROVADA_OFICIALMENTE'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_ZERO = '0' * 64
_I10_FIELDS = frozenset({
    'xml_bytes', 'chave_nfe_esperada', 'cnpj_emitente_esperado',
    'xml_sha256_esperado', 'intermediarios_der', 'raiz_confiada_der',
    'raiz_sha256_aprovado', 'instante_referencia_utc',
    'lcrs_der', 'lcrs_sha256_aprovados',
})
_BODY = frozenset({
    'schema_version', 'issuer', 'scope', 'event_id', 'sequencia',
    'manifesto_anterior_sha256', 'chave_publica_sha256', 'observado_em_utc',
    'xml_sha256', 'chave_sha256', 'recibo_i10_sha256',
    'raiz_sha256', 'lcrs', 'declaracao_procedencia',
})
_ALL = _BODY | {'assinatura_ed25519_base64'}
_ENTRY = frozenset({'der_sha256', 'numero', 'this_update_utc', 'next_update_utc'})
_PRIOR = frozenset({'schema_version','sequencia','manifesto_sha256','raiz_sha256','lcrs'})


class EnterpriseI11ProvenanceError(ValueError):
    """STOP seguro, sem incluir dados de pessoa, certificado ou XML."""


def _stop(reason: str):
    raise EnterpriseI11ProvenanceError('I11_' + reason)


def _sha(v):
    return type(v) is str and _SHA.fullmatch(v) is not None


def _utc(v):
    if type(v) is not str or not v.endswith('Z'):
        _stop('TIME_INVALID')
    try:
        t = datetime.fromisoformat(v[:-1] + '+00:00')
    except (ValueError, TypeError):
        _stop('TIME_INVALID')
    if t.utcoffset() != timedelta(0):
        _stop('TIME_INVALID')
    return t


def _iso(t):
    return t.isoformat(timespec='seconds').replace('+00:00','Z')


def _json_bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def _signed_bytes(manifesto: dict):
    return _json_bytes({k:manifesto[k] for k in sorted(_BODY)})


def _crl_items(raws, digests):
    out=[]
    for raw, pinned_sha in zip(raws,digests):
        try:
            crl = x509.load_der_x509_crl(raw)
            ext = crl.extensions.get_extension_for_oid(ExtensionOID.CRL_NUMBER).value
        except (ValueError, TypeError, x509.ExtensionNotFound):
            _stop('LCR_METADATA_UNREADABLE')
        if crl.last_update_utc is None or crl.next_update_utc is None:
            _stop('LCR_DATES_UNREADABLE')
        out.append({'der_sha256':pinned_sha,'numero':ext.crl_number,
                    'this_update_utc':_iso(crl.last_update_utc),
                    'next_update_utc':_iso(crl.next_update_utc)})
    return out


def _validate_entry(v):
    return (type(v) is dict and set(v) == _ENTRY and _sha(v['der_sha256'])
            and type(v['numero']) is int and v['numero'] > 0
            and _utc(v['this_update_utc']) < _utc(v['next_update_utc']))


def conferir_proveniencia_lcr_i11(*, parametros_i10: dict,
                                   manifesto: dict, trusted_public_key: bytes,
                                   estado_previo_aprovado: dict | None,
                                   agora_utc: datetime) -> dict:
    """Confere manifestação ASSINADA de custódia e compara progressão com estado EXTERNO.

    O chamador deve aprovar a chave e o estado prévio FORA do manifesto.
    Este módulo NÃO mantém ledger ou valida oficialmente o canal de aquisição.
    """
    if (type(parametros_i10) is not dict or set(parametros_i10) != _I10_FIELDS
        or type(trusted_public_key) is not bytes or len(trusted_public_key) != 32
        or type(agora_utc) is not datetime or agora_utc.tzinfo is None
        or agora_utc.utcoffset() != timedelta(0)):
        _stop('INPUT_INVALID')
    if type(manifesto) is not dict or set(manifesto) != _ALL:
        _stop('MANIFEST_SCHEMA_INVALID')
    if (manifesto['schema_version'] != SCHEMA
        or manifesto['issuer'] != 'CUSTODIANTE_EXTERNO_CONTROLADO'
        or manifesto['scope'] != 'SOLVERIS_ENTERPRISE_NFE_LCR'
        or manifesto['declaracao_procedencia'] != _DECLARATION):
        _stop('MANIFEST_CLAIMS_INVALID')
    seq = manifesto['sequencia']
    if type(seq) is not int or seq < 1 or seq > 2**63 - 1:
        _stop('SEQUENCE_INVALID')
    for field in ('manifesto_anterior_sha256','chave_publica_sha256',
                  'xml_sha256','chave_sha256','recibo_i10_sha256','raiz_sha256'):
        if not _sha(manifesto[field]):
            _stop('MANIFEST_DIGEST_INVALID')
    try:
        uid = UUID(manifesto['event_id'])
        if uid.version != 4 or str(uid) != manifesto['event_id']:
            _stop('EVENT_ID_INVALID')
    except (ValueError,TypeError,AttributeError):
        _stop('EVENT_ID_INVALID')
    observed = _utc(manifesto['observado_em_utc'])
    if not timedelta(0) <= agora_utc - observed <= timedelta(minutes=5):
        _stop('MANIFEST_TIME_EXPIRED_OR_FUTURE')
    if not hmac.compare_digest(hashlib.sha256(trusted_public_key).hexdigest(),
                               manifesto['chave_publica_sha256']):
        _stop('CUSTODIAN_KEY_MISMATCH')
    rawsig=manifesto['assinatura_ed25519_base64']
    if type(rawsig) is not str or len(rawsig)!=88:
        _stop('MANIFEST_SIGNATURE_FORMAT_INVALID')
    try:
        sig=base64.b64decode(rawsig,validate=True)
        if len(sig)!=64 or base64.b64encode(sig).decode('ascii')!=rawsig:
            _stop('MANIFEST_SIGNATURE_FORMAT_INVALID')
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(sig,_signed_bytes(manifesto))
    except (InvalidSignature,ValueError,TypeError,binascii.Error):
        _stop('MANIFEST_SIGNATURE_INVALID')
    supplied=manifesto['lcrs']
    if (type(supplied) is not list or not 1 <= len(supplied) <= 6
        or any(not _validate_entry(x) for x in supplied)):
        _stop('MANIFEST_LCR_SCHEMA_INVALID')
    # Não se deve aceitar um recibo I10 arbitrário como substituto da execução real.
    try:
        i10=verificar_lcr_nfe_i10(**parametros_i10)
    except (ValueError,TypeError,KeyError):
        _stop('I10_EVIDENCE_NOT_VERIFIED')
    if (type(i10) is not dict
        or i10.get('schema_version') != 'ENTERPRISE_NFE_I10_SUPPLIED_CRL_EVIDENCE_V1'
        or i10.get('assinaturas_lcrs_fornecidas_verificadas') is not True
        or i10.get('certificados_nao_listados_nas_lcrs_fornecidas') is not True
        or i10.get('cadeia_icp_brasil_verificada') is not False
        or i10.get('checkout_autorizado') is not False):
        _stop('I10_CONTRACT_INVALID')
    current=_crl_items(parametros_i10['lcrs_der'],parametros_i10['lcrs_sha256_aprovados'])
    expected={
        'xml_sha256':i10['xml_sha256'],
        'chave_sha256':i10['chave_sha256'],
        'recibo_i10_sha256':hashlib.sha256(_json_bytes(i10)).hexdigest(),
        'raiz_sha256':i10['raiz_aprovada_sha256'],
        'lcrs':current,
    }
    for k,v in expected.items():
        if type(manifesto[k]) is not type(v) or manifesto[k] != v:
            _stop('MANIFEST_EVIDENCE_IDENTITY_MISMATCH')
    if estado_previo_aprovado is None:
        if seq != 1 or manifesto['manifesto_anterior_sha256'] != _ZERO:
            _stop('PREVIOUS_STATE_MISSING')
    else:
        prev=estado_previo_aprovado
        if (type(prev) is not dict or set(prev) != _PRIOR
            or prev['schema_version'] != _STATE
            or type(prev['sequencia']) is not int or prev['sequencia'] < 1
            or not _sha(prev['manifesto_sha256'])
            or not _sha(prev['raiz_sha256'])
            or type(prev['lcrs']) is not list
            or len(prev['lcrs']) != len(current)
            or any(type(x) is not dict or set(x) != {'numero','der_sha256'}
                   or type(x['numero']) is not int or x['numero'] <= 0
                   or not _sha(x['der_sha256']) for x in prev['lcrs'])):
            _stop('PREVIOUS_STATE_INVALID')
        if (seq != prev['sequencia'] + 1
            or not hmac.compare_digest(manifesto['manifesto_anterior_sha256'],prev['manifesto_sha256'])
            or not hmac.compare_digest(manifesto['raiz_sha256'],prev['raiz_sha256'])):
            _stop('ROLLBACK_SEQUENCE_OR_ROOT_INVALID')
        for prior,entry in zip(prev['lcrs'],current):
            if entry['numero'] < prior['numero']:
                _stop('CRL_ROLLBACK_DETECTED')
            if entry['numero'] == prior['numero'] and entry['der_sha256'] != prior['der_sha256']:
                _stop('CRL_SAME_NUMBER_DIFFERENT_BYTES')
    mdig=hashlib.sha256(_signed_bytes(manifesto)).hexdigest()
    proposed={'schema_version':_STATE,'sequencia':seq,
              'manifesto_sha256':mdig,'raiz_sha256':i10['raiz_aprovada_sha256'],
              'lcrs':[{'numero':x['numero'],'der_sha256':x['der_sha256']} for x in current]}
    return {
        'schema_version':SCHEMA,
        'xml_sha256':i10['xml_sha256'],
        'chave_sha256':i10['chave_sha256'],
        'raiz_aprovada_sha256':i10['raiz_aprovada_sha256'],
        'recibo_i10_sha256':expected['recibo_i10_sha256'],
        'manifesto_assinado_sha256':mdig,
        'sequencia':seq,
        'assinatura_custodiante_verificada':True,
        'comparacao_rollback_com_estado_fornecido':estado_previo_aprovado is not None,
        'estado_proposto_para_custodia_externa':proposed,
        'origem_oficial_iti_verificada':False,
        'estado_previo_autenticado_pelo_modulo':False,
        'antirollback_duravel_verificado':False,
        'temporalidade_externa_autenticada':False,
        'cadeia_icp_brasil_verificada':False,
        'revogacao_oficial_global_verificada':False,
        'situacao_sefaz_confirmada':False,
        'efd_competencia_reconciliada':False,
        'apuracao_mensal_completa':False,
        'direito_creditorio_comprovado':False,
        'checkout_autorizado':False,
        'uso':'INTERNO_NAO_PUBLICAVEL',
    }


__all__=['SCHEMA','EnterpriseI11ProvenanceError','conferir_proveniencia_lcr_i11']
