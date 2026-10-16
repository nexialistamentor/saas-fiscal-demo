"""P1-04C2 RED: standalone durable documentary Enterprise checkout intent.

Read-only test. It does not grant checkout, publish an offer, commit, or use
payment providers. The guard implemented by P1-04C1 must remain closed.
"""
from __future__ import annotations

import ast
import importlib
from inspect import signature
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GUARD = ROOT / "app/services/checkout_offer_prerequisite.py"
COMPOSER = ROOT / "app/services/checkout_offer_order_composition.py"
CANDIDATE = ROOT / "app/services/enterprise_documental_commercial_candidate.py"
WRITER = ROOT / "app/services/enterprise_documental_checkout_intent.py"
MIGRATION = ROOT / "migrations/versions/0061_enterprise_documental_checkout_intent.py"
OFFER = "enterprise-documental-diagnostic-one-time-company"
LEGACY = "tax-report-one-time-company"
CAPABILITY = "enterprise.diagnostic.documental"


class _ReadOnlyDB:
    def __init__(self):
        self.queries = 0

    def scalar(self, _statement):
        self.queries += 1
        return None

    def __getattr__(self, name):
        if name in ("add", "flush", "commit", "rollback", "delete", "execute"):
            raise AssertionError("P104C2_UNEXPECTED_DB_MUTATION_" + name)
        raise AttributeError(name)


class TestP104C2DurableEnterpriseIntentRED(unittest.TestCase):
    def test_01_existing_enterprise_checkout_guard_stays_closed(self):
        for path in (GUARD, COMPOSER, CANDIDATE):
            self.assertTrue(path.is_file(), "P104C2_BASELINE_FILE_MISSING")
        guard_source = GUARD.read_text(encoding="utf-8-sig")
        self.assertIn(OFFER, guard_source)
        self.assertIn("raise CheckoutOfferPrerequisiteError()", guard_source)
        self.assertIn(LEGACY, guard_source)
        composer_source = COMPOSER.read_text(encoding="utf-8-sig")
        self.assertEqual(composer_source.count("CheckoutOfferPrerequisite(sessao).require("), 2)
        candidate_source = CANDIDATE.read_text(encoding="utf-8-sig")
        self.assertIn('"checkout_autorizado": False', candidate_source)

    def test_02_enterprise_denied_and_old_tax_gate_unchanged(self):
        from app.services.checkout_offer_prerequisite import (
            CheckoutOfferPrerequisite,
            CheckoutOfferPrerequisiteError,
        )
        for code, expected_queries in ((OFFER, 0), (LEGACY, 1)):
            db = _ReadOnlyDB()
            with self.assertRaises(CheckoutOfferPrerequisiteError):
                CheckoutOfferPrerequisite(db).require(
                    authenticated_user_id=11, empresa_id=21,
                    offer_code=code, idempotency_key="p104c2-test-only",
                )
            self.assertEqual(db.queries, expected_queries)
        db = _ReadOnlyDB()
        self.assertIsNone(CheckoutOfferPrerequisite(db).require(
            authenticated_user_id=11, empresa_id=21,
            offer_code="unrelated-document-offer", idempotency_key="key",
        ))
        self.assertEqual(db.queries, 0)

    def test_03_own_append_only_model_and_full_evidence_binding(self):
        from app import models
        model = getattr(models, "EnterpriseDocumentalCheckoutIntent", None)
        self.assertIsNotNone(model, "P104C2_INTENT_MODEL_MISSING")
        table = model.__table__
        self.assertEqual(table.name, "enterprise_documental_checkout_intents")
        expected = {
            "id", "checkout_idempotency_key", "user_id", "empresa_id",
            "relatorio_analise_id", "documento_fiscal_id", "offer_id",
            "offer_code", "offer_contract_version", "capability",
            "request_fingerprint", "xml_sha256", "created_at",
        }
        self.assertEqual(set(table.columns.keys()), expected)
        self.assertTrue(table.c.id.primary_key)
        for name in expected - {"id"}:
            self.assertFalse(table.c[name].nullable, "P104C2_NULLABLE_" + name)
        fks = {
            "user_id": "usuarios.id", "empresa_id": "empresas.id",
            "relatorio_analise_id": "relatorios_analise.id",
            "documento_fiscal_id": "documentos_fiscais.id",
            "offer_id": "checkout_offers.id",
        }
        for name, target in fks.items():
            self.assertEqual(
                {fk.target_fullname for fk in table.c[name].foreign_keys},
                {target}, "P104C2_FOREIGN_KEY_" + name,
            )
        self.assertEqual(table.c.checkout_idempotency_key.type.length, 255)
        self.assertEqual(table.c.request_fingerprint.type.length, 64)
        self.assertEqual(table.c.xml_sha256.type.length, 64)
        self.assertIsNotNone(table.c.created_at.server_default)
        from sqlalchemy import UniqueConstraint, CheckConstraint
        self.assertTrue(any(
            isinstance(c, UniqueConstraint)
            and {col.name for col in c.columns} == {"checkout_idempotency_key"}
            for c in table.constraints
        ) or table.c.checkout_idempotency_key.unique,
            "P104C2_IDEMPOTENCY_NOT_UNIQUE")
        check_text = " ".join(
            str(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)
        )
        self.assertIn(CAPABILITY, check_text, "P104C2_CAPABILITY_NOT_FIXED")
        self.assertIn(OFFER, check_text, "P104C2_OFFER_NOT_FIXED")

    def test_04_narrow_alembic_migration_append_only_postgresql(self):
        self.assertTrue(MIGRATION.is_file(), "P104C2_INTENT_MIGRATION_MISSING")
        source = MIGRATION.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        assigned = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                name_node = node.targets[0] if isinstance(node, ast.Assign) else node.target
                if isinstance(name_node, ast.Name):
                    val_node = node.value
                    if isinstance(val_node, ast.Constant):
                        assigned[name_node.id] = val_node.value
        self.assertEqual(assigned.get("revision"), "0061_enterprise_documental_checkout_intent")
        self.assertEqual(assigned.get("down_revision"), "0060_item_fiscal_st_observado_xml")
        self.assertIn("enterprise_documental_checkout_intents", source)
        self.assertEqual(source.count("op.create_table("), 1)
        self.assertIn("BEFORE UPDATE OR DELETE", source)
        self.assertIn("CREATE TRIGGER", source)
        self.assertIn("CREATE FUNCTION", source)
        self.assertIn("DROP TRIGGER", source)
        self.assertIn("DROP FUNCTION", source)
        self.assertIn("op.drop_table(", source)
        forbidden = (
            'op.alter_column("ordens_checkout"',
            'op.alter_column("tax_report_checkout_intents"',
            'op.alter_column("mei_competencia_checkout_intents"',
            'op.drop_table("ordens_checkout"',
        )
        self.assertFalse(any(item in source for item in forbidden),
                         "P104C2_MIGRATION_TOUCHES_SHARED_PAYMENT")

    def test_05_writer_api_verifies_candidate_and_never_opens_checkout(self):
        self.assertTrue(WRITER.is_file(), "P104C2_INTENT_WRITER_MISSING")
        module = importlib.import_module("app.services.enterprise_documental_checkout_intent")
        for symbol in (
            "EnterpriseDocumentalCheckoutIntent",
            "EnterpriseDocumentalCheckoutIntentError",
            "EnterpriseDocumentalCheckoutIntentResult",
        ):
            self.assertTrue(hasattr(module, symbol), "P104C2_API_MISSING_" + symbol)
        service = module.EnterpriseDocumentalCheckoutIntent
        self.assertEqual(tuple(signature(service.persist).parameters), (
            "self", "user_id", "empresa_id", "relatorio_id",
            "offer_code", "checkout_idempotency_key", "request_fingerprint",
            "xml_bytes",
        ), "P104C2_WRITER_SIGNATURE_DIVERGENT")
        source = WRITER.read_text(encoding="utf-8-sig")
        self.assertIn("avaliar_candidatura_comercial_documental", source)
        self.assertIn("checkout_offer_snapshot", source)
        self.assertIn("compare_digest", source)
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".rollback(", source)
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module or "")
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
        forbidden = (
            "checkout_offer_order_composition", "mercado_pago", "grant",
            "tax_report_checkout_intent", "mei_competencia_checkout_intent",
        )
        self.assertFalse(any(any(word in module for word in forbidden)
                             for module in imports),
                         "P104C2_WRITER_IMPORTS_PAYMENT_AUTHORITY")


if __name__ == "__main__":
    print("SOLVERIS_P104C2_DURABLE_INTENT_RED_START", flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TestP104C2DurableEnterpriseIntentRED
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    expected = {
        "test_03_own_append_only_model_and_full_evidence_binding":
            "P104C2_INTENT_MODEL_MISSING",
        "test_04_narrow_alembic_migration_append_only_postgresql":
            "P104C2_INTENT_MIGRATION_MISSING",
        "test_05_writer_api_verifies_candidate_and_never_opens_checkout":
            "P104C2_INTENT_WRITER_MISSING",
    }
    actual = {case._testMethodName: detail for case, detail in result.failures}
    if result.wasSuccessful() and result.testsRun == 5:
        print("SOLVERIS_P104C2_DURABLE_INTENT_GREEN", flush=True)
        sys.exit(0)
    if (result.testsRun == 5 and not result.errors
            and set(actual) == set(expected)
            and all(marker in actual[name] for name, marker in expected.items())):
        print("SOLVERIS_P104C2_DURABLE_INTENT_RED_CAUSAL_CONFIRMED", flush=True)
        print("P104C2_2_PASS_3_CAUSAL_RED_NO_COMMIT_NO_PUSH_NO_DEPLOY", flush=True)
        sys.exit(0)
    print("STOP: P104C2_RED_NON_CAUSAL", flush=True)
    sys.exit(1)
