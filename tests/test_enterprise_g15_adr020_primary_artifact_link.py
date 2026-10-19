"""G1.5: 28 testes sintéticos puros, nenhum dado real, DB ou rede."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace as S
from unittest.mock import patch
import sys
import unittest

TARGET = Path(os.environ.get('SOLVERIS_G15_MODULE_PATH',str(Path(__file__).resolve().parents[1]/'app/services/enterprise_g15_adr020_primary_artifact_link.py')))
app=ModuleType('app');app.__path__=[]
serv=ModuleType('app.services');serv.__path__=[]
models=ModuleType('app.models')
g14mod=ModuleType('app.services.enterprise_g14_operational_normative_scope')
class ArtifactReference:pass
class AcquisitionExecution:pass
class NormativeArtifact:pass
class ArtifactVerificationRecord:pass
models.ArtifactReference=ArtifactReference
models.AcquisitionExecution=AcquisitionExecution
models.NormativeArtifact=NormativeArtifact
models.ArtifactVerificationRecord=ArtifactVerificationRecord
g14mod.cotejar_enquadramento_normativo_operacao_g14=lambda **kwargs:None
with patch.dict(sys.modules,{'app':app,'app.services':serv,'app.models':models,
                             'app.services.enterprise_g14_operational_normative_scope':g14mod}):
    spec=importlib.util.spec_from_file_location('_g15_target',TARGET)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

RAW=b'<ato>FONTE SINTETICA - NAO OFICIAL</ato>'
HASH=sha256(RAW).hexdigest()
XML=b'<xml-sintetico sem dados empresariais/>'
XHASH=sha256(XML).hexdigest()

def link(index=1):
    return {'indice_item':index,'artifact_reference_record_id':f'ref-{index}',
            'acquisition_execution_record_id':f'exec-{index}',
            'normative_artifact_id':f'art-{index}',
            'authenticity_verification_record_id':f'auth-{index}',
            'integrity_verification_record_id':f'integ-{index}',
            'preservation_verification_record_id':f'pres-{index}'}

def g14(n=1):
    return {'schema_version':'SOLVERIS_ENTERPRISE_G14_OPERATIONAL_NORMATIVE_SCOPE_V1',
            'empresa_id':8,'relatorio_id':7,'documento_id':6,'xml_sha256':XHASH,
            'posse_e_proveniencia_interna_g13':True,'itens_total':n,
            'itens':[{'indice_item':i,'ncm':'10019010','cest_observado':'0100100',
                     'estado':'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
                     'url_fonte_candidata':'https://exemplo.invalid/ato',
                     'fonte_legal_candidata':'ATO SINTETICO',
                     'sha256_texto_normativo_declarado':HASH} for i in range(1,n+1)],
            **{x:False for x in m._FLAGS}}

def rows(index=1):
    L=link(index)
    ref=S(artifact_reference_record_id=L['artifact_reference_record_id'],
          artifact_reference_id=f'group-{index}',reference_event='resolvida',
          source_id='SINTETICO-SEM-TRUST',
          exact_locator='https://exemplo.invalid/ato',official_identifier='ATO SINTETICO',record_hash='a'*64)
    ex=S(acquisition_execution_record_id=L['acquisition_execution_record_id'],
         artifact_reference_record_id=ref.artifact_reference_record_id,
         artifact_reference_id=ref.artifact_reference_id,
         acquisition_execution_id=f'att-{index}',attempt_number=1,
         execution_event='conclusao',projected_state='concluida',record_hash='b'*64)
    ar=S(normative_artifact_id=L['normative_artifact_id'],artifact_reference_id=ref.artifact_reference_id,
         acquisition_execution_record_id=ex.acquisition_execution_record_id,
         acquisition_execution_id=ex.acquisition_execution_id,acquisition_attempt_number=ex.attempt_number,
         acquisition_event='conclusao',acquisition_state='concluida',immutable_bytes=RAW,
         immutable_location=None,artifact_hash=HASH,byte_size=len(RAW),record_hash='c'*64)
    def ver(which,vtype,char):
        return S(artifact_verification_record_id=L[which],normative_artifact_id=ar.normative_artifact_id,
                 verified_artifact_hash=HASH,verification_type=vtype,outcome='conclusivo_favoravel',
                 incident_id=None,record_hash=char*64,authenticity_verification_record_id=None,
                 authenticity_predecessor_type=None,authenticity_predecessor_outcome=None,
                 integrity_verification_record_id=None,integrity_predecessor_type=None,
                 integrity_predecessor_outcome=None)
    auth=ver('authenticity_verification_record_id','authenticity','d')
    integ=ver('integrity_verification_record_id','integrity','e')
    integ.authenticity_verification_record_id=auth.artifact_verification_record_id
    integ.authenticity_predecessor_type='authenticity'
    integ.authenticity_predecessor_outcome='conclusivo_favoravel'
    pres=ver('preservation_verification_record_id','preservation','f')
    pres.authenticity_verification_record_id=auth.artifact_verification_record_id
    pres.integrity_verification_record_id=integ.artifact_verification_record_id
    pres.authenticity_predecessor_type='authenticity'
    pres.integrity_predecessor_type='integrity'
    pres.authenticity_predecessor_outcome='conclusivo_favoravel'
    pres.integrity_predecessor_outcome='conclusivo_favoravel'
    return {(ArtifactReference,L['artifact_reference_record_id']):ref,
            (AcquisitionExecution,L['acquisition_execution_record_id']):ex,
            (NormativeArtifact,L['normative_artifact_id']):ar,
            (ArtifactVerificationRecord,L['authenticity_verification_record_id']):auth,
            (ArtifactVerificationRecord,L['integrity_verification_record_id']):integ,
            (ArtifactVerificationRecord,L['preservation_verification_record_id']):pres}

class FakeDB:
    def __init__(self,records): self.records=records;self.reads=0;self.writes=0
    def get(self,t,k): self.reads+=1;return self.records.get((t,k))
    def add(self,*a):self.writes+=1;raise AssertionError('NO_DB_WRITE')
    def commit(self):self.writes+=1;raise AssertionError('NO_DB_COMMIT')

class G15(unittest.TestCase):
    def setUp(self):
        self.record_map=rows()
        self.db=FakeDB(self.record_map)
        self.projection=g14()
        self.bridge=patch.object(m,'cotejar_enquadramento_normativo_operacao_g14',side_effect=lambda **kw:self.projection)
        self.bridge.start();self.addCleanup(self.bridge.stop)
    def run_case(self,**kw):
        a={'db':self.db,'authenticated_user_id':9,'empresa_id':8,'relatorio_id':7,
           'xml_bytes':XML,'candidatos_normativos':[], 'referencias_adr020':[link()]}
        a.update(kw)
        return m.cotejar_artefacto_primario_g15(**a)
    def assert_blocked(self,r):
        self.assertFalse(r['fonte_primaria_autenticada']);self.assertFalse(r['checkout_autorizado'])
        self.assertFalse(r['credito_confirmado']);self.assertFalse(r['autoridade_fiscal'])
        self.assertFalse(r['versao_oficial_verificada'])
        self.assertEqual(self.db.writes,0)
    def row(self,t,k):return self.record_map[(t,k)]
    def test_01_cadeia_interna_sintetica_cotejada(self):
        r=self.run_case();self.assertEqual(r['itens_com_cadeia_interna'],1);self.assert_blocked(r)
    def test_02_nao_promove_legal_por_tres_estados_favoraveis(self):
        r=self.run_case();self.assertEqual(r['itens'][0]['estado'],'ARTEFACTO_INTERNO_COTEJADO_SEM_AUTORIDADE');self.assert_blocked(r)
    def test_03_nao_coteja_sem_evidencia(self):
        r=self.run_case(referencias_adr020=None);self.assertEqual(r['itens_com_cadeia_interna'],0);self.assertEqual(self.db.reads,0)
    def test_04_g14_bloqueia_antes_da_bd(self):
        with patch.object(m,'cotejar_enquadramento_normativo_operacao_g14',side_effect=ValueError('bad')):
            with self.assertRaises(m.EnterpriseG15GateError):self.run_case()
        self.assertEqual(self.db.reads,0)
    def test_05_g14_hash_xml_divergente(self):
        self.projection['xml_sha256']='1'*64
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case()
    def test_06_g14_fonte_trust_fabricada(self):
        self.projection['fonte_primaria_autenticada']=True
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case()
    def test_07_documento_alheio(self):
        self.projection['empresa_id']=999
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case()
    def test_08_referencia_duplicada_recusada(self):
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case(referencias_adr020=[link(),link()])
    def test_09_referencia_extra_recusada(self):
        l=link();l['trust']=True
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case(referencias_adr020=[l])
    def test_10_referencia_item_nao_existente(self):
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case(referencias_adr020=[link(2)])
    def test_11_missing_row(self):
        self.record_map.pop((NormativeArtifact,'art-1'))
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_12_source_wrong_url(self):
        self.row(ArtifactReference,'ref-1').exact_locator='https://evil.invalid/x'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_13_source_wrong_identifier(self):
        self.row(ArtifactReference,'ref-1').official_identifier='outro'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_14_reference_not_resolved(self):
        self.row(ArtifactReference,'ref-1').reference_event='identificada'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_15_acquisition_not_complete(self):
        self.row(AcquisitionExecution,'exec-1').projected_state='concluida_parcial'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_16_acquisition_reference_different(self):
        self.row(AcquisitionExecution,'exec-1').artifact_reference_record_id='wrong'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_17_artifact_execution_different(self):
        self.row(NormativeArtifact,'art-1').acquisition_execution_record_id='other'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_18_artifact_wrong_bytes_hash(self):
        self.row(NormativeArtifact,'art-1').immutable_bytes=b'CHANGED'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_19_candidate_digest_different(self):
        self.projection['itens'][0]['sha256_texto_normativo_declarado']='0'*64
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_20_artifact_only_cas_location(self):
        a=self.row(NormativeArtifact,'art-1');a.immutable_bytes=None;a.immutable_location='sha256:'+HASH
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_21_artifact_bad_byte_size(self):
        self.row(NormativeArtifact,'art-1').byte_size+=1
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_22_auth_unfavorable(self):
        self.row(ArtifactVerificationRecord,'auth-1').outcome='inconclusivo'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_23_integrity_unfavorable(self):
        self.row(ArtifactVerificationRecord,'integ-1').outcome='conclusivo_desfavoravel'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_24_preservation_unfavorable(self):
        self.row(ArtifactVerificationRecord,'pres-1').outcome='inconclusivo'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_25_verification_cross_artifact(self):
        self.row(ArtifactVerificationRecord,'integ-1').normative_artifact_id='art-2'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_26_wrong_predecessor(self):
        self.row(ArtifactVerificationRecord,'pres-1').integrity_verification_record_id='integ-2'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_27_incident_blocks(self):
        self.row(ArtifactVerificationRecord,'auth-1').incident_id='incident-1'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_28_two_items_one_proven_partial(self):
        self.projection=g14(2)
        r=self.run_case();self.assertEqual(r['estado'],'COBERTURA_ADR020_PARCIAL_SEM_AUTORIDADE')
        self.assertEqual(r['itens_com_cadeia_interna'],1);self.assert_blocked(r)
    def test_29_uncotejado_g14_never_reads_records(self):
        self.projection['itens'][0]['estado']='LACUNA_CANDIDATO_NORMATIVO'
        r=self.run_case();self.assertEqual(self.db.reads,0);self.assertEqual(r['itens_com_cadeia_interna'],0)
    def test_30_invalid_input_no_g14(self):
        with patch.object(m,'cotejar_enquadramento_normativo_operacao_g14',side_effect=AssertionError('CALLED')):
            with self.assertRaises(m.EnterpriseG15GateError):self.run_case(xml_bytes='texto')
    def test_31_ref_boolean_index_denied(self):
        l=link();l['indice_item']=True
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case(referencias_adr020=[l])
    def test_33_verification_primary_key_forged(self):
        self.row(ArtifactVerificationRecord,'auth-1').artifact_verification_record_id='auth-other'
        self.assertEqual(self.run_case()['itens_com_cadeia_interna'],0)
    def test_34_g14_boolean_total_not_accepted(self):
        self.projection['itens_total']=True
        with self.assertRaises(m.EnterpriseG15GateError):self.run_case()
    def test_32_output_never_leaks_legal_bytes(self):
        r=self.run_case();self.assertNotIn(RAW.decode(),str(r));self.assertNotIn('xml-sintetico',str(r))

if __name__=='__main__':unittest.main()
