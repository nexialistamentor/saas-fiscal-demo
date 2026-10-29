"""Unit contracts for the G5 V5 transaction caller; no physical DB writes."""
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

P = Path(__file__).resolve().parents[1] / "tools" / "b02_g5_v5_atomic_transaction_harness.py"
spec = importlib.util.spec_from_file_location("b02_g5_v5_atomic_transaction_harness", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REQUEST = {
    "execution": {"policy_activation_execution_id": "e1"},
    "activation": {"policy_activation_id": "a1"},
    "generation_id": "g1", "outbox_id": "o1",
    "provenance": {},
}

class AtomicCallerTests(TestCase):
    def engine(self):
        engine = MagicMock()
        engine.begin.return_value.__enter__.return_value = MagicMock()
        return engine

    def test_rollback_probe_reconciles_absent(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": False}), patch.object(mod, "reconcile_unit", return_value="ABSENT") as recon:
            result = mod.run(engine, REQUEST, commit=False)
        self.assertEqual(result["status"], "ROLLBACK_RECONCILED")
        recon.assert_called_once()

    def test_rollback_probe_detects_persisted_records(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={}), patch.object(mod, "reconcile_unit", return_value="PARTIAL_CONFLICT"):
            with self.assertRaisesRegex(mod.Stop, "ROLLBACK_NOT_ABSENT"):
                mod.run(engine, REQUEST, commit=False)

    def test_intermediate_failure_does_not_retry(self):
        engine = self.engine()
        with patch.object(mod, "stage", side_effect=ValueError("middle failure")) as stage, patch.object(mod, "reconcile_unit", return_value="ABSENT"):
            with self.assertRaisesRegex(mod.Stop, "TRANSACTION_FAILED_RECONCILIATION_ABSENT"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_unknown_commit_ack_does_not_retry(self):
        engine = self.engine()
        engine.begin.return_value.__exit__.side_effect = OSError("unknown commit ACK")
        with patch.object(mod, "stage", return_value={"reused": False}) as stage, patch.object(mod, "reconcile_unit", return_value="PRESENT_FOUR_RECORDS_REQUIRES_EXACT_EVIDENCE_CHECK"):
            with self.assertRaisesRegex(mod.Stop, "TRANSACTION_FAILED_RECONCILIATION_PRESENT_FOUR_RECORDS"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_unknown_commit_and_unavailable_reconciliation(self):
        engine = self.engine()
        engine.begin.return_value.__exit__.side_effect = OSError("unknown commit ACK")
        with patch.object(mod, "stage", return_value={}) as stage, patch.object(mod, "reconcile_unit", side_effect=OSError("db unavailable")):
            with self.assertRaisesRegex(mod.Stop, "UNKNOWN_STOP_NO_RETRY"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_successful_commit_requires_independent_reconciliation(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": False}) as stage, patch.object(mod, "reconcile_unit", return_value="PRESENT_FOUR_RECORDS_REQUIRES_EXACT_EVIDENCE_CHECK"):
            result = mod.run(engine, REQUEST, commit=True)
        self.assertEqual(result["status"], "PRESENT_FOUR_RECORDS_REQUIRES_EXACT_EVIDENCE_CHECK")
        stage.assert_called_once()

    def test_re_delivery_is_delegated_to_existing_idempotent_service(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": True}) as stage, patch.object(mod, "reconcile_unit", return_value="PRESENT_FOUR_RECORDS_REQUIRES_EXACT_EVIDENCE_CHECK"):
            result = mod.run(engine, REQUEST, commit=True)
        self.assertTrue(result["staged"]["reused"])
        stage.assert_called_once()

    def test_stage_rejects_incomplete_request(self):
        conn = MagicMock()
        with patch.object(mod, "assert_writer"):
            with self.assertRaisesRegex(mod.Stop, "EXACT_REQUEST_FIELDS_REQUIRED"):
                mod.stage(conn, {"execution": {}})
