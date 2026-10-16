"""I7: regressao de C14N inclusiva com namespace default herdado.

Apenas XML sintetico, nunca ficheiros reais nem chamadas externas.
"""
import unittest
from lxml import etree

from app.services.enterprise_nfe_i7_xml_signature import _canonical

NFE = 'http://www.portalfiscal.inf.br/nfe'
DS = 'http://www.w3.org/2000/09/xmldsig#'


class TestI7CanonicalizationInheritedNamespace(unittest.TestCase):
    def test_00_inherited_default_namespace_canonicalized_without_spurious_xmlns_reset(self):
        raw = ('<nfeProc xmlns="%s" versao="4.00"><NFe>'
               '<infNFe Id="NFeTESTESINTETICO" versao="4.00">'
               '<ide><natOp>OPERACAO SINTETICA</natOp></ide>'
               '</infNFe></NFe></nfeProc>' % NFE).encode('ascii')
        root = etree.fromstring(raw)
        inf = root.find('.//{%s}infNFe' % NFE)
        expected = ('<infNFe xmlns="%s" Id="NFeTESTESINTETICO" versao="4.00">'
                    '<ide><natOp>OPERACAO SINTETICA</natOp></ide></infNFe>' % NFE).encode('ascii')
        if _canonical(inf) != expected:
            self.fail('I7_C14N_NAMESPACE_CANONICALIZATION_MISMATCH')

    def test_01_inherited_signature_namespace_canonicalization(self):
        raw = ('<nfeProc xmlns="%s"><NFe><Signature xmlns="%s">'
               '<SignedInfo><Reference><DigestValue>AAA=</DigestValue></Reference>'
               '</SignedInfo></Signature></NFe></nfeProc>' % (NFE,DS)).encode('ascii')
        root = etree.fromstring(raw)
        signed = root.find('.//{%s}SignedInfo' % DS)
        expected = ('<SignedInfo xmlns="%s"><Reference><DigestValue>AAA='
                    '</DigestValue></Reference></SignedInfo>' % DS).encode('ascii')
        self.assertEqual(_canonical(signed), expected)

    def test_02_canonicalization_does_not_modify_original_tree(self):
        raw = ('<nfeProc xmlns="%s"><NFe><infNFe Id="NFeTESTE">'
               '<ide><natOp>SINTETICO</natOp></ide></infNFe></NFe></nfeProc>' % NFE).encode('ascii')
        root = etree.fromstring(raw)
        before = etree.tostring(root)
        inf = root.find('.//{%s}infNFe' % NFE)
        self.assertEqual(_canonical(inf), _canonical(inf))
        self.assertEqual(etree.tostring(root), before)


if __name__ == '__main__':
    unittest.main()
