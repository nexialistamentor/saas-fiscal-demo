"""P1-04C2: defensive isolated writer tests; no live DB, orders or payments."""
from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.models import (
    CheckoutOffer, DocumentoFiscal, Empresa, EnterpriseDocumentalCheckoutIntent as Model,
    RelatorioAnalise,
)
from app.services import enterprise_documental_checkout_intent as subject

ROOT = Path(__file__).resolve().parents[1]
XML = b'<synthetic-nfe-not-real/>'
SHA = hashlib.sha256(XML).hexdigest()
FP = 'a' * 64
CODE = 'enterprise-documental-diagnostic-one-time-company'
CAP = 'enterprise.diagnostic.documental'
GOOD = {'oferta_documental_valida': True, 'candidatura_comercial': True,
        'checkout_autorizado': False}


class FakeDb:
    def __init__(self):
        self.company = SimpleNamespace(user_id=11)
        self.report = SimpleNamespace(user_id=11, empresa_id=21, analysis_type='xml_analise',
                                      status='ok', fingerprint=FP)
        self.document = SimpleNamespace(usuario_id=11, empresa_id=21, conteudo_sha256=SHA)
        self.offer = SimpleNamespace(id=41)
        self.existing = None
        self.added = []
        self.get_calls = []
        self.scalar_calls = 0
        self.flush_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def get(self, model, identity):
        self.get_calls.append((model, identity))
        return {Empresa: self.company, RelatorioAnalise: self.report,
                DocumentoFiscal: self.document}.get(model)

    def scalar(self, _statement):
        self.scalar_calls += 1
        return self.offer if self.scalar_calls % 2 == 1 else self.existing

    def add(self, value):
        self.added.append(value)

    def flush(self):
        self.flush_calls += 1
        for item in self.added:
            item.id = 51
            item.created_at = datetime(2026, 10, 16)

    def commit(self):
        self.commit_calls += 1
        raise AssertionError('P104C2_COMMIT_FORBIDDEN')

    def rollback(self):
        self.rollback_calls += 1
        raise AssertionError('P104C2_ROLLBACK_FORBIDDEN')


def call(db, **changes):
    args = dict(user_id=11, empresa_id=21, relatorio_id=31,
                offer_code=CODE, checkout_idempotency_key='enterprise-unique-key-1',
                request_fingerprint=FP, xml_bytes=XML)
    args.update(changes)
    snapshot = SimpleNamespace(id=41, contract_version=2, capabilities=(CAP,))
    with patch.object(subject, 'verificar_resultado_persistido', return_value={
        'empresa_id': 21, subject.EVIDENCE_KEY: {'documento_id': 71}
    }), patch.object(subject, 'checkout_offer_snapshot', return_value=snapshot), \
         patch.object(subject, 'avaliar_candidatura_comercial_documental', return_value=GOOD):
        return subject.EnterpriseDocumentalCheckoutIntent(db).persist(**args)


class P104C2Defense(unittest.TestCase):
    def test_01_exact_binding_persist_no_commit_or_checkout(self):
        db = FakeDb()
        result = call(db)
        self.assertIsInstance(result, subject.EnterpriseDocumentalCheckoutIntentResult)
        self.assertEqual(result.intent_id, 51)
        self.assertEqual(result.documento_fiscal_id, 71)
        self.assertEqual(result.xml_sha256, SHA)
        self.assertEqual(result.offer_contract_version, 2)
        self.assertEqual((len(db.added), db.flush_calls, db.commit_calls, db.rollback_calls), (1, 1, 0, 0))

    def test_02_idempotent_exact_retry_without_new_row(self):
        db = FakeDb()
        first = call(db)
        db.existing = db.added[0]
        again = call(db)
        self.assertEqual(first, again)
        self.assertEqual(len(db.added), 1)
        self.assertEqual(db.flush_calls, 1)

    def test_03_divergent_retry_cannot_rebind_without_write(self):
        db = FakeDb()
        call(db)
        db.existing = db.added[0]
        db.existing.offer_contract_version = 3
        with self.assertRaises(subject.EnterpriseDocumentalCheckoutIntentError):
            call(db)
        self.assertEqual(len(db.added), 1)

    def test_04_invalid_inputs_reject_before_database_access(self):
        for change in ({'user_id': True}, {'empresa_id': 0}, {'relatorio_id': -1},
                       {'offer_code': 'tax-report-one-time-company'},
                       {'checkout_idempotency_key': ''},
                       {'checkout_idempotency_key': 'bad key'},
                       {'checkout_idempotency_key': 'z'*256},
                       {'request_fingerprint': 'F'*64},
                       {'xml_bytes': 'str'}, {'xml_bytes': b''},
                       {'xml_bytes': b'x'*(2*1024*1024+1)}):
            with self.subTest(change=str(change)[:60]):
                db = FakeDb()
                with self.assertRaises(subject.EnterpriseDocumentalCheckoutIntentError):
                    call(db, **change)
                self.assertFalse(db.get_calls)
                self.assertEqual(db.scalar_calls, 0)
                self.assertFalse(db.added)

    def test_05_provenance_mismatch_fails_before_mutation(self):
        for name, value in (('company', SimpleNamespace(user_id=99)),
                            ('report', SimpleNamespace(user_id=11, empresa_id=21, analysis_type='empresa_tax',
                                                       status='ok', fingerprint=FP)),
                            ('document', SimpleNamespace(usuario_id=11, empresa_id=21,
                                                         conteudo_sha256='f'*64))):
            with self.subTest(name=name):
                db = FakeDb()
                setattr(db, name, value)
                with self.assertRaises(subject.EnterpriseDocumentalCheckoutIntentError):
                    call(db)
                self.assertEqual(db.flush_calls, 0)

    def test_06_candidate_rejection_is_not_purchase_authority(self):
        db = FakeDb()
        with patch.object(subject, 'verificar_resultado_persistido', return_value={
            'empresa_id': 21, subject.EVIDENCE_KEY: {'documento_id': 71}
        }), patch.object(subject, 'checkout_offer_snapshot', return_value=SimpleNamespace(
            id=41, contract_version=2, capabilities=(CAP,))), \
             patch.object(subject, 'avaliar_candidatura_comercial_documental', return_value={
                 **GOOD, 'checkout_autorizado': True
             }):
            with self.assertRaises(subject.EnterpriseDocumentalCheckoutIntentError):
                subject.EnterpriseDocumentalCheckoutIntent(db).persist(
                    user_id=11, empresa_id=21, relatorio_id=31,
                    offer_code=CODE, checkout_idempotency_key='enterprise-key',
                    request_fingerprint=FP, xml_bytes=XML)
        self.assertEqual(db.flush_calls, 0)

    def test_07_model_and_pg_trigger_append_only_safety(self):
        self.assertEqual(Model.__tablename__, 'enterprise_documental_checkout_intents')
        source = (ROOT/'migrations/versions/0061_enterprise_documental_checkout_intent.py').read_text(encoding='utf-8')
        self.assertIn('BEFORE UPDATE OR DELETE', source)
        self.assertIn('CREATE TRIGGER', source)
        from sqlalchemy import event
        self.assertTrue(event.contains(Model, 'before_update',
                            __import__('app.models', fromlist=['_reject_enterprise_documental_checkout_intent_mutation'])._reject_enterprise_documental_checkout_intent_mutation))

    def test_08_guard_p104c1_unmodified_and_no_imports_payments(self):
        guarded = (ROOT/'app/services/checkout_offer_prerequisite.py').read_text(encoding='utf-8-sig')
        self.assertIn('if offer_code == "enterprise-documental-diagnostic-one-time-company":', guarded)
        self.assertIn('raise CheckoutOfferPrerequisiteError()', guarded)
        source = (ROOT/'app/services/enterprise_documental_checkout_intent.py').read_text(encoding='utf-8')
        for marker in ('.commit(', '.rollback(', 'mercado_pago', 'CheckoutOfferOrderComposer', 'checkout_autorizado": True'):
            self.assertNotIn(marker, source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
