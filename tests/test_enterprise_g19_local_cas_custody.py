"""G1.9 synthetic CAS contract; no HTTP, real DB, taxes, payment or deploy."""
import hashlib
from pathlib import Path
import os
import sys
import tempfile
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.enterprise_g19_local_cas_custody import (
    SCHEMA, PREFIX, MAX_PDF, EnterpriseG19GateError,
    guardar_pdf_cas_g19, verificar_pdf_cas_g19,
    cotejar_localizacao_adr020_g19,
)

PDF = b'%PDF-1.7\n' + b'S' * 1024
DIGEST = hashlib.sha256(PDF).hexdigest()
ZERO = '0' * 64
URL = 'https://www.ioepa.com.br/arquivos/2026/2026.02.23.DOE.pdf'
FLAGS = ('fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente')


class G19(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'cas'
        self.location = PREFIX + DIGEST

    def store(self, *, raw=PDF, digest=DIGEST, root=None):
        return guardar_pdf_cas_g19(root=self.root if root is None else root,
                                   pdf_bytes=raw, sha256_esperado=digest)

    def read(self, **kwargs):
        args = dict(root=self.root, immutable_location=self.location,
                    sha256_esperado=DIGEST, tamanho_esperado=len(PDF))
        args.update(kwargs)
        return verificar_pdf_cas_g19(**args)

    def deny(self, callback, *args, **kwargs):
        with self.assertRaises(EnterpriseG19GateError):
            callback(*args, **kwargs)

    def blocked(self, result):
        for flag in FLAGS:
            self.assertIs(result[flag], False, flag)
        self.assertIs(result['custodia_externa_imutavel_comprovada'], False)
        self.assertIs(result['cadeia_g15_location_integrada'], False)

    def test_01_create_exclusive_and_verify(self):
        r=self.store();self.assertEqual(r['schema_version'],SCHEMA)
        self.assertEqual(r['immutable_location_proposta'],self.location)
        self.blocked(r)
        a=self.read();self.assertEqual(a['tamanho_bytes'],len(PDF))
        self.blocked(a)

    def test_02_already_exists_never_overwritten(self):
        self.store();self.deny(self.store)
        self.assertEqual(self.read()['sha256_recalculado'],DIGEST)

    def test_03_read_absent(self):
        self.root.mkdir();self.deny(self.read)

    def test_04_hash_wrong_on_write(self):
        self.deny(self.store,digest=ZERO)

    def test_05_bad_pdf_header(self):
        raw=b'NOPE' + PDF[4:]
        self.deny(self.store,raw=raw,digest=hashlib.sha256(raw).hexdigest())

    def test_06_too_small_pdf(self):
        raw=b'%PDF-' + b'X'*10
        self.deny(self.store,raw=raw,digest=hashlib.sha256(raw).hexdigest())

    def test_07_not_exact_bytes(self):
        self.deny(self.store,raw=bytearray(PDF))

    def test_08_more_than_limit(self):
        raw=b'%PDF-' + b'x'*MAX_PDF
        self.deny(self.store,raw=raw,digest=hashlib.sha256(raw).hexdigest())

    def test_09_bad_digest_syntax(self):
        self.deny(self.store,digest='A'*64)

    def test_10_relative_root_rejected(self):
        self.deny(self.store,root='relative/path')

    def test_11_parent_traversal_root_rejected(self):
        self.deny(self.store,root=str(self.root / '..' / 'other'))

    def test_12_location_suffix_rejected(self):
        self.store();self.deny(self.read,immutable_location=self.location+'/x')

    def test_13_wrong_scheme_rejected(self):
        self.store();self.deny(self.read,immutable_location='file:///tmp/'+DIGEST)

    def test_14_location_digest_mismatch_rejected(self):
        self.store();self.deny(self.read,immutable_location=PREFIX+ZERO)

    def test_15_expected_hash_mismatch_rejected(self):
        self.store();self.deny(self.read,sha256_esperado=ZERO)

    def test_16_expected_size_mismatch_rejected(self):
        self.store();self.deny(self.read,tamanho_esperado=len(PDF)+1)

    def test_17_boolean_size_rejected(self):
        self.store();self.deny(self.read,tamanho_esperado=True)

    def test_18_disk_tamper_same_size_rejected(self):
        self.store();p=self.root/'sha256'/DIGEST[:2]/(DIGEST+'.pdf')
        p.chmod(0o600);p.write_bytes(PDF[:10]+b'X'+PDF[11:])
        self.deny(self.read)

    def test_19_symlink_object_rejected(self):
        self.root.mkdir()
        p=self.root/'sha256'/DIGEST[:2]/(DIGEST+'.pdf')
        p.parent.mkdir(parents=True)
        other=Path(self.tmp.name)/'outside.pdf';other.write_bytes(PDF)
        try:p.symlink_to(other)
        except (OSError,NotImplementedError):self.skipTest('symlink unavailable')
        self.deny(self.read)

    def test_20_symlink_root_rejected(self):
        source=Path(self.tmp.name)/'real';source.mkdir()
        try:self.root.symlink_to(source,target_is_directory=True)
        except (OSError,NotImplementedError):self.skipTest('symlink unavailable')
        self.deny(self.store)

    def test_21_no_record_authority(self):
        self.store();r=self.read();self.assertFalse(r['vinculo_adr020'])
        self.assertFalse(r['assinatura_pdf_validada_neste_servico'])
        self.blocked(r)

    def test_22_medium_pdf_over_two_mib(self):
        raw=b'%PDF-1.7\n'+b'X'*(2764152-len(b'%PDF-1.7\n'))
        sha=hashlib.sha256(raw).hexdigest()
        r=self.store(raw=raw,digest=sha)
        self.assertEqual(r['tamanho_bytes'],2764152)
        got=verificar_pdf_cas_g19(root=self.root,
           immutable_location=PREFIX+sha,sha256_esperado=sha,tamanho_esperado=len(raw))
        self.assertEqual(got['sha256_recalculado'],sha)
        self.blocked(got)

    def _db(self):
        mod=types.ModuleType('app.models')
        for name in ('NormativeArtifact','ArtifactReference','AcquisitionExecution'):
            setattr(mod,name,type(name,(),{}))
        art=SimpleNamespace(normative_artifact_id='artifact',
            artifact_reference_id='reference', artifact_hash=DIGEST,
            byte_size=len(PDF),immutable_bytes=None,immutable_location=self.location,
            acquisition_execution_record_id='execution',acquisition_execution_id='execution-id',
            acquisition_attempt_number=1,acquisition_event='conclusao',
            acquisition_state='concluida',record_hash=ZERO)
        ref=SimpleNamespace(artifact_reference_record_id='ref',
            artifact_reference_id='reference',reference_event='resolvida',
            exact_locator=URL,record_hash=ZERO)
        exe=SimpleNamespace(acquisition_execution_record_id='execution',
            artifact_reference_record_id='ref',artifact_reference_id='reference',
            execution_event='conclusao',projected_state='concluida',
            acquisition_execution_id='execution-id',attempt_number=1,record_hash=ZERO)
        rows={(mod.NormativeArtifact,'artifact'):art,
              (mod.ArtifactReference,'ref'):ref,
              (mod.AcquisitionExecution,'execution'):exe}
        fake=SimpleNamespace(get=lambda model,key:rows.get((model,key)))
        return mod,fake,art,ref,exe

    def _cotejar(self, *, db=None, **changes):
        args=dict(db=db,root=self.root,normative_artifact_id='artifact',
            artifact_reference_record_id='ref',acquisition_execution_record_id='execution',
            url_publicacao=URL,sha256_esperado=DIGEST,tamanho_esperado=len(PDF))
        args.update(changes)
        return cotejar_localizacao_adr020_g19(**args)

    def test_23_cotejo_full_exact_no_trust(self):
        self.store();mod,db,*_=self._db()
        with patch.dict(sys.modules,{'app.models':mod}):r=self._cotejar(db=db)
        self.assertTrue(r['vinculo_adr020'])
        self.assertEqual(r['estado'],'CAS_ADR020_BYTES_COTEJADOS_G15_AINDA_BLOQUEADO')
        self.blocked(r)

    def test_24_cotejo_wrong_document_hash(self):
        self.store();mod,db,art,*_=self._db();art.artifact_hash=ZERO
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_25_cotejo_wrong_location(self):
        self.store();mod,db,art,*_=self._db();art.immutable_location=PREFIX+ZERO
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_26_cotejo_duplicate_inline_bytes(self):
        self.store();mod,db,art,*_=self._db();art.immutable_bytes=PDF
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_27_cotejo_other_reference(self):
        self.store();mod,db,art,*_=self._db();art.artifact_reference_id='other'
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_28_cotejo_other_execution(self):
        self.store();mod,db,art,*_=self._db();art.acquisition_execution_id='other'
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_29_cotejo_unfinished_acquisition(self):
        self.store();mod,db,_,_,exe=self._db();exe.projected_state='falhada'
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_30_cotejo_wrong_url(self):
        self.store();mod,db,*_=self._db()
        with patch.dict(sys.modules,{'app.models':mod}):
            self.deny(self._cotejar,db=db,url_publicacao='https://different.example/x.pdf')

    def test_31_cotejo_unresolved_reference(self):
        self.store();mod,db,_,ref,_=self._db();ref.reference_event='agendada'
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_32_cotejo_bad_record_hash(self):
        self.store();mod,db,art,*_=self._db();art.record_hash='bad'
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_33_cotejo_invalid_db(self):
        self.store();mod,db,*_=self._db()
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=None)

    def test_34_cotejo_db_read_fails(self):
        self.store();mod,db,*_=self._db();db.get=lambda cls,key:1/0
        with patch.dict(sys.modules,{'app.models':mod}):self.deny(self._cotejar,db=db)

    def test_35_invalid_identifier(self):
        self.store();mod,db,*_=self._db()
        with patch.dict(sys.modules,{'app.models':mod}):
            self.deny(self._cotejar,db=db,normative_artifact_id='../escape')


    def test_36_windows_path_stat_metadata_drift_not_object_swap(self):
        # Reproduce a post-read Path.stat discrepancy without changing bytes.
        # R1 compared descriptor stats with path stats and failed spuriously.
        target = self.root/'sha256'/DIGEST[:2]/(DIGEST+'.pdf')
        target.parent.mkdir(parents=True)
        target.write_bytes(PDF)
        original = Path.stat
        calls = [0]

        class Drift:
            def __init__(self, value):
                self.value = value
            def __getattr__(self, name):
                if name == 'st_ctime_ns':
                    return self.value.st_ctime_ns + 1000000000
                return getattr(self.value, name)

        def stat_with_path_drift(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if Path(path) == target:
                calls[0] += 1
                if calls[0] > 1:
                    return Drift(value)
            return value

        with patch.object(Path, 'stat', stat_with_path_drift):
            result = self.read()
        self.assertEqual(result['sha256_recalculado'], DIGEST)
        self.blocked(result)

    def test_37_second_handle_substitution_rejected(self):
        self.store()
        target = self.root/'sha256'/DIGEST[:2]/(DIGEST+'.pdf')
        other = Path(self.tmp.name)/'different.pdf'
        other.write_bytes(PDF[:10] + b'Z' + PDF[11:])
        original = os.open
        reads = [0]

        def substitute(path, flags, *args, **kwargs):
            if Path(path) == target and not (flags & os.O_CREAT):
                reads[0] += 1
                if reads[0] == 2:
                    return original(other, flags, *args, **kwargs)
            return original(path, flags, *args, **kwargs)

        with patch('app.services.enterprise_g19_local_cas_custody.os.open', substitute):
            self.deny(self.read)
        self.assertEqual(reads[0], 2)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), DIGEST)

if __name__ == '__main__':
    unittest.main()
