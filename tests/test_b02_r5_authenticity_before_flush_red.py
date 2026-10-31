"""B02 R5: executable RED contract for a G5-only authenticity staging hook.

Synthetic fixtures. No PostgreSQL, signed origins, authority or PDF source touched.
Existing frozen R4G contract is not edited.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "app/services/enterprise_b02_noncredential_acquisition.py"
spec = importlib.util.spec_from_file_location("b02_r5_authenticity_contract", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
RAW = b"%PDF-1.7\nSYNTHETIC_TEST_ONLY\n"
DIGEST = hashlib.sha256(RAW).hexdigest()

class FakeResult:
    def __init__(self, value): self.value = value
    def one(self): return self.value
    def mappings(self): return self
    def scalar_one(self): return self.value

class Operation:
    def __init__(self, name): self.name = name
    def values(self, **kwargs): return self
    def returning(self, *args): return self

class Table:
    def __init__(self, name): self.name = name
    def insert(self): return Operation(self.name)

class FakeConnection:
    def __init__(self):
        self.log = []
        self.auth_staged = False
    def in_transaction(self): return True
    def execute(self, statement, parameters=None):
        if isinstance(statement, Operation):
            self.log.append("insert:" + statement.name)
            if statement.name == "AcquisitionModeBinding":
                return FakeResult({"mode_binding_id":"b","record_hash":"p"})
            if statement.name == "NonCredentialAcquisitionReceipt":
                return FakeResult({"receipt_id":"r","receipt_hash":"h"})
            if statement.name == "NonCredentialSanitizationVerification":
                return FakeResult({"verification_id":"v","record_hash":"vhash"})
            return FakeResult(None)
        sql = str(statement)
        if "SELECT current_database(), session_user, current_user" in sql:
            return FakeResult(("solveris_b02_r4g_test","solveris_b02_writer","solveris_b02_writer"))
        if "SELECT COUNT(*)" in sql and "artifact_verification_records" in sql:
            self.log.append("auth_readback")
            return FakeResult(1 if self.auth_staged else 0)
        if "SET CONSTRAINTS ALL IMMEDIATE" in sql:
            self.log.append("constraints_immediate")
            return FakeResult(None)
        raise AssertionError("unexpected SQL: " + sql[:100])

def fake_models():
    m = ModuleType("app.models")
    for name in ("AcquisitionModeBinding","NonCredentialAcquisitionReceipt",
                 "NonCredentialSanitizationVerification","AcquisitionExecution",
                 "NormativeArtifact"):
        setattr(m, name, type(name, (), {"__table__": Table(name)}))
    return m

def exercise(conn, *, authenticity=None, real=True):
    binding = {"mode":"LOCAL_CAS_INCORPORATION","acquisition_execution_id":"e",
               "attempt_number":1,"provenance":{"synthetic_only":not real}}
    def evidence(_binding, raw):
        return {
            "receipt":{"artifact_hash":DIGEST,"byte_size":len(raw)},
            "verification":{},
            "terminal":{"structured_result":{}},
            "artifact":{"normative_artifact_id":"a","immutable_bytes":raw}
        }
    kwargs = dict(connection=conn, binding=binding, start={},
                  read_cas=lambda: RAW, build_evidence=evidence)
    if authenticity is not None:
        kwargs["stage_authenticity"] = authenticity
    with patch.dict(sys.modules, {"app.models":fake_models()}):
        return mod.stage_completion(**kwargs)

class G5SignedAuthenticityBeforeFlushRED(unittest.TestCase):
    def test_real_without_authorized_stager_rejected_before_writes(self):
        conn=FakeConnection()
        with self.assertRaisesRegex(mod.AcquisitionEvidenceError,"REAL_AUTHENTICITY_STAGER_REQUIRED"):
            exercise(conn,real=True)
        self.assertFalse(any(x.startswith("insert:") for x in conn.log))

    def test_favorable_authenticated_row_before_deferred_flush(self):
        conn=FakeConnection()
        def staged(c, artifact_id, pdf_hash, pdf_bytes):
            self.assertEqual((artifact_id,pdf_hash,pdf_bytes),("a",DIGEST,RAW))
            c.log.append("independent_stager")
            c.auth_staged=True
        result=exercise(conn,authenticity=staged,real=True)
        self.assertEqual(result["artifact_hash"],DIGEST)
        self.assertLess(conn.log.index("insert:NormativeArtifact"),
                        conn.log.index("independent_stager"))
        self.assertLess(conn.log.index("independent_stager"),
                        conn.log.index("auth_readback"))
        self.assertLess(conn.log.index("auth_readback"),
                        conn.log.index("constraints_immediate"))

    def test_no_inserted_authenticity_row_stops_before_flush(self):
        conn=FakeConnection()
        with self.assertRaisesRegex(mod.AcquisitionEvidenceError,"EXACT_FOUNDER_AUTHENTICITY_ROW_REQUIRED"):
            exercise(conn,authenticity=lambda *_:None,real=True)
        self.assertNotIn("constraints_immediate",conn.log)

    def test_callback_cannot_be_used_for_synthetic_unit(self):
        conn=FakeConnection()
        with self.assertRaisesRegex(mod.AcquisitionEvidenceError,"REAL_AUTHENTICITY_ONLY"):
            exercise(conn,authenticity=lambda *_:None,real=False)
        self.assertFalse(any(x.startswith("insert:") for x in conn.log))

    def test_legacy_synthetic_without_callback_remains_unchanged(self):
        conn=FakeConnection()
        result=exercise(conn,real=False)
        self.assertEqual(result["artifact_hash"],DIGEST)
        self.assertIn("constraints_immediate",conn.log)
        self.assertNotIn("auth_readback",conn.log)

if __name__=="__main__":
    unittest.main()
