"""Rollback-mode contracts; no PostgreSQL connection or institutional writes."""
import ast
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

RUNNER = Path(__file__).resolve().parents[1] / "tools" / "b02_g5_v5_policy_runner.py"
spec = importlib.util.spec_from_file_location("g5_v5_policy_runner_rollback", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class PolicyRollbackContractTests(TestCase):
    def test_physical_probe_does_not_require_fabricated_authorization(self):
        import sys
        with patch.object(sys, "argv", ["runner", "--probe-policy-rollback"]):
            with patch.object(runner, "candidate", return_value={"policy_version": 2}):
                with patch.object(runner, "execute") as execute:
                    with patch.object(runner, "authorize") as authorize:
                        runner.main()
        authorize.assert_not_called()
        execute.assert_called_once()
        args, kwargs = execute.call_args
        self.assertTrue(kwargs["rollback_probe"])
        self.assertEqual(args[2], {"policy_version_record_id": "B02-G5-V5-ROLLBACK-PROBE"})

    def test_real_commit_still_requires_existing_authorization_manifest(self):
        import sys
        with patch.object(sys, "argv", ["runner", "--execute-policy-only"]):
            with patch.object(runner, "candidate", return_value={"policy_version": 2}):
                with patch.object(runner, "execute") as execute:
                    with self.assertRaisesRegex(RuntimeError, "STOP_EXPLICIT_AUTHORIZATION_REQUIRED"):
                        runner.main()
        execute.assert_not_called()

    def test_rollback_exception_is_inside_outer_transaction(self):
        tree = ast.parse(RUNNER.read_text(encoding="utf-8"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
        txs = [
            n for n in ast.walk(function)
            if isinstance(n, ast.With)
            and any(isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Attribute)
                    and item.context_expr.func.attr == "begin"
                    for item in n.items)
        ]
        self.assertEqual(len(txs), 1)
        self.assertTrue(any(
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and isinstance(node.exc.func, ast.Name)
            and node.exc.func.id == "_PolicyRollbackProbe"
            for node in ast.walk(txs[0])
        ))
        self.assertTrue(any(
            isinstance(handler.type, ast.Name) and handler.type.id == "_PolicyRollbackProbe"
            for node in ast.walk(function) if isinstance(node, ast.Try)
            for handler in node.handlers
        ))

    def test_dry_run_remains_without_database_access(self):
        import sys
        with patch.object(sys, "argv", ["runner"]):
            with patch.object(runner, "candidate", return_value={"policy_version": 2}):
                with patch.object(runner, "execute") as execute:
                    runner.main()
        execute.assert_not_called()
