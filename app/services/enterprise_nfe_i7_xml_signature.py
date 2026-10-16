"""I7 Enterprise — verificacao MATEMATICA de XMLDSig enveloped em NF-e modelo 55.

Nao prova confianca ICP-Brasil, relacao do certificado com emitente, consulta
SEFAZ, validade fiscal, norma, escritura, credito ou checkout. Sem I/O externo.
O X509 embutido e fornecido PELO XML, nunca uma ancora de confianca.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import re

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from app.services.enterprise_nfe_sefaz_nacional_i3n import preparar_consulta_nfe_nacional

SCHEMA = 'ENTERPRISE_NFE_I7_XML_SIGNATURE_V1'
_NFE = 'http://www.portalfiscal.inf.br/nfe'
_DS = 'http://www.w3.org/2000/09/xmldsig#'
_N = '{' + _NFE + '}'
_D = '{' + _DS + '}'
_CAN = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
_ENV = _DS + 'enveloped-signature'
_RSA_SHA1 = _DS + 'rsa-sha1'
_DIG_SHA1 = _DS + 'sha1'
_RSA_SHA256 = 'http://www.w3.org/2001/04/xmldsig-more#rsa-sha256'
_DIG_SHA256 = 'http://www.w3.org/2001/04/xmlenc#sha256'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_MAX = 2 * 1024 * 1024


class EnterpriseI7SignatureError(ValueError):
    """Fail-closed com codigos sem dados fiscais."""


def _stop(code: str):
    raise EnterpriseI7SignatureError(code)


def _only(parent, tag):
    found = parent.findall(tag)
    if len(found) != 1:
        _stop('I7_STRUCTURE_CARDINALITY_INVALID')
    return found[0]


def _b64(value, max_length):
    if type(value) is not str or len(value) > max_length or not value.strip():
        _stop('I7_BASE64_INVALID')
    try:
        compact = ''.join(value.split())
        if len(compact) > max_length:
            _stop('I7_BASE64_INVALID')
        return base64.b64decode(compact, validate=True)
    except (ValueError, binascii.Error, TypeError):
        _stop('I7_BASE64_INVALID')


def _canonical(node):
    try:
        return etree.tostring(node, method='c14n', exclusive=False, with_comments=False)
    except (etree.LxmlError, ValueError, TypeError):
        _stop('I7_C14N_INVALID')


def verificar_assinatura_nfe_i7(*, xml_bytes: bytes,
                                 chave_nfe_esperada: str,
                                 xml_sha256_esperado: str) -> dict:
    """Verifica DigestValue e SignatureValue contra X509 embutido, nunca CA.

    XMLDSig enveloped com referencia UNICA ao infNFe; sem resolver URI externa,
    schemas, DTD, XSLT, XPath de terceiros, rede, ficheiros ou certificados do OS.
    Aceita RSA-SHA1 LEGADO (marcado fraco) ou RSA-SHA256, ambos com C14N 1.0.
    """
    if (type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= _MAX
        or type(xml_sha256_esperado) is not str
        or _SHA.fullmatch(xml_sha256_esperado) is None):
        _stop('I7_INPUT_INVALID')
    digest_xml = hashlib.sha256(xml_bytes).hexdigest()
    if not hmac.compare_digest(digest_xml, xml_sha256_esperado):
        _stop('I7_XML_SHA256_MISMATCH')
    try:
        rota = preparar_consulta_nfe_nacional(chave_nfe_esperada)
    except (ValueError, TypeError):
        _stop('I7_NFE_KEY_INVALID')
    if b'<!DOCTYPE' in xml_bytes.upper() or b'<!ENTITY' in xml_bytes.upper():
        _stop('I7_XML_DTD_FORBIDDEN')
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True,
                             huge_tree=False, remove_blank_text=False, recover=False,
                             remove_comments=False)
    try:
        root = etree.fromstring(xml_bytes, parser=parser)
    except (etree.XMLSyntaxError, ValueError, TypeError):
        _stop('I7_XML_INVALID')
    if root.tag == _N+'NFe':
        nfe = root
    elif root.tag == _N+'nfeProc':
        nfe = _only(root, _N+'NFe')
    else:
        _stop('I7_ROOT_UNSUPPORTED')
    if len(root.xpath('descendant-or-self::n:NFe', namespaces={'n':_NFE})) != 1:
        _stop('I7_NFE_DUPLICATED')
    inf = _only(nfe, _N+'infNFe')
    if inf.get('Id') != 'NFe'+chave_nfe_esperada or inf.get('versao') != '4.00':
        _stop('I7_SIGNED_REFERENCE_TARGET_INVALID')
    # XPath/ID wrapping: nenhuma outra identificacao no XML pode reapontar a URI.
    identity = 'NFe'+chave_nfe_esperada
    matches = []
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        for k,v in element.attrib.items():
            if k.split('}')[-1].lower() == 'id' and v == identity:
                matches.append(element)
    if len(matches) != 1 or matches[0] is not inf:
        _stop('I7_REFERENCE_ID_NOT_UNIQUE')
    signatures = root.findall('.//'+_D+'Signature')
    if root.tag == _N+'NFe':
        signatures = [x for x in root.iter(_D+'Signature')]
    if len(signatures) != 1:
        _stop('I7_SIGNATURE_CARDINALITY_INVALID')
    signature = signatures[0]
    if signature.getparent() is not nfe:
        _stop('I7_SIGNATURE_NOT_DIRECT_NFE_CHILD')
    signed_info = _only(signature, _D+'SignedInfo')
    canmethod = _only(signed_info, _D+'CanonicalizationMethod')
    sigmethod = _only(signed_info, _D+'SignatureMethod')
    reference = _only(signed_info, _D+'Reference')
    if canmethod.get('Algorithm') != _CAN or reference.get('URI') != '#'+identity:
        _stop('I7_REFERENCE_OR_C14N_UNSUPPORTED')
    transforms = _only(reference, _D+'Transforms')
    algorithms = [x.get('Algorithm') for x in transforms]
    if len(algorithms) != 2 or algorithms != [_ENV, _CAN] or any(x.tag != _D+'Transform' for x in transforms):
        _stop('I7_TRANSFORMS_UNSUPPORTED')
    digestmethod = _only(reference, _D+'DigestMethod')
    digestvalue = _only(reference, _D+'DigestValue')
    methods = {
        (_RSA_SHA1, _DIG_SHA1): (hashlib.sha1, hashes.SHA1, 'RSA_SHA1_LEGADO_COLISAO_RISCO'),
        (_RSA_SHA256, _DIG_SHA256): (hashlib.sha256, hashes.SHA256, 'RSA_SHA256'),
    }
    methods_chosen = methods.get((sigmethod.get('Algorithm'),digestmethod.get('Algorithm')))
    if methods_chosen is None:
        _stop('I7_ALGORITHM_UNSUPPORTED')
    digest_func, sig_hash, policy = methods_chosen
    observed_digest = digest_func(_canonical(inf)).digest()
    expected_digest = _b64(digestvalue.text, 128)
    if not hmac.compare_digest(observed_digest, expected_digest):
        _stop('I7_REFERENCE_DIGEST_INVALID')
    keyinfo = _only(signature, _D+'KeyInfo')
    x509data = _only(keyinfo, _D+'X509Data')
    certificate_b64 = _only(x509data, _D+'X509Certificate')
    cert_bytes = _b64(certificate_b64.text, 65536)
    try:
        cert = x509.load_der_x509_certificate(cert_bytes)
        public_key = cert.public_key()
    except (ValueError, TypeError):
        _stop('I7_X509_INVALID')
    if not isinstance(public_key, rsa.RSAPublicKey):
        _stop('I7_RSA_KEY_REQUIRED')
    if public_key.key_size < 1024 or public_key.key_size > 8192:
        _stop('I7_RSA_KEY_SIZE_INVALID')
    signature_bytes = _b64(_only(signature, _D+'SignatureValue').text, 16384)
    try:
        public_key.verify(signature_bytes, _canonical(signed_info),
                          padding.PKCS1v15(), sig_hash())
    except (InvalidSignature, ValueError, TypeError):
        _stop('I7_SIGNATURE_VALUE_INVALID')
    return {
        'schema_version': SCHEMA,
        'xml_sha256': digest_xml,
        'chave_sha256': hashlib.sha256(chave_nfe_esperada.encode('ascii')).hexdigest(),
        'certificado_embutido_der_sha256': hashlib.sha256(cert_bytes).hexdigest(),
        'uf_emissora_chave': rota['uf_emissora_chave'],
        'assinatura_matematica_verificada': True,
        'digest_infNFe_verificado': True,
        'algoritmo_observado': policy,
        'cadeia_icp_brasil_verificada': False,
        'revogacao_certificado_verificada': False,
        'titularidade_emitente_verificada': False,
        'situacao_sefaz_confirmada': False,
        'protocolo_sefaz_autenticado': False,
        'norma_vigente_verificada': False,
        'apuracao_mensal_completa': False,
        'direito_creditorio_comprovado': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
    }


__all__ = ['SCHEMA','EnterpriseI7SignatureError','verificar_assinatura_nfe_i7']
