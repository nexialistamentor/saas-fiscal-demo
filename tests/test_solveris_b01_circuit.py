"""Bloco 01: verificacao sintetica REAL do escritor e dos consumidores canonicos.

Sem rede/SEFAZ; SQLite :memory:; PDF produzido pela fixture em bytes.
C3-C7 devem receber SAIDAS DE FUNCOES, jamais fixtures prontas de output.
"""
from __future__ import annotations

from datetime import date
from hashlib import sha256
from io import BytesIO
from unittest import TestCase
from unittest.mock import patch
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pypdf import PdfWriter, PdfReader
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from app.database import Base
from app.models import (Plano, User, Empresa, DocumentoFiscal, ItemFiscal,
                        RelatorioAnalise, UsoPlataforma, TabelaMVA, TabelaPMPF, AlertaFiscal)
from app.services import registro_analise_service as registro

_CNPJ = "12345678000190"  # exclusivamente sintético
_KEY = "1" * 44
_URL = "https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/sintetico_b01.pdf"
_SOURCE = "ATO SINTETICO DE TESTE NAO OFICIAL"


def nfe(*, emitter=_CNPJ, key=_KEY, ncm="12119090", cest="2000100"):
    return f'''<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">
  <NFe><infNFe Id="NFe{key}"><ide><mod>55</mod><tpNF>1</tpNF><finNFe>1</finNFe><idDest>1</idDest>
    <dhEmi>2026-04-01T12:00:00-03:00</dhEmi><nNF>123</nNF></ide>
    <emit><CNPJ>{emitter}</CNPJ><xNome>Empresa Sintetica</xNome><enderEmit><UF>PR</UF></enderEmit></emit>
    <dest><enderDest><UF>PR</UF></enderDest></dest>
    <det nItem="1"><prod><NCM>{ncm}</NCM><CEST>{cest}</CEST><CFOP>5102</CFOP><qCom>1</qCom><vProd>100.00</vProd></prod>
      <imposto><ICMS><ICMS10><orig>0</orig><CST>10</CST><modBCST>4</modBCST><vBC>100.00</vBC>
      <pICMS>18.00</pICMS><vICMS>18.00</vICMS><vBCST>146.78</vBCST><vICMSST>8.42</vICMSST></ICMS10></ICMS></imposto>
    </det><total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
  </infNFe></NFe><protNFe><infProt><chNFe>{key}</chNFe></infProt></protNFe>
</nfeProc>'''.encode('utf-8')


def synthetic_pdf():
    w = PdfWriter()
    w.add_metadata({'/SyntheticBloco01': 'padding' * 200})
    font = w._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    }))
    page = w.add_blank_page(width=595, height=842)
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})
    })
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 40 780 Td '
        b'(1 20.001.00 1211.90.90 Henna 200 g 46, 78 2 20.002.00 2712.10.00 Vaselina) Tj ET')
    page[NameObject('/Contents')] = w._add_object(stream)
    buffer = BytesIO(); w.write(buffer); raw = buffer.getvalue()
    text = PdfReader(BytesIO(raw), strict=True).pages[0].extract_text(extraction_mode='plain')
    start = text.index('20.001.00')
    part = text[start:text.index('20.002.00')]
    excerpt = part[:part.index('46, 78') + len('46, 78')].strip()
    evidence = {
        'versao_id': 'sintetica_v1', 'uf': 'PR', 'ncm': '12119090',
        'cest': '2000100', 'descricao_marcador': 'Henna',
        'source_url': _URL, 'pdf_sha256': sha256(raw).hexdigest(),
        'pagina_1_based': 1,
        'pagina_texto_sha256': sha256(text.encode('utf-8')).hexdigest(),
        'inicio_caracter': start,
        'excerto_sha256': sha256(excerpt.encode('utf-8')).hexdigest(),
        'proximo_cest': '2000200', 'numero_proxima_linha': 2,
        'mva_original_percentual': '46.78',
        'vigencia_inicio_declarada': '2026-04-01',
        'vigencia_fim_declarada': None,
        'observacao_inicio': '2026-04-01',
        'observacao_fim': '2026-04-01',
        'dispositivo_declarado': 'ARTIGO SINTETICO - NAO OFICIAL',
    }
    return raw, evidence


def candidate(pdf_sha):
    return {
        'indice_item': 1, 'uf': 'PR', 'ncm': '12119090',
        'cest': '2000100', 'cfop': '5102', 'cst': '10', 'regime': 'real',
        'operacao': 'saida_interna', 'metodo_base': 'iva_st',
        'vigencia_inicio': '2026-04-01', 'vigencia_fim': None,
        'fonte_legal': _SOURCE, 'url_fonte': _URL,
        'sha256_texto_normativo_declarado': pdf_sha,
        'versao_ato': 'sintetica_v1',
    }


class TestEnterpriseB01SyntheticIntegration(TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        tables = [m.__table__ for m in
                  (Plano, User, Empresa, DocumentoFiscal, ItemFiscal,
                   RelatorioAnalise, UsoPlataforma, TabelaMVA, TabelaPMPF, AlertaFiscal)]
        Base.metadata.create_all(self.engine, tables=tables)  # SOMENTE teste :memory:
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.db.add(User(id=7, email='b01@synthetic.invalid', hashed_password='!'))
        self.db.add(Empresa(id=41, user_id=7, cnpj=_CNPJ,
                            regime_tributario='real', optante_mei=False))
        self.db.add(TabelaMVA(id=92, estado='PR', ncm='12119090', mva=0.4678,
            aliquota_interna=0.18, vigencia_inicio=date(2026, 4, 1),
            vigencia_fim=None, fonte_legal=_SOURCE,
            nivel_confianca_fonte='oficial', url_fonte=_URL,
            importado_por='B01_SYNTHETIC_FIXTURE'))
        self.db.commit()
        self.raw = nfe()
        self.pdf, self.evidence = synthetic_pdf()
        self.kw = dict(db=self.db, xml_bytes=self.raw, authenticated_user_id=7,
                       empresa_id=41, candidatos_normativos=[candidate(sha256(self.pdf).hexdigest())],
                       pdfs_por_url={_URL: self.pdf}, evidencias_por_item={1:[self.evidence]})
        # Apenas servicos complementares de score/insights sao isolados:
        # registro, persistencia, I2, G12, G13, G14, ADR-020, C3-C7 sao REAIS.
        from app.services.insights_engine import InsightEngine
        self.patches = [
            patch.object(InsightEngine, 'gerar_insights_empresa', return_value=None),
            patch.object(registro, 'calcular_score_global_tributario', return_value={}),
        ]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.db.close(); self.engine.dispose()

    def run_circuit(self, **updates):
        params = dict(self.kw); params.update(updates)
        return registro.executar_circuito_enterprise_01(**params)

    def test_01_circuito_real_writer_i2_g12_g14_adr020_c3_c7(self):
        from app.services.resultado_provenance_service import verificar_resultado_persistido
        r = self.run_circuit()
        self.assertEqual(r['uso'], 'INTERNO_NAO_PUBLICAVEL')
        self.assertEqual(r['xml_sha256'], sha256(self.raw).hexdigest())
        self.assertEqual(r['empresa_id'], 41)
        self.assertEqual(r['authenticated_user_id'], 7)
        self.assertEqual(r['itens'][0]['estado'], 'DOSSIER_INTERNO_NAO_PUBLICAVEL')
        self.assertEqual(r['itens'][0]['dossie']['id_registo_l2_observado'], 92)
        self.assertIs(r['itens'][0]['dossie']['comparacoes_monetarias_condicionais']['BASE_ST']['credito_comprovado'], False)
        self.assertIs(r['itens'][0]['dossie']['comparacoes_monetarias_condicionais']['ICMS_ST']['credito_comprovado'], False)
        self.assertIs(r['compatibilidade_g1_apenas_negacao_comercial'], True)
        self.assertTrue(r['g13']['confronto_condicional_g12']['itens'][0]['comparacao_condicional'])
        # Contrato G1 original preservado, sem nenhuma manipulacao dos pares.
        g1 = r['g13']['confronto_condicional_g12']['confronto_g1']
        self.assertNotIn('usavel_comercialmente', g1)
        self.assertEqual({x['tipo'] for x in g1['comparacoes']}, {'BASE_ST','ICMS_ST'})
        self.assertEqual(r['itens'][0]['dossie']['comparacoes_monetarias_condicionais']['BASE_ST']['valor_motor_condicional'],
                         next(x['valor_motor'] for x in g1['comparacoes'] if x['tipo']=='BASE_ST'))
        self.assertEqual(len(r['i0']['cobertura']), 52)
        self.assertEqual(sum(x['estado']=='nao_integrado_ao_snapshot'
                             for x in r['i0']['cobertura']), 33)
        self.assertFalse(r['autoridade_fiscal'])
        self.assertFalse(r['credito_confirmado'])
        self.assertFalse(r['checkout_autorizado'])
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 1)
        self.assertEqual(self.db.query(ItemFiscal).count(), 1)
        rel = self.db.get(RelatorioAnalise, r['relatorio_id'])
        self.assertEqual(verificar_resultado_persistido(rel)['empresa_id'], 41)
        self.assertEqual(rel.fingerprint, r['resultado_fingerprint'])
        print('SOLVERIS_B01_REAL_SYNTHETIC_DOCUMENT_PERSISTENCE_I2_G12_G14_G17_C3_C7_PASS')

    def test_02_identidade_divergente_rejeitada_antes_da_escrita(self):
        with self.assertRaisesRegex(ValueError, 'B01_SUJEITO_NAO_AUTORIZADO'):
            self.run_circuit(authenticated_user_id=999)
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 0)

    def test_03_xml_estrutural_invalido_rejeitado_antes_da_escrita(self):
        with self.assertRaisesRegex(ValueError, 'B01_XML_INVALIDO'):
            self.run_circuit(xml_bytes=b'<NFe><broken>')
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 0)

    def test_04_regra_l2_ausente_abstencao_sem_credito(self):
        self.db.query(TabelaMVA).delete(); self.db.commit()
        r = self.run_circuit()
        self.assertEqual(r['itens'][0]['estado'], 'ABSTENCAO')
        self.assertFalse(r['credito_confirmado'])
        self.assertFalse(r['checkout_autorizado'])

    def test_05_dependencia_c3_falha_fecha_circuito(self):
        damaged = self.pdf + b'!'
        with self.assertRaises(Exception):
            self.run_circuit(pdfs_por_url={_URL:damaged})

    def test_06_sem_manifesto_normativo_abstencao_sem_inventar_c7(self):
        r = self.run_circuit(pdfs_por_url=None, evidencias_por_item=None,
                             candidatos_normativos=None)
        self.assertEqual(r['itens'][0]['estado'], 'ABSTENCAO')
        self.assertIsNone(r['itens'][0]['dossie'])
        self.assertFalse(r['adr020_g17']['autoridade_fiscal'])

    def test_07_sqlite_em_disco_proibida(self):
        from types import SimpleNamespace
        simulated_disk = SimpleNamespace(get_bind=lambda: SimpleNamespace(
            dialect=SimpleNamespace(name='sqlite'),
            url=SimpleNamespace(database='forbidden.sqlite')))
        with self.assertRaisesRegex(ValueError, 'B01_APENAS_SQLITE_EM_MEMORIA'):
            self.run_circuit(db=simulated_disk)
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 0)

    def test_08_duplicado_nao_pode_virar_nova_prova(self):
        self.run_circuit()
        with self.assertRaisesRegex(ValueError, 'B01_RELATORIO_NAO_ELEGIVEL'):
            self.run_circuit()

    def test_09_sem_injecao_de_autoridade_nao_autorizada(self):
        r = self.run_circuit()
        for k in ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente'):
            self.assertIs(r[k], False)
        for stage in ('g13','g14','adr020_g17'):
            for k in ('autoridade_fiscal','credito_confirmado','checkout_autorizado'):
                self.assertIs(r[stage][k], False)

    def test_10_falha_dependencia_adr020_nao_cria_resultado_c7(self):
        with patch('app.services.enterprise_g17_publication_coverage_checkpoint.cotejar_cobertura_publicacao_g17',
                   side_effect=RuntimeError('B01_DEPENDENCIA_TESTE_INDISPONIVEL')):
            with self.assertRaisesRegex(RuntimeError, 'B01_DEPENDENCIA_TESTE_INDISPONIVEL'):
                self.run_circuit()


    def test_11_cnpj_xml_estranho_rejeitado_antes_de_persistir(self):
        with self.assertRaisesRegex(ValueError, 'B01_XML_SUJEITO_OU_CHAVE_DIVERGENTE'):
            self.run_circuit(xml_bytes=nfe(emitter='99999999000199'))
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 0)

    def test_12_chave_invalida_rejeitada_antes_de_persistir(self):
        with self.assertRaisesRegex(ValueError, 'B01_XML_SUJEITO_OU_CHAVE_DIVERGENTE'):
            self.run_circuit(xml_bytes=nfe(key='123'))
        self.assertEqual(self.db.query(DocumentoFiscal).count(), 0)
