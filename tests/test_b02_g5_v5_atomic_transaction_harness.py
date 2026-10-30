"""Unit contracts for the G5 V5 transaction caller; no physical DB writes."""
import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

P = Path(__file__).resolve().parents[1] / "tools" / "b02_g5_v5_atomic_transaction_harness.py"
spec = importlib.util.spec_from_file_location("b02_g5_v5_atomic_transaction_harness", P)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

REQUEST = {
    "execution": {"policy_activation_execution_id": "e1"},
    "activation": {"policy_activation_id": "a1"},
    "generation_id": "g1", "outbox_id": "o1",
    "provenance": {},
}

class AtomicCallerTests(TestCase):
    def engine(self):
        engine = MagicMock()
        engine.begin.return_value.__enter__.return_value = MagicMock()
        return engine

    def test_rollback_probe_reconciles_absent(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": False}), patch.object(mod, "reconcile_unit", return_value="ABSENT") as recon:
            result = mod.run(engine, REQUEST, commit=False)
        self.assertEqual(result["status"], "ROLLBACK_RECONCILED")
        self.assertEqual(recon.call_count, 2)

    def test_rollback_probe_detects_persisted_records(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={}), patch.object(mod, "reconcile_unit", side_effect=["ABSENT","PARTIAL_CONFLICT"]):
            with self.assertRaisesRegex(mod.Stop, "ROLLBACK_CHANGED_BASELINE"):
                mod.run(engine, REQUEST, commit=False)

    def test_intermediate_failure_does_not_retry(self):
        engine = self.engine()
        with patch.object(mod, "stage", side_effect=ValueError("middle failure")) as stage, patch.object(mod, "reconcile_unit", return_value="ABSENT"):
            with self.assertRaisesRegex(mod.Stop, "TRANSACTION_FAILED_RECONCILIATION_ABSENT"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_unknown_commit_ack_does_not_retry(self):
        engine = self.engine()
        engine.begin.return_value.__exit__.side_effect = OSError("unknown commit ACK")
        with patch.object(mod, "stage", return_value={"reused": False}) as stage, patch.object(mod, "reconcile_unit", side_effect=["ABSENT","PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"]):
            with self.assertRaisesRegex(mod.Stop, "TRANSACTION_FAILED_RECONCILIATION_PRESENT_FOUR_RECORDS"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_unknown_commit_and_unavailable_reconciliation(self):
        engine = self.engine()
        engine.begin.return_value.__exit__.side_effect = OSError("unknown commit ACK")
        with patch.object(mod, "stage", return_value={}) as stage, patch.object(mod, "reconcile_unit", side_effect=["ABSENT",OSError("db unavailable")]):
            with self.assertRaisesRegex(mod.Stop, "UNKNOWN_STOP_NO_RETRY"):
                mod.run(engine, REQUEST, commit=True)
        stage.assert_called_once()

    def test_successful_commit_requires_independent_reconciliation(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": False}) as stage, patch.object(mod, "reconcile_unit", return_value="PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"):
            result = mod.run(engine, REQUEST, commit=True)
        self.assertEqual(result["status"], "PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED")
        stage.assert_called_once()

    def test_re_delivery_is_delegated_to_existing_idempotent_service(self):
        engine = self.engine()
        with patch.object(mod, "stage", return_value={"reused": True}) as stage, patch.object(mod, "reconcile_unit", return_value="PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"):
            result = mod.run(engine, REQUEST, commit=True)
        self.assertTrue(result["staged"]["reused"])
        stage.assert_called_once()

    def test_rollback_reused_existing_unit_preserves_baseline(self):
        engine = self.engine()
        status = "PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED"
        with patch.object(mod, "stage", return_value={"reused": True}), patch.object(mod, "reconcile_unit", return_value=status):
            result = mod.run(engine, REQUEST, commit=False)
        self.assertEqual(result["status"], "ROLLBACK_RECONCILED")
        self.assertTrue(result["staged"]["reused"])

    def test_partial_baseline_blocks_staging(self):
        engine = self.engine()
        with patch.object(mod, "stage") as stage, patch.object(mod, "reconcile_unit", return_value="PARTIAL_CONFLICT"):
            with self.assertRaisesRegex(mod.Stop, "PREEXISTING_UNIT_CONFLICT"):
                mod.run(engine, REQUEST, commit=False)
        stage.assert_not_called()

    def test_stage_rejects_incomplete_request(self):
        conn = MagicMock()
        with patch.object(mod, "assert_writer"):
            with self.assertRaisesRegex(mod.Stop, "EXACT_REQUEST_FIELDS_REQUIRED"):
                mod.stage(conn, {"execution": {}})

    def test_reconciliation_requires_canonical_record_hashes_and_read_only_tx(self):
        import inspect
        source=inspect.getsource(mod.reconcile_unit)
        self.assertIn('SET TRANSACTION READ ONLY', source)
        self.assertIn('RECORD_HASH_CONFLICT', source)
        self.assertEqual(source.count("public.b02_json_hash(to_jsonb(t)-'record_hash')"), 4)
        for table in ("policy_activation_executions", "policy_activations",
                      "policy_activation_generations", "policy_activation_outbox_events"):
            self.assertIn("FROM public."+table+" t", source)
        self.assertIn("hashes_valid is not True", source)

    def test_reconciliation_rejects_wrong_links(self):
        from unittest.mock import MagicMock
        from sqlalchemy import select
        e={"policy_activation_execution_id":"e1","policy_decision_id":"d1",
           "policy_decision_record_hash":"dh","policy_id":"p1","policy_version":2,
           "policy_hash":"ph","record_hash":"eh","state":"concluida"}
        a=dict(e,policy_activation_id="a1",record_hash="ah",
               policy_activation_execution_record_hash="eh",state="activa")
        g=dict(a,policy_activation_generation_id="g1",policy_activation_record_hash="ah",record_hash="gh",
               is_complete=True,provenance={"source":"verified"})
        o=dict(g,policy_activation_outbox_event_id="o1",
               policy_activation_generation_hash="gh",provenance={"source":"verified"})
        def check(rows, hashes_valid=True):
            engine=MagicMock()
            conn=engine.connect.return_value.__enter__.return_value
            conn.execute.return_value.mappings.return_value.one_or_none.side_effect=rows
            conn.execute.return_value.scalar_one.return_value=hashes_valid
            import sys, types
            from sqlalchemy import Table, Column, MetaData, String
            metadata=MetaData()
            fake_models=types.ModuleType("app.models")
            fake_atomic=types.ModuleType("app.models_policy_activation_atomicity")
            for module,attr,name,key in (
                (fake_models,"PolicyActivationExecution","policy_activation_executions","policy_activation_execution_id"),
                (fake_models,"PolicyActivation","policy_activations","policy_activation_id"),
                (fake_atomic,"PolicyActivationGeneration","policy_activation_generations","policy_activation_generation_id"),
                (fake_atomic,"PolicyActivationOutboxEvent","policy_activation_outbox_events","policy_activation_outbox_event_id")):
                table=Table(name,metadata,Column(key,String,primary_key=True))
                setattr(module,attr,type(attr,(),{"__table__":table}))
            with patch.object(mod,"assert_writer"),patch.dict(sys.modules,{
                    "app.models":fake_models,
                    "app.models_policy_activation_atomicity":fake_atomic}):
                return mod.reconcile_unit(engine,"e1","a1","g1","o1")
        self.assertEqual(check([e,a,g,o]),"PRESENT_FOUR_RECORDS_EXACT_LINKS_VERIFIED")
        self.assertEqual(check([e,a,g,o], hashes_valid=False),"RECORD_HASH_CONFLICT")
        self.assertEqual(check([e,a,g,o], hashes_valid=None),"RECORD_HASH_CONFLICT")
        broken=dict(o,policy_activation_generation_hash="wrong")
        self.assertEqual(check([e,a,g,broken]),"GENERATION_HASH_LINK_CONFLICT")
        broken_a=dict(a,policy_activation_execution_record_hash="wrong")
        self.assertEqual(check([e,broken_a,g,o]),"EXECUTION_HASH_LINK_CONFLICT")
        self.assertEqual(check([e,a,g,None]),"PARTIAL_CONFLICT")
