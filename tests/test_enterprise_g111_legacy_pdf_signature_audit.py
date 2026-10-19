"""G1.11 synthetic cryptographic contracts. No network, DB or real certificate authority."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import sys
import re
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tools.enterprise_g111_legacy_pdf_signature_audit as g111

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, ByteStringObject, DictionaryObject, NameObject, NumberObject, TextStringObject


def build_pdf(*, subfilter='/adbe.pkcs7.sha1', signer_digest='sha256', no_signed_attrs=False):
    # Only a synthetic self-signed certificate; NEVER a trusted ICP-Brasil anchor.
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'SOLVERIS SYNTHETIC UNTRUSTED TEST')])
    now = datetime(2026, 10, 19, tzinfo=timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(1234567)
            .not_valid_before(now-timedelta(days=1)).not_valid_after(now+timedelta(days=1))
            .sign(key, hashes.SHA256()))
    writer = PdfWriter()
    writer.add_blank_page(width=600, height=800)
    sig = DictionaryObject({
        NameObject('/Type'): NameObject('/Sig'),
        NameObject('/Filter'): NameObject('/Adobe.PPKLite'),
        NameObject('/SubFilter'): NameObject(subfilter),
        NameObject('/ByteRange'): ArrayObject([NumberObject(0), NumberObject(1111111111), NumberObject(2222222222), NumberObject(3333333333)]),
        NameObject('/Contents'): ByteStringObject(b'\0'*8192),
    })
    sig_ref = writer._add_object(sig)
    field = DictionaryObject({NameObject('/FT'): NameObject('/Sig'), NameObject('/T'): TextStringObject('TesteAssinatura'), NameObject('/V'): sig_ref})
    field_ref = writer._add_object(field)
    form = DictionaryObject({NameObject('/Fields'): ArrayObject([field_ref]), NameObject('/SigFlags'): NumberObject(3)})
    form_ref = writer._add_object(form)
    writer._root_object[NameObject('/AcroForm')] = form_ref
    stream = BytesIO()
    writer.write(stream)
    raw = stream.getvalue()
    matches = list(re.finditer(rb'/Contents\s*(<0{16384}>)', raw))
    assert len(matches) == 1
    start, end = matches[0].start(1), matches[0].end(1)
    replacements = (f'{start:010}', f'{end:010}', f'{len(raw)-end:010}')
    for original, new in zip((b'1111111111', b'2222222222', b'3333333333'), replacements):
        assert raw.count(original) == 1
        raw = raw.replace(original, new.encode('ascii'))
    signed_part = raw[:start] + raw[end:]
    algorithm = {'sha256': hashes.SHA256(), 'sha1': hashes.SHA1()}[signer_digest]
    options = [pkcs7.PKCS7Options.Binary]
    if no_signed_attrs:
        options.append(pkcs7.PKCS7Options.NoAttributes)
    signed_cms = (pkcs7.PKCS7SignatureBuilder().set_data(hashlib.sha1(signed_part).digest())
                  .add_signer(cert, key, algorithm)
                  .sign(serialization.Encoding.DER, options))
    assert len(signed_cms) < 8192
    padded_hex = signed_cms.hex().encode('ascii') + b'0'*(16384-len(signed_cms)*2)
    signed_pdf = raw[:start+1] + padded_hex + raw[end-1:]
    assert len(signed_pdf)==len(raw)
    return signed_pdf


class G111(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = build_pdf()
        cls.sha = hashlib.sha256(cls.pdf).hexdigest()

    def audit(self, pdf=None, sha=None):
        raw=self.pdf if pdf is None else pdf
        return g111.verificar_assinatura_legada_pdf_g111(pdf_bytes=raw,
               sha256_esperado=hashlib.sha256(raw).hexdigest() if sha is None else sha)

    def test_01_valid_cryptography_still_no_official_authority(self):
        result = self.audit()
        self.assertTrue(result['cms_assinatura_rsa_valida'])
        self.assertTrue(result['pdf_byterange_totalmente_coberto'])
        self.assertTrue(result['sha1_legado_risco_colisao'])
        for field in g111._DENIED:
            self.assertIs(result[field], False, field)

    def test_02_tamper_byte_with_updated_sha256_is_rejected(self):
        raw=bytearray(self.pdf)
        idx=raw.index(b'/Type /Page')
        raw[idx+8] = (raw[idx+8]+1) % 256
        with self.assertRaises(g111.G111SignatureError):self.audit(bytes(raw))

    def test_03_append_after_signature_is_rejected(self):
        with self.assertRaises(g111.G111SignatureError):self.audit(self.pdf+b'\n%new content')

    def test_04_pdf_digest_claim_is_not_trust(self):
        with self.assertRaises(g111.G111SignatureError):self.audit(sha='0'*64)

    def test_05_subfilter_other_is_denied(self):
        raw = self.pdf.replace(b'/adbe.pkcs7.sha1', b'/adbe.pkcs7.shax')
        with self.assertRaises(g111.G111SignatureError):self.audit(raw)

    def test_06_requires_pdf_bytes_type(self):
        with self.assertRaises(g111.G111SignatureError):
            g111.verificar_assinatura_legada_pdf_g111(pdf_bytes=bytearray(self.pdf), sha256_esperado=self.sha)

    def test_07_no_hidden_signed_time_authority(self):
        result=self.audit()
        self.assertFalse(result['carimbo_tempo_rfc3161_verificado'])
        self.assertFalse(result['revogacao_historica_comprovada'])
        self.assertFalse(result['identidade_publicador_autenticada'])

    def test_08_bad_expected_hash_syntax(self):
        with self.assertRaises(g111.G111SignatureError):self.audit(sha='XYZ')

    def test_09_sha1_signer_crypto_valid_but_legacy_risk(self):
        try:
            raw=build_pdf(signer_digest='sha1')
        except (ValueError, TypeError):
            self.skipTest('Cryptography policy excludes synthetic SHA-1 signer')
        r=self.audit(raw)
        self.assertEqual(r['cms_digest_algorithm'], 'sha1')
        self.assertTrue(r['sha1_legado_risco_colisao'])

    def test_10_repeat_deterministic_observation(self):
        a=self.audit(); b=self.audit()
        self.assertEqual(a,b)

    def test_11_digest_exact_bytes(self):
        r=self.audit()
        self.assertEqual(r['pdf_sha256'],self.sha)
        self.assertEqual(r['pdf_tamanho_bytes'],len(self.pdf))

    def test_12_cms_padding_nonzero_rejected(self):
        raw=bytearray(self.pdf)
        found = re.search(rb'/Contents\s*<([0-9a-f]{16384})>', raw)
        self.assertIsNotNone(found)
        raw[found.end(1)-1]=ord('1')
        with self.assertRaises(g111.G111SignatureError):self.audit(bytes(raw))

    def test_13_unsigned_form_rejected(self):
        raw=self.pdf.replace(b'/FT /Sig', b'/FT /Txt')
        with self.assertRaises(g111.G111SignatureError):self.audit(raw)

    def _cms_reframe(self, *, mutate=None, pdf=None):
        """Re-encode only unsigned /Contents; ByteRange remains unchanged."""
        from asn1crypto import parser
        raw = self.pdf if pdf is None else pdf
        found = re.search(rb'/Contents\s*<([0-9a-f]{16384})>', raw)
        self.assertIsNotNone(found)
        reserved = bytes.fromhex(found.group(1).decode('ascii'))
        cls, constructed, tag, header, content, trailer = parser.parse(reserved)
        self.assertEqual((cls, constructed, tag), (0, 1, 16))
        self.assertEqual(trailer, b'')
        self.assertGreaterEqual(len(header), 2)
        # Definite DER outer sequence -> indefinite BER with mandatory EOC.
        framed = b'\x30\x80' + content + b'\x00\x00'
        if mutate is not None:
            framed = mutate(framed)
        self.assertLessEqual(len(framed), len(reserved))
        replacement = framed.hex().encode('ascii') + b'0' * (16384 - 2 * len(framed))
        return raw[:found.start(1)] + replacement + raw[found.end(1):]

    def test_14_ber_indefinite_outer_eoc_zero_padding_crypto_valid(self):
        raw = self._cms_reframe()
        result = self.audit(raw)
        self.assertTrue(result['cms_assinatura_rsa_valida'])
        self.assertTrue(result['pdf_byterange_totalmente_coberto'])
        self.assertTrue(result['sha1_legado_risco_colisao'])
        for field in g111._DENIED:
            self.assertIs(result[field], False, field)

    def test_15_ber_indefinite_nonzero_reserve_rejected(self):
        raw = bytearray(self._cms_reframe())
        found = re.search(rb'/Contents\s*<([0-9a-f]{16384})>', raw)
        self.assertIsNotNone(found)
        raw[found.end(1)-1] = ord('1')
        with self.assertRaises(g111.G111SignatureError):
            self.audit(bytes(raw))

    def test_16_ber_indefinite_eoc_corrupted_rejected(self):
        # With zero padding, absence of EOC is indistinguishable from its
        # adjacent zeros; make a structurally corrupted, nonzero terminator.
        raw = self._cms_reframe(mutate=lambda framed: framed[:-2] + b'\x00\xff')
        with self.assertRaises(g111.G111SignatureError):
            self.audit(raw)

    def test_17_ber_indefinite_nonzero_after_eoc_rejected(self):
        raw = self._cms_reframe(mutate=lambda framed: framed + b'\x01')
        with self.assertRaises(g111.G111SignatureError):
            self.audit(raw)


    def test_18_no_signed_attrs_rsa_over_econtent_valid(self):
        # A real CMS-compatible PKCS7 SignedData without authenticated attrs.
        raw = build_pdf(no_signed_attrs=True)
        result = self.audit(raw)
        self.assertTrue(result['cms_assinatura_rsa_valida'])
        self.assertTrue(result['cms_assinatura_sem_atributos_verificada'])
        self.assertFalse(result['cms_signed_attributes_digest_confere'])
        self.assertFalse(result['cms_tem_signing_time_nao_confiavel'])
        self.assertTrue(result['pdf_sha1_legado_encapsulado_confere'])
        for field in g111._DENIED:
            self.assertIs(result[field], False, field)

    def test_19_no_signed_attrs_ber_eoc_zero_padding_crypto_valid(self):
        raw = build_pdf(no_signed_attrs=True)
        raw = self._cms_reframe(pdf=raw)
        result = self.audit(raw)
        self.assertTrue(result['cms_assinatura_sem_atributos_verificada'])
        self.assertTrue(result['cms_assinatura_rsa_valida'])
        for field in g111._DENIED:
            self.assertIs(result[field], False, field)

    def test_20_no_signed_attrs_tampered_pdf_denied(self):
        raw = bytearray(build_pdf(no_signed_attrs=True))
        idx = raw.index(b'/Type /Page')
        raw[idx + 8] = (raw[idx + 8] + 1) % 256
        with self.assertRaises(g111.G111SignatureError):
            self.audit(bytes(raw))

    def test_21_signed_attrs_still_checked_not_fallback(self):
        result = self.audit()
        self.assertTrue(result['cms_signed_attributes_digest_confere'])
        self.assertFalse(result['cms_assinatura_sem_atributos_verificada'])

    def test_22_no_signed_attrs_bad_signature_denied(self):
        # Change signature bytes in unsigned PDF /Contents, preserve CMS parse.
        from asn1crypto import cms, parser
        raw = build_pdf(no_signed_attrs=True)
        found = re.search(rb'/Contents\s*<([0-9a-f]{16384})>', raw)
        self.assertIsNotNone(found)
        reserved = bytes.fromhex(found.group(1).decode('ascii'))
        _, _, _, head, content, trailer = parser.parse(reserved)
        asn1 = head + content + trailer
        envelope = cms.ContentInfo.load(asn1)
        signer = envelope['content']['signer_infos'][0]
        self.assertIsNone(signer['signed_attrs'].native)
        signature = signer['signature'].native
        # Target one byte of the RSA value, not the ASN.1 header or padding.
        pos = reserved.find(signature)
        self.assertGreater(pos, 0)
        modified = bytearray(reserved)
        modified[pos + 10] ^= 1
        replacement = bytes(modified).hex().encode('ascii')
        changed = raw[:found.start(1)] + replacement + raw[found.end(1):]
        with self.assertRaises(g111.G111SignatureError):
            self.audit(changed)

if __name__=='__main__':
    unittest.main(verbosity=2)
