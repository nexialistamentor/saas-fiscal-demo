"""B02 R5 G5-specific negative guards: preserve five prior RED/GREEN tests."""
from __future__ import annotations
import sys
import unittest
from unittest.mock import patch
import test_b02_r5_authenticity_before_flush_red as original

def malformed_stage(provenance):
    c = original.FakeConnection()
    binding = {"mode":"LOCAL_CAS_INCORPORATION","acquisition_execution_id":"e",
               "attempt_number":1}
    if provenance is not _MISSING:
        binding["provenance"] = provenance
    with patch.dict(sys.modules, {"app.models":original.fake_models()}):
        return c, original.mod.stage_completion(
            c, binding=binding, start={}, read_cas=lambda:original.RAW,
            build_evidence=lambda *_: {},
        )
_MISSING=object()

class R5ExactOriginGuardRED(unittest.TestCase):
    def test_missing_provenance_rejected_before_dml(self):
        conn=original.FakeConnection()
        with patch.dict(sys.modules, {"app.models":original.fake_models()}):
            with self.assertRaisesRegex(original.mod.AcquisitionEvidenceError,
                                        "EXPLICIT_SYNTHETIC_CLASS_REQUIRED"):
                original.mod.stage_completion(
                    conn,binding={"mode":"LOCAL_CAS_INCORPORATION",
                                  "acquisition_execution_id":"e","attempt_number":1},
                    start={},read_cas=lambda:original.RAW,build_evidence=lambda *_:{},
                )
        self.assertFalse(any(v.startswith("insert:") for v in conn.log))

    def test_false_text_not_boolean_rejected(self):
        conn=original.FakeConnection()
        with patch.dict(sys.modules, {"app.models":original.fake_models()}):
            with self.assertRaisesRegex(original.mod.AcquisitionEvidenceError,
                                        "EXPLICIT_SYNTHETIC_CLASS_REQUIRED"):
                original.mod.stage_completion(
                    conn,binding={"mode":"LOCAL_CAS_INCORPORATION",
                                  "provenance":{"synthetic_only":"false"},
                                  "acquisition_execution_id":"e","attempt_number":1},
                    start={},read_cas=lambda:original.RAW,build_evidence=lambda *_:{},
                )
        self.assertFalse(any(v.startswith("insert:") for v in conn.log))

    def test_current_g4_policy_and_signed_origin_bindings_required_in_readback(self):
        class TracingConnection(original.FakeConnection):
            query=None
            def execute(self, statement, parameters=None):
                if "SELECT COUNT(*)" in str(statement) and "artifact_verification_records" in str(statement):
                    self.query=str(statement)
                    self.parameters=dict(parameters or {})
                return super().execute(statement,parameters)
        conn=TracingConnection()
        def accepted(c,*_): c.auth_staged=True
        original.exercise(conn,authenticity=accepted,real=True)
        self.assertIsNotNone(conn.query)
        for source_requirement in (
            "public.b02_policy_grant(", "g4_origin_report_binding",
            "authorized_verifier_hash", "assigned_txid",
            "pg_current_xact_id()", "acquisition_execution_id",
            "doc->'g4'->'verifier'"):
            with self.subTest(name=source_requirement):
                self.assertIn(source_requirement,conn.query)
        self.assertEqual(conn.parameters["artifact_id"],"a")
        self.assertEqual(conn.parameters["digest"],original.DIGEST)

    def test_legacy_five_tests_unchanged_contract_not_edited(self):
        # Frozen previous test is not rewritten, skipped, or removed.
        from pathlib import Path
        path=Path(original.__file__)
        self.assertEqual(path.name,"test_b02_r5_authenticity_before_flush_red.py")
        text=path.read_text(encoding="utf-8")
        for original_test in (
            "test_real_without_authorized_stager_rejected_before_writes",
            "test_favorable_authenticated_row_before_deferred_flush",
            "test_no_inserted_authenticity_row_stops_before_flush",
            "test_callback_cannot_be_used_for_synthetic_unit",
            "test_legacy_synthetic_without_callback_remains_unchanged"):
            self.assertIn("def "+original_test+"(",text)

if __name__=="__main__":
    unittest.main()
