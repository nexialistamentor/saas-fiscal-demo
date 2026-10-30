"""Focused result-only checks; no PostgreSQL, G4, Docker or prior suites."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import b02_g5_v5_institutional_audit_result_runner as result


def own_act(event="auditada_favoravelmente"):
    return {
        "issued_at_utc": "2026-10-30T16:00:00Z",
        "rationale": "Revisao documental propria; gates operacionais separados.",
        "findings": {"documental": "favoravel condicionado", "operacional": "nao homologado"},
        "policy": {
            "policy_type": "activation_authority",
            "policy_id": result.policy.POLICY_ID,
            "policy_version": 2, "policy_hash": result.policy.POLICY_HASH,
        },
        "institutional_role": "auditor_independente",
        "actor": result.start.REVIEWER, "event": event,
        "previous_decision_id": result.START_ID,
        "previous_decision_record_hash": result.START_HASH,
        "evidence": {"previous_decision_record_hash": result.START_HASH},
    }


class ResultGate(unittest.TestCase):
    def test_favorable_and_unfavorable_are_not_predetermined(self):
        for event in ("auditada_favoravelmente", "auditada_desfavoravelmente"):
            d = own_act(event)
            p = result.expected_payload(d, event,
                "B02_G5_V5_AUDITOR_RESULTADO.json", "a" * 40, "b" * 40)
            self.assertEqual(p["decision_event"], event)
            self.assertEqual(p["institutional_role"], "auditor_independente")
            self.assertEqual(p["actor"], result.start.REVIEWER)
            self.assertEqual(p["previous_decision_id"], result.START_ID)
            self.assertEqual(p["evidence"]["previous_decision_record_hash"], result.START_HASH)
            self.assertEqual(p["policy_version"], 2)
            self.assertEqual(len(p["idempotency_key"]), 56)

    def test_one_insert_only_no_activation_and_no_retry_sql(self):
        d = own_act()
        p = result.expected_payload(d, d["event"],
            "B02_G5_V5_AUDITOR_RESULTADO.json", "a" * 40, "b" * 40)
        sql = result.commit_sql(p)
        self.assertEqual(sql.count("INSERT INTO public.policy_decisions"), 1)
        self.assertEqual(sql.count("\nCOMMIT;"), 1)
        self.assertIn("STOP_G5_RESULT_PREDECESSOR", sql)
        self.assertIn("2026-11-08T00:00:00Z", sql)
        self.assertNotIn("INSERT INTO public.policy_activations", sql)
        self.assertNotIn("UPDATE public.policy_decisions", sql)
        self.assertNotIn("GRANT ", sql)

    def test_unknown_or_missing_act_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "STOP_G5_V5_AUDIT_RESULT"):
            result.load_issued_act("../fake.json", "a" * 40, "b" * 40)
        with self.assertRaisesRegex(RuntimeError, "STOP_G5_V5_AUDIT_RESULT"):
            result.load_issued_act("B02_G5_V5_RESULTADO.json", "bad", "b" * 40)

    def test_exact_readback_and_conflicting_count(self):
        p = result.expected_payload(own_act(), "auditada_favoravelmente",
            "B02_G5_V5_AUDITOR_RESULTADO.json", "a" * 40, "b" * 40)
        startrow = {
            "decision_id": result.START_ID, "record_hash": result.START_HASH,
            "actor": result.start.REVIEWER, "decision_event": "auditoria_iniciada",
            "policy_hash": result.policy.POLICY_HASH
        }
        got = ["BEGIN",
            result.bridge.DATABASE + "|" + result.bridge.ROLE + "|" + result.bridge.ROLE,
            "0063_adr020_policy_activation_atomicity",
            json.dumps({"row": startrow, "hash_ok": True}), "null", "2", "ROLLBACK"]
        with patch.object(result.owner, "psql", return_value=got):
            self.assertEqual(result.independent_readback(p), ("ABSENT", None))
        got[5] = "4"
        with patch.object(result.owner, "psql", return_value=got):
            self.assertEqual(result.independent_readback(p), ("CONFLICT", None))

    def test_bridge_is_connected(self):
        self.assertIn(result.PATH, result.bridge.ALLOWED)
        self.assertEqual(result.owner.OWNER, "solveris_test")
        self.assertEqual(result.bridge.ROLE, "solveris_b02_policy_writer")
        self.assertNotEqual(result.start.REVIEWER, result.start.PROPONENT)


if __name__ == "__main__":
    unittest.main()
