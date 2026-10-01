"""Synthetic SQLite recovery tests; no external providers."""

from datetime import datetime
from decimal import Decimal
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models as m
from app.services.mei_competencia_checkout_recovery import (
    MeiCompetenciaCheckoutRecovery as Recovery,
    MeiCompetenciaCheckoutRecoveryNotFoundError as NotFound,
    MeiCompetenciaCheckoutRecoveryConflictError as Conflict,
)


class RecoveryBehavior(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        m.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add(m.User(id=1, email="synthetic@test.invalid", hashed_password="unused"))
        self.db.add(m.Empresa(id=77, user_id=1, cnpj="12345678000195",
            regime_tributario="mei", status_empresa="ativa"))
        self.db.add(m.CheckoutOffer(id=1, codigo="mei-das-one-time-company",
            nome_publico="Synthetic MEI", vertical="tax", commercial_model="one_time",
            subject_type="company", estado="published", moeda="BRL",
            preco=Decimal("39.90"), usage_unit="competence", usage_limit=1,
            contract_version=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def order(self, number=1, competencia="202609", paid=False):
        key = f"synthetic-recovery-{number}"
        order = m.OrdemCheckout(id=number, user_id=1, empresa_id=77,
            offer_id=1, offer_code="mei-das-one-time-company", contract_version=1,
            vertical="tax", commercial_model="one_time", subject_type="company",
            subject_id=77, valor=Decimal("39.90"), moeda="BRL",
            estado="paid" if paid else "pending", idempotency_key=key,
            usage_unit="competence", usage_limit=1,
            provider_order_id=f"synthetic-pref-{number}",
            checkout_url="https://checkout.example.invalid/synthetic",
            payment_id=f"synthetic-payment-{number}" if paid else None)
        self.db.add(order)
        self.db.add(m.OrdemCheckoutCapability(ordem_id=number, codigo="mei.das"))
        self.db.add(m.MeiCompetenciaCheckoutIntent(user_id=1, empresa_id=77,
            competencia=competencia, capability="mei.das",
            offer_code=order.offer_code, checkout_idempotency_key=key))
        if paid:
            self.db.add(m.Pagamento(user_id=1, ordem_checkout_id=number,
                idempotency_key=key, valor=order.valor, status="approved",
                confirmado_em=datetime.utcnow()))
            self.db.add(m.MeiCompetenciaAuthorityBinding(ordem_id=number,
                empresa_id=77, competencia=competencia, capability="mei.das"))
        self.db.commit()
        return order

    def recover(self, **changes):
        return Recovery(self.db).resolve(**(dict(user_id=1, empresa_id=77,
            competencia="202609") | changes))

    def test_pending_recovers_original_checkout_without_authority(self):
        order = self.order()
        result = self.recover()
        self.assertEqual(result.estado, "pending")
        self.assertFalse(result.autorizado)
        self.assertEqual(result.checkout_idempotency_key, order.idempotency_key)
        self.assertEqual(result.checkout_url, order.checkout_url)
        self.assertFalse(self.db.new or self.db.dirty or self.db.deleted)

    def test_paid_recovers_authority_without_new_checkout(self):
        self.order(paid=True)
        result = self.recover()
        self.assertEqual(result.estado, "paid")
        self.assertTrue(result.autorizado)
        self.assertIsNone(result.checkout_url)

    def test_other_competence_is_not_recovered(self):
        self.order(paid=True)
        with self.assertRaises(NotFound):
            self.recover(competencia="202610")

    def test_other_user_is_not_recovered(self):
        self.order(paid=True)
        with self.assertRaises(NotFound):
            self.recover(user_id=2)

    def test_paid_label_without_binding_or_payment_is_blocked(self):
        order = self.order()
        order.estado = "paid"
        self.db.commit()
        with self.assertRaises(Conflict):
            self.recover()

    def test_valid_paid_purchase_prevents_repurchase_after_newer_pending(self):
        self.order(paid=True)
        self.order(number=2)
        self.assertEqual(self.recover().estado, "paid")

    def test_unsafe_checkout_url_is_blocked(self):
        order = self.order()
        order.checkout_url = "http://checkout.example.invalid/synthetic"
        self.db.commit()
        with self.assertRaises(Conflict):
            self.recover()
