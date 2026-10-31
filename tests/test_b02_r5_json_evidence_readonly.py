"""Five synthetic tests of the B02 R5 read-only JSON semantics probe.

No database, Docker, G4 origin, policy activation, or protected data used.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/"tools/b02_g5_v5_physical_readonly_preflight.py"
spec=importlib.util.spec_from_file_location("b02_r5_json_probe",PATH)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class Result:
    def __init__(self, value):self.value=value
    def one(self):return self.value
    def scalar_one(self):return self.value
    def mappings(self):return self

class Connection:
    def __init__(self,*,storage="json",db=None,revision=None,valid=True):
        self.storage=storage
        self.db=db or probe.DB
        self.revision=revision or probe.REV
        self.valid=valid
        self.commands=[]
        self.rolled_back=False
    def execute(self,statement,args=None):
        sql=str(statement)
        self.commands.append(sql)
        if sql=="SET TRANSACTION READ ONLY":return Result(None)
        if "SELECT current_database(),session_user,current_user" in sql:
            return Result((self.db,"solveris_b02_policy_writer",
                           "solveris_b02_policy_writer",self.revision))
        if "pg_catalog.pg_attribute" in sql:return Result(self.storage)
        if "CAST(:evidence AS json)::jsonb" in sql:
            if not args or "synthetic-readonly-type-probe" not in args.get("evidence",""):
                raise AssertionError("UNEXPECTED_REAL_EVIDENCE")
            return Result({
                "synthetic_false":self.valid,
                "exact_g4_binding":self.valid,
                "exact_verifier_hash":self.valid,
            })
        raise AssertionError("UNEXPECTED_SQL_IN_SYNTHETIC_PROBE")
    def rollback(self):self.rolled_back=True

class Engine:
    def __init__(self,c):self.c=c
    def connect(self):
        conn=self.c
        class Context:
            def __enter__(self):return conn
            def __exit__(self,*args):return False
        return Context()

class R5JSONEvidenceReadOnly(unittest.TestCase):
    def test_json_column_predicates_are_cast_and_readonly(self):
        c=Connection(storage="json")
        out=probe._r5_json_evidence_readonly(Engine(c))
        self.assertEqual(out["status"],"R5_JSON_EVIDENCE_PG17_READ_ONLY_PREDICATES_PASS")
        self.assertEqual(out["artifact_verification_evidence_storage"],"json")
        self.assertEqual((out["writes"],out["grants"],out["ddl"]),(0,0,0))
        self.assertEqual(c.commands[0],"SET TRANSACTION READ ONLY")
        self.assertTrue(c.rolled_back)
        self.assertTrue(out["type_safe_boolean_match"])
        self.assertTrue(out["type_safe_origin_binding_match"])
        self.assertFalse(out["g5_release_permission"])
        self.assertEqual(out["protected_reads_of_artifact_rows"],0)

    def test_jsonb_column_compatibility_remains_supported(self):
        out=probe._r5_json_evidence_readonly(Engine(Connection(storage="jsonb")))
        self.assertEqual(out["artifact_verification_evidence_storage"],"jsonb")

    def test_non_json_storage_fails_closed(self):
        c=Connection(storage="text")
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_JSON_UNRECOGNIZED_STORAGE_TYPE"):
            probe._r5_json_evidence_readonly(Engine(c))
        self.assertEqual(len(c.commands),3)

    def test_wrong_database_or_revision_rejected_before_catalog(self):
        for conn in (Connection(db="postgres"),Connection(revision="0064_adr020")):
            with self.subTest(db=conn.db,revision=conn.revision):
                with self.assertRaisesRegex(RuntimeError,"STOP_R5_JSON_IDENTITY_REVISION"):
                    probe._r5_json_evidence_readonly(Engine(conn))
                self.assertEqual(len(conn.commands),2)

    def test_false_origin_comparison_cannot_pass(self):
        c=Connection(valid=False)
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_JSON_EXPLICIT_CAST_PREDICATE"):
            probe._r5_json_evidence_readonly(Engine(c))
        self.assertTrue(all("GRANT " not in x and "INSERT INTO" not in x for x in c.commands))

if __name__=="__main__":
    unittest.main()
