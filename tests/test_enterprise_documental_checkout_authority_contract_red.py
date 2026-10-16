"""P1-04C3 — contrato RED da autoridade transacional Enterprise.

Esta é uma prova de ausências, não uma autorização de venda. A P1-04C1
permanece fechada até ser provada a autorização da ordem e do despacho.
Nunca faz chamadas HTTP, migrations, INSERT, pagamentos ou alterações produtivas.
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "app/services/enterprise_documental_checkout_order_authority.py"
GUARD = ROOT / "app/services/checkout_offer_prerequisite.py"
COMPOSER = ROOT / "app/services/checkout_offer_order_composition.py"
DISPATCH = ROOT / "app/services/checkout_offer_one_time_dispatch.py"
WRITER = ROOT / "app/services/enterprise_documental_checkout_intent.py"
MIGRATION = ROOT / "migrations/versions/0061_enterprise_documental_checkout_intent.py"
MODEL = ROOT / "app/models.py"
OFFER = "enterprise-documental-diagnostic-one-time-company"
AUTH_CLASS = "EnterpriseDocumentalCheckoutOrderAuthority"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def method(path: Path, cls: str, name: str) -> ast.FunctionDef:
    tree = ast.parse(text(path))
    target = next((node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == cls), None)
    if target is None:
        raise AssertionError("P104C3_CLASS_ABSENT_" + cls)
    fn = next((node for node in target.body if isinstance(node, ast.FunctionDef)
               and node.name == name), None)
    if fn is None:
        raise AssertionError("P104C3_METHOD_ABSENT_" + name)
    return fn


class TestP104C3OrderAuthorityRED(unittest.TestCase):
    def test_01_current_enterprise_checkout_guard_is_closed(self):
        """A segurança ratificada P1-04C1 não pode desaparecer."""
        self.assertTrue(GUARD.is_file())
        source = text(GUARD)
        fn = method(GUARD, "CheckoutOfferPrerequisite", "require")
        self.assertIn("if offer_code == \"" + OFFER + "\":", source)
        self.assertIn("CheckoutOfferPrerequisiteError", ast.dump(fn))
        for name in ("iniciar_checkout_empresa", "_retry"):
            callsite = method(COMPOSER, "CheckoutOfferOrderComposer", name)
            self.assertIn("CheckoutOfferPrerequisite", ast.dump(callsite))
            self.assertIn("require", ast.dump(callsite))

    def test_02_durable_intent_is_not_in_itself_payment_authority(self):
        """O writer P1-04C2 nunca substitui o gate transacional P1-04C3."""
        for file in (WRITER, MIGRATION, MODEL):
            self.assertTrue(file.is_file(), "P104C3_BASELINE_MISSING_" + file.name)
        source = text(WRITER)
        self.assertIn("EnterpriseDocumentalCheckoutIntent", source)
        self.assertIn("checkout_autorizado\": False", source)
        self.assertNotIn("CheckoutOfferOrderComposer", source)
        self.assertNotIn("CheckoutOfferOneTimeDispatcher", source)
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".rollback(", source)
        self.assertIn("BEFORE UPDATE OR DELETE", text(MIGRATION))
        self.assertIn("enterprise_documental_checkout_intents", text(MODEL))

    def test_03_explicit_enterprise_transaction_authority_is_missing(self):
        self.assertTrue(AUTH.is_file(), "P104C3_TRANSACTION_AUTHORITY_MODULE_MISSING")
        body = ast.parse(text(AUTH))
        classes = {n.name for n in body.body if isinstance(n, ast.ClassDef)}
        self.assertIn(AUTH_CLASS, classes, "P104C3_AUTHORITY_CLASS_MISSING")
        func = method(AUTH, AUTH_CLASS, "require")
        self.assertTrue(func, "P104C3_AUTHORITY_REQUIRE_METHOD_MISSING")

    def test_04_create_and_retry_lack_enterprise_authority_hook(self):
        for name in ("iniciar_checkout_empresa", "_retry"):
            fn = method(COMPOSER, "CheckoutOfferOrderComposer", name)
            symbols = {node.id for node in ast.walk(fn) if isinstance(node, ast.Name)}
            self.assertIn(
                AUTH_CLASS, symbols,
                "P104C3_COMPOSER_ENTERPRISE_AUTHORITY_MISSING_" + name,
            )

    def test_05_payment_dispatch_lacks_enterprise_authority_revalidation(self):
        """Verificar sob lock ANTES do claim ou efeito do fornecedor de pagamentos."""
        fn = method(DISPATCH, "CheckoutOfferOneTimeDispatcher", "_claim_dispatch")
        symbols = {node.id for node in ast.walk(fn) if isinstance(node, ast.Name)}
        self.assertIn(
            AUTH_CLASS, symbols,
            "P104C3_PROVIDER_DISPATCH_ENTERPRISE_AUTHORITY_MISSING",
        )


if __name__ == "__main__":
    print("SOLVERIS_P104C3_TRANSACTION_AUTHORITY_RED_START", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestP104C3OrderAuthorityRED)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    expected = {
        "test_03_explicit_enterprise_transaction_authority_is_missing":
            "P104C3_TRANSACTION_AUTHORITY_MODULE_MISSING",
        "test_04_create_and_retry_lack_enterprise_authority_hook":
            "P104C3_COMPOSER_ENTERPRISE_AUTHORITY_MISSING_iniciar_checkout_empresa",
        "test_05_payment_dispatch_lacks_enterprise_authority_revalidation":
            "P104C3_PROVIDER_DISPATCH_ENTERPRISE_AUTHORITY_MISSING",
    }
    actual = {test._testMethodName: report for test, report in result.failures}
    causal_red = (
        result.testsRun == 5 and not result.errors
        and len(result.failures) == 3 and set(actual) == set(expected)
        and all(marker in actual[name] for name, marker in expected.items())
    )
    if causal_red:
        print("SOLVERIS_P104C3_RED_THREE_CAUSAL_GAPS_CONFIRMED", flush=True)
        print("P104C3_2_PASS_3_EXPECTED_RED_NO_PRODUCTIVE_CHANGE", flush=True)
        sys.exit(0)
    if result.wasSuccessful():
        print("STOP: P104C3_ALREADY_GREEN_NEW_REVIEW_REQUIRED", flush=True)
    else:
        print("STOP: P104C3_RED_NON_CAUSAL_OR_BASELINE_DRIFT", flush=True)
    sys.exit(1)
