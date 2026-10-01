"""Recovery boundary for MEI purchases; no provider or production access."""

import ast
import importlib
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "app/services/mei_competencia_checkout_recovery.py"


class NoDatabaseAccess:
    def __getattr__(self, name):
        raise AssertionError("Invalid recovery input accessed storage")


class MeiCompetenciaCheckoutRecoveryContract(unittest.TestCase):
    def service_module(self):
        self.assertTrue(SERVICE.is_file(), "MEI checkout recovery service is absent")
        return importlib.import_module("app.services.mei_competencia_checkout_recovery")

    def test_invalid_identity_and_competence_fail_before_storage(self):
        module = self.service_module()
        service = module.MeiCompetenciaCheckoutRecovery(NoDatabaseAccess())
        valid = dict(user_id=1, empresa_id=77, competencia="202609")
        for changes in (
            {"user_id": True}, {"user_id": 0}, {"empresa_id": -1},
            {"empresa_id": "77"}, {"competencia": "202613"},
            {"competencia": "202600"}, {"competencia": "2026-09"},
            {"competencia": None},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(module.MeiCompetenciaCheckoutRecoveryConflictError):
                    service.resolve(**(valid | changes))

    def test_recovery_has_no_write_or_provider_authority(self):
        self.assertTrue(SERVICE.is_file(), "MEI checkout recovery service is absent")
        tree = ast.parse(SERVICE.read_text(encoding="utf-8-sig"))
        forbidden_calls = {"commit", "flush", "add", "add_all", "delete", "execute"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, forbidden_calls)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                         else [alias.name for alias in node.names])
                for name in names:
                    self.assertFalse(any(token in name.lower() for token in
                                         ("mercadopago", "serpro", "requests", "httpx")))

    def test_authenticated_competence_recovery_route_exists(self):
        source = (ROOT / "app/routes/imposto_router.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        matches = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if (isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Attribute)
                    and decorator.func.attr == "get" and decorator.args
                    and isinstance(decorator.args[0], ast.Constant)
                    and decorator.args[0].value == "/mei/{empresa_id}/checkout-recovery"):
                    matches.append(node)
        self.assertEqual(len(matches), 1, "Authenticated MEI recovery GET route is absent")
        endpoint = ast.get_source_segment(source, matches[0])
        self.assertIn("get_usuario_atual", endpoint)
        self.assertIn("competencia", endpoint)
        self.assertIn(".resolve(", endpoint)


if __name__ == "__main__":
    unittest.main()
