"""Focused submission tests only: no Docker, no database, no historical reruns."""
import contextlib
from datetime import datetime, timezone
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT/"tools") not in sys.path:sys.path.insert(0,str(ROOT/"tools"))
import b02_g5_v5_submission_runner as runner


class SubmissionDeltaTests(unittest.TestCase):
    def test_proponent_identity_is_not_claude_or_root(self):
        self.assertIn("GPT-6",runner.ACTOR)
        self.assertNotIn("/root",runner.ACTOR)
        self.assertNotIn("Claude",runner.ACTOR)
        self.assertEqual(runner.DECISION_ID,"B02-G5-V5-GPT6-submetida-v1")

    def test_only_submission_and_no_policy_write_or_review(self):
        s=json.loads((ROOT/runner.SUBMISSION).read_text(encoding="utf-8"))
        expected=runner.payload(s)
        sql=runner.commit_sql(expected)
        self.assertEqual(sql.count("INSERT INTO public.policy_decisions"),1)
        self.assertEqual(sql.count("COMMIT;"),1)
        self.assertNotIn("INSERT INTO public.policy_versions",sql)
        self.assertNotIn("INSERT INTO public.policy_activations",sql)
        self.assertNotIn("GRANT ",sql)
        self.assertIn("2026-10-30T13:00:00+00:00",sql)
        self.assertIn(runner.POLICY_RECORD_HASH,sql)
        self.assertEqual(expected["previous_decision_id"],None)
        self.assertEqual(expected["decision_event"],"submetida")
        self.assertEqual(expected["institutional_role"],"proponente_institucional")
        self.assertEqual(expected["evidence"]["mandate_addendum_git_blob"],
                         runner.BLOBS[runner.DESIGNATION])

    def test_pinned_issued_acts_match_exact_git_blobs(self):
        s=runner.sources()
        self.assertEqual(s["actor"],runner.ACTOR)
        self.assertEqual(s["policy"]["policy_hash"],runner.policy.POLICY_HASH)

    def test_independent_readback_requires_both_hashes(self):
        s=json.loads((ROOT/runner.SUBMISSION).read_text(encoding="utf8"))
        expected=runner.payload(s)
        row={**expected,"record_hash":"a"*64,"timestamp":"2026-10-30T00:20:00+00:00"}
        base=["BEGIN",runner.bridge.DATABASE+"|"+runner.bridge.ROLE+"|"+runner.bridge.ROLE,
              "0063_adr020_policy_activation_atomicity",
              json.dumps({"row":row,"hash_ok":True}),"1","1","2","ROLLBACK"]
        with patch.object(runner.owner,"psql",return_value=base) as psql:
            status,_=runner.independent_readback(expected)
        self.assertEqual(status,"PRESENT_EXACT")
        self.assertEqual(psql.call_args.args[1],runner.bridge.ROLE)
        base[3]=json.dumps({"row":row,"hash_ok":False})
        with patch.object(runner.owner,"psql",return_value=base):
            status,_=runner.independent_readback(expected)
        self.assertEqual(status,"CONFLICT")

    def test_single_commit_attempt_and_restricted_readback(self):
        submission=json.loads((ROOT/runner.SUBMISSION).read_text(encoding="utf8"))
        row={"record_hash":"a"*64}
        with patch.object(runner,"datetime",**{"now.return_value":datetime(2026,10,30,0,30,tzinfo=timezone.utc)}), \
             patch.object(runner.bridge,"managed_container",return_value=contextlib.nullcontext()), \
             patch.object(runner.owner,"psql",return_value=["COMMIT","B02_G5_V5_SUBMISSION_COMMIT_ACK"]) as psql, \
             patch.object(runner,"independent_readback",side_effect=[
                ("ABSENT",None),("PRESENT_EXACT",row)]) as readback:
            runner.execute(submission)
        psql.assert_called_once()
        self.assertEqual(psql.call_args.args[1],runner.owner.OWNER)
        self.assertEqual(readback.call_count,2)

    def test_network_failure_never_retries_even_if_record_is_present(self):
        submission=json.loads((ROOT/runner.SUBMISSION).read_text(encoding="utf8"))
        with patch.object(runner,"datetime",**{"now.return_value":datetime(2026,10,30,0,30,tzinfo=timezone.utc)}), \
             patch.object(runner.bridge,"managed_container",return_value=contextlib.nullcontext()), \
             patch.object(runner.owner,"psql",side_effect=RuntimeError("ACK_LOST")) as psql, \
             patch.object(runner,"independent_readback",side_effect=[
                ("ABSENT",None),("PRESENT_EXACT",{"record_hash":"a"*64})]) as readback:
            with self.assertRaisesRegex(RuntimeError,"STOP_G5_SUBMISSION_ACK_UNCERTAIN_MANUAL_RECONCILIATION"):
                runner.execute(submission)
        self.assertEqual(psql.call_count,1)
        self.assertEqual(readback.call_count,2)


if __name__=="__main__":
    unittest.main()
