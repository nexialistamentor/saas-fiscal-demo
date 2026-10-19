"""G1.13-C1 synthetic only: PDF text locator to G16/G18 item and ADR-020 rows.

This test proves the absence of false authority; it does not interpret a law.
"""
from __future__ import annotations

import copy
import hashlib
from io import BytesIO
from types import SimpleNamespace as S
import unittest

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from tools.enterprise_g113_exact_normative_excerpt import (
    SCHEMA, G113EvidenceError, cotejar_excerto_normativo_g113,
)

H = lambda c: c*64
QUOTATION = 'Artigo 10. No exemplo SINTETICO, a MVA declarada e 40 porcento.'


def build_pdf():
    writer = PdfWriter()
    writer.add_metadata({'/G113SyntheticPadding': 'P'*1024})
    page = writer.add_blank_page(width=595, height=842)
    font = writer._add_object(DictionaryObject({
        NameObject('/Type'):NameObject('/Font'),
        NameObject('/Subtype'):NameObject('/Type1'),
        NameObject('/BaseFont'):NameObject('/Helvetica'),
    }))
    resources = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'):font})})
    page[NameObject('/Resources')] = resources
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 12 Tf 40 780 Td (' + QUOTATION + ') Tj ET').encode('latin-1'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class G113Synthetic(unittest.TestCase):
    def setUp(self):
        self.pdf = build_pdf()
        self.digest = hashlib.sha256(self.pdf).hexdigest()
        txt = PdfReader(BytesIO(self.pdf), strict=True).pages[0].extract_text(extraction_mode='plain')
        self.anchor = {
            'pdf_sha256':self.digest,
            'pagina_1_based':1,
            'pagina_texto_sha256':hashlib.sha256(txt.encode('utf-8')).hexdigest(),
            'inicio_caracter':txt.index(QUOTATION),
            'excerto_exato':QUOTATION,
            'excerto_sha256':hashlib.sha256(QUOTATION.encode('utf-8')).hexdigest(),
            'dispositivo_declarado':'Artigo 10 — SINTETICO',
        }
        self.rule = {
            'uf':'PA','ncm':'10019010','cest':'0100100','cfop':'5102','cst':'10',
            'regime':'real','operacao':'saida_interna','metodo_base':'iva_st',
            'vigencia_inicio':'2026-01-01','vigencia_fim':'2026-12-31',
            'mva_percentual':'40.00','aliquota_percentual':'18.00',
        }
        self.e = S(extraction_result_id='extraction', normative_artifact_id='art',
            artifact_hash=self.digest,outcome='conclusivo',record_hash=H('a'),
            evidence={'g113_v1':copy.deepcopy(self.anchor)},
            structured_content={'g113_v1':copy.deepcopy(self.rule)})
        self.r = S(rule_version_record_id='rule-record',extraction_result_id='extraction',
            extraction_result_record_hash=H('a'),rule_id='rule-1',rule_version=1,
            rule_hash=H('b'),record_hash=H('c'),
            evidence={'g113_v1':copy.deepcopy(self.anchor)},
            structured_content={'g113_v1':copy.deepcopy(self.rule)})
        self.g14 = dict(indice_item=1,estado='COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
            sha256_texto_normativo_declarado=self.digest,
            uf_operacao='PA',ncm='10019010',cest_observado='0100100',
            cfop='5102',cst_observado='10',regime_empresa='real',competencia_declarada='2026-09')
        self.g16 = dict(schema_version='SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1',
            empresa_id=8,relatorio_id=7,documento_id=6,xml_sha256=H('d'),
            data_operacao_observada='2026-09-12',itens_total=1,
            itens=[dict(indice_item=1,estado='CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE',
                regra_interna_cotejada=True,rule_id='rule-1',rule_version=1,rule_hash=H('b'))],
            fonte_primaria_autenticada=False,autoridade_fiscal=False,credito_confirmado=False,checkout_autorizado=False)
        self.g18 = dict(schema_version='SOLVERIS_ENTERPRISE_G18_EXTERNAL_PUBLICATION_HASH_LINK_V1',
            empresa_id=8,relatorio_id=7,documento_id=6,xml_sha256=H('d'),itens_total=1,
            itens=[dict(indice_item=1,vinculo_hash_adr020=True,pdf_bytes_recalculados=True,
                sha256_publicacao_observado=self.digest,custodia_externa_revalidada=False,
                fonte_primaria_autenticada=False)],
            fonte_primaria_autenticada=False,autoridade_fiscal=False,credito_confirmado=False,checkout_autorizado=False)

    def audit(self, **overrides):
        args=dict(pdf_bytes=self.pdf,pdf_sha256=self.digest,indice_item=1,
            g14_item=self.g14,g16_result=self.g16,g18_result=self.g18,
            extraction_result=self.e,rule_version=self.r)
        args.update(overrides)
        return cotejar_excerto_normativo_g113(**args)

    def assert_denied(self):
        with self.assertRaises(G113EvidenceError):
            self.audit()

    def test_01_genuine_synthetic_page_rule_item_bridge_noncommercial(self):
        r=self.audit()
        self.assertEqual(r['schema_version'],SCHEMA)
        self.assertEqual(r['pdf_sha256'],self.digest)
        self.assertTrue(r['excerto_presente_nos_bytes_pdf_extraidos'])
        self.assertFalse(r['prova_de_relacao_semantica_entre_excerto_e_parametros'])
        self.assertEqual(r['mva_percentual_declarada'],'40.00')
        self.assertEqual(r['indice_item'],1)
        for k in ('autoridade_fiscal','credito_confirmado','checkout_autorizado',
                  'vigencia_juridica_comprovada','formula_juridicamente_autorizada'):
            self.assertIs(r[k],False)

    def test_02_exact_excerpt_sha_not_pdf_hash(self):
        r=self.audit()
        self.assertNotEqual(r['pdf_sha256'],r['excerto_sha256'])

    def test_03_pdf_mutation_with_old_digest(self):
        with self.assertRaises(G113EvidenceError):self.audit(pdf_bytes=self.pdf+b' ')

    def test_04_updated_pdf_digest_cannot_rebind_old_anchor(self):
        pdf=self.pdf+b' '
        with self.assertRaises(G113EvidenceError):self.audit(pdf_bytes=pdf,pdf_sha256=hashlib.sha256(pdf).hexdigest())

    def test_05_g18_hash_mismatch(self):
        self.g18['itens'][0]['sha256_publicacao_observado']=H('0')
        self.assert_denied()

    def test_06_g18_bridge_not_cotejado(self):
        self.g18['itens'][0]['vinculo_hash_adr020']=False
        self.assert_denied()

    def test_07_g16_unlinked_rule(self):
        self.g16['itens'][0]['regra_interna_cotejada']=False
        self.assert_denied()

    def test_08_g16_risk_relation_alert(self):
        self.g16['itens'][0]['estado']='ALERTA_RELACAO_NORMATIVA_SEM_DECISAO'
        self.assert_denied()

    def test_09_item_ncm_mismatch(self):
        self.g14['ncm']='00000000'
        self.assert_denied()

    def test_10_rule_record_wrong_extraction_hash(self):
        self.r.extraction_result_record_hash=H('0')
        self.assert_denied()

    def test_11_rule_hash_mismatch(self):
        self.r.rule_hash=H('0')
        self.assert_denied()

    def test_12_missing_extraction_anchor(self):
        self.e.evidence={}
        self.assert_denied()

    def test_13_rule_anchor_different_offset(self):
        self.r.evidence['g113_v1']['inicio_caracter']+=1
        self.assert_denied()

    def test_14_missing_quote(self):
        self.e.evidence['g113_v1']['excerto_exato']='Artigo 10. A norma sintetica nao existe nesta pagina textual.'
        self.r.evidence=copy.deepcopy(self.e.evidence)
        self.assert_denied()

    def test_15_nonunique_quote(self):
        self.e.evidence['g113_v1']['excerto_exato']='SINTETICO'
        self.e.evidence['g113_v1']['excerto_sha256']=hashlib.sha256(b'SINTETICO').hexdigest()
        self.r.evidence=copy.deepcopy(self.e.evidence)
        self.assert_denied()

    def test_16_page_hash_changed(self):
        self.e.evidence['g113_v1']['pagina_texto_sha256']=H('f')
        self.r.evidence=copy.deepcopy(self.e.evidence)
        self.assert_denied()

    def test_17_wrong_page(self):
        self.e.evidence['g113_v1']['pagina_1_based']=2
        self.r.evidence=copy.deepcopy(self.e.evidence)
        self.assert_denied()

    def test_18_rule_extraction_disagree_params(self):
        self.r.structured_content['g113_v1']['mva_percentual']='45.00'
        self.assert_denied()

    def test_19_unparsable_percent(self):
        self.r.structured_content['g113_v1']['mva_percentual']='1e500'
        self.e.structured_content=copy.deepcopy(self.r.structured_content)
        self.assert_denied()

    def test_20_vigencia_declared_outside_operation(self):
        self.r.structured_content['g113_v1']['vigencia_inicio']='2027-01-01'
        self.e.structured_content=copy.deepcopy(self.r.structured_content)
        self.assert_denied()

    def test_21_auth_escalation_in_upstream(self):
        self.g18['fonte_primaria_autenticada']=True
        self.assert_denied()

    def test_22_missing_rule_evidence(self):
        self.r.evidence={}
        self.assert_denied()

    def test_23_other_item_identity(self):
        self.g18['itens'][0]['indice_item']=2
        self.assert_denied()

    def test_25_mva_above_one_hundred_can_be_declared(self):
        self.r.structured_content['g113_v1']['mva_percentual']='150.00'
        self.e.structured_content=copy.deepcopy(self.r.structured_content)
        self.assertEqual(self.audit()['mva_percentual_declarada'], '150.00')

    def test_26_aliquota_above_one_hundred_denied(self):
        self.r.structured_content['g113_v1']['aliquota_percentual']='150.00'
        self.e.structured_content=copy.deepcopy(self.r.structured_content)
        self.assert_denied()

    def test_24_no_implicit_db_network(self):
        r=self.audit()
        self.assertEqual(r['consultas_db_neste_servico'],0)
        self.assertFalse(r['checkout_autorizado'])

if __name__=='__main__':
    unittest.main(verbosity=2)
