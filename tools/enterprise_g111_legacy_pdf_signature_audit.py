"""SOLVERIS G1.11: bounded read-only PDF legacy CMS signature cryptographic audit.

This is not a trust-anchor, timestamp, historical revocation, publisher,
legal-effect, or commercial verifier. Never creates or modifies a file or DB.
Use an isolated Python environment with pypdf, asn1crypto and cryptography.
"""
from __future__ import annotations

import hashlib
import hmac
from io import BytesIO
import re
from typing import Any

from asn1crypto import cms, parser
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from pypdf import PdfReader

SCHEMA = "SOLVERIS_ENTERPRISE_G111_LEGACY_CMS_CRYPTO_V1"
MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_CMS_BYTES = 262144
MAX_FIELDS = 64
MAX_CERTS = 16
_DENIED = (
    "fonte_primaria_autenticada", "cadeia_icp_brasil_validada",
    "identidade_publicador_autenticada", "instante_assinatura_comprovado",
    "revogacao_historica_comprovada", "versao_oficial_verificada",
    "atualizacao_e_revogacao_exaustivas", "vigencia_juridica_comprovada",
    "autoridade_fiscal", "credito_confirmado", "checkout_autorizado",
    "usavel_comercialmente",
)
_HASHES = {
    "sha1": hashes.SHA1,
    "sha256": hashes.SHA256,
    "sha384": hashes.SHA384,
    "sha512": hashes.SHA512,
}
_HEX_GAP = re.compile(rb"<([A-Fa-f0-9]+)>\Z")


class G111SignatureError(ValueError):
    pass


def _stop(reason: str) -> None:
    raise G111SignatureError("G111_" + reason)


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _signatures(reader: PdfReader):
    try:
        root = reader.trailer["/Root"]
        acro = root["/AcroForm"].get_object()
        fields = acro["/Fields"].get_object()
    except (KeyError, TypeError, AttributeError) as exc:
        raise G111SignatureError("G111_ACROFORM_ASSINATURA_AUSENTE") from exc
    if not 0 < len(fields) <= MAX_FIELDS:
        _stop("QUANTIDADE_CAMPOS_INVALIDA")
    found = []
    pending = list(fields)
    visited = set()
    while pending:
        node = pending.pop().get_object()
        ident = id(node)
        if ident in visited:
            _stop("GRAFO_CAMPOS_CICLICO")
        visited.add(ident)
        if len(visited) > MAX_FIELDS:
            _stop("CAMPOS_EXCESSIVOS")
        kids = node.get("/Kids")
        if kids is not None:
            pending.extend(kids.get_object())
        kind = node.get("/FT")
        if kind is not None and str(kind) == "/Sig":
            value = node.get("/V")
            if value is None:
                _stop("ASSINATURA_SEM_VALOR")
            found.append(value.get_object())
    if len(found) != 1:
        _stop("ASSINATURAS_NAO_EXATAMENTE_UMA")
    return found[0]


def _get_cms(signature, pdf: bytes):
    if str(signature.get("/SubFilter")) != "/adbe.pkcs7.sha1":
        _stop("SUBFILTER_NAO_SUPORTADO")
    br = signature.get("/ByteRange")
    if br is None or len(br) != 4 or not all(_is_int(v) for v in br):
        _stop("BYTERANGE_INVALIDO")
    a, b, c, d = map(int, br)
    if a != 0 or b <= 0 or c <= b + 2 or d <= 0 or c + d != len(pdf):
        _stop("BYTERANGE_SEM_COBERTURA_TOTAL")
    gap = pdf[b:c]
    match = _HEX_GAP.fullmatch(gap)
    if match is None or len(match.group(1)) % 2:
        _stop("BYTERANGE_GAP_NAO_CANONICO")
    expected_raw = bytes.fromhex(match.group(1).decode("ascii"))
    contents = signature.get("/Contents")
    if contents is None:
        _stop("CMS_CONTENTS_AUSENTE")
    if not hmac.compare_digest(expected_raw, bytes(contents)):
        _stop("GAP_CMS_DIVERGENTE")
    if len(expected_raw) > MAX_CMS_BYTES:
        _stop("CMS_BYTES_EXCESSIVOS")
    try:
        cls, constructed, tag, header, content, trailing = parser.parse(expected_raw)
        if (cls, constructed, tag) != (0, 1, 16):
            _stop("CMS_ASN1_TIPO_INVALIDO")
        # parser.parse() returns a *structural* EOC trailer (00 00) for
        # BER indefinite-length outer SEQUENCE. It is part of CMS, not a
        # post-CMS byte nor invalid reserved-space padding. The IOEPA pilot
        # uses this legitimate BER form; definite-length DER has no trailer.
        if header == b"\x30\x80":
            if trailing != b"\x00\x00":
                _stop("CMS_BER_EOC_INVALIDO")
        elif trailing:
            _stop("CMS_ASN1_TRAILER_INESPERADO")
        # Enforce exactly the CMS ContentInfo children; asn1crypto can
        # otherwise parse its two fields and silently tolerate extra bytes
        # inside a BER indefinite outer SEQUENCE before the final EOC.
        remaining = content
        for required_tag in ((0, 0, 6), (2, 1, 0)):
            inner_cls, inner_cons, inner_tag, inner_head, inner_body, inner_eoc = parser.parse(remaining)
            if (inner_cls, inner_cons, inner_tag) != required_tag:
                _stop("CMS_BER_CONTENTINFO_FIELDS_INVALIDOS")
            consumed = len(inner_head) + len(inner_body) + len(inner_eoc)
            remaining = remaining[consumed:]
        if remaining:
            _stop("CMS_BER_BYTES_EXTRAS_DENTRO_SEQUENCE")
        asn1_object = header + content + trailing
        if any(expected_raw[len(asn1_object):]):
            _stop("CMS_PADDING_NAO_ZERO")
        envelope = cms.ContentInfo.load(asn1_object, strict=True)
    except (ValueError, TypeError, IndexError) as exc:
        raise G111SignatureError("G111_CMS_ASN1_INVALIDO") from exc
    signed_bytes = pdf[:b] + pdf[c:]
    return envelope, signed_bytes


def verificar_assinatura_legada_pdf_g111(*, pdf_bytes: bytes, sha256_esperado: str) -> dict:
    """Independently recompute legacy ByteRange SHA1 and CMS RSA signature.

    Does not accept caller claims about cryptographic validity. Verification of
    the embedded signer's certificate chain, revocation, timestamps and legal
    publisher authority are NOT part of this gate, and all remain false.
    """
    if type(pdf_bytes) is not bytes or not 1024 <= len(pdf_bytes) <= MAX_PDF_BYTES:
        _stop("PDF_BYTES_INVALIDOS")
    if not pdf_bytes.startswith(b"%PDF-"):
        _stop("PDF_CABECALHO_INVALIDO")
    if type(sha256_esperado) is not str or not re.fullmatch(r"[0-9a-f]{64}", sha256_esperado):
        _stop("SHA256_ESPERADO_INVALIDO")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    if not hmac.compare_digest(digest, sha256_esperado):
        _stop("PDF_SHA256_DIVERGENTE")
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        value = _signatures(reader)
        envelope, signed_data = _get_cms(value, pdf_bytes)
    except G111SignatureError:
        raise
    except Exception as exc:
        raise G111SignatureError("G111_PDF_ASSINATURA_ESTRUTURA_INVALIDA") from exc
    try:
        if envelope["content_type"].native != "signed_data":
            _stop("CMS_CONTENT_TYPE_INVALIDO")
        obj = envelope["content"]
        eci = obj["encap_content_info"]
        if eci["content_type"].native != "data":
            _stop("CMS_ENCAP_TYPE_INVALIDO")
        encapsulated = eci["content"].native
        if type(encapsulated) is not bytes or len(encapsulated) != 20:
            _stop("CMS_SHA1_ENCAPSULADO_INVALIDO")
        if not hmac.compare_digest(encapsulated, hashlib.sha1(signed_data).digest()):
            _stop("PDF_BYTERANGE_SHA1_DIVERGENTE")
        signers = obj["signer_infos"]
        if len(signers) != 1:
            _stop("CMS_ASSINANTES_NAO_EXATAMENTE_UM")
        signer = signers[0]
        sid = signer["sid"]
        if sid.name != "issuer_and_serial_number":
            _stop("CMS_SIGNER_ID_NAO_SUPORTADO")
        alg = signer["digest_algorithm"]["algorithm"].native
        if alg not in _HASHES:
            _stop("CMS_DIGEST_ALGORITMO_NAO_SUPORTADO")
        signature_algo = signer["signature_algorithm"]["algorithm"].native
        if signature_algo not in ("rsassa_pkcs1v15", "sha1_rsa", "sha256_rsa", "sha384_rsa", "sha512_rsa"):
            _stop("CMS_ASSINATURA_NAO_RSA_PKCS1")
        attrs = signer["signed_attrs"]
        has_signed_attrs = attrs.native is not None and len(attrs) > 0
        hash_name = alg.replace("-", "")
        if hash_name not in _HASHES:
            _stop("CMS_HASH_NAO_SUPORTADO")
        if has_signed_attrs:
            # RFC 5652 5.3-5.6: signed attrs MUST contain exactly one
            # matching content-type and message-digest attribute. No fallback
            # to direct-content RSA is permitted if these attrs are malformed.
            message_digests = [a["values"][0].native for a in attrs if a["type"].native == "message_digest" and len(a["values"]) == 1]
            content_types = [a["values"][0].native for a in attrs if a["type"].native == "content_type" and len(a["values"]) == 1]
            if len(message_digests) != 1 or len(content_types) != 1 or content_types[0] != "data":
                _stop("CMS_ATRIBUTOS_OBRIGATORIOS_INVALIDOS")
            hash_function = getattr(hashlib, hash_name)
            if not hmac.compare_digest(message_digests[0], hash_function(encapsulated).digest()):
                _stop("CMS_SIGNED_ATTRIBUTES_DIGEST_DIVERGENTE")
        certs = obj["certificates"]
        if certs.native is None or not 1 <= len(certs) <= MAX_CERTS:
            _stop("CMS_CERTIFICADOS_INVALIDOS")
        matches = []
        for certificate_choice in certs:
            if certificate_choice.name != "certificate":
                continue
            candidate = certificate_choice.chosen
            if candidate.issuer == sid.chosen["issuer"] and candidate.serial_number == sid.chosen["serial_number"].native:
                matches.append(candidate)
        if len(matches) != 1:
            _stop("CMS_CERTIFICADO_SIGNATARIO_AMBIGUO")
        cert_der = matches[0].dump()
        leaf = x509.load_der_x509_certificate(cert_der)
        public_key = leaf.public_key()
        if not isinstance(public_key, rsa.RSAPublicKey):
            _stop("CMS_CHAVE_NAO_RSA")
        if has_signed_attrs:
            # signed_attrs is [0] IMPLICIT. Sign the DER SET OF encoding,
            # never the PDF contents directly in this branch.
            attrs_der = attrs.dump(force=True)
            if attrs_der[:1] != b"\xa0":
                _stop("CMS_ATRIBUTOS_ASN1_INVALIDOS")
            signed_payload = b"\x31" + attrs_der[1:]
        else:
            # RFC 5652 5.4: when signedAttrs is ABSENT (permitted for id-data),
            # RSA signs the raw OCTETS of eContent, not the SignerInfo ASN.1,
            # not the SHA-1 PDF ByteRange directly, and not a manufactured SET.
            signed_payload = encapsulated
        public_key.verify(signer["signature"].native, signed_payload,
                          padding.PKCS1v15(), _HASHES[hash_name]())
    except G111SignatureError:
        raise
    except Exception as exc:
        raise G111SignatureError("G111_CMS_RSA_VERIFICACAO_FALHOU") from exc
    return {
        "schema_version": SCHEMA,
        "estado": "PDF_LEGADO_CRIPTOGRAFIA_VERIFICADA_SEM_AUTORIDADE",
        "pdf_sha256": digest,
        "pdf_tamanho_bytes": len(pdf_bytes),
        "subfilter": "adbe.pkcs7.sha1",
        "pdf_byterange_totalmente_coberto": True,
        "pdf_sha1_legado_encapsulado_confere": True,
        "cms_signed_attributes_digest_confere": bool(has_signed_attrs),
        "cms_assinatura_sem_atributos_verificada": not has_signed_attrs,
        "cms_assinatura_rsa_valida": True,
        "cms_certificado_signatario_sha256": hashlib.sha256(cert_der).hexdigest(),
        "cms_digest_algorithm": hash_name,
        "sha1_legado_risco_colisao": True,
        "cms_tem_signing_time_nao_confiavel": has_signed_attrs and any(a["type"].native == "signing_time" for a in attrs),
        "carimbo_tempo_rfc3161_verificado": False,
        "cms_cadeia_certificados_verificada": False,
        "cms_lcr_ocsp_historicos_verificados": False,
        **{name: False for name in _DENIED},
    }


__all__ = ["SCHEMA", "G111SignatureError", "verificar_assinatura_legada_pdf_g111"]
