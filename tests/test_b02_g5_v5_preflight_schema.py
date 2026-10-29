"""Regression for the canonical decision schema and complete G5 V5 preflight."""
import ast
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "tools" / "b02_g5_v5_physical_readonly_preflight.py"
MIGRATION = ROOT / "migrations" / "versions" / "0022_adr020_policy_foundation.py"


def decision_columns():
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_table" and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "policy_decisions"):
            return {
                col.args[0].value for col in node.args[1:]
                if isinstance(col, ast.Call)
                and isinstance(col.func, ast.Attribute)
                and col.func.attr == "Column"
                and col.args and isinstance(col.args[0], ast.Constant)
            }
    raise AssertionError("Canonical policy_decisions table not found")


def load_preflight():
    spec = importlib.util.spec_from_file_location("b02_g5_v5_physical_readonly_preflight", PREFLIGHT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Result:
    def __init__(self, value):
        self.value = value

    def one(self):
        return self.value

    def scalar_one(self):
        return self.value

    def mappings(self):
        return self

    def scalars(self):
        return self

    def all(self):
        return self.value


class ReadOnlyPreflightTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_preflight()
        self.engine = MagicMock()
        self.conn = self.engine.connect.return_value.__enter__.return_value

    def seed(self, divergent=0, total=37):
        vals = [
            None,
            (self.mod.DB, "solveris_b02_policy_writer", "solveris_b02_policy_writer"),
            self.mod.REV,
            (False, False, False, False, False, False),
            0,
            [{"hash_equivalent": True}, {"hash_equivalent": True}],
            [],
            ["policy_activation_executions", "policy_activations",
             "policy_activation_generations", "policy_activation_outbox_events", "policy_decisions"],
            {"total": total, "divergent": divergent},
        ]
        self.conn.execute.side_effect = [Result(x) for x in vals]

    def test_migration_has_actual_decision_columns(self):
        columns = decision_columns()
        self.assertTrue({"decision_id", "policy_id", "policy_version", "policy_hash", "record_hash"} <= columns)
        self.assertNotIn("policy_decision_id", columns)

    def test_complete_aggregate_not_limited_to_twenty_rows(self):
        self.seed(total=37)
        result = self.mod.inspect(self.engine)
        self.assertEqual(result["g5_v5_decision_rows"], 37)
        self.assertEqual(result["writes"], 0)
        sql = "\n".join(str(call.args[0]) for call in self.conn.execute.call_args_list)
        self.assertNotIn("policy_decision_id", sql)
        self.assertNotIn("LIMIT 20", sql)
        self.assertIn("count(*) FILTER", sql)
        self.assertIn("SET TRANSACTION READ ONLY", sql)
        self.conn.rollback.assert_called_once()

    def test_divergent_policy_hash_fails_closed(self):
        self.seed(divergent=1)
        with self.assertRaisesRegex(RuntimeError, "STOP_G5_DECISION_POLICY_HASH_CONFLICT"):
            self.mod.inspect(self.engine)


if __name__ == "__main__":
    unittest.main()
