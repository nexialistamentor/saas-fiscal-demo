"""Focused mock tests for G5 V2 institutional chain inventory; no physical DB writes."""
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("g5_v2_preflight",ROOT/"tools"/"b02_g5_v5_physical_readonly_preflight.py")
p=importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Result:
    def __init__(self,val): self.val=val
    def one(self): return self.val
    def mappings(self): return self
    def one_or_none(self): return self.val
    def all(self): return self.val


class G5ChainInventoryDeltaTests(unittest.TestCase):
    def setUp(self):
        self.engine=MagicMock()
        self.connection=self.engine.connect.return_value.__enter__.return_value
        self.row={"policy_version_record_id":"B02-G5-V5-policy-v2",
            "policy_hash":p.POLICY_HASH,
            "record_hash":"fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9",
            "hash_ok":True}

    def seed(self,decisions=(),bootstraps=(),activations=(),row=None):
        self.connection.execute.side_effect=[
            Result(None),
            Result((p.DB,"solveris_b02_policy_writer","solveris_b02_policy_writer",p.REV)),
            Result(self.row if row is None else row),
            Result(list(decisions)),Result(list(bootstraps)),Result(list(activations))
        ]

    def test_physical_policy_present_but_first_real_submission_missing(self):
        self.seed()
        result=p._g5_v2_chain_inventory(self.engine)
        self.assertEqual(result["status"],"PHYSICAL_G5_V2_CHAIN_READ_ONLY")
        self.assertEqual(result["decision_count"],0)
        self.assertEqual(result["next_required_decision_event"],"submetida")
        self.assertEqual(result["activation_count"],0)
        self.assertEqual(result["writes"],0)
        sql="\\n".join(str(c.args[0]) for c in self.connection.execute.call_args_list)
        self.assertIn("SET TRANSACTION READ ONLY",sql)
        self.assertNotIn("INSERT INTO",sql)
        self.connection.rollback.assert_called_once()

    def test_conflicting_hash_blocks_before_chain_claim(self):
        self.seed(row={**self.row,"hash_ok":False})
        with self.assertRaisesRegex(RuntimeError,"STOP_G5_V2_COMMITTED_POLICY_IDENTITY"):
            p._g5_v2_chain_inventory(self.engine)

    def test_out_of_order_or_unproven_event_never_accepted(self):
        decision={"decision_id":"d2","decision_event":"ratificada",
            "previous_decision_id":"d1","institutional_role":"autoridade_constitucional_final",
            "actor":"someone","record_hash":"f"*64,"policy_hash":p.POLICY_HASH,
            "hash_ok":True,"evidence_present":True}
        self.seed(decisions=(decision,))
        with self.assertRaisesRegex(RuntimeError,"STOP_G5_CHAIN_EVENTS_NOT_EXACT"):
            p._g5_v2_chain_inventory(self.engine)

    def test_role_and_missing_evidence_fail_closed(self):
        decision={"decision_id":"d1","decision_event":"submetida",
            "previous_decision_id":None,"institutional_role":"proponente_institucional",
            "actor":"","record_hash":"f"*64,"policy_hash":p.POLICY_HASH,
            "hash_ok":True,"evidence_present":False}
        self.seed(decisions=(decision,))
        with self.assertRaisesRegex(RuntimeError,"STOP_G5_CHAIN_ROLE_OR_EVIDENCE"):
            p._g5_v2_chain_inventory(self.engine)


if __name__=="__main__":
    unittest.main()
