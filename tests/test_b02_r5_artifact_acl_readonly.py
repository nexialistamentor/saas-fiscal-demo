"""Synthetic-only read-only R5 artifact ACL checks; never opens PostgreSQL."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

MODULE=Path(__file__).resolve().parents[1]/"tools"/"b02_g5_v5_physical_readonly_preflight.py"
spec=importlib.util.spec_from_file_location("b02_r5_artifact_acl_probe",MODULE)
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

TABLES=(
    "artifact_verification_records","normative_artifacts",
    "acquisition_mode_bindings","noncredential_acquisition_receipts",
    "noncredential_sanitization_verifications","acquisition_executions",
)

class Result:
    def __init__(self,data):self.data=data
    def one(self):return self.data
    def one_or_none(self):return self.data
    def scalar_one(self):return self.data
    def mappings(self):return self
    def all(self):return self.data

class Connection:
    def __init__(self,*,insert=False,revision=None,db=None,role=None,
                 member_count=0,missing=False):
        self.sql=[];self.rolled_back=False
        self.insert=insert;self.revision=revision or probe.REV
        self.db=db or probe.DB
        self.role=role if role is not None else (False,)*6
        self.member_count=member_count
        self.missing=missing

    def execute(self,statement,params=None):
        query=str(statement)
        self.sql.append(query)
        if query=="SET TRANSACTION READ ONLY":return Result(None)
        if "SELECT current_database(),session_user,current_user" in query:
            return Result((self.db,"solveris_b02_policy_writer",
                           "solveris_b02_policy_writer",self.revision))
        if "FROM pg_catalog.pg_roles" in query:return Result(self.role)
        if "FROM pg_catalog.pg_auth_members" in query:
            return Result(self.member_count)
        if "FROM pg_catalog.pg_class" in query:
            names=TABLES[:-1] if self.missing else TABLES
            return Result([
                dict(table_name=name,owner="solveris_test",
                     can_select=True,
                     can_insert=self.insert if name=="artifact_verification_records" else False,
                     can_insert_any_column=self.insert if name=="artifact_verification_records" else False,
                     can_update=False,can_delete=False)
                for name in names
            ])
        raise AssertionError("UNEXPECTED_SQL_IN_READ_ONLY_PROBE")
    def rollback(self):self.rolled_back=True

class Engine:
    def __init__(self,c):self.c=c
    def connect(self):
        conn=self.c
        class Context:
            def __enter__(self):return conn
            def __exit__(self,*args):return False
        return Context()

class R5ArtifactAclReadonlyTests(unittest.TestCase):
    def test_denied_insert_is_recorded_not_granted(self):
        conn=Connection()
        result=probe._g5_artifact_acl_inventory(Engine(conn))
        self.assertEqual(result["status"],"R5_ARTIFACT_ACL_PHYSICAL_READ_ONLY_INVENTORY_PASS")
        self.assertFalse(result["artifact_verification_record_direct_insert_observed"])
        self.assertFalse(result["artifact_verification_any_column_insert_observed"])
        self.assertFalse(result["release_0064_0065_authorized"])
        self.assertTrue(conn.rolled_back)
        self.assertEqual((result["writes"],result["ddl"],result["grants"]),(0,0,0))
        self.assertEqual(conn.sql[0],"SET TRANSACTION READ ONLY")
        self.assertEqual(len(result["tables"]),6)
        self.assertNotIn("GRANT ", " ".join(conn.sql))
        self.assertNotIn("INSERT INTO", " ".join(conn.sql))

    def test_direct_insert_permission_is_only_an_observation(self):
        conn=Connection(insert=True)
        result=probe._g5_artifact_acl_inventory(Engine(conn))
        self.assertTrue(result["artifact_verification_record_direct_insert_observed"])
        self.assertEqual(result["authority_to_create_favorable_report"],"NOT_INFERRED")
        self.assertFalse(result["release_0064_0065_authorized"])

    def test_revision_mismatch_fails_before_catalog_lookups(self):
        conn=Connection(revision="0062_adr020_noncredential_acquisition")
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_ARTIFACT_ACL_IDENTITY_REVISION"):
            probe._g5_artifact_acl_inventory(Engine(conn))
        self.assertEqual(len(conn.sql),2)

    def test_wrong_database_fails_closed(self):
        conn=Connection(db="postgres")
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_ARTIFACT_ACL_IDENTITY_REVISION"):
            probe._g5_artifact_acl_inventory(Engine(conn))

    def test_elevated_target_writer_fails_closed(self):
        conn=Connection(role=(True,False,False,False,False,False))
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_WRITER_ROLE_MISSING_OR_ELEVATED"):
            probe._g5_artifact_acl_inventory(Engine(conn))

    def test_target_writer_role_membership_fails_closed(self):
        conn=Connection(member_count=1)
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_WRITER_ROLE_MEMBERSHIP"):
            probe._g5_artifact_acl_inventory(Engine(conn))

    def test_missing_artifact_table_fails_closed(self):
        conn=Connection(missing=True)
        with self.assertRaisesRegex(RuntimeError,"STOP_R5_ARTIFACT_TABLES_MISSING"):
            probe._g5_artifact_acl_inventory(Engine(conn))

if __name__=="__main__":
    unittest.main()
