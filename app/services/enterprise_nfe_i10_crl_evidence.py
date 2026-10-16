"""I10: verificacao OFFLINE de LCRs fornecidas e pinadas por SHA-256.

Um resultado positivo e APENAS 'nao listado em LCRs fornecidas, com assinatura
matematica correta'. Nao comprova fonte oficial, ICP-Brasil, atualidade real,
revogacao global, OCSP, SEFAZ ou direitos fiscais. Nenhum I/O.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import hmac
import re

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtensionOID, SignatureAlgorithmOID

from app.services.enterprise_nfe_i9_chain_anchor import (
    _embedded_leaf, _cert, verificar_cadeia_nfe_i9,
)

SCHEMA = 'ENTERPRISE_NFE_I10_SUPPLIED_CRL_EVIDENCE_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_MAX_CRL = 2 * 1024 * 1024
_MAX_XML = 2 * 1024 * 1024
_ALLOWED_CRITICAL_CRL = frozenset((ExtensionOID.CRL_NUMBER, ExtensionOID.AUTHORITY_KEY_IDENTIFIER))
_RSA_CRLS = {
    SignatureAlgorithmOID.RSA_WITH_SHA1: 'SHA1_LEGACY',
    SignatureAlgorithmOID.RSA_WITH_SHA256: 'SHA256',
    SignatureAlgorithmOID.RSA_WITH_SHA384: 'SHA384',
    SignatureAlgorithmOID.RSA_WITH_SHA512: 'SHA512',
}

class EnterpriseI10CRLError(ValueError):
    """Recusa estrita sem revelar dados empresariais ou certificados."""


def _stop(reason: str):
    raise EnterpriseI10CRLError('I10_' + reason)


def _digest(v):
    return type(v) is str and _SHA.fullmatch(v) is not None


def _ext(cert, oid):
    try:
        return cert.extensions.get_extension_for_oid(oid).value
    except x509.ExtensionNotFound:
        return None


def _read_crl(raw):
    if type(raw) is not bytes or not 128 <= len(raw) <= _MAX_CRL:
        _stop('CRL_BYTES_INVALID')
    try:
        return x509.load_der_x509_crl(raw)
    except (ValueError, TypeError):
        _stop('CRL_DER_INVALID')


def _verify_crl(crl, issuer, child, reference_utc):
    if crl.issuer != issuer.subject:
        _stop('CRL_ISSUER_MISMATCH')
    if crl.last_update_utc is None or crl.next_update_utc is None or not (
            crl.last_update_utc <= reference_utc < crl.next_update_utc):
        _stop('CRL_REFERENCE_WINDOW_INVALID')
    if any(ext.critical and ext.oid not in _ALLOWED_CRITICAL_CRL for ext in crl.extensions):
        _stop('CRL_CRITICAL_EXTENSION_UNHANDLED')
    if _ext(crl, ExtensionOID.ISSUING_DISTRIBUTION_POINT) is not None:
        _stop('CRL_INDIRECT_OR_SCOPED_UNSUPPORTED')
    if _ext(crl, ExtensionOID.DELTA_CRL_INDICATOR) is not None:
        _stop('CRL_DELTA_UNSUPPORTED')
    number = _ext(crl, ExtensionOID.CRL_NUMBER)
    if number is None or type(number.crl_number) is not int or number.crl_number <= 0:
        _stop('CRL_NUMBER_MISSING')
    aki = _ext(crl, ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
    ski = _ext(issuer, ExtensionOID.SUBJECT_KEY_IDENTIFIER)
    if aki is not None:
        if aki.key_identifier is not None and ski is not None and not hmac.compare_digest(aki.key_identifier, ski.digest):
            _stop('CRL_AUTHORITY_KEY_MISMATCH')
        if aki.authority_cert_serial_number is not None and aki.authority_cert_serial_number != issuer.serial_number:
            _stop('CRL_AUTHORITY_SERIAL_MISMATCH')
        if aki.authority_cert_issuer is not None and (
                len(aki.authority_cert_issuer) != 1 or
                not isinstance(aki.authority_cert_issuer[0], x509.DirectoryName) or
                aki.authority_cert_issuer[0].value != issuer.subject):
            _stop('CRL_AUTHORITY_NAME_MISMATCH')
    usage = _ext(issuer, ExtensionOID.KEY_USAGE)
    if usage is None or not usage.crl_sign:
        _stop('CRL_ISSUER_NOT_AUTHORIZED')
    alg = _RSA_CRLS.get(crl.signature_algorithm_oid)
    if alg is None:
        _stop('CRL_SIGNATURE_ALGORITHM_UNSUPPORTED')
    key = issuer.public_key()
    if not isinstance(key, rsa.RSAPublicKey) or not 2048 <= key.key_size <= 8192:
        _stop('CRL_ISSUER_KEY_UNSUPPORTED')
    try:
        key.verify(crl.signature, crl.tbs_certlist_bytes, padding.PKCS1v15(),
                   crl.signature_hash_algorithm)
    except (InvalidSignature, ValueError, TypeError):
        _stop('CRL_SIGNATURE_INVALID')
    # Certificado listado => STOP, inclusive se a data declarada de revogacao
    # for posterior ao instante, pois nao ha prova de fonte/timestamp independente.
    revoked = crl.get_revoked_certificate_by_serial_number(child.serial_number)
    if revoked is not None:
        _stop('CRL_CERTIFICATE_LISTED')
    # Sem suporte a extensoes criticas de entrada, IDs indiretos e delta.
    for entry in crl:
        if any(ext.critical for ext in entry.extensions):
            _stop('CRL_ENTRY_CRITICAL_UNHANDLED')
    return alg


def verificar_lcr_nfe_i10(*, xml_bytes: bytes, chave_nfe_esperada: str,
                           cnpj_emitente_esperado: str, xml_sha256_esperado: str,
                           intermediarios_der: tuple[bytes, ...],
                           raiz_confiada_der: bytes, raiz_sha256_aprovado: str,
                           instante_referencia_utc: datetime,
                           lcrs_der: tuple[bytes, ...],
                           lcrs_sha256_aprovados: tuple[str, ...]) -> dict:
    """Reusa I9 e verifica LCR diretas completas, uma por emissor da cadeia.

    O chamador deve obter e aprovar LCRs/raiz por canal independente. Apenas
    hashes autodeclarados nao provam a origem ou qualidade desse canal.
    """
    if (type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= _MAX_XML
        or type(intermediarios_der) is not tuple or len(intermediarios_der) > 5
        or type(lcrs_der) is not tuple or type(lcrs_sha256_aprovados) is not tuple
        or len(lcrs_der) != len(intermediarios_der)+1
        or len(lcrs_sha256_aprovados) != len(lcrs_der)
        or any(not _digest(v) for v in lcrs_sha256_aprovados)
        or type(instante_referencia_utc) is not datetime
        or instante_referencia_utc.tzinfo is None
        or instante_referencia_utc.utcoffset() != timedelta(0)):
        _stop('INPUT_INVALID')
    for raw, pin in zip(lcrs_der, lcrs_sha256_aprovados):
        if type(raw) is not bytes or len(raw) > _MAX_CRL or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(),pin):
            _stop('CRL_DIGEST_MISMATCH')
    if len(set(lcrs_sha256_aprovados)) != len(lcrs_sha256_aprovados):
        _stop('CRL_DUPLICATED')
    try:
        result_i9 = verificar_cadeia_nfe_i9(
            xml_bytes=xml_bytes, chave_nfe_esperada=chave_nfe_esperada,
            cnpj_emitente_esperado=cnpj_emitente_esperado,
            xml_sha256_esperado=xml_sha256_esperado,
            intermediarios_der=intermediarios_der,
            raiz_confiada_der=raiz_confiada_der,
            raiz_sha256_aprovado=raiz_sha256_aprovado,
            instante_referencia_utc=instante_referencia_utc)
    except (ValueError, TypeError):
        _stop('I9_CHAIN_NOT_VERIFIED')
    if (type(result_i9) is not dict or
        result_i9.get('cadeia_assinaturas_ate_ancora_pinada_verificada') is not True or
        result_i9.get('cadeia_icp_brasil_verificada') is not False or
        result_i9.get('checkout_autorizado') is not False):
        _stop('I9_CONTRACT_INVALID')
    leaf = _cert(_embedded_leaf(xml_bytes))
    chain = [leaf] + [_cert(v) for v in intermediarios_der] + [_cert(raiz_confiada_der)]
    algs = []
    for i, (raw, pin) in enumerate(zip(lcrs_der,lcrs_sha256_aprovados)):
        crl = _read_crl(raw)
        algs.append(_verify_crl(crl, chain[i+1], chain[i], instante_referencia_utc))
    return {
        'schema_version': SCHEMA,
        'xml_sha256': xml_sha256_esperado,
        'chave_sha256': result_i9['chave_sha256'],
        'raiz_aprovada_sha256': raiz_sha256_aprovado,
        'quantidade_lcrs_avaliadas': len(lcrs_der),
        'assinaturas_lcrs_fornecidas_verificadas': True,
        'certificados_nao_listados_nas_lcrs_fornecidas': True,
        'cadeia_i9_para_ancora_pinada_verificada': True,
        'algoritmo_sha1_legado_observado': 'SHA1_LEGACY' in algs or result_i9['algoritmo_fraco_na_cadeia'],
        'origem_oficial_das_lcrs_verificada': False,
        'atualidade_externa_das_lcrs_verificada': False,
        'revogacao_oficial_global_verificada': False,
        'politica_icp_brasil_completa_verificada': False,
        'cadeia_icp_brasil_verificada': False,
        'ocsp_verificado': False,
        'antirreplay_duravel_verificado': False,
        'situacao_sefaz_confirmada': False,
        'efd_competencia_reconciliada': False,
        'apuracao_mensal_completa': False,
        'direito_creditorio_comprovado': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
        'limite': 'LCRS_EXTERNAS_NAO_ATROFIA_VALIDACAO_OFICIAL',
    }


__all__ = ['SCHEMA', 'EnterpriseI10CRLError', 'verificar_lcr_nfe_i10']
