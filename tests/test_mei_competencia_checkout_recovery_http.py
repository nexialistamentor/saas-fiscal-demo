"""HTTP recovery boundary with isolated authentication and storage."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.routes import imposto_router as routes
from app.services.mei_competencia_checkout_recovery import (
    MeiCompetenciaCheckoutRecoveryNotFoundError,
    MeiCompetenciaCheckoutRecoveryConflictError,
    MeiCompetenciaCheckoutRecoveryStorageError,
)


class RecoveryHttp(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(routes.router, prefix="/imposto")
        self.app.dependency_overrides[routes.get_db] = lambda: object()
        self.app.dependency_overrides[routes.get_usuario_atual] = lambda: SimpleNamespace(id=9)
        self.client = TestClient(self.app)
        self.url = "/imposto/mei/77/checkout-recovery?competencia=202609"

    def test_authentication_blocks_service_execution(self):
        def denied():
            raise HTTPException(status_code=401)
        self.app.dependency_overrides[routes.get_usuario_atual] = denied
        with patch.object(routes, "MeiCompetenciaCheckoutRecovery") as service:
            self.assertEqual(self.client.get(self.url).status_code, 401)
            service.assert_not_called()

    def test_authenticated_identity_and_competence_reach_service(self):
        with patch.object(routes, "MeiCompetenciaCheckoutRecovery") as service:
            service.return_value.resolve.return_value = dict(
                estado="paid", competencia="202609", autorizado=True,
                checkout_url=None, checkout_idempotency_key="synthetic-key")
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["autorizado"])
            service.return_value.resolve.assert_called_once_with(
                user_id=9, empresa_id=77, competencia="202609")

    def test_domain_errors_remain_distinct_and_do_not_leak_details(self):
        for error, status in (
            (MeiCompetenciaCheckoutRecoveryNotFoundError, 404),
            (MeiCompetenciaCheckoutRecoveryConflictError, 409),
            (MeiCompetenciaCheckoutRecoveryStorageError, 503),
        ):
            with self.subTest(status=status):
                with patch.object(routes, "MeiCompetenciaCheckoutRecovery") as service:
                    service.return_value.resolve.side_effect = error("private-storage-detail")
                    response = self.client.get(self.url)
                    self.assertEqual(response.status_code, status)
                    self.assertNotIn("private-storage-detail", response.text)
