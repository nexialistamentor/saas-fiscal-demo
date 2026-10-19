"""G1.10: CAS PDF (>2 MiB) through actual G15->G16->G17->G18; synthetic-only.

No production database, network, SEFAZ, checkout or official trust. G19 is real,
ADR-020 rows are synthetic objects keyed by *real* SQLAlchemy model classes.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from types import SimpleNamespace as S
from unittest.mock import patch

import pytest

from app import models
from app.services import enterprise_g15_adr020_primary_artifact_link as g15
from app.services import enterprise_g16_temporal_rule_chain as g16
from app.services import enterprise_g17_publication_coverage_checkpoint as g17
from app.services import enterprise_g18_external_publication as g18
from app.services.enterprise_g19_local_cas_custody import (
    PREFIX, guardar_pdf_cas_g19,
)

PDF = b'%PDF-1.7\n' + b'X' * (2764152 - len(b'%PDF-1.7\n'))
DIGEST = hashlib.sha256(PDF).hexdigest()
XML = (b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"><infNFe>'
       b'<ide><dhEmi>2026-09-12T10:00:00-03:00</dhEmi></ide>'
       b'</infNFe></NFe>')
XML_HASH = hashlib.sha256(XML).hexdigest()
URL = 'https://www.ioepa.com.br/arquivos/2026/2026.02.23.DOE.pdf'
H = lambda value: value * 64
DENIED = ('fonte_primaria_autenticada','versao_oficial_verificada',
          'atualizacao_e_revogacao_exaustivas','vigencia_juridica_comprovada',
          'autoridade_fiscal','credito_confirmado','checkout_autorizado',
          'usavel_comercialmente')

class ReadOnlyDB:
    def __init__(self, rows):
        self.rows, self.reads, self.writes = rows, 0, 0
    def get(self, cls, key):
        self.reads += 1
        return self.rows.get((cls, key))
    def add(self, *args, **kwargs):
        self.writes += 1
        raise AssertionError('DB_WRITE_FORBIDDEN')
    def commit(self):
        self.writes += 1
        raise AssertionError('DB_WRITE_FORBIDDEN')
    def query(self, *args):
        raise AssertionError('UNBOUNDED_QUERY_FORBIDDEN')


def fixture_data(root):
    guardar_pdf_cas_g19(root=root, pdf_bytes=PDF, sha256_esperado=DIGEST)
    ref = S(artifact_reference_record_id='ref', artifact_reference_id='refgroup',
            reference_event='resolvida', source_id='PA-DOE', exact_locator=URL,
            official_identifier='ATO SINTETICO', record_hash=H('a'))
    exe = S(acquisition_execution_record_id='exec', artifact_reference_record_id='ref',
            artifact_reference_id='refgroup', acquisition_execution_id='attempt-id',
            attempt_number=1, execution_event='conclusao', projected_state='concluida',
            record_hash=H('b'))
    art = S(normative_artifact_id='art', artifact_reference_id='refgroup',
            acquisition_execution_record_id='exec', acquisition_execution_id='attempt-id',
            acquisition_attempt_number=1, acquisition_event='conclusao',
            acquisition_state='concluida', artifact_hash=DIGEST, byte_size=len(PDF),
            immutable_bytes=None, immutable_location=PREFIX+DIGEST, record_hash=H('c'))
    def ver(id_, kind, c):
        return S(artifact_verification_record_id=id_, normative_artifact_id='art',
                 verified_artifact_hash=DIGEST, verification_type=kind,
                 outcome='conclusivo_favoravel', incident_id=None, record_hash=H(c),
                 authenticity_verification_record_id=None,
                 authenticity_predecessor_type=None,
                 authenticity_predecessor_outcome=None,
                 integrity_verification_record_id=None,
                 integrity_predecessor_type=None,
                 integrity_predecessor_outcome=None)
    auth = ver('auth', 'authenticity', 'd')
    integ = ver('integ', 'integrity', 'e')
    integ.authenticity_verification_record_id = 'auth'
    integ.authenticity_predecessor_type = 'authenticity'
    integ.authenticity_predecessor_outcome = 'conclusivo_favoravel'
    pres = ver('pres', 'preservation', 'f')
    pres.authenticity_verification_record_id = 'auth'
    pres.integrity_verification_record_id = 'integ'
    pres.authenticity_predecessor_type = 'authenticity'
    pres.integrity_predecessor_type = 'integrity'
    pres.authenticity_predecessor_outcome = 'conclusivo_favoravel'
    pres.integrity_predecessor_outcome = 'conclusivo_favoravel'

    extraction = S(extraction_result_id='extraction', normative_artifact_id='art',
                   artifact_hash=DIGEST, outcome='conclusivo', run_event='conclusao',
                   run_state='concluida', record_hash=H('3'), extraction_run_record_id='run')
    run = S(extraction_run_record_id='run', normative_artifact_id='art', artifact_hash=DIGEST,
            run_event='conclusao', projected_state='concluida', record_hash=H('4'))
    rule = S(rule_version_record_id='rule-record', rule_id='rule-1',
             rule_version=1, rule_hash=H('5'), extraction_result_id='extraction',
             extraction_result_record_hash=H('3'), record_hash=H('6'))
    review = S(rule_review_record_id='review', subject_id='rule-1', subject_version=1,
               subject_hash=H('5'), review_event='revisao_concluida', outcome='validada',
               record_hash=H('7'))
    activation = S(normative_activation_id='activation', subject_type='rule_version',
                   subject_id='rule-1', subject_version=1, subject_hash=H('5'),
                   review_record_id='review', review_record_hash=H('7'),
                   state='active', record_hash=H('8'))
    utc = timezone.utc
    begin = datetime(2026, 9, 12, tzinfo=utc)
    end = datetime(2026, 9, 13, 6, tzinfo=utc)
    contract = S(coverage_contract_record_id='contract-record', coverage_contract_id='contract',
                 contract_version=1, contract_hash=H('9'), record_hash=H('a'),
                 contract_state='ratificada', source_id='PA-DOE',
                 effective_from=datetime(2026, 9, 1, tzinfo=utc),
                 effective_to=datetime(2026, 10, 1, tzinfo=utc))
    checkpoint = S(coverage_checkpoint_record_id='checkpoint',
                   coverage_contract_id='contract', contract_version=1,
                   contract_hash=H('9'), record_hash=H('b'), checkpoint_sequence=1,
                   cycle_fully_evaluated=True, pending_gap_from=None,
                   covered_through=2, completed_through=2, observed_through=2,
                   window_start=begin, window_end=end, last_ledger_entry_id='ledger-2')
    rows = {(models.ArtifactReference, 'ref'): ref,
            (models.AcquisitionExecution, 'exec'): exe,
            (models.NormativeArtifact, 'art'): art,
            (models.ArtifactVerificationRecord, 'auth'): auth,
            (models.ArtifactVerificationRecord, 'integ'): integ,
            (models.ArtifactVerificationRecord, 'pres'): pres,
            (models.ExtractionResult, 'extraction'): extraction,
            (models.ExtractionRun, 'run'): run,
            (models.RuleVersion, 'rule-record'): rule,
            (models.RuleReviewRecord, 'review'): review,
            (models.NormativeActivation, 'activation'): activation,
            (models.CoverageContract, 'contract-record'): contract,
            (models.CoverageCheckpointRecord, 'checkpoint'): checkpoint}
    for idx in (1, 2):
        rows[(models.CoverageLedgerEntry, f'ledger-{idx}')] = S(
            coverage_ledger_entry_id=f'ledger-{idx}', coverage_contract_id='contract',
            contract_version=1, contract_hash=H('9'), record_hash=H(str(idx)),
            window_start=begin, window_end=end, unit_order=idx,
            coverage_outcome='covered', observation_outcome='observed',
            processing_outcome='succeeded', response_kind='non_empty',
            cycle_fully_evaluated=True)
    g14_data = {'schema_version':g15._G14_SCHEMA, 'empresa_id':8, 'relatorio_id':7,
                'documento_id':6, 'xml_sha256':XML_HASH,
                'posse_e_proveniencia_interna_g13':True, 'itens_total':1,
                'itens':[{'indice_item':1,'ncm':'10019010','cest_observado':'0100100',
                          'estado':'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST',
                          'url_fonte_candidata':URL,'fonte_legal_candidata':'ATO SINTETICO',
                          'sha256_texto_normativo_declarado':DIGEST}],
                **{x:False for x in g15._FLAGS}}
    refs = [{'indice_item':1,'artifact_reference_record_id':'ref',
             'acquisition_execution_record_id':'exec','normative_artifact_id':'art',
             'authenticity_verification_record_id':'auth',
             'integrity_verification_record_id':'integ',
             'preservation_verification_record_id':'pres'}]
    time_refs = [{'indice_item':1,'extraction_result_id':'extraction',
                  'rule_version_record_id':'rule-record','rule_review_record_id':'review',
                  'normative_activation_id':'activation','relation_version_record_ids':[]}]
    coverage_refs = [{'indice_item':1,'rule_version_record_id':'rule-record',
                      'extraction_result_id':'extraction','normative_artifact_id':'art',
                      'artifact_reference_record_id':'ref',
                      'coverage_contract_record_id':'contract-record',
                      'coverage_checkpoint_record_id':'checkpoint',
                      'coverage_ledger_entry_ids':['ledger-1','ledger-2']}]
    evidence = [{'indice_item':1, 'normative_artifact_id':'art',
                 'artifact_reference_record_id':'ref', 'url_publicacao':URL,
                 'sha256_publicacao':DIGEST,'pdf_bytes':PDF}]
    args = dict(db=ReadOnlyDB(rows), authenticated_user_id=9, empresa_id=8,
                relatorio_id=7, xml_bytes=XML, candidatos_normativos=[],
                referencias_adr020=refs, referencias_temporais=time_refs,
                referencias_cobertura=coverage_refs, evidencias_externas=evidence)
    return args, g14_data, rows

@pytest.fixture
def context(tmp_path):
    root = tmp_path / 'CAS'
    args, g14_data, rows = fixture_data(root)
    with patch.object(g15, 'cotejar_enquadramento_normativo_operacao_g14',
                      side_effect=lambda **kw: g14_data):
        yield root, args, rows

def call(module, args, root=None):
    keys = {
        g15:('db','authenticated_user_id','empresa_id','relatorio_id','xml_bytes',
             'candidatos_normativos','referencias_adr020'),
        g16:('db','authenticated_user_id','empresa_id','relatorio_id','xml_bytes',
             'candidatos_normativos','referencias_adr020','referencias_temporais'),
        g17:('db','authenticated_user_id','empresa_id','relatorio_id','xml_bytes',
             'candidatos_normativos','referencias_adr020','referencias_temporais',
             'referencias_cobertura'),
        g18:('db','authenticated_user_id','empresa_id','relatorio_id','xml_bytes',
             'candidatos_normativos','referencias_adr020','referencias_temporais',
             'referencias_cobertura','evidencias_externas'),
    }
    subset = {k:args[k] for k in keys[module]}
    if root is not None:
        subset['cas_root'] = root
    func = {g15:g15.cotejar_artefacto_primario_g15,
            g16:g16.cotejar_ciclo_normativo_g16,
            g17:g17.cotejar_cobertura_publicacao_g17,
            g18:g18.cotejar_evidencia_externa_publicacao_g18}[module]
    return func(**subset)

def blocked(result):
    if result.get('schema_version') == g15.SCHEMA:
        # G1.5 predates the later temporal and legal-validity fields.
        # Preserve its complete established set of fail-closed flags.
        for key in g15._FLAGS:
            assert result[key] is False, key
        assert result['versao_oficial_verificada'] is False
        assert result['texto_normativo_interpretado_e_aplicado'] is False
        return
    for key in DENIED:
        assert result[key] is False, key


def test_g110_01_g15_explicit_location(context):
    root,args,_=context
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==1
    assert result['itens'][0]['artefacto_sha256']==DIGEST
    assert args['db'].writes==0
    blocked(result)


def test_g110_02_g15_default_remains_closed(context):
    _,args,_=context
    result=call(g15,args)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_03_g15_wrong_root_denied(context,tmp_path):
    _,args,_=context
    wrong=tmp_path/'empty'
    wrong.mkdir()
    result=call(g15,args,wrong)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_04_g15_wrong_hash_denied(context):
    root,args,rows=context
    rows[(models.NormativeArtifact,'art')].artifact_hash=H('0')
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_05_g15_storage_double_mode_denied(context):
    root,args,rows=context
    rows[(models.NormativeArtifact,'art')].immutable_bytes=PDF
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_06_g15_missing_auth_verification_denied(context):
    root,args,rows=context
    rows.pop((models.ArtifactVerificationRecord,'auth'))
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_07_g15_bad_preservation_predecessor_denied(context):
    root,args,rows=context
    rows[(models.ArtifactVerificationRecord,'pres')].integrity_verification_record_id='other'
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_08_g15_acquisition_mismatch_denied(context):
    root,args,rows=context
    rows[(models.NormativeArtifact,'art')].acquisition_attempt_number=2
    result=call(g15,args,root)
    assert result['itens_com_cadeia_interna']==0
    blocked(result)


def test_g110_09_g16_real_chain_cas(context):
    root,args,_=context
    result=call(g16,args,root)
    assert result['itens_com_cadeia_temporal_interna']==1
    assert result['itens'][0]['regra_interna_cotejada'] is True
    blocked(result)


def test_g110_10_g17_real_chain_cas(context):
    root,args,_=context
    result=call(g17,args,root)
    assert result['itens_janela_interna_cotejada']==1
    assert result['itens'][0]['janela_administrativa_cotejada'] is True
    blocked(result)


def test_g110_11_g18_real_chain_cas(context):
    root,args,_=context
    result=call(g18,args,root)
    assert result['itens_hash_externo_cotejado']==1
    assert result['itens'][0]['vinculo_hash_adr020'] is True
    assert result['itens'][0]['custodia_externa_revalidada'] is False
    assert args['db'].writes==0
    blocked(result)


def test_g110_12_g18_default_blocks_cas(context):
    _,args,_=context
    result=call(g18,args)
    assert result['itens_hash_externo_cotejado']==0
    blocked(result)


def test_g110_13_g16_bad_temporal_chain_denied(context):
    root,args,rows=context
    rows[(models.ExtractionResult,'extraction')].artifact_hash=H('0')
    result=call(g16,args,root)
    assert result['itens_com_cadeia_temporal_interna']==0
    blocked(result)


def test_g110_14_g17_cross_source_denied(context):
    root,args,rows=context
    rows[(models.CoverageContract,'contract-record')].source_id='OTHER'
    result=call(g17,args,root)
    assert result['itens_janela_interna_cotejada']==0
    blocked(result)


def test_g110_15_g18_wrong_pdf_denied(context):
    root,args,_=context
    args['evidencias_externas'][0]['pdf_bytes']=PDF[:-1]+b'Y'
    with pytest.raises(g18.EnterpriseG18GateError):
        call(g18,args,root)


def test_g110_16_g15_reject_untrusted_g14(context):
    root,args,_=context
    # Test an actual caller controlled candidate cannot elevate G14 trust.
    with patch.object(g15,'cotejar_enquadramento_normativo_operacao_g14',
        side_effect=lambda **kw:{'fonte_primaria_autenticada':True}):
        with pytest.raises(g15.EnterpriseG15GateError):
            call(g15,args,root)


def test_g110_17_g18_cas_read_failure_closed(context):
    root,args,_=context
    # Removing CAS entirely makes G15 refuse, then cascades through the chain.
    import os
    cas_file=root/'sha256'/DIGEST[:2]/(DIGEST+'.pdf')
    cas_file.unlink()
    result=call(g18,args,root)
    assert result['itens_hash_externo_cotejado']==0
    blocked(result)
