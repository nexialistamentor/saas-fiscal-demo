"""P1-04C1 GREEN defense: Enterprise checkout must be DENIED without own durable authority.

Pure unit tests. No actual order, database mutation, payment, HTTP, migration.
Separate eventual commercial enablement from this temporary denial contract.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
PREREQ = ROOT / 'app/services/checkout_offer_prerequisite.py'
COMPOSER = ROOT / 'app/services/checkout_offer_order_composition.py'
ENTERPRISE = 'enterprise-documental-diagnostic-one-time-company'
LEGACY = 'tax-report-one-time-company'


class NoAccessDB:
    def __init__(self, value=None):
        self.value = value
        self.queries = 0
        self.writes = 0

    def scalar(self, statement):
        self.queries += 1
        return self.value

    def __getattr__(self, name):
        if name in ('add', 'flush', 'commit', 'delete', 'merge', 'execute', 'rollback'):
            self.writes += 1
            raise AssertionError('P104C1_UNEXPECTED_WRITE_' + name)
        raise AttributeError(name)


def prerequisite(db, **kwargs):
    from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisite
    values = {
        'authenticated_user_id': 11,
        'empresa_id': 21,
        'offer_code': ENTERPRISE,
        'idempotency_key': 'p104c1-enterprise-test',
    }
    values.update(kwargs)
    return CheckoutOfferPrerequisite(db).require(**values)


class P104C1Defense(unittest.TestCase):
    def test_01_enterprise_denied_without_read_or_write(self):
        from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisiteError
        db = NoAccessDB()
        with self.assertRaises(CheckoutOfferPrerequisiteError):
            prerequisite(db)
        self.assertEqual((db.queries, db.writes), (0, 0))

    def test_02_fake_old_intent_cannot_grant_enterprise(self):
        from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisiteError
        db = NoAccessDB(SimpleNamespace(user_id=11, empresa_id=21,
            offer_code=LEGACY, checkout_idempotency_key='p104c1-enterprise-test',
            candidatura_comercial=True, checkout_autorizado=True))
        with self.assertRaises(CheckoutOfferPrerequisiteError):
            prerequisite(db)
        self.assertEqual((db.queries, db.writes), (0, 0))

    def test_03_candidate_flag_cannot_grant_enterprise(self):
        from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisiteError
        for obj in (SimpleNamespace(candidatura_comercial=True),
                    {'candidatura_comercial': True, 'checkout_autorizado': True},
                    SimpleNamespace(checkout_autorizado=True), None):
            db = NoAccessDB(obj)
            with self.subTest(value=type(obj).__name__):
                with self.assertRaises(CheckoutOfferPrerequisiteError):
                    prerequisite(db)
                self.assertEqual((db.queries, db.writes), (0, 0))

    def test_04_unsafe_replay_and_ids_cannot_grant_enterprise(self):
        from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisiteError
        for field, value in (
            ('authenticated_user_id', 12), ('authenticated_user_id', True),
            ('authenticated_user_id', 0), ('empresa_id', 22),
            ('empresa_id', True), ('empresa_id', 0),
            ('idempotency_key', ''), ('idempotency_key', 'different-key'),
            ('idempotency_key', 'bad key with spaces'),
        ):
            db = NoAccessDB()
            with self.subTest(field=field, value=value):
                with self.assertRaises(CheckoutOfferPrerequisiteError):
                    prerequisite(db, **{field: value})
                self.assertEqual((db.queries, db.writes), (0, 0))

    def test_05_old_tax_report_missing_intent_still_denied(self):
        from app.services.checkout_offer_prerequisite import CheckoutOfferPrerequisiteError
        db = NoAccessDB()
        with self.assertRaises(CheckoutOfferPrerequisiteError):
            prerequisite(db, offer_code=LEGACY, idempotency_key='legacy')
        self.assertEqual((db.queries, db.writes), (1, 0))

    def test_06_other_offer_remains_outside_tax_prerequisite(self):
        db = NoAccessDB()
        self.assertIsNone(prerequisite(db, offer_code='document-extract-company'))
        self.assertEqual((db.queries, db.writes), (0, 0))

    def test_07_composer_requires_prerequisite_on_create_and_retry(self):
        tree = ast.parse(COMPOSER.read_text(encoding='utf-8-sig'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'CheckoutOfferOrderComposer')
        for name in ('iniciar_checkout_empresa', '_retry'):
            fn = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == name)
            source = ast.dump(fn)
            self.assertIn('CheckoutOfferPrerequisite', source, name)
            self.assertIn("attr='require'", source, name)
        source = COMPOSER.read_text(encoding='utf-8-sig')
        self.assertIn('CheckoutOfferPrerequisite(sessao).require(', source)

    def test_08_guard_import_boundary_and_legacy_binding_preserved(self):
        tree = ast.parse(PREREQ.read_text(encoding='utf-8-sig'))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module or '')
            elif isinstance(node, ast.Import):
                imports.update(v.name for v in node.names)
        forbidden = {'app.services.enterprise_documental_commercial_candidate',
                     'app.services.enterprise_diagnostic_readiness',
                     'app.services.mercado_pago_checkout_offer_one_time',
                     'app.services.checkout_offer_order_composition'}
        self.assertFalse(imports & forbidden)
        source = PREREQ.read_text(encoding='utf-8-sig')
        self.assertIn('TaxReportCheckoutIntent', source)
        self.assertIn('tax-report-one-time-company', source)
        self.assertIn('enterprise-documental-diagnostic-one-time-company', source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
