"""I9 — encadeamento criptográfico X509 para a assinatura I8, offline.

Uma raiz recebida e pinada pelo chamador NÃO prova ser ICP-Brasil.
Não implementa toda RFC5280 (políticas, CRL, OCSP e validação de caminhos
alternativos); só atesta a cadeia fechada no perfil estrito aqui suportado.
Sem rede, sistema de ficheiros, certificados do Windows ou escritas.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
import hashlib
import hmac
import re

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtensionOID, SignatureAlgorithmOID
from cryptography.hazmat.primitives import serialization
from lxml import etree

from app.services.enterprise_nfe_i8_signer_identity import vincular_signatario_nfe_i8

SCHEMA = 'ENTERPRISE_NFE_I9_PINNED_CHAIN_V1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_MAX_XML = 2 * 1024 * 1024
_NFE = '{http://www.portalfiscal.inf.br/nfe}'
_DS = '{http://www.w3.org/2000/09/xmldsig#}'
_SUPPORTED_RSA_SIG = {
    SignatureAlgorithmOID.RSA_WITH_SHA1: 'SHA1_LEGACY',
    SignatureAlgorithmOID.RSA_WITH_SHA256: 'SHA256',
    SignatureAlgorithmOID.RSA_WITH_SHA384: 'SHA384',
    SignatureAlgorithmOID.RSA_WITH_SHA512: 'SHA512',
}
_ALLOWED_CRITICAL_CA_EXTENSIONS = {ExtensionOID.BASIC_CONSTRAINTS, ExtensionOID.KEY_USAGE}


class EnterpriseI9ChainError(ValueError):
    """STOP técnico, sem divulgação de nomes, CNPJ ou certificados."""


def _stop(code: str):
    raise EnterpriseI9ChainError('I9_' + code)


def _sha(v: object) -> bool:
    return type(v) is str and _HEX.fullmatch(v) is not None


def _cert(data: bytes) -> x509.Certificate:
    if type(data) is not bytes or not 128 <= len(data) <= 65536:
        _stop('CERT_DER_SIZE_INVALID')
    try:
        return x509.load_der_x509_certificate(data)
    except (ValueError, TypeError):
        _stop('CERT_DER_INVALID')


def _extension(cert: x509.Certificate, oid, reason: str):
    try:
        return cert.extensions.get_extension_for_oid(oid).value
    except (x509.ExtensionNotFound, ValueError):
        _stop(reason)


def _check_window(cert: x509.Certificate, instant: datetime):
    if not cert.not_valid_before_utc <= instant <= cert.not_valid_after_utc:
        _stop('CERT_REFERENCE_TIME_INVALID')


def _verify_signature(child: x509.Certificate, issuer: x509.Certificate) -> str:
    if child.issuer != issuer.subject:
        _stop('CHAIN_ISSUER_SUBJECT_MISMATCH')
    alg = _SUPPORTED_RSA_SIG.get(child.signature_algorithm_oid)
    if alg is None:
        _stop('CHAIN_SIGNATURE_ALGORITHM_UNSUPPORTED')
    key = issuer.public_key()
    if not isinstance(key, rsa.RSAPublicKey) or not 2048 <= key.key_size <= 8192:
        _stop('CHAIN_ISSUER_KEY_UNSUPPORTED')
    try:
        key.verify(child.signature, child.tbs_certificate_bytes,
                   padding.PKCS1v15(), child.signature_hash_algorithm)
    except (InvalidSignature, ValueError, TypeError):
        _stop('CHAIN_CERT_SIGNATURE_INVALID')
    try:
        aki = child.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_KEY_IDENTIFIER).value
    except x509.ExtensionNotFound:
        aki = None
    try:
        ski = issuer.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER).value
    except x509.ExtensionNotFound:
        ski = None
    if aki is not None:
        if aki.key_identifier is not None and ski is not None and not hmac.compare_digest(aki.key_identifier, ski.digest):
            _stop('CHAIN_KEY_IDENTIFIER_MISMATCH')
        if aki.authority_cert_serial_number is not None and aki.authority_cert_serial_number != issuer.serial_number:
            _stop('CHAIN_AUTHORITY_SERIAL_MISMATCH')
        if aki.authority_cert_issuer is not None:
            if len(aki.authority_cert_issuer) != 1 or not isinstance(aki.authority_cert_issuer[0], x509.DirectoryName) or aki.authority_cert_issuer[0].value != issuer.subject:
                _stop('CHAIN_AUTHORITY_NAME_MISMATCH')
    return alg


def _check_ca(cert: x509.Certificate, subordinate_cas: int):
    bc = _extension(cert, ExtensionOID.BASIC_CONSTRAINTS, 'CA_CONSTRAINTS_MISSING')
    usage = _extension(cert, ExtensionOID.KEY_USAGE, 'CA_KEY_USAGE_MISSING')
    if not bc.ca or not usage.key_cert_sign:
        _stop('CA_NOT_AUTHORIZED_TO_SIGN')
    if bc.path_length is not None and subordinate_cas > bc.path_length:
        _stop('CA_PATH_LENGTH_EXCEEDED')
    if any(ext.critical and ext.oid not in _ALLOWED_CRITICAL_CA_EXTENSIONS for ext in cert.extensions):
        _stop('CA_CRITICAL_EXTENSION_UNHANDLED')


def _embedded_leaf(xml_bytes: bytes) -> bytes:
    # Reconhece somente um certificado na assinatura direta NF-e, nunca URI externa.
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                             huge_tree=False, recover=False, remove_comments=False)
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except (ValueError, etree.XMLSyntaxError):
        _stop('XML_PARSE_INVALID')
    nfe = root if root.tag == _NFE+'NFe' else root.find(_NFE+'NFe') if root.tag == _NFE+'nfeProc' else None
    if nfe is None:
        _stop('XML_NFE_INVALID')
    signatures = nfe.findall(_DS+'Signature')
    if len(signatures) != 1:
        _stop('XML_SIGNATURE_INVALID')
    sig = signatures[0]
    nodes = sig.findall(_DS+'KeyInfo/'+_DS+'X509Data/'+_DS+'X509Certificate')
    if len(nodes) != 1 or type(nodes[0].text) is not str:
        _stop('XML_CERT_CARDINALITY_INVALID')
    try:
        compact = ''.join(nodes[0].text.split())
        if len(compact) > 88000:
            _stop('XML_CERT_SIZE_INVALID')
        data = base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error, TypeError):
        _stop('XML_CERT_ENCODING_INVALID')
    return data


def verificar_cadeia_nfe_i9(*, xml_bytes: bytes, chave_nfe_esperada: str,
                            cnpj_emitente_esperado: str, xml_sha256_esperado: str,
                            intermediarios_der: tuple[bytes, ...],
                            raiz_confiada_der: bytes, raiz_sha256_aprovado: str,
                            instante_referencia_utc: datetime) -> dict:
    """Confere cadeia linear e hash de âncora EXTERNA; não certifica ICP-Brasil.

    Âncora e digest devem vir de gestão de confiança independente do XML.
    O instante é parâmetro externo não atestado: apenas teste de janela temporal.
    """
    if (type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= _MAX_XML
        or type(intermediarios_der) is not tuple or len(intermediarios_der) > 5
        or not _sha(xml_sha256_esperado) or not _sha(raiz_sha256_aprovado)
        or type(instante_referencia_utc) is not datetime
        or instante_referencia_utc.tzinfo is None
        or instante_referencia_utc.utcoffset() != timedelta(0)):
        _stop('INPUT_INVALID')
    if not hmac.compare_digest(hashlib.sha256(raiz_confiada_der if type(raiz_confiada_der) is bytes else b'').hexdigest(), raiz_sha256_aprovado):
        _stop('ROOT_PIN_MISMATCH')
    try:
        signed = vincular_signatario_nfe_i8(
            xml_bytes=xml_bytes, chave_nfe_esperada=chave_nfe_esperada,
            cnpj_emitente_esperado=cnpj_emitente_esperado,
            xml_sha256_esperado=xml_sha256_esperado)
    except (ValueError, TypeError):
        _stop('I8_IDENTITY_NOT_VERIFIED')
    if signed.get('cnpj_embutido_certificado_corresponde_emitente') is not True or signed.get('checkout_autorizado') is not False:
        _stop('I8_CONTRACT_INVALID')
    leaf_bytes = _embedded_leaf(xml_bytes)
    if not hmac.compare_digest(hashlib.sha256(leaf_bytes).hexdigest(), signed['certificado_embutido_der_sha256']):
        _stop('LEAF_I8_DIGEST_MISMATCH')
    leaf = _cert(leaf_bytes)
    roots = [_cert(data) for data in intermediarios_der] + [_cert(raiz_confiada_der)]
    chain = [leaf] + roots
    digests = [hashlib.sha256(x.public_bytes(encoding=serialization.Encoding.DER)).hexdigest() for x in chain]
    if len(set(digests)) != len(digests):
        _stop('CHAIN_REPEATED_CERTIFICATE')
    for cert in chain:
        _check_window(cert, instante_referencia_utc)
    algorithms = []
    for i, issuer in enumerate(roots):
        _check_ca(issuer, i)
        algorithms.append(_verify_signature(chain[i], issuer))
    root = roots[-1]
    if root.subject != root.issuer:
        _stop('ROOT_NOT_SELF_ISSUED')
    algorithms.append(_verify_signature(root, root))
    return {
        'schema_version': SCHEMA,
        'xml_sha256': xml_sha256_esperado,
        'chave_sha256': signed['chave_sha256'],
        'certificado_signatario_sha256': signed['certificado_embutido_der_sha256'],
        'raiz_aprovada_sha256': raiz_sha256_aprovado,
        'intermediarios': len(intermediarios_der),
        'assinatura_xml_i7_e_identidade_i8_verificadas': True,
        'cadeia_assinaturas_ate_ancora_pinada_verificada': True,
        'algoritmo_fraco_na_cadeia': 'SHA1_LEGACY' in algorithms,
        'instante_referencia_autenticado_externamente': False,
        'politicas_icp_brasil_e_caminho_rfc5280_completos': False,
        'cadeia_icp_brasil_verificada': False,
        'revogacao_crl_ocsp_verificada': False,
        'situacao_sefaz_confirmada': False,
        'efd_competencia_reconciliada': False,
        'apuracao_mensal_completa': False,
        'direito_creditorio_comprovado': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
    }


__all__ = ['SCHEMA', 'EnterpriseI9ChainError', 'verificar_cadeia_nfe_i9']
