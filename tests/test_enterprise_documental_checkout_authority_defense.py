"""P1-04C3 defensive GREEN: read-only binding + hard provider hold.

Test only, synthetic fake sessions. No payment provider or production DB access.
"""
from __future__ import annotations

import ast
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.models import CheckoutOffer, DocumentoFiscal, Empresa, RelatorioAnalise
from app.services import enterprise_documental_checkout_order_authority as subject

ROOT = Path(__file__).resolve().parents[1]
CODE = "enterprise-documental-diagnostic-one-time-company"
CAP = "enterprise.diagnostic.documental"
KEY = "c3-test-unique-key"
FP = "a" * 64
SHA = "b" * 64


def _intent():
    return SimpleNamespace(
        id=91, checkout_idempotency_key=KEY, user_id=11, empresa_id=21,
        relatorio_analise_id=31, documento_fiscal_id=71, offer_id=41,
        offer_code=CODE, offer_contract_version=2, capability=CAP,
        request_fingerprint=FP, xml_sha256=SHA,
        created_at=datetime(2026, 10, 16),
    )


def _offer():
    return SimpleNamespace(
        id=41, codigo=CODE, contract_version=2, estado="published",
        vertical="tax", commercial_model="one_time", subject_type="company",
        checkout_mode="automatic", moeda="BRL", billing_period=None,
        usage_unit="diagnostic", usage_limit=1, capabilities=(CAP,),
        preco=Decimal("39.90"),
    )


class FakeDB:
    def __init__(self):
        self.intent = _intent()
        self.company = SimpleNamespace(user_id=11)
        self.report = SimpleNamespace(id=31, user_id=11, empresa_id=21,
                                      analysis_type="xml_analise", status="ok", fingerprint=FP)
        self.document = SimpleNamespace(id=71, empresa_id=21, usuario_id=11,
                                        conteudo_sha256=SHA)
        self.offer = SimpleNamespace(id=41)
        self.scalar_calls = 0
        self.get_calls = 0
        self.writes = 0

    def scalar(self, stmt):
        self.scalar_calls += 1
        return self.intent if self.scalar_calls == 1 else self.offer

    def get(self, model, primary_key):
        self.get_calls += 1
        return {Empresa: self.company, RelatorioAnalise: self.report,
                DocumentoFiscal: self.document}.get(model)

    def __getattr__(self, method):
        if method in ("add", "flush", "commit", "rollback", "delete", "merge"):
            self.writes += 1
            raise AssertionError("NO_WRITE_AUTHORITY_" + method)
        raise AttributeError(method)


def _require(db, **changes):
    args = dict(authenticated_user_id=11, empresa_id=21, offer_code=CODE,
                idempotency_key=KEY, offer_id=41, offer_contract_version=2,
                capabilities=(CAP,))
    args.update(changes)
    with patch.object(subject, "checkout_offer_snapshot", return_value=_offer()), \
         patch.object(subject, "validar_vinculo_documento_relatorio", return_value=True):
        return subject.EnterpriseDocumentalCheckoutOrderAuthority(db).require(**args)


def _method(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError("NO_METHOD_" + name)


class P104C3Defense(unittest.TestCase):
    def test_01_legacy_and_unrelated_offers_never_touch_db(self):
        for code in ("tax-report-one-time-company", "document-extract-company"):
            db = FakeDB()
            self.assertIsNone(_require(db, offer_code=code))
            self.assertEqual((db.scalar_calls, db.get_calls, db.writes), (0, 0, 0))

    def test_02_realistic_valid_intent_only_produces_readonly_verification(self):
        db = FakeDB()
        self.assertIsNone(_require(db))
        self.assertEqual((db.scalar_calls, db.get_calls, db.writes), (2, 3, 0))

    def test_03_persisted_intent_is_never_dispatch_permission(self):
        db = FakeDB()
        with self.assertRaises(subject.EnterpriseDocumentalCheckoutOrderAuthorityError):
            _require(db, for_dispatch=True)
        self.assertEqual((db.scalar_calls, db.get_calls, db.writes), (2, 3, 0))

    def test_04_all_broken_intent_bindings_fail_closed(self):
        changes = ("user_id", "empresa_id", "offer_id", "offer_contract_version",
                   "relatorio_analise_id", "documento_fiscal_id", "capability",
                   "request_fingerprint", "xml_sha256", "checkout_idempotency_key")
        for field in changes:
            db = FakeDB()
            setattr(db.intent, field, "wrong")
            with self.subTest(field=field):
                with self.assertRaises(subject.EnterpriseDocumentalCheckoutOrderAuthorityError):
                    _require(db)
                self.assertEqual(db.writes, 0)

    def test_05_invalid_input_is_rejected_before_io(self):
        for changed in (dict(authenticated_user_id=True), dict(empresa_id=0),
                        dict(offer_id=False), dict(offer_contract_version=-1),
                        dict(idempotency_key="bad key"), dict(capabilities=("tax.report",)),
                        dict(for_dispatch=1)):
            db = FakeDB()
            with self.subTest(case=str(changed)):
                with self.assertRaises(subject.EnterpriseDocumentalCheckoutOrderAuthorityError):
                    _require(db, **changed)
                self.assertEqual((db.scalar_calls, db.get_calls, db.writes), (0, 0, 0))

    def test_06_report_and_company_drift_fail_closed(self):
        for where, field, value in (("company", "user_id", 99),
                                    ("report", "status", "erro"),
                                    ("report", "fingerprint", "c" * 64),
                                    ("document", "conteudo_sha256", "d" * 64)):
            db = FakeDB()
            setattr(getattr(db, where), field, value)
            with self.subTest(where=where, field=field):
                with self.assertRaises(subject.EnterpriseDocumentalCheckoutOrderAuthorityError):
                    _require(db)
                self.assertEqual(db.writes, 0)

    def test_07_order_and_offer_drift_fail_closed(self):
        order = SimpleNamespace(
            user_id=11, empresa_id=21, offer_id=41, offer_code=CODE,
            contract_version=2, idempotency_key=KEY, vertical="tax",
            commercial_model="one_time", subject_type="company", subject_id=21,
            estado="pending", moeda="BRL", valor=Decimal("39.90"),
            billing_period=None, usage_unit="diagnostic", usage_limit=1,
        )
        self.assertIsNone(_require(FakeDB(), order=order))
        order.valor = Decimal("1.00")
        with self.assertRaises(subject.EnterpriseDocumentalCheckoutOrderAuthorityError):
            _require(FakeDB(), order=order)

    def test_08_create_retry_and_locked_claim_order_before_mutation(self):
        composition = ROOT / "app/services/checkout_offer_order_composition.py"
        dispatch = ROOT / "app/services/checkout_offer_one_time_dispatch.py"
        for name in ("iniciar_checkout_empresa", "_retry"):
            fn = _method("app/services/checkout_offer_order_composition.py", name)
            self.assertIn("EnterpriseDocumentalCheckoutOrderAuthority", ast.dump(fn))
            self.assertIn("CheckoutOfferPrerequisite", ast.dump(fn))
        claim = _method("app/services/checkout_offer_one_time_dispatch.py", "_claim_dispatch")
        source = ast.get_source_segment(dispatch.read_text(encoding="utf-8-sig"), claim)
        self.assertIsNotNone(source)
        a = source.index("EnterpriseDocumentalCheckoutOrderAuthority(session).require(")
        b = source.index("order.checkout_dispatch_claimed_at = database_now")
        self.assertLess(a, b)
        load = _method("app/services/checkout_offer_one_time_dispatch.py", "_load_dispatch_context")
        src = ast.get_source_segment(dispatch.read_text(encoding="utf-8-sig"), load)
        self.assertIn("snapshot.offer_code ==", src)
        self.assertIn("raise CheckoutOfferOneTimeDispatchError()", src)
        self.assertIn("if offer_code == \"enterprise-documental-diagnostic-one-time-company\":",
                      (ROOT / "app/services/checkout_offer_prerequisite.py").read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
