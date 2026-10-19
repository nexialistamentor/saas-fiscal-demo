"""Enterprise G17: bounded synthetic coverage gates, fake database only."""
from __future__ import annotations
import hashlib
import importlib.util
import os
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace as S
from unittest.mock import patch
import sys
import unittest

PATH=Path(os.environ.get('SOLVERIS_G17_MODULE_PATH',str(Path(__file__).resolve().parents[1]/'app/services/enterprise_g17_publication_coverage_checkpoint.py')))
app=ModuleType('app');app.__path__=[]
serv=ModuleType('app.services');serv.__path__=[]
models=ModuleType('app.models')
g16mod=ModuleType('app.services.enterprise_g16_temporal_rule_chain')
class ArtifactReference:pass
class NormativeArtifact:pass
class ExtractionResult:pass
class RuleVersion:pass
class CoverageContract:pass
class CoverageCheckpointRecord:pass
class CoverageLedgerEntry:pass
for C in (ArtifactReference,NormativeArtifact,ExtractionResult,RuleVersion,CoverageContract,CoverageCheckpointRecord,CoverageLedgerEntry):setattr(models,C.__name__,C)
g16mod.cotejar_ciclo_normativo_g16=lambda **kwargs:None
with patch.dict(sys.modules,{'app':app,'app.services':serv,'app.models':models,
         'app.services.enterprise_g16_temporal_rule_chain':g16mod}):
    spec=importlib.util.spec_from_file_location('_g17_test',PATH)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

XML=b'<nfe synthetic="yes"/>'
XHASH=hashlib.sha256(XML).hexdigest()
H=lambda c:c*64
S0=datetime(2026,9,1,tzinfo=timezone.utc)
S1=datetime(2026,10,1,tzinfo=timezone.utc)

def g16(*,count=1):
    return {'schema_version':m._G16_SCHEMA,'empresa_id':8,'relatorio_id':7,'documento_id':6,
      'xml_sha256':XHASH,'posse_documental_interna_g15':True,
      'data_operacao_observada':'2026-09-12','itens_total':count,
      'itens':[{'indice_item':i,'estado':'CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE',
          'regra_interna_cotejada':True,'rule_id':'rule-1','rule_version':1,
          'rule_hash':H('b'),'fonte_oficial_autenticada':False,
          'cobertura_publicacoes_completa':False,'vigencia_juridica_comprovada':False,
          'ausencia_revogacao_comprovada':False} for i in range(1,count+1)],
      **{flag:False for flag in m._FORBIDDEN}}

def link(index=1, units=2):
    return {'indice_item':index,'rule_version_record_id':'rule-record',
      'extraction_result_id':'extract','normative_artifact_id':'artifact',
      'artifact_reference_record_id':'reference','coverage_contract_record_id':'contract',
      'coverage_checkpoint_record_id':'checkpoint',
      'coverage_ledger_entry_ids':[f'ledger-{i}' for i in range(1,units+1)]}

def records():
    rule=S(rule_version_record_id='rule-record',rule_id='rule-1',rule_version=1,
       rule_hash=H('b'),record_hash=H('c'),extraction_result_id='extract',
       extraction_result_record_hash=H('d'))
    ext=S(extraction_result_id='extract',normative_artifact_id='artifact',
       artifact_hash=H('e'),record_hash=H('d'))
    art=S(normative_artifact_id='artifact',artifact_hash=H('e'),
          artifact_reference_id='refgroup')
    ref=S(artifact_reference_record_id='reference',artifact_reference_id='refgroup',
         reference_event='resolvida',source_id='PA-DOE')
    contract=S(coverage_contract_record_id='contract',coverage_contract_id='cont-1',
       contract_version=1,contract_hash=H('f'),record_hash=H('0'),
       contract_state='ratificada',source_id='PA-DOE',effective_from=S0,effective_to=S1)
    checkpoint=S(coverage_checkpoint_record_id='checkpoint',coverage_contract_id='cont-1',
       contract_version=1,contract_hash=H('f'),record_hash=H('1'),
       checkpoint_sequence=1,cycle_fully_evaluated=True,pending_gap_from=None,
       covered_through=2,completed_through=2,observed_through=2,
       window_start=S0,window_end=S1,last_ledger_entry_id='ledger-2')
    a={}
    for i in (1,2):
        a[(CoverageLedgerEntry,f'ledger-{i}')]=S(coverage_ledger_entry_id=f'ledger-{i}',
            coverage_contract_id='cont-1',contract_version=1,contract_hash=H('f'),
            record_hash=H(str(i+1)),window_start=S0,window_end=S1,
            unit_order=i,coverage_outcome='covered',observation_outcome='observed',
            processing_outcome='succeeded',response_kind='non_empty',cycle_fully_evaluated=True)
    a.update({(RuleVersion,'rule-record'):rule,(ExtractionResult,'extract'):ext,
       (NormativeArtifact,'artifact'):art,(ArtifactReference,'reference'):ref,
       (CoverageContract,'contract'):contract,
       (CoverageCheckpointRecord,'checkpoint'):checkpoint})
    return a

class FakeDB:
    def __init__(self):self.rows=records();self.reads=0;self.writes=0
    def get(self,cls,key):self.reads+=1;return self.rows.get((cls,key))
    def add(self,*args):self.writes+=1;raise AssertionError('WRITE')
    def commit(self,*args):self.writes+=1;raise AssertionError('COMMIT')
    def query(self,*args):self.writes+=1;raise AssertionError('QUERY_NOT_ALLOWED')

class G17(unittest.TestCase):
    def setUp(self):
        self.db=FakeDB();self.up=g16()
        patcher=patch.object(m,'cotejar_ciclo_normativo_g16',side_effect=lambda **kw:self.up)
        patcher.start();self.addCleanup(patcher.stop)
    def call(self,**kw):
        args={'db':self.db,'authenticated_user_id':9,'empresa_id':8,'relatorio_id':7,
          'xml_bytes':XML,'referencias_cobertura':[link()]}
        args.update(kw)
        return m.cotejar_cobertura_publicacao_g17(**args)
    def blocked(self,r):
        for key in m._FORBIDDEN:
            self.assertIs(r[key],False,key)
        self.assertIs(r['itens'][0]['edicao_oficial_assinatura_validada'],False)
        self.assertFalse(self.db.writes)
    def wrong(self):
        r=self.call();self.assertEqual(r['itens_janela_interna_cotejada'],0);self.blocked(r)
    def stop(self):
        with self.assertRaises(m.EnterpriseG17GateError):self.call()
    def test_01_bounded_window_only(self):
        r=self.call();self.assertEqual(r['itens_janela_interna_cotejada'],1)
        self.assertEqual(r['itens'][0]['unidades_observadas'],2);self.blocked(r)
    def test_02_no_external_authentication(self):
        r=self.call();self.assertFalse(r['fonte_primaria_autenticada']);self.blocked(r)
    def test_03_empty_refs_never_reads(self):
        r=self.call(referencias_cobertura=[]);self.assertEqual(self.db.reads,0);self.blocked(r)
    def test_04_g16_failure_before_read(self):
        with patch.object(m,'cotejar_ciclo_normativo_g16',side_effect=ValueError('failed')):
            self.stop()
        self.assertEqual(self.db.reads,0)
    def test_05_company_mismatch(self):self.up['empresa_id']=99;self.stop()
    def test_06_document_hash_mismatch(self):self.up['xml_sha256']=H('e');self.stop()
    def test_07_fake_authority(self):self.up['autoridade_fiscal']=True;self.stop()
    def test_08_duplicate_ref(self):
        with self.assertRaises(m.EnterpriseG17GateError):self.call(referencias_cobertura=[link(),link()])
    def test_09_extra_ref_field(self):
        x=link();x['trusted']=True
        with self.assertRaises(m.EnterpriseG17GateError):self.call(referencias_cobertura=[x])
    def test_10_outside_item(self):
        with self.assertRaises(m.EnterpriseG17GateError):self.call(referencias_cobertura=[link(2)])
    def test_11_duplicate_ledger(self):
        x=link();x['coverage_ledger_entry_ids']=['ledger-1','ledger-1']
        with self.assertRaises(m.EnterpriseG17GateError):self.call(referencias_cobertura=[x])
    def test_12_bogus_boolean_index(self):
        with self.assertRaises(m.EnterpriseG17GateError):self.call(referencias_cobertura=[link(True)])
    def test_13_bad_rule_origin(self):
        self.db.rows[(RuleVersion,'rule-record')].extraction_result_id='other';self.wrong()
    def test_14_bad_artifact_digest(self):
        self.db.rows[(NormativeArtifact,'artifact')].artifact_hash=H('1');self.wrong()
    def test_15_reference_other_source(self):
        self.db.rows[(ArtifactReference,'reference')].source_id='SP-DOE';self.wrong()
    def test_16_unratified_contract(self):
        self.db.rows[(CoverageContract,'contract')].contract_state='proposta';self.wrong()
    def test_17_expired_contract(self):
        self.db.rows[(CoverageContract,'contract')].effective_to=datetime(2026,9,1,tzinfo=timezone.utc);self.wrong()
    def test_18_naive_contract_date(self):
        self.db.rows[(CoverageContract,'contract')].effective_from=datetime(2026,9,1);self.wrong()
    def test_19_checkpoint_other_contract(self):
        self.db.rows[(CoverageCheckpointRecord,'checkpoint')].coverage_contract_id='other';self.wrong()
    def test_20_checkpoint_gap(self):
        self.db.rows[(CoverageCheckpointRecord,'checkpoint')].pending_gap_from=1;self.wrong()
    def test_21_checkpoint_incomplete(self):
        self.db.rows[(CoverageCheckpointRecord,'checkpoint')].cycle_fully_evaluated=False;self.wrong()
    def test_22_frontier_incomplete(self):
        self.db.rows[(CoverageCheckpointRecord,'checkpoint')].covered_through=1;self.wrong()
    def test_23_window_not_covering_document(self):
        chk=self.db.rows[(CoverageCheckpointRecord,'checkpoint')]
        chk.window_start=datetime(2026,9,15,tzinfo=timezone.utc);self.wrong()
    def test_24_ledger_missing(self):
        self.db.rows.pop((CoverageLedgerEntry,'ledger-2'));self.wrong()
    def test_25_ledger_gap_in_sequence(self):
        self.db.rows[(CoverageLedgerEntry,'ledger-2')].unit_order=9;self.wrong()
    def test_26_unavailable_source(self):
        self.db.rows[(CoverageLedgerEntry,'ledger-2')].observation_outcome='source_unavailable';self.wrong()
    def test_27_not_proven_absence(self):
        self.db.rows[(CoverageLedgerEntry,'ledger-2')].processing_outcome='proven_absence';self.wrong()
    def test_28_last_ledger_wrong(self):
        self.db.rows[(CoverageCheckpointRecord,'checkpoint')].last_ledger_entry_id='ledger-1';self.wrong()
    def test_29_g16_relation_risk_blocks_before_reads(self):
        self.up['itens'][0]['estado']='ALERTA_RELACAO_NORMATIVA_SEM_DECISAO'
        r=self.call();self.assertEqual(self.db.reads,0);self.assertEqual(r['itens_janela_interna_cotejada'],0)
    def test_30_g16_incomplete_blocks_before_reads(self):
        self.up['itens'][0]['regra_interna_cotejada']=False
        r=self.call();self.assertEqual(self.db.reads,0);self.assertEqual(r['itens_janela_interna_cotejada'],0)
    def test_31_multi_item_partial(self):
        self.up=g16(count=2)
        r=self.call();self.assertEqual(r['estado'],'COBERTURA_PARCIAL_NAO_EXAUSTIVA')
        self.assertEqual(r['itens_janela_interna_cotejada'],1);self.blocked(r)
    def test_32_datetime_not_accepted_as_date(self):
        self.up['data_operacao_observada']='2026-09-12T00:00:00'
        self.stop()
    def test_33_binary_xml_only(self):
        with self.assertRaises(m.EnterpriseG17GateError):self.call(xml_bytes='xml')
    def test_34_no_secret_bytes_in_output(self):
        r=self.call();self.assertNotIn('immutable_bytes',str(r));self.assertNotIn('reference_event',str(r))
    def test_35_bool_g16_item_total(self):
        self.up['itens_total']=True;self.stop()
    def test_36_no_stale_checkpoint_trust_claim(self):
        r=self.call();self.assertFalse(r['atualizacao_e_revogacao_exaustivas'])
        self.assertFalse(r['itens'][0]['cobertura_publicacoes_exaustiva'])

    def _align_window(self, *, start=None, end=None):
        chk=self.db.rows[(CoverageCheckpointRecord,'checkpoint')]
        if start is not None: chk.window_start=start
        if end is not None: chk.window_end=end
        for i in (1,2):
            row=self.db.rows[(CoverageLedgerEntry,f'ledger-{i}')]
            if start is not None: row.window_start=start
            if end is not None: row.window_end=end
    def test_37_partial_start_same_date_must_not_count(self):
        self._align_window(start=datetime(2026,9,12,12,0,tzinfo=timezone.utc))
        self.wrong()
    def test_38_partial_end_next_date_must_not_count(self):
        self._align_window(end=datetime(2026,9,13,0,0,tzinfo=timezone.utc))
        self.wrong()
    def test_39_contract_partial_start_same_date_must_not_count(self):
        partial=datetime(2026,9,12,12,0,tzinfo=timezone.utc)
        self.db.rows[(CoverageContract,'contract')].effective_from=partial
        self._align_window(start=partial)
        self.wrong()
    def test_40_contract_partial_end_next_date_must_not_count(self):
        partial=datetime(2026,9,13,0,0,tzinfo=timezone.utc)
        self.db.rows[(CoverageContract,'contract')].effective_to=partial
        self._align_window(end=partial)
        self.wrong()
    def test_41_non_utc_offset_must_be_normalized(self):
        from datetime import timedelta
        tz=timezone(timedelta(hours=-3))
        # Sep 12 00:00 -03 is 03:00Z, missing the start of the guard.
        partial=datetime(2026,9,12,0,0,tzinfo=tz)
        self._align_window(start=partial)
        self.wrong()
    def test_42_full_conservative_utc_bounds_accepted_without_trust(self):
        self._align_window(start=datetime(2026,9,12,0,0,tzinfo=timezone.utc),
            end=datetime(2026,9,13,6,0,tzinfo=timezone.utc))
        r=self.call()
        self.assertEqual(r['itens_janela_interna_cotejada'],1)
        self.blocked(r)

if __name__=='__main__':unittest.main()
