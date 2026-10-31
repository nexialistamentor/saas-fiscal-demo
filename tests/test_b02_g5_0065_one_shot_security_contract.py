"""0065 candidate security regression only: no database, no migration, no authority."""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py"


def candidate_sql():
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "_SQL"
                   for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError("0065 immutable SQL literal not found")


class OneShotDirectInsertBoundary(unittest.TestCase):
    def test_restricted_writer_cannot_insert_reservation_directly(self):
        sql = candidate_sql()
        table = "public.b02_g5_operational_approval_uses"
        self.assertIn(f"REVOKE ALL ON {table} FROM PUBLIC;", sql)
        self.assertIn(f"REVOKE ALL ON {table} FROM solveris_b02_writer;", sql)
        self.assertIn(f"GRANT SELECT ON {table} TO solveris_b02_writer;", sql)
        self.assertNotRegex(sql, r"GRANT\s+(?:INSERT|ALL)\b[^;]*\bTO\s+solveris_b02_writer;")

    def test_reservation_only_via_owner_guarded_definer(self):
        sql = candidate_sql()
        reserve = sql.split(
            "CREATE FUNCTION public.b02_g5_reserve_operational_decision(", 1
        )[1].split("CREATE FUNCTION public.b02_g5_assert_one_shot()", 1)[0]
        self.assertIn("RETURNS text LANGUAGE plpgsql SECURITY DEFINER", reserve)
        self.assertIn("SET search_path=pg_catalog,pg_temp", reserve)
        self.assertIn("session_user<>'solveris_b02_writer'", reserve)
        self.assertIn("current_user<>'solveris_test'", reserve)
        self.assertIn("public.b02g5_native_profile()<>'REAL_PROFILE_COMPILED_APPROVED_ROOTS'", reserve)
        self.assertIn("INSERT INTO public.b02_g5_operational_approval_uses", reserve)
        self.assertIn("pg_current_xact_id()::text", reserve)
        self.assertIn(
            "GRANT EXECUTE ON FUNCTION public.b02_g5_reserve_operational_decision"
            "(varchar,varchar,char,char) TO solveris_b02_writer;", sql)
        self.assertNotIn("SECURITY DEFINER", sql.split(
            "CREATE FUNCTION public.b02_g5_assert_one_shot()", 1
        )[1].split("CREATE OR REPLACE FUNCTION public.b02g5_capability_manifest()", 1)[0])

    def test_unchanged_one_shot_signed_precommit_boundaries(self):
        sql = candidate_sql()
        self.assertIn("approval_id varchar(128) PRIMARY KEY", sql)
        self.assertIn("release_id varchar(128) NOT NULL UNIQUE", sql)
        self.assertIn("assigned_txid text NOT NULL UNIQUE", sql)
        self.assertIn("PERFORM public.b02_g5_assert_one_shot();", sql)
        self.assertIn("PERFORM public.b02g5_assert_transaction_capability();", sql)
        self.assertIn("jsonb_build_object('g5_one_shot',reservation)", sql)
        self.assertIn("IF n<>2 THEN RAISE EXCEPTION 'G5_ONESHOT_TWO_DOCUMENTS_REQUIRED'", sql)
        self.assertIn("DEFERRABLE INITIALLY DEFERRED FOR EACH ROW", sql)
        self.assertNotIn("ON CONFLICT", sql.split(
            "CREATE FUNCTION public.b02_g5_reserve_operational_decision(", 1
        )[1].split("CREATE FUNCTION public.b02_g5_assert_one_shot()", 1)[0].split("INSERT INTO", 1)[-1])


if __name__ == "__main__":
    unittest.main()
