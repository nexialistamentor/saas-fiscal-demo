"""Focused physical-inventory contract; source-only tests, no DB or old suites."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import b02_g5_v5_current_inventory_readonly as inv


def fixture():
    return {
      "database":inv.bridge.DATABASE,
      "session_user":inv.bridge.ROLE,
      "current_user":inv.bridge.ROLE,
      "alembic_revision":"0063_adr020_policy_activation_atomicity",
      "policies":[
        {"version":1,"id":"B02-57982-policy-v1","policy_hash":inv.HASH_V1,
         "record_hash":"1"*64,"record_hash_valid":True},
        {"version":2,"id":"B02-G5-V5-policy-v2","policy_hash":inv.HASH_V2,
         "record_hash":inv.POLICY_RECORD_V2,"record_hash_valid":True}],
      "decisions":[
        {"version":2,"id":"B02-G5-V5-GPT6-submetida-v1",
         "hash":inv.SUBMITTED_HASH,"hash_valid":True,"event":"submetida"},
        {"version":2,"id":"B02-G5-V5-GPT6-auditoria-iniciada-v1",
         "hash":inv.START_HASH,"hash_valid":True,"event":"auditoria_iniciada"}],
      "bootstraps":[],"activations":[],"executions":[],"generations":[],"outbox":[]
    }


class InventoryTests(unittest.TestCase):
    def test_inventory_sql_is_read_only_and_all_versions(self):
        sql=inv.SQL
        self.assertIn("BEGIN READ ONLY;",sql)
        self.assertIn("\nROLLBACK;",sql)
        self.assertNotIn("INSERT INTO",sql)
        self.assertNotIn("UPDATE public.",sql)
        self.assertNotIn("DELETE FROM",sql)
        self.assertNotIn("DO $$",sql)
        self.assertIn("public.policy_activations",sql)
        self.assertIn("public.policy_activation_generations",sql)
        self.assertIn("public.policy_activation_outbox_events",sql)
        self.assertIn("public.policy_decisions",sql)
        self.assertIn("public.bootstrap_authority_records",sql)
        self.assertIn("b02_g5_operational_approval_uses",sql)
        self.assertIn("B02-05ede-activation-v3",sql)

    def test_no_activation_is_not_interpreted_as_disappeared(self):
        result=inv.classify(fixture())
        self.assertEqual(result["classification"]["2"]["activation_count"],0)
        self.assertEqual(result["version_next_free_candidate"],3)
        self.assertIn("NOT_INFERRED",result["eligibility"])
        self.assertEqual(result["database_writes"],0)

    def test_existing_v1_activation_is_preserved(self):
        sample=fixture()
        sample["activations"].append({"version":1,"id":"B02-57982-activation-v1",
                                      "hash":"b"*64,"state":"activa"})
        result=inv.classify(sample)
        self.assertEqual(result["classification"]["1"]["activation_count"],1)
        self.assertEqual(result["classification"]["2"]["activation_count"],0)
        self.assertEqual(result["classification"]["1"]["activations"],["B02-57982-activation-v1"])

    def test_known_start_or_policy_hash_drift_stops(self):
        for subject in ("policy","submission","start"):
            sample=fixture()
            if subject=="policy":sample["policies"][1]["record_hash"]="0"*64
            elif subject=="submission":sample["decisions"][0]["hash"]="0"*64
            else:sample["decisions"][1]["hash_valid"]=False
            with self.assertRaises(RuntimeError):
                inv.classify(sample)

    def test_wrong_database_and_ambiguous_inventory_stop(self):
        sample=fixture()
        sample["database"]="postgres"
        with self.assertRaisesRegex(RuntimeError,"WRONG_DB_OR_ROLE"):
            inv.classify(sample)
        sample=fixture()
        sample["decisions"]=[sample["decisions"][0]]*101
        with self.assertRaisesRegex(RuntimeError,"TOO_MANY_ROWS"):
            inv.classify(sample)

    def test_bridge_is_allowlisted_without_new_privileges(self):
        self.assertIn(inv.PATH, inv.bridge.ALLOWED)
        self.assertEqual(inv.owner.OWNER,"solveris_test")
        self.assertEqual(inv.bridge.ROLE,"solveris_b02_policy_writer")
        self.assertNotIn("SOLVERIS_B02_POLICY_WRITER_DSN",inv.SQL)


if __name__=="__main__":unittest.main()
