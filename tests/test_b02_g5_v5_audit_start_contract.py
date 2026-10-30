"""Bounded tests for G5 V5 audit-start only. No database, Docker or G4 execution."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import b02_g5_v5_institutional_audit_start_runner as runner


class AuditStartContract(unittest.TestCase):
    def test_event_is_start_only(self):
        body = runner.expected_payload()
        self.assertEqual(body["decision_event"], "auditoria_iniciada")
        self.assertEqual(body["institutional_role"], "auditor_independente")
        self.assertEqual(body["previous_decision_id"], "B02-G5-V5-GPT6-submetida-v1")
        self.assertNotEqual(body["actor"], runner.PROPONENT)
        self.assertEqual(body["policy_version"], 2)
        self.assertEqual(body["policy_hash"], "007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf")
        self.assertEqual(body["evidence"]["previous_decision_record_hash"], runner.PREVIOUS_HASH)
        self.assertEqual(body["evidence"]["audit_result"], "NOT_ISSUED_NOT_PREJUDGED")
        self.assertTrue(body["evidence"]["no_operational_approval_or_signature"])

    def test_sql_uses_exact_owner_and_predecessor_and_single_commit(self):
        sql = runner.commit_sql(runner.expected_payload())
        self.assertIn("session_user<>'solveris_test'", sql)
        self.assertIn("clock_timestamp()>=TIMESTAMPTZ '2026-11-08T00:00:00+00:00'", sql)
        self.assertIn("STOP_G5_AUDIT_START_PREDECESSOR_MISMATCH", sql)
        self.assertIn("STOP_G5_AUDIT_START_DECISION_ALREADY_EXISTS", sql)
        self.assertIn("STOP_G5_AUDIT_START_PRECOMMIT_HASH", sql)
        self.assertEqual(sql.count("INSERT INTO public.policy_decisions"), 1)
        self.assertEqual(sql.count("\nCOMMIT;"), 1)
        self.assertNotIn("INSERT INTO public.policy_activations", sql)
        self.assertNotIn("UPDATE public.policy_decisions", sql)
        self.assertNotIn("CREATE OR REPLACE", sql)
        self.assertNotIn("GRANT ", sql)

    def test_non_operational_and_bridge_allowlist(self):
        self.assertIn(runner.PATH, runner.bridge.ALLOWED)
        self.assertEqual(runner.owner.OWNER, "solveris_test")
        self.assertEqual(runner.bridge.ROLE, "solveris_b02_policy_writer")
        self.assertNotEqual(runner.DECISION_ID, runner.PREVIOUS_ID)
        self.assertNotEqual(runner.REVIEWER, runner.PROPONENT)
        self.assertEqual(len(runner.SOURCE_BLOBS), 2)

if __name__ == "__main__":
    unittest.main()
