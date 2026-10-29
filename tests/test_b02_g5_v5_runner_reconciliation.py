"""Isolated, read-only tests of G5 V5 reconciliation and authorization guards."""
import importlib.util
import pathlib
import unittest
from unittest.mock import MagicMock

RUNNER = pathlib.Path(__file__).resolve().parents[1] / "tools" / "b02_g5_v5_policy_runner.py"
spec = importlib.util.spec_from_file_location("b02_g5_v5_policy_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

class ReconcileTests(unittest.TestCase):
    def engine(self, row):
        engine = MagicMock()
        conn = engine.connect.return_value.__enter__.return_value
        conn.execute.return_value.mappings.return_value.one_or_none.return_value = row
        return engine, conn

    def test_absent(self):
        engine, conn = self.engine(None)
        self.assertEqual(runner.reconcile(engine, "B02-G5-V5"), ("ABSENT", None))
        conn.rollback.assert_called_once()

    def test_exact_identity_is_not_misreported_as_full_equality(self):
        row = {"policy_version_record_id": "B02-G5-V5", "policy_hash": runner.POLICY_HASH,
               "policy_type": "activation_authority", "record_hash": "a" * 64}
        engine, _ = self.engine(row)
        self.assertEqual(runner.reconcile(engine, "B02-G5-V5")[0], "PRESENT_IDENTITY")

    def test_conflicting_hash(self):
        row = {"policy_version_record_id": "B02-G5-V5", "policy_hash": "b" * 64,
               "policy_type": "activation_authority", "record_hash": "a" * 64}
        engine, _ = self.engine(row)
        self.assertEqual(runner.reconcile(engine, "B02-G5-V5")[0], "CONFLICT")

    def test_no_automatic_retry_on_unknown_commit(self):
        # Reconciliation is a read-only classifier, never a write or retry.
        engine, conn = self.engine(None)
        runner.reconcile(engine, "B02-G5-V5")
        self.assertEqual(conn.execute.call_count, 1)
        self.assertFalse(conn.commit.called)

if __name__ == "__main__":
    unittest.main()
