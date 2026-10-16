"""I12: ledger CAS apenas SQLite :memory:/ficheiro temporario + NF-e sintetica."""
from copy import deepcopy
from datetime import timedelta
import base64
import hashlib
import importlib
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

import test_enterprise_nfe_i11_crl_provenance as i11f

LEDGER='123e4567-e89b-42d3-a456-426614174000'
LEDGER_OTHER='123e4567-e89b-42d3-a456-426614174001'
ZERO='0'*64
NOW=i11f.NOW


class TestI12CustodyCASLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i11f.TestI11SignedCRLProvenance.setUpClass()

    def setUp(self):
        self.src=i11f.TestI11SignedCRLProvenance(methodName='test_00_module_required')
        self.src.setUp()
        self.key=Ed25519PrivateKey.from_private_bytes(b'\xbd'*32)  # somente TESTE
        self.pub=self.key.public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.conn=sqlite3.connect(':memory:',timeout=0.2)

    def tearDown(self):
        self.conn.close()

    def module(self):
        try:return importlib.import_module('app.services.enterprise_nfe_i12_custody_ledger')
        except ModuleNotFoundError as e:
            if e.name=='app.services.enterprise_nfe_i12_custody_ledger':
                self.fail('I12_RED_CAUSAL_MISSING_MODULE')
            raise

    def provision(self):
        self.module().provisionar_schema_ledger_i12(
            sqlite_conn=self.conn,autorizar_criacao_esquema=True)

    def checkpoint(self,seq=0,state=ZERO,manifest=ZERO,ledger=LEDGER,**mods):
        m=self.module()
        data=dict(schema_version=m.CHECKPOINT_SCHEMA,ledger_id=ledger,
                  sequence=seq,state_sha256=state,last_manifest_sha256=manifest,
                  checkpoint_pub_sha256=hashlib.sha256(self.pub).hexdigest(),
                  issuer='CUSTODIANTE_CHECKPOINT_EXTERNO_CONTROLADO',
                  scope='SOLVERIS_ENTERPRISE_NFE_LCR_LEDGER')
        data.update(mods)
        signed=m._canonical(data)
        data['signature_ed25519_b64']=base64.b64encode(self.key.sign(signed)).decode('ascii')
        return data

    def kwargs(self):
        return dict(sqlite_conn=self.conn,ledger_id=LEDGER,
                    parametros_i10=self.src.i10args, manifesto_i11=self.src.manifest(),
                    trusted_custodian_public_key=self.src.pub,
                    trusted_checkpoint_public_key=self.pub,
                    checkpoint_externo=self.checkpoint(),agora_utc=NOW)

    def runcheck(self,**mods):
        inp=self.kwargs();inp.update(mods)
        return self.module().registrar_custodia_lcr_i12(**inp)

    def failcheck(self,reason,**mods):
        with self.assertRaisesRegex(self.module().EnterpriseI12LedgerError,reason):
            self.runcheck(**mods)

    def first(self):
        self.provision()
        return self.runcheck()

    def second_kwargs(self):
        result=self.first()
        prior=self.src.runcheck()['estado_proposto_para_custodia_externa']
        self.assertEqual(self.module()._canonical(prior).decode(), self.conn.execute(
            'SELECT state_json FROM enterprise_i12_nfe_crl_ledger').fetchone()[0])
        cp=self.checkpoint(1,result['estado_local_sha256'],result['manifesto_i11_sha256'])
        manifesto=self.src.manifest(sequencia=2,manifesto_anterior_sha256=prior['manifesto_sha256'])
        return dict(manifesto_i11=manifesto,checkpoint_externo=cp)

    def test_00_module_required(self):
        self.assertTrue(callable(self.module().registrar_custodia_lcr_i12))

    def test_01_schema_opt_in_required(self):
        with self.assertRaisesRegex(self.module().EnterpriseI12LedgerError,'SCHEMA_OPT_IN_REQUIRED'):
            self.module().provisionar_schema_ledger_i12(sqlite_conn=self.conn)

    def test_02_no_implicit_ddl(self):
        self.failcheck('LEDGER_SCHEMA_OR_READ_FAILED')
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sqlite_master WHERE name='enterprise_i12_nfe_crl_ledger'").fetchone()[0],0)

    def test_03_provision_schema_explicit_only(self):
        self.provision();self.assertEqual(self.conn.execute("SELECT count(*) FROM sqlite_master WHERE name='enterprise_i12_nfe_crl_ledger'").fetchone()[0],1)

    def test_04_bootstrap_signed_checkpoint_local_commit(self):
        r=self.first()
        self.assertEqual(r['sequencia_local_committed'],1)
        self.assertTrue(r['checkpoint_externo_entrada_verificado'])
        self.assertTrue(r['comparacao_cas_sqlite_local_confirmada'])
        self.assertFalse(r['custodia_externa_duravel_verificada'])
        self.assertFalse(r['checkout_autorizado'])
        self.assertFalse(self.conn.in_transaction)

    def test_05_query_empty_head(self):
        self.provision()
        r=self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)
        self.assertEqual(r['sequence'],0)
        self.assertEqual(r['state_sha256'],ZERO)

    def test_06_query_after_commit(self):
        saved=self.first();head=self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)
        self.assertEqual(head['state_sha256'],saved['estado_local_sha256'])
        self.assertEqual(head['last_manifest_sha256'],saved['manifesto_i11_sha256'])

    def test_07_second_sequence_with_new_signed_external_checkpoint(self):
        kwargs=self.second_kwargs()
        r=self.runcheck(**kwargs)
        self.assertEqual(r['sequencia_local_committed'],2)
        self.assertEqual(self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)['sequence'],2)

    def test_08_reuse_genesis_refused(self):
        self.first();self.failcheck('CHECKPOINT_LEDGER_HEAD_MISMATCH')

    def test_09_stale_checkpoint_after_two_commits(self):
        self.runcheck(**self.second_kwargs());self.failcheck('CHECKPOINT_LEDGER_HEAD_MISMATCH')

    def test_10_checkpoint_signed_wrong_key(self):
        self.provision()
        cp=self.checkpoint()
        cp['signature_ed25519_b64']=base64.b64encode(bytes(64)).decode('ascii')
        self.failcheck('CHECKPOINT_SIGNATURE_INVALID',checkpoint_externo=cp)

    def test_11_checkpoint_wrong_pin(self):
        self.provision();pub=Ed25519PrivateKey.from_private_bytes(b'\xbe'*32).public_key().public_bytes(
            serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        self.failcheck('CHECKPOINT_KEY_PIN_MISMATCH',trusted_checkpoint_public_key=pub)

    def test_12_custodian_and_checkpoint_must_have_distinct_keys(self):
        self.provision()
        self.failcheck('INPUT_OR_KEY_SEPARATION_INVALID',trusted_checkpoint_public_key=self.src.pub)

    def test_13_manifest_tampered_rolls_back(self):
        self.provision();fake=self.src.manifest();fake['sequencia']=2
        self.failcheck('I11_PROVENANCE_NOT_VERIFIED',manifesto_i11=fake)
        self.assertEqual(self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)['sequence'],0)
        self.assertFalse(self.conn.in_transaction)

    def test_14_checkpoint_wrong_ledger_id(self):
        self.provision();self.failcheck('CHECKPOINT_CLAIMS_INVALID',checkpoint_externo=self.checkpoint(ledger=LEDGER_OTHER))

    def test_15_checkpoint_extra_claim_rejected(self):
        self.provision();cp=self.checkpoint();cp['icp_brasil_verificada']=True
        self.failcheck('CHECKPOINT_SCHEMA_INVALID',checkpoint_externo=cp)

    def test_16_checkpoint_unknown_issuer_refused(self):
        self.provision();self.failcheck('CHECKPOINT_CLAIMS_INVALID',checkpoint_externo=self.checkpoint(issuer='ITI'))

    def test_17_checkpoint_genesis_nonzero_refused(self):
        self.provision();self.failcheck('CHECKPOINT_GENESIS_INVALID',checkpoint_externo=self.checkpoint(state='a'*64))

    def test_18_wrong_state_checkpoint_denied(self):
        self.first();cp=self.checkpoint(1,'e'*64,'f'*64)
        self.failcheck('CHECKPOINT_LEDGER_HEAD_MISMATCH',checkpoint_externo=cp)

    def test_19_checkpoint_boolean_seq_refused(self):
        self.provision();self.failcheck('CHECKPOINT_CLAIMS_INVALID',checkpoint_externo=self.checkpoint(seq=True))

    def test_20_checkpoint_noncanonical_base64(self):
        self.provision();cp=self.checkpoint();cp['signature_ed25519_b64']='!'*88
        self.failcheck('CHECKPOINT_SIGNATURE_INVALID',checkpoint_externo=cp)

    def test_21_no_xml_or_certificate_in_persistent_state(self):
        self.first();raw=self.conn.execute('SELECT state_json FROM enterprise_i12_nfe_crl_ledger').fetchone()[0]
        self.assertNotIn(i11f.i10fixture.i9f.i8f.CNPJ,raw)
        self.assertNotIn(i11f.i10fixture.i9f.i8f.key(),raw)
        self.assertNotIn('assinatura_ed25519_base64',raw)
        self.assertNotIn('certificado_der',raw)
        self.assertNotIn('xml_bytes',raw)
        self.assertNotIn('lcrs_der',raw)

    def test_22_tamper_row_hash_denied(self):
        self.first();self.conn.execute("UPDATE enterprise_i12_nfe_crl_ledger SET state_json='{}'")
        self.conn.commit()
        cp=self.checkpoint(1,'a'*64,'b'*64)
        self.failcheck('LEDGER_ROW_HASH_INVALID',checkpoint_externo=cp)

    def test_23_query_tamper_denied(self):
        self.first();self.conn.execute("UPDATE enterprise_i12_nfe_crl_ledger SET state_sha256=?",('0'*64,));self.conn.commit()
        with self.assertRaisesRegex(self.module().EnterpriseI12LedgerError,'LEDGER_ROW_HASH_INVALID'):
            self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)

    def test_24_cannot_call_during_prior_transaction(self):
        self.provision();self.conn.execute('BEGIN')
        self.failcheck('CONNECTION_ALREADY_IN_TRANSACTION')
        self.conn.rollback()

    def test_25_bad_conn(self):
        self.failcheck('SQLITE_CONNECTION_REQUIRED',sqlite_conn=None)

    def test_26_wrong_clock(self):
        self.provision();self.failcheck('INPUT_OR_KEY_SEPARATION_INVALID',agora_utc=NOW.replace(tzinfo=None))

    def test_27_repeat_seq_two_from_existing_head(self):
        kwargs=self.second_kwargs()
        self.runcheck(**kwargs)
        self.failcheck('CHECKPOINT_LEDGER_HEAD_MISMATCH',**kwargs)

    def test_28_sqlite_file_persists_across_reconnections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=os.path.join(tmp,'ledger.sqlite3')
            self.conn.close()
            self.conn=sqlite3.connect(path)
            try:
                self.first()
                self.conn.close()
                self.conn=sqlite3.connect(path)
                head=self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)
                self.assertEqual(head['sequence'],1)
            finally:
                self.conn.close()

    def test_29_different_ledger_ids_isolated(self):
        self.first()
        r=self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER_OTHER)
        self.assertEqual(r['sequence'],0)

    def test_30_wrong_model_does_not_migrate(self):
        self.provision()
        self.failcheck('INPUT_OR_KEY_SEPARATION_INVALID',ledger_id='not-a-uuid')

    def test_31_read_only_no_network(self):
        self.provision()
        with patch('socket.create_connection',side_effect=AssertionError('NETWORK')):
            self.assertEqual(self.module().consultar_ponta_ledger_i12(sqlite_conn=self.conn,ledger_id=LEDGER)['sequence'],0)

    def test_32_second_rejects_crl_rollback_i11(self):
        kwargs=self.second_kwargs()
        row=self.conn.execute('SELECT state_json FROM enterprise_i12_nfe_crl_ledger').fetchone()
        forged_prior=json.loads(row[0])
        forged_prior['lcrs'][0]['numero']+=1
        canon=self.module()._canonical(forged_prior).decode('ascii')
        forged_sha=hashlib.sha256(canon.encode('ascii')).hexdigest()
        self.conn.execute('UPDATE enterprise_i12_nfe_crl_ledger SET state_json=?,state_sha256=?',
                          (canon,forged_sha))
        self.conn.commit()
        # Mesmo com checkpoint externo sinteticamente assinado, I11 trava retrocesso.
        cp=self.checkpoint(1,forged_sha,forged_prior['manifesto_sha256'])
        self.failcheck('I11_PROVENANCE_NOT_VERIFIED',
                       manifesto_i11=kwargs['manifesto_i11'],checkpoint_externo=cp)
        self.assertEqual(self.module().consultar_ponta_ledger_i12(
            sqlite_conn=self.conn,ledger_id=LEDGER)['sequence'],1)

    def test_33_receipt_never_claims_icp_or_sefaz(self):
        r=self.first()
        for k in ('origem_iti_oficial_verificada','cadeia_icp_brasil_verificada',
                  'revogacao_oficial_global_verificada','situacao_sefaz_confirmada',
                  'efd_competencia_reconciliada','apuracao_mensal_completa',
                  'direito_creditorio_comprovado','checkout_autorizado'):
            self.assertIs(r[k],False,k)

if __name__=='__main__':unittest.main()
