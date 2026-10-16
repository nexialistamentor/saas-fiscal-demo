"""I6 — verifica assinatura de custódia EXTERNA sobre bytes I5/I4N/I2.

Uma assinatura Ed25519 prova qual chave assinou o registo, NÃO que a SEFAZ
respondeu, que TLS ocorreu, que a NF-e e autentica ou que ha credito fiscal.
Sem rede, sem acesso a ficheiros/certificados, sem writes, sem chaves privadas.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.services.enterprise_nfe_i5_observation_link import vincular_observacao_nfe_i5

SCHEMA = 'ENTERPRISE_I6_EXTERNAL_CUSTODY_V1'
_ISSUER = 'SOLVERIS_ENTERPRISE_EXPLICIT_EXTERNAL_CUSTODIAN'
_SCOPE = 'ENTERPRISE_ONLY_SINGLE_NFE_OBSERVATION'
_TLS = 'TLS_VALIDATION_DECLARED_BY_CUSTODIAN_NOT_INDEPENDENTLY_PROVEN'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_BODY_FIELDS = frozenset({
    'schema_version', 'issuer', 'scope', 'event_id', 'public_key_sha256',
    'observed_at_utc', 'xml_sha256', 'chave_sha256', 'resposta_soap_sha256',
    'endpoint_sha256', 'autorizador', 'uf_emissora', 'certificate_der_sha256',
    'tls_validation_declaration', 'client_certificate_declared',
})
_ALL_FIELDS = _BODY_FIELDS | {'signature_ed25519_b64'}


class EnterpriseI6CustodyError(ValueError):
    """Falha fechada de identidade, assinatura ou timestamp de custodiante."""


def _stop(reason: str):
    raise EnterpriseI6CustodyError(reason)


def _sha(v: object) -> bool:
    return type(v) is str and _HEX.fullmatch(v) is not None


def _utc(value: object) -> datetime:
    if type(value) is not str or not value.endswith('Z'):
        _stop('I6_TIME_FORMAT_INVALID')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        _stop('I6_TIME_FORMAT_INVALID')
    if parsed.utcoffset() != timedelta(0):
        _stop('I6_TIME_FORMAT_INVALID')
    return parsed


def _signing_bytes(att: dict) -> bytes:
    """Formato determinístico; somente os campos de dados, nunca a assinatura."""
    return json.dumps({k: att[k] for k in sorted(_BODY_FIELDS)},
                      ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def vincular_custodia_nfe_i6(*, db: object, authenticated_user_id: int,
                             empresa_id: int, relatorio_id: int,
                             xml_bytes: bytes, resposta_soap: bytes,
                             atestado: dict, trusted_public_key: bytes,
                             now_utc: datetime) -> dict:
    """Reusa I5 e valida um atestado ASSINADO de terceiro confiado pelo chamador.

    O chamador é responsável por obter a chave pública de um canal INDEPENDENTE,
    avaliar a legitimidade da entidade e manter controlo de anti-replay no host.
    Não aceita chave pública contida no próprio atestado como âncora de confiança.
    """
    if (type(trusted_public_key) is not bytes or len(trusted_public_key) != 32
        or type(now_utc) is not datetime or now_utc.tzinfo is None
        or now_utc.utcoffset() != timedelta(0)):
        _stop('I6_TRUST_ANCHOR_OR_CLOCK_INVALID')
    if type(atestado) is not dict or set(atestado) != _ALL_FIELDS:
        _stop('I6_ATTESTATION_SCHEMA_INVALID')
    if (atestado.get('schema_version') != SCHEMA or atestado.get('issuer') != _ISSUER
        or atestado.get('scope') != _SCOPE
        or atestado.get('tls_validation_declaration') != _TLS
        or atestado.get('client_certificate_declared') is not True):
        _stop('I6_CUSTODIAN_CLAIMS_INVALID')
    if any(not _sha(atestado.get(k)) for k in (
        'public_key_sha256', 'xml_sha256', 'chave_sha256',
        'resposta_soap_sha256', 'endpoint_sha256', 'certificate_der_sha256',
    )):
        _stop('I6_DIGEST_FORMAT_INVALID')
    try:
        uid = UUID(atestado['event_id'])
        if uid.version != 4 or str(uid) != atestado['event_id']:
            _stop('I6_EVENT_ID_INVALID')
    except (ValueError, TypeError, AttributeError):
        _stop('I6_EVENT_ID_INVALID')
    observed = _utc(atestado['observed_at_utc'])
    if not timedelta(0) <= now_utc - observed <= timedelta(minutes=5):
        _stop('I6_ATTESTATION_EXPIRED_OR_FUTURE')
    pub_digest = hashlib.sha256(trusted_public_key).hexdigest()
    if not hmac.compare_digest(atestado['public_key_sha256'], pub_digest):
        _stop('I6_TRUST_ANCHOR_DIGEST_MISMATCH')
    sigstr = atestado.get('signature_ed25519_b64')
    if type(sigstr) is not str or len(sigstr) != 88:
        _stop('I6_SIGNATURE_FORMAT_INVALID')
    try:
        signature = base64.b64decode(sigstr, validate=True)
        if len(signature) != 64 or base64.b64encode(signature).decode('ascii') != sigstr:
            _stop('I6_SIGNATURE_FORMAT_INVALID')
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(signature, _signing_bytes(atestado))
    except (ValueError, TypeError, binascii.Error, InvalidSignature):
        _stop('I6_SIGNATURE_INVALID')
    # Só depois de validar a assinatura verifica o titular/documento/bytes reais I5.
    try:
        linked = vincular_observacao_nfe_i5(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes, resposta_soap=resposta_soap,
        )
    except Exception:
        _stop('I6_DOCUMENTARY_I5_NOT_VERIFIED')
    if (type(linked) is not dict or linked.get('schema_version') !=
        'ENTERPRISE_NFE_I5_DOCUMENTARY_OBSERVATION_V1'
        or linked.get('checkout_autorizado') is not False
        or linked.get('origem_resposta_atestada') is not False):
        _stop('I6_I5_CONTRACT_INVALID')
    expected = {
        'xml_sha256': linked['xml_sha256'],
        'chave_sha256': linked['chave_sha256'],
        'resposta_soap_sha256': linked['resposta_soap_sha256'],
        'endpoint_sha256': hashlib.sha256(linked['endpoint_catalogado'].encode('utf-8')).hexdigest(),
        'autorizador': linked['autorizador_catalogado'],
        'uf_emissora': linked['uf_emissora_chave'],
    }
    for key, val in expected.items():
        if type(atestado.get(key)) is not type(val) or atestado[key] != val:
            _stop('I6_SIGNED_EVIDENCE_IDENTITY_MISMATCH')
    # Não inclui telefone, CNPJ, chave em claro, cert, assinatura, SOAP nem valores.
    receipt = {
        'schema_version': SCHEMA,
        'empresa_id': linked['empresa_id'],
        'relatorio_id': linked['relatorio_id'],
        'documento_id': linked['documento_id'],
        'recibo_i5_sha256': linked['recibo_fingerprint_sha256'],
        'atestado_assinado_sha256': hashlib.sha256(_signing_bytes(atestado)).hexdigest(),
        'assinatura_custodiante_verificada': True,
        'origem_sefaz_criptograficamente_comprovada': False,
        'tls_mtls_comprovado_independentemente': False,
        'assinatura_xml_nfe_verificada': False,
        'situacao_sefaz_confirmada': False,
        'efd_competencia_reconciliada': False,
        'apuracao_mensal_completa': False,
        'direito_creditorio_comprovado': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
        'limite': 'I6_CUSTODIA_ASSINADA_NAO_COMPROVA_ORIGEM_SEFAZ_NEM_ANTIREPLAY',
    }
    return receipt


__all__ = ['SCHEMA', 'EnterpriseI6CustodyError', 'vincular_custodia_nfe_i6']
