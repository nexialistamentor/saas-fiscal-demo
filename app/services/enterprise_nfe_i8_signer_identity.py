"""I8 Enterprise: enlace offline entre NF-e 55, assinatura I7 e CNPJ no X509.

Somente identidade DECLARADA pelo certificado embutido. Sem cadeia ICP-Brasil,
revogacao, SEFAZ, CA externa, rede, BD, credito ou checkout. Nao devolve CNPJ.
DOC-ICP-04: otherName OID 2.16.76.1.3.3, ASN.1 PrintableString/OCTET STRING.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re

from cryptography import x509
from cryptography.x509.oid import ExtensionOID, ObjectIdentifier
from lxml import etree

from app.services.enterprise_nfe_i7_xml_signature import verificar_assinatura_nfe_i7

SCHEMA = 'ENTERPRISE_NFE_I8_SIGNER_IDENTITY_V1'
_N = '{http://www.portalfiscal.inf.br/nfe}'
_D = '{http://www.w3.org/2000/09/xmldsig#}'
_OID = ObjectIdentifier('2.16.76.1.3.3')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_CNPJ = re.compile(r'[0-9]{14}\Z')
_MAX = 2 * 1024 * 1024

class EnterpriseI8IdentityError(ValueError):
    """Recusa sem publicar identidade ou material de certificado."""

def _stop(code):
    raise EnterpriseI8IdentityError('I8_' + code)

def _single(parent, name):
    values = parent.findall(name)
    if len(values) != 1:
        _stop('XML_CARDINALITY_INVALID')
    return values[0]

def _cnpj_valid(v):
    if type(v) is not str or not _CNPJ.fullmatch(v) or len(set(v)) == 1:
        return False
    def digit(x, weights):
        r = sum(int(d) * w for d, w in zip(x, weights)) % 11
        return 0 if r < 2 else 11-r
    return int(v[12]) == digit(v[:12], [5,4,3,2,9,8,7,6,5,4,3,2]) and int(v[13]) == digit(v[:13], [6,5,4,3,2,9,8,7,6,5,4,3,2])

def _der_value(data):
    """Decodifica somente DER minimo PrintableString/Octet String ascii."""
    if type(data) is not bytes or len(data) < 2 or data[0] not in (0x13, 0x04):
        _stop('CNPJ_ASN1_UNSUPPORTED')
    if data[1] & 0x80:
        count = data[1] & 0x7f
        if count not in (1, 2) or len(data) < 2 + count or data[2] == 0:
            _stop('CNPJ_ASN1_LENGTH_INVALID')
        length = int.from_bytes(data[2:2+count], 'big')
        if length < 128 or (count == 2 and length < 256):
            _stop('CNPJ_ASN1_LENGTH_NONCANONICAL')
        offset = 2+count
    else:
        length = data[1]
        offset = 2
    if length != 14 or offset+length != len(data):
        _stop('CNPJ_ASN1_LENGTH_INVALID')
    try:
        value = data[offset:].decode('ascii')
    except UnicodeDecodeError:
        _stop('CNPJ_ASN1_ENCODING_INVALID')
    if not _cnpj_valid(value):
        _stop('CNPJ_CERT_INVALID')
    return value

def _san_cnpj(cert):
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    except x509.ExtensionNotFound:
        _stop('SAN_CNPJ_MISSING')
    vals = [v for v in san if isinstance(v, x509.OtherName) and v.type_id == _OID]
    if len(vals) != 1:
        _stop('SAN_CNPJ_CARDINALITY_INVALID')
    return _der_value(vals[0].value)

def vincular_signatario_nfe_i8(*, xml_bytes: bytes, chave_nfe_esperada: str,
                               cnpj_emitente_esperado: str, xml_sha256_esperado: str) -> dict:
    """Assinatura I7 valida + emit CNPJ + chave NF-e + otherName CNPJ.

    Sem alegar ICP-Brasil nem propriedade juridica antes da cadeia/revogacao.
    """
    if (type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= _MAX or
        type(chave_nfe_esperada) is not str or
        type(xml_sha256_esperado) is not str or _SHA.fullmatch(xml_sha256_esperado) is None or
        not _cnpj_valid(cnpj_emitente_esperado)):
        _stop('INPUT_INVALID')
    try:
        signed = verificar_assinatura_nfe_i7(
            xml_bytes=xml_bytes, chave_nfe_esperada=chave_nfe_esperada,
            xml_sha256_esperado=xml_sha256_esperado)
    except ValueError:
        _stop('I7_SIGNATURE_NOT_VERIFIED')
    if (type(signed) is not dict or
        signed.get('assinatura_matematica_verificada') is not True or
        signed.get('digest_infNFe_verificado') is not True or
        signed.get('checkout_autorizado') is not False or
        signed.get('xml_sha256') != xml_sha256_esperado):
        _stop('I7_SIGNED_CONTRACT_INVALID')
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                             huge_tree=False, recover=False, remove_comments=False)
    try:
        root=etree.fromstring(xml_bytes, parser=parser)
    except (ValueError, etree.XMLSyntaxError):
        _stop('XML_INVALID')
    nfe = root if root.tag == _N+'NFe' else _single(root, _N+'NFe') if root.tag == _N+'nfeProc' else None
    if nfe is None:
        _stop('NFE_INVALID')
    inf = _single(nfe,_N+'infNFe')
    issuer = _single(inf,_N+'emit')
    cnpj_node = _single(issuer, _N+'CNPJ')
    xml_cnpj = cnpj_node.text
    if not _cnpj_valid(xml_cnpj) or not hmac.compare_digest(xml_cnpj,cnpj_emitente_esperado):
        _stop('CNPJ_EMITENTE_INVALID')
    if (len(chave_nfe_esperada) != 44 or
        not hmac.compare_digest(chave_nfe_esperada[6:20], xml_cnpj)):
        _stop('CNPJ_CHAVE_DIVERGENTE')
    sig = _single(nfe,_D+'Signature')
    cert_text = _single(_single(_single(sig,_D+'KeyInfo'),_D+'X509Data'),_D+'X509Certificate').text
    try:
        if type(cert_text) is not str:
            _stop('CERT_EMBEDDED_INVALID')
        compact=''.join(cert_text.split())
        raw=base64.b64decode(compact,validate=True)
        if len(raw)>65536 or len(raw)<128:
            _stop('CERT_SIZE_INVALID')
        cert=x509.load_der_x509_certificate(raw)
    except (ValueError,binascii.Error,TypeError):
        _stop('CERT_EMBEDDED_INVALID')
    cert_hash=hashlib.sha256(raw).hexdigest()
    if signed.get('certificado_embutido_der_sha256') != cert_hash:
        _stop('CERT_I7_FINGERPRINT_DIVERGENTE')
    san_cnpj=_san_cnpj(cert)
    if not hmac.compare_digest(san_cnpj,xml_cnpj):
        _stop('CNPJ_CERT_DIVERGENTE')
    try:
        use=cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value
        bc=cert.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value
    except x509.ExtensionNotFound:
        _stop('CERT_USAGE_UNDEFINED')
    if bc.ca or not (use.digital_signature or use.content_commitment):
        _stop('CERT_USAGE_NOT_ELIGIBLE')
    date_str=_single(_single(inf,_N+'ide'),_N+'dhEmi').text
    try:
        stamp=datetime.fromisoformat(date_str)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError('timezone missing')
        issued=stamp.astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):
        _stop('ISSUE_DATE_INVALID')
    if not cert.not_valid_before_utc <= issued <= cert.not_valid_after_utc:
        _stop('CERT_OUTSIDE_DECLARED_ISSUE_DATE')
    return {
        'schema_version': SCHEMA,
        'xml_sha256': xml_sha256_esperado,
        'chave_sha256': signed['chave_sha256'],
        'cnpj_emitente_sha256': hashlib.sha256(xml_cnpj.encode('ascii')).hexdigest(),
        'certificado_embutido_der_sha256': cert_hash,
        'uf_emissora_chave': signed['uf_emissora_chave'],
        'algoritmo_observado': signed['algoritmo_observado'],
        'assinatura_matematica_i7_verificada': True,
        'cnpj_embutido_certificado_corresponde_emitente': True,
        'cnpj_chave_nfe_corresponde_emitente': True,
        'certificado_na_janela_de_emissao_declarada': True,
        'validade_temporal_autenticada_externamente': False,
        'cadeia_icp_brasil_verificada': False,
        'revogacao_certificado_verificada': False,
        'titularidade_juridica_verificada': False,
        'situacao_sefaz_confirmada': False,
        'efd_competencia_reconciliada': False,
        'credito_fiscal_comprovado': False,
        'apuracao_mensal_completa': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
    }

__all__=['SCHEMA','EnterpriseI8IdentityError','vincular_signatario_nfe_i8']
