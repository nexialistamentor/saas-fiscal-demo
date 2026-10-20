"""G1.13-C3 tests: synthetic original PDF bytes; historical actual hashes in docs.

NO DB, network, SEFAZ, actual NF-e, payments, production, or legal authority.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from io import BytesIO
import unittest

from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from tools.enterprise_g113_temporal_mva_evidence import (
    SCHEMA, G113C3EvidenceError, selecionar_mva_temporal_g113_c3,
)

URL = 'https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/synthetic.pdf'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sample_pdf(extra_rate_new=''):
    w = PdfWriter()
    w.add_metadata({'/G113C3Synthetic': 'padding' * 200})
    font = w._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    }))
    for rate in ('41, 42', '46, 78'):
        page = w.add_blank_page(width=595, height=842)
        page[NameObject('/Resources')] = DictionaryObject({
            NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})
        })
        content = ('BT /F1 12 Tf 40 780 Td '
                   '(1 20.001.00 1211.90.90 Henna 200 g ' + rate +
                   (' ' + extra_rate_new if rate == '46, 78' and extra_rate_new else '') +
                   ' 2 20.002.00 2712.10.00 Vaselina) Tj ET')
        stream = DecodedStreamObject()
        stream.set_data(content.encode('latin-1'))
        page[NameObject('/Contents')] = w._add_object(stream)
    out = BytesIO()
    w.write(out)
    return out.getvalue()


def evidence(pdf, page, key, mva, start, end, validity_start, validity_end):
    text = PdfReader(BytesIO(pdf), strict=True).pages[page-1].extract_text(extraction_mode='plain')
    position = text.index('20.001.00')
    region = text[position:text.index('20.002.00')]
    raw_rate = mva.replace('.', ', ')
    excerpt = region[:region.index(raw_rate)+len(raw_rate)].strip()
    return {
        'versao_id': key, 'uf': 'PR', 'ncm': '12119090', 'cest': '2000100',
        'descricao_marcador': 'Henna', 'source_url': URL,
        'pdf_sha256': digest(pdf), 'pagina_1_based': page,
        'pagina_texto_sha256': digest(text.encode('utf-8')),
        'inicio_caracter': position, 'excerto_sha256': digest(excerpt.encode('utf-8')),
        'proximo_cest': '2000200', 'numero_proxima_linha': 2,
        'mva_original_percentual': mva, 'vigencia_inicio_declarada': validity_start,
        'vigencia_fim_declarada': validity_end,
        'observacao_inicio': start, 'observacao_fim': end,
        'dispositivo_declarado': 'TESTE SINTETICO SEFA Artigo 12',
    }


class TemporalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.pdf = sample_pdf()
        self.documents = {URL:self.pdf}
        self.item = dict(indice_item=1, uf='PR', ncm='12119090', cest='2000100')
        self.versions = [
            evidence(self.pdf,1,'historical','41.42', '2026-03-31','2026-03-31',None,'2026-03-31'),
            evidence(self.pdf,2,'amended','46.78','2026-04-01','2026-04-01','2026-04-01',None),
        ]

    def run_selection(self, day='2026-04-01', **changes):
        kwargs=dict(pdfs_por_url=self.documents,item=self.item,
                    data_operacao=day,evidencias=self.versions)
        kwargs.update(changes)
        return selecionar_mva_temporal_g113_c3(**kwargs)

    def deny(self, reason=None):
        with self.assertRaises(G113C3EvidenceError) as caught:
            self.run_selection()
        if reason:
            self.assertIn(reason, str(caught.exception))

    def test_01_select_old_only_at_bounded_date(self):
        result=self.run_selection('2026-03-31')
        self.assertEqual(result['versao_selecionada'],'historical')
        self.assertEqual(result['mva_original_percentual_observada'],'41.42')
        self.assertEqual(result['estado'],'CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE')

    def test_02_select_new_only_at_bounded_date(self):
        result=self.run_selection('2026-04-01')
        self.assertEqual(result['versao_selecionada'],'amended')
        self.assertEqual(result['mva_original_percentual_observada'],'46.78')
        self.assertEqual(result['schema_version'],SCHEMA)
        self.assertTrue(result['verificacao_pdf_pagina_excerto'])

    def test_03_beyond_checked_windows_abstain(self):
        result=self.run_selection('2026-05-01')
        self.assertEqual(result['estado'],'ABSTENCAO_TEMPORAL')
        self.assertEqual(result['motivo'],'SEM_JANELA_DOCUMENTAL_COTEJADA')
        self.assertIsNone(result['mva_original_percentual_observada'])

    def test_04_before_checked_window_abstain(self):
        self.assertEqual(self.run_selection('2026-03-30')['estado'],'ABSTENCAO_TEMPORAL')

    def test_05_different_uf_abstains(self):
        other=dict(self.item,uf='PA')
        self.assertEqual(self.run_selection(item=other)['estado'],'ABSTENCAO_TEMPORAL')

    def test_06_different_ncm_abstains(self):
        self.assertEqual(self.run_selection(item=dict(self.item,ncm='11111111'))['estado'],'ABSTENCAO_TEMPORAL')

    def test_07_different_cest_abstains(self):
        self.assertEqual(self.run_selection(item=dict(self.item,cest='0000001'))['estado'],'ABSTENCAO_TEMPORAL')

    def test_08_every_trust_flag_false(self):
        r=self.run_selection()
        for field in ('fonte_primaria_autenticada','vigencia_juridica_comprovada',
                      'completude_alteracoes_posteriores','aplicabilidade_st_comprovada',
                      'condicoes_operacionais_comprovadas','aliquota_interna_comprovada',
                      'reconciliacao_monetaria_com_nf_e','autoridade_fiscal',
                      'credito_confirmado','checkout_autorizado','usavel_comercialmente',
                      'prova_nf_e_real','prova_adr020_regra_persistida'):
            self.assertIs(r[field],False)

    def test_09_pdf_tamper_deny(self):
        self.documents[URL] += b'!'
        self.deny('PDF_SHA256_DIVERGENTE')

    def test_10_pdf_missing_deny(self):
        self.documents={}
        self.deny('CORPUS_INVALIDO')

    def test_11_wrong_page_digest_deny(self):
        self.versions[1]['pagina_texto_sha256']='0'*64
        self.deny('PAGINA_SHA256_DIVERGENTE')

    def test_12_wrong_excerpt_digest_deny(self):
        self.versions[1]['excerto_sha256']='f'*64
        self.deny('EXCERTO_SHA256_DIVERGENTE')

    def test_13_wrong_mva_deny(self):
        self.versions[1]['mva_original_percentual']='47.00'
        self.deny('MVA_TEXTO_REGRA_DIVERGENTE')

    def test_14_wrong_ncm_deny(self):
        self.versions[0]['ncm']='00000000'
        self.deny('PRODUTO_NCM_NAO_COTEJADOS')

    def test_15_wrong_next_row_deny(self):
        self.versions[0]['proximo_cest']='9999999'
        self.deny('CEST_NAO_UNICO')

    def test_16_wrong_offset_deny(self):
        self.versions[0]['inicio_caracter']+=1
        self.deny('POSICAO_CEST_DIVERGENTE')

    def test_17_ambiguous_version_overlap_abstain(self):
        self.versions[0]['observacao_fim']='2026-04-01'
        self.versions[0]['vigencia_fim_declarada']='2026-04-01'
        r=self.run_selection()
        self.assertEqual(r['estado'],'ABSTENCAO_TEMPORAL')
        self.assertEqual(r['motivo'],'SOBREPOSICAO_VERSOES_CANDIDATAS')

    def test_18_duplicate_version_deny(self):
        self.versions[1]['versao_id']='historical'
        self.deny('VERSAO_DUPLICADA')

    def test_19_effective_window_violation_deny(self):
        self.versions[1]['observacao_inicio']='2026-03-31'
        self.deny('JANELA_FORA_DA_VIGENCIA_DECLARADA')

    def test_20_invalid_date_deny(self):
        with self.assertRaises(G113C3EvidenceError):
            self.run_selection('2026-02-30')

    def test_21_malformed_ncm_deny(self):
        with self.assertRaises(G113C3EvidenceError):
            self.run_selection(item=dict(self.item,ncm='12.11.90'))

    def test_22_extra_evidence_key_deny(self):
        self.versions[0]['AUTORIZADO']=True
        self.deny('CONTRATO_EVIDENCIA_INVALIDO')

    def test_23_http_source_deny(self):
        self.versions[0]['source_url']='http://example.com/file.pdf'
        self.deny('CAMPOS_EVIDENCIA_INVALIDOS')

    def test_24_next_row_number_deny(self):
        self.versions[0]['numero_proxima_linha']=3
        self.deny('LINHA_SEGUINTE_CONTAMINADA')

    def test_25_query_without_evidence_deny(self):
        with self.assertRaises(G113C3EvidenceError):
            self.run_selection(evidencias=[])

    def test_26_no_db_and_no_network_imports(self):
        import inspect
        from tools import enterprise_g113_temporal_mva_evidence as service
        src=inspect.getsource(service)
        for term in ('from app.models','from app.database','urllib.request',
                     'requests.get','session.commit','open('):
            self.assertNotIn(term, src)

    def test_27_two_percentages_in_same_row_deny(self):
        changed = sample_pdf(extra_rate_new='57, 50')
        self.documents = {URL:changed}
        self.versions = [
            evidence(changed, 1, 'historical', '41.42',
                     '2026-03-31', '2026-03-31', None, '2026-03-31'),
            evidence(changed, 2, 'amended', '46.78',
                     '2026-04-01', '2026-04-01', '2026-04-01', None),
        ]
        self.deny('MVA_NAO_UNICA_NO_EXCERTO')

    def test_28_empty_date_window_deny(self):
        self.versions[0]['observacao_inicio']='2026-04-01'
        self.deny('JANELA_FORA_DA_VIGENCIA_DECLARADA')

    def test_29_mva_above_100_permitted_synthetically(self):
        # The engine must not invent a cap at 100%; this is *not* a real tax rule.
        from tools.enterprise_g113_temporal_mva_evidence import _mva
        self.assertEqual(_mva('150.00'), 150)

    def test_30_rate_integer_without_canonical_fraction_denied(self):
        self.versions[0]['mva_original_percentual']='41'
        self.deny('MVA_FORMATO_INVALIDO')

if __name__=='__main__':
    unittest.main(verbosity=2)
