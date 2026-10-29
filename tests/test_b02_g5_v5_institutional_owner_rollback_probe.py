"""Tests owner-only rollback SQL and independent readonly reconciliation."""
import importlib.util
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch, call

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
import sys
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import b02_g5_v5_institutional_owner_rollback_probe as probe


class OwnerRollbackProbeTests(unittest.TestCase):
    def test_sql_is_strictly_rollback_only(self):
        sql = probe.make_rollback_sql({"policy_id": probe.policy.POLICY_ID})
        self.assertIn("BEGIN;", sql)
        self.assertIn("INSERT INTO public.policy_versions", sql)
        self.assertIn("RETURNING policy_hash,record_hash", sql)
        self.assertIn("ROLLBACK;\nSELECT 'B02_G5_V5_OWNER_ROLLBACK_ACK'", sql)
        self.assertNotIn("COMMIT;", sql)
        self.assertNotIn("GRANT ", sql)
        self.assertNotIn("SET ROLE ", sql)
        self.assertIn("public.b02_json_hash(body)", sql)

    def test_sql_rejects_delimiter_collision(self):
        with self.assertRaisesRegex(RuntimeError,"STOP_PAYLOAD_DELIMITER_COLLISION"):
            probe.make_rollback_sql({"x": "$b02g5_v5_body$"})

    def test_authoritative_catalog_preflight_rejects_nonowner(self):
        with patch.object(probe,"psql", return_value=["BEGIN",probe.bridge.DATABASE+"|postgres|postgres",
                                probe.policy.POLICY_HASH,"postgres","0","ROLLBACK"]):
            with self.assertRaisesRegex(RuntimeError,"STOP_POLICY_OWNER_IDENTITY_SCHEMA_OR_VERSION"):
                probe.owner_preflight()

    def test_postrollback_requires_zero_v5_and_preserved_g4(self):
        with patch.object(probe,"psql",return_value=["BEGIN","0","0","2","ROLLBACK"]) as psql:
            self.assertTrue(probe.independent_absence())
            self.assertEqual(psql.call_args.args[1],probe.bridge.ROLE)
        with patch.object(probe,"psql",return_value=["BEGIN","1","0","2","ROLLBACK"]):
            with self.assertRaisesRegex(RuntimeError,"STOP_POLICY_PROBE_POSTREAD_CONFLICT"):
                probe.independent_absence()

    def test_main_success_runs_single_attempt_and_readback(self):
        with patch.object(probe.bridge,"validate_checkout") as guard, \
             patch.object(probe.bridge,"managed_container",return_value=nullcontext()), \
             patch.object(probe.policy,"candidate",return_value={"policy_id":probe.policy.POLICY_ID}), \
             patch.object(probe,"owner_preflight"), \
             patch.object(probe,"psql",return_value=["BEGIN","ROLLBACK","B02_G5_V5_OWNER_ROLLBACK_ACK"]) as sql, \
             patch.object(probe,"independent_absence") as reconcile:
            probe.main()
        guard.assert_called_once_with(probe.PATH)
        self.assertEqual(sql.call_count,1)
        self.assertEqual(sql.call_args.args[1],probe.OWNER)
        reconcile.assert_called_once()

    def test_main_failed_insert_never_retries_and_reconciles(self):
        with patch.object(probe.bridge,"validate_checkout"), \
             patch.object(probe.bridge,"managed_container",return_value=nullcontext()), \
             patch.object(probe.policy,"candidate",return_value={"policy_id":probe.policy.POLICY_ID}), \
             patch.object(probe,"owner_preflight"), \
             patch.object(probe,"psql",side_effect=RuntimeError("SIMULATED_SQL_ERROR")) as sql, \
             patch.object(probe,"independent_absence") as reconcile:
            with self.assertRaisesRegex(RuntimeError,"SIMULATED_SQL_ERROR"):
                probe.main()
        self.assertEqual(sql.call_count,1)
        reconcile.assert_called_once()


if __name__=="__main__":
    unittest.main()
