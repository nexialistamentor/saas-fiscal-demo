"""G1.8 RED/GREEN: no network/DB connection, file writes, or commercial trust."""
import hashlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.enterprise_g18_external_publication import (
    SCHEMA, MAX_PDF, EnterpriseG18GateError, observar_pdf_publicacao_g18,
    cotejar_evidencia_externa_publicacao_g18,
)

PDF = b'%PDF-1.7\n' + b'X' * 1024
H = lambda v: hashlib.sha256(v).hexdigest()
URL = 'https://www.ioepa.com.br/arquivos/2026/2026.02.23.DOE.pdf'
XML = b'<NFe><infNFe>synthetic</infNFe></NFe>'
ZERO = '0' * 64
HASH = H(PDF)
FORBIDDEN = (
    'fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente',
)


def evidence(index=1, **changes):
    e = dict(indice_item=index, normative_artifact_id='artifact',
             artifact_reference_record_id='ref', url_publicacao=URL,
             sha256_publicacao=HASH, pdf_bytes=PDF)
    e.update(changes)
    return e


def g17(items=1, linked=True):
    lines = [dict(indice_item=i,
                  janela_administrativa_cotejada=linked,
                  fonte_primaria_autenticada=False,
                  edicao_oficial_assinatura_validada=False,
                  vigencia_juridica_comprovada=False) for i in range(1, items+1)]
    result = dict(schema_version='SOLVERIS_ENTERPRISE_G17_BOUNDED_COVERAGE_V1',
                  empresa_id=2, relatorio_id=3, documento_id=4,
                  xml_sha256=H(XML), posse_documental_interna_g16=True,
                  itens=lines, itens_total=items)
    result.update({key: False for key in FORBIDDEN})
    return result


class FakeDB:
    def __init__(self, models):
        self.writes = 0
        self.reads = 0
        self.rows = {
            (models.NormativeArtifact, 'artifact'):
                SimpleNamespace(normative_artifact_id='artifact', artifact_reference_id='reference',
                                artifact_hash=HASH, byte_size=len(PDF), immutable_bytes=PDF,
                                immutable_location=None, record_hash=ZERO),
            (models.ArtifactReference, 'ref'):
                SimpleNamespace(artifact_reference_record_id='ref',
                                artifact_reference_id='reference', reference_event='resolvida',
                                exact_locator=URL, record_hash=ZERO),
        }

    def get(self, model, key):
        self.reads += 1
        return self.rows.get((model, key))


class G18(unittest.TestCase):
    def setUp(self):
        self.models = types.ModuleType('app.models')
        self.models.NormativeArtifact = type('NormativeArtifact', (), {})
        self.models.ArtifactReference = type('ArtifactReference', (), {})
        self.external = types.ModuleType('app.services.enterprise_g17_publication_coverage_checkpoint')
        self.up = g17()
        self.calls = []
        def upstream(**kwargs):
            self.calls.append(kwargs)
            return self.up
        self.external.cotejar_cobertura_publicacao_g17 = upstream
        self.fake_modules = patch.dict(sys.modules, {
            'app.models': self.models,
            'app.services.enterprise_g17_publication_coverage_checkpoint': self.external,
        })
        self.fake_modules.start()
        self.addCleanup(self.fake_modules.stop)
        self.db = FakeDB(self.models)
        self.cover = [dict(indice_item=1, normative_artifact_id='artifact',
                           artifact_reference_record_id='ref')]

    def call(self, entries=None, **changes):
        p = dict(db=self.db, authenticated_user_id=1, empresa_id=2,
                 relatorio_id=3, xml_bytes=XML, referencias_cobertura=self.cover,
                 evidencias_externas=[evidence()] if entries is None else entries)
        p.update(changes)
        return cotejar_evidencia_externa_publicacao_g18(**p)

    def fail(self, entries=None, **changes):
        with self.assertRaises(EnterpriseG18GateError):
            self.call(entries, **changes)

    def blocked(self, result):
        for f in FORBIDDEN:
            self.assertIs(result[f], False, f)
        for item in result.get('itens', []):
            self.assertIs(item['fonte_primaria_autenticada'], False)
            self.assertIs(item['edicao_oficial_assinatura_validada'], False)
            self.assertIs(item['vigencia_juridica_comprovada'], False)

    def test_01_observe_real_pilot_shape_without_trust(self):
        r = observar_pdf_publicacao_g18(pdf_bytes=PDF, url_publicacao=URL, sha256_publicacao=HASH)
        self.assertEqual(r['schema_version'], SCHEMA)
        self.assertTrue(r['pdf_bytes_recalculados'])
        self.assertFalse(r['vinculo_adr020'])
        self.blocked(r)

    def test_02_observe_hash_mismatch_stop(self):
        with self.assertRaises(EnterpriseG18GateError):
            observar_pdf_publicacao_g18(pdf_bytes=PDF, url_publicacao=URL, sha256_publicacao=ZERO)

    def test_03_observe_not_pdf_stop(self):
        with self.assertRaises(EnterpriseG18GateError):
            observar_pdf_publicacao_g18(pdf_bytes=b'X'*len(PDF), url_publicacao=URL, sha256_publicacao=H(b'X'*len(PDF)))

    def test_04_observe_wrong_scheme_stop(self):
        with self.assertRaises(EnterpriseG18GateError):
            observar_pdf_publicacao_g18(pdf_bytes=PDF, url_publicacao=URL.replace('https:', 'http:'), sha256_publicacao=HASH)

    def test_05_observe_oversized_stop(self):
        with self.assertRaises(EnterpriseG18GateError):
            observar_pdf_publicacao_g18(pdf_bytes=b'%PDF-' + b'0'*MAX_PDF, url_publicacao=URL, sha256_publicacao=HASH)

    def test_06_bound_readonly(self):
        r = self.call()
        self.assertEqual(r['itens_hash_externo_cotejado'], 1)
        self.assertEqual(r['itens'][0]['estado'], 'HASH_PDF_ADR020_COTEJADO_SEM_AUTORIDADE')
        self.assertTrue(r['itens'][0]['vinculo_hash_adr020'])
        self.assertFalse(r['itens'][0]['custodia_externa_revalidada'])
        self.assertGreater(self.db.reads, 0)
        self.assertEqual(self.db.writes, 0)
        self.blocked(r)

    def test_07_no_evidence_no_reads(self):
        r=self.call([])
        self.assertEqual(r['itens_hash_externo_cotejado'],0)
        self.assertEqual(self.db.reads,0)
        self.blocked(r)

    def test_08_partial_window_no_reads(self):
        self.up=g17(linked=False)
        r=self.call()
        self.assertEqual(r['itens'][0]['motivo'],'G17_JANELA_NAO_COTEJADA')
        self.assertEqual(self.db.reads,0)
        self.blocked(r)

    def test_09_untrusted_g17_flag_stop(self):
        self.up['checkout_autorizado']=True
        self.fail()

    def test_10_wrong_g17_schema_stop(self):
        self.up['schema_version']='OTHER'
        self.fail()

    def test_11_wrong_g17_digest_stop(self):
        self.up['xml_sha256']=ZERO
        self.fail()

    def test_12_g17_boolean_count_stop(self):
        self.up['itens_total']=True
        self.fail()

    def test_13_g17_item_true_source_stop(self):
        self.up['itens'][0]['fonte_primaria_autenticada']=True
        self.fail()

    def test_14_g17_exception_stop(self):
        self.external.cotejar_cobertura_publicacao_g17=lambda **kw: 1/0
        self.fail()

    def test_15_invalid_identity_bool_stop(self):
        self.fail(authenticated_user_id=True)

    def test_16_invalid_xml_stop(self):
        self.fail(xml_bytes='XML')

    def test_17_duplicate_index_stop(self):
        self.fail([evidence(),evidence()])

    def test_18_extra_field_stop(self):
        self.fail([evidence(fonte_primaria_autenticada=True)])

    def test_19_index_outside_g17_stop(self):
        self.fail([evidence(index=2)])

    def test_20_bool_index_stop(self):
        self.fail([evidence(index=True)])

    def test_21_fake_hash_stop_before_g17(self):
        self.fail([evidence(sha256_publicacao=ZERO)])
        self.assertEqual(len(self.calls),0)

    def test_22_source_locator_mismatch_no_link(self):
        row=self.db.rows[(self.models.ArtifactReference,'ref')]
        row.exact_locator='https://other.example/document.pdf'
        r=self.call()
        self.assertEqual(r['itens_hash_externo_cotejado'],0)
        self.assertEqual(r['itens'][0]['motivo'],'REGISTO_ADR020_OU_DIGEST_DIVERGENTE')
        self.blocked(r)

    def test_23_cross_artifact_mismatch_no_link(self):
        self.cover[0]['normative_artifact_id']='other'
        r=self.call()
        self.assertEqual(r['itens'][0]['motivo'],'REFERENCIA_G17_DIVERGENTE')
        self.assertEqual(self.db.reads,0)

    def test_24_db_hash_mismatch_no_link(self):
        self.db.rows[(self.models.NormativeArtifact,'artifact')].artifact_hash=ZERO
        r=self.call()
        self.assertEqual(r['itens_hash_externo_cotejado'],0)
        self.blocked(r)

    def test_25_db_bytes_mismatch_no_link(self):
        self.db.rows[(self.models.NormativeArtifact,'artifact')].immutable_bytes=b'x'*len(PDF)
        r=self.call()
        self.assertEqual(r['itens'][0]['motivo'],'BYTES_ADR020_DIVERGENTES')
        self.blocked(r)

    def test_26_db_reference_missing_no_link(self):
        self.db.rows.pop((self.models.ArtifactReference,'ref'))
        r=self.call()
        self.assertEqual(r['itens'][0]['motivo'],'REGISTO_ADR020_AUSENTE')
        self.blocked(r)

    def test_27_location_only_hash_link_custody_false(self):
        art=self.db.rows[(self.models.NormativeArtifact,'artifact')]
        art.immutable_bytes=None
        art.immutable_location='cas:sha256:' + HASH
        r=self.call()
        self.assertEqual(r['itens_hash_externo_cotejado'],1)
        self.assertFalse(r['itens'][0]['custodia_externa_revalidada'])
        self.blocked(r)

    def test_28_inconsistent_both_storage_blocks(self):
        art=self.db.rows[(self.models.NormativeArtifact,'artifact')]
        art.immutable_location='cas:sha256:' + HASH
        r=self.call()
        self.assertEqual(r['itens'][0]['motivo'],'ARMAZENAMENTO_ADR020_INVALIDO')

    def test_29_wrong_db_length_blocks(self):
        self.db.rows[(self.models.NormativeArtifact,'artifact')].byte_size=len(PDF)+1
        r=self.call()
        self.assertEqual(r['itens_hash_externo_cotejado'],0)

    def test_30_multi_item_partial(self):
        self.up=g17(items=2)
        r=self.call()
        self.assertEqual(r['itens_total'],2)
        self.assertEqual(r['itens_hash_externo_cotejado'],1)
        self.assertEqual(r['estado'],'COBERTURA_EXTERNA_PARCIAL_SEM_AUTORIDADE')
        self.blocked(r)

    def test_31_g17_receives_exact_same_context(self):
        self.call()
        self.assertEqual(len(self.calls),1)
        self.assertIs(self.calls[0]['db'],self.db)
        self.assertEqual(self.calls[0]['xml_bytes'],XML)
        self.assertIs(self.calls[0]['referencias_cobertura'],self.cover)

    def test_32_no_sensitive_xml_or_pdf_in_output(self):
        r=self.call()
        self.assertNotIn('synthetic',str(r))
        self.assertNotIn('immutable_bytes',str(r))
        self.assertNotIn('pdf_bytes',str(r))

    def test_33_url_credentials_forbidden(self):
        self.fail([evidence(url_publicacao='https://user:pass@www.ioepa.com.br/foo.pdf')])

    def test_34_future_digest_not_crypto_trust(self):
        r=self.call()
        self.assertFalse(r['autoridade_fiscal'])
        self.assertFalse(r['itens'][0]['assinatura_cms_verificada_neste_servico'])
        self.assertFalse(r['itens'][0]['revogacao_historica_comprovada'])

    def test_35_evidence_limit(self):
        self.fail([evidence(index=i) for i in range(1,34)])

if __name__ == '__main__': unittest.main()
