"""SOLVERIS P1-04C1 RED: Enterprise must be denied at checkout without a transaction authority.

Test-only; no orders, payment providers, migrations, or production changes.
The current composer already calls CheckoutOfferPrerequisite on creation and retry.
This contract requires a FAIL-CLOSED Enterprise offer even if P1-04B is positive.
A later phase will introduce a distinct durable transactional intent before enabling sale.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
COMPOSER = ROOT / 'app/services/checkout_offer_order_composition.py'
PREREQUISITE = ROOT / 'app/services/checkout_offer_prerequisite.py'
CANDIDATE = ROOT / 'app/services/enterprise_documental_commercial_candidate.py'
READINESS = ROOT / 'app/services/enterprise_diagnostic_readiness.py'
ENTERPRISE = 'enterprise-documental-diagnostic-one-time-company'
LEGACY = 'tax-report-one-time-company'


class _ReadOnlyFakeDB:
    def __init__(self, result=None):
        self.result = result
        self.calls = 0

    def scalar(self, stmt):
        self.calls += 1
        return self.result

    def __getattr__(self, method):
        if method in ('add', 'commit', 'flush', 'delete', 'merge', 'execute'):
            raise AssertionError('P104C_UNEXPECTED_DB_WRITE_' + method)
        raise AttributeError(method)


def _check_denied(db, *, who=11, empresa=21, offer_code=ENTERPRISE,
                  key='enterprise-test-key'):
    from app.services.checkout_offer_prerequisite import (
        CheckoutOfferPrerequisite,
        CheckoutOfferPrerequisiteError,
    )
    try:
        CheckoutOfferPrerequisite(db).require(
            authenticated_user_id=who,
            empresa_id=empresa,
            offer_code=offer_code,
            idempotency_key=key,
        )
    except CheckoutOfferPrerequisiteError:
        return True
    return False


class TestP104CEnterpriseCheckoutFailClosedRED(unittest.TestCase):
    def test_01_baseline_composer_checks_prerequisite_on_create_and_retry(self):
        for f in (COMPOSER, PREREQUISITE, CANDIDATE, READINESS):
            self.assertTrue(f.is_file(), 'P104C_BASELINE_FILE_MISSING_' + f.name)
        tree = ast.parse(COMPOSER.read_text(encoding='utf-8-sig'))
        cls = next((n for n in tree.body if isinstance(n, ast.ClassDef)
                    and n.name == 'CheckoutOfferOrderComposer'), None)
        self.assertIsNotNone(cls, 'P104C_COMPOSER_CLASS_MISSING')
        for method in ('iniciar_checkout_empresa', '_retry'):
            fn = next((n for n in cls.body if isinstance(n, ast.FunctionDef)
                       and n.name == method), None)
            self.assertIsNotNone(fn, 'P104C_COMPOSER_PATH_MISSING_' + method)
            call_names = [n.func.attr for n in ast.walk(fn)
                          if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
            self.assertIn('require', call_names, 'P104C_CHECKOUT_PREREQUISITE_NOT_IN_' + method)
            self.assertIn('CheckoutOfferPrerequisite', ast.dump(fn),
                          'P104C_LEGACY_PREREQUISITE_REMOVED_' + method)
        candidate = CANDIDATE.read_text(encoding='utf-8-sig')
        self.assertIn('checkout_autorizado', candidate)
        self.assertIn('enterprise-documental-diagnostic-one-time-company', candidate)

    def test_02_legacy_tax_report_and_unrelated_offer_behavior_preserved(self):
        from app.services.checkout_offer_prerequisite import (
            CheckoutOfferPrerequisite, CheckoutOfferPrerequisiteError,
        )
        missing = _ReadOnlyFakeDB()
        with self.assertRaises(CheckoutOfferPrerequisiteError):
            CheckoutOfferPrerequisite(missing).require(
                authenticated_user_id=11, empresa_id=21,
                offer_code=LEGACY, idempotency_key='legacy-no-intent',
            )
        self.assertEqual(missing.calls, 1)
        unrelated = _ReadOnlyFakeDB()
        self.assertIsNone(CheckoutOfferPrerequisite(unrelated).require(
            authenticated_user_id=11, empresa_id=21,
            offer_code='document-extract-company', idempotency_key='unchanged',
        ))
        self.assertEqual(unrelated.calls, 0)

    def test_03_enterprise_offer_without_durable_intent_must_be_denied(self):
        db = _ReadOnlyFakeDB()
        self.assertTrue(_check_denied(db),
                        'P104C_ENTERPRISE_ORDER_WITHOUT_INTENT_ACCEPTED')

    def test_04_enterprise_invalid_identity_and_replay_keys_must_be_denied(self):
        bad = []
        for changes in (
            {'who': 12}, {'empresa': 22}, {'who': True},
            {'empresa': True}, {'who': 0}, {'empresa': 0},
            {'key': ''}, {'key': 'wrong-replay-key'},
            {'key': 'bad key with spaces'},
        ):
            if not _check_denied(_ReadOnlyFakeDB(), **changes):
                bad.append(changes)
        self.assertEqual(bad, [], 'P104C_ENTERPRISE_INVALID_OR_UNBOUND_REPLAY_ACCEPTED')

    def test_05_enterprise_cannot_reuse_tax_intent_or_candidate_flag_as_authority(self):
        # Even a fake existing old tax-report intent must not grant Enterprise.
        forged = SimpleNamespace(
            user_id=11, empresa_id=21,
            offer_code=LEGACY, checkout_idempotency_key='reused-legacy',
            candidatura_comercial=True, checkout_autorizado=True,
        )
        self.assertTrue(_check_denied(_ReadOnlyFakeDB(forged), key='reused-legacy'),
                        'P104C_CROSS_VERTICAL_LEGACY_INTENT_REUSED_AS_ENTERPRISE')
        candidate_only = SimpleNamespace(candidatura_comercial=True,
                                         checkout_autorizado=False)
        self.assertTrue(_check_denied(_ReadOnlyFakeDB(candidate_only)),
                        'P104C_CANDIDACY_ONLY_ESCALATED_TO_CHECKOUT')


if __name__ == '__main__':
    print('SOLVERIS_P104C_ENTERPRISE_CHECKOUT_RED_START', flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestP104CEnterpriseCheckoutFailClosedRED
    )
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    expected = {'test_03_enterprise_offer_without_durable_intent_must_be_denied',
                'test_04_enterprise_invalid_identity_and_replay_keys_must_be_denied',
                'test_05_enterprise_cannot_reuse_tax_intent_or_candidate_flag_as_authority'}
    failed = {case._testMethodName for case, _ in outcome.failures}
    markers = ('P104C_ENTERPRISE_ORDER_WITHOUT_INTENT_ACCEPTED',
               'P104C_ENTERPRISE_INVALID_OR_UNBOUND_REPLAY_ACCEPTED',
               'P104C_CROSS_VERTICAL_LEGACY_INTENT_REUSED_AS_ENTERPRISE')
    passed_red = (outcome.testsRun == 5 and not outcome.errors
                  and len(outcome.failures) == 3 and failed == expected
                  and all(marker in detail for marker, (_, detail)
                          in zip(markers, sorted(outcome.failures,
                          key=lambda pair: pair[0]._testMethodName))))
    if outcome.wasSuccessful() and outcome.testsRun == 5:
        print('SOLVERIS_P104C_ENTERPRISE_CHECKOUT_GREEN', flush=True)
        sys.exit(0)
    if not passed_red:
        print('STOP: P104C_RED_NON_CAUSAL', flush=True)
        sys.exit(1)
    print('SOLVERIS_P104C_ENTERPRISE_CHECKOUT_RED_CAUSAL_CONFIRMED', flush=True)
    print('P104C_2_PASS_3_CAUSAL_RED_NO_COMMIT_NO_PUSH_NO_DEPLOY', flush=True)
    sys.exit(0)
