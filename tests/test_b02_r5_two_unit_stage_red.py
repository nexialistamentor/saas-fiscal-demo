"""B02 R5 G5 two-unit stage: RED source-only contract, isolated no PostgreSQL.

These five fixtures never stage real documents, persist origin, or modify 0062/64/65.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
from unittest import TestCase, mock
from types import SimpleNamespace

PATH = Path(__file__).resolve().parents[1]/"app/services/enterprise_b02_g5_two_unit_stage.py"
PIN_A = b"SYNTHETIC_PDF_TEST_A"
PIN_B = b"SYNTHETIC_PDF_TEST_B"
TEST_PINS = {
    "101201900571":(hashlib.sha256(PIN_A).hexdigest(),len(PIN_A)),
    "101202501245":(hashlib.sha256(PIN_B).hexdigest(),len(PIN_B)),
}

class FakeConnection:
    def __init__(self):self.statements=[]
    def in_transaction(self):return True
    def execute(self, statement):
        sql=str(statement)
        self.statements.append(sql)
        if sql!="SET CONSTRAINTS public.z_b02_complete_unit DEFERRED":
            raise AssertionError("unreviewed SQL "+sql)
        return None

def unit(document_id, raw, *, real=True):
    return dict(document_id=document_id,
                binding={"mode":"LOCAL_CAS_INCORPORATION","provenance":{"synthetic_only":not real},
                         "acquisition_execution_id":"e-"+document_id},
                start={},read_cas=lambda:raw,build_evidence=lambda *_:None,
                stage_authenticity=lambda *_:None)

def module():
    if not PATH.exists():return None
    spec=importlib.util.spec_from_file_location("b02_g5_two_unit_red",PATH)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

class TwoRealC3DeferredUnitRED(TestCase):
    def setUp(self):
        self.module=module()
        self.assertIsNotNone(self.module,"NEW_G5_TWO_UNIT_STAGE_MODULE_REQUIRED")
        self.calls=[]
        self.connection=FakeConnection()
        self.units=[unit("101201900571",PIN_A),unit("101202501245",PIN_B)]

    def executor(self, conn, *, binding, start, read_cas, build_evidence, stage_authenticity):
        data=read_cas()
        self.calls.append(("stage",binding["acquisition_execution_id"],data))
        return {"artifact_hash":hashlib.sha256(data).hexdigest()}

    def run_units(self, units=None):
        with mock.patch.object(self.module,"C3_DOCUMENTS",TEST_PINS),\
             mock.patch.object(self.module,"stage_completion",side_effect=self.executor):
            return self.module.stage_two_real_c3_units(
                self.connection,units=self.units if units is None else units)

    def test_two_real_units_named_redefer_after_first_and_no_commit(self):
        result=self.run_units()
        self.assertEqual(len(result),2)
        self.assertEqual([x[0] for x in self.calls],["stage","stage"])
        self.assertEqual(self.connection.statements,
                         ["SET CONSTRAINTS public.z_b02_complete_unit DEFERRED"]*2)
        self.assertEqual(self.calls[0][2],PIN_A)
        self.assertEqual(self.calls[1][2],PIN_B)

    def test_missing_or_duplicate_exact_document_set_fails_before_db(self):
        for bad in ([self.units[0]],[self.units[0],self.units[0]],
                    [self.units[0],unit("other",b"wrong")]):
            with self.subTest(bad=repr([x["document_id"] for x in bad])):
                with self.assertRaisesRegex(ValueError,"EXACT_TWO_C3_DOCUMENTS_REQUIRED"):
                    self.run_units(bad)
        self.assertEqual(self.connection.statements,[])
        self.assertEqual(self.calls,[])

    def test_forged_or_mixed_synthetic_class_fails_before_db(self):
        cases=[
            [unit("101201900571",PIN_A,real=False),self.units[1]],
            [unit("101201900571",PIN_A),dict(self.units[1],binding={"provenance":{}})],
            [unit("101201900571",PIN_A),dict(self.units[1],binding={"provenance":{"synthetic_only":"false"}})]
        ]
        for bad in cases:
            with self.subTest(bad=str(bad[0]["document_id"])):
                with self.assertRaisesRegex(ValueError,"REAL_C3_UNIT_REQUIRED"):
                    self.run_units(bad)
        self.assertEqual(self.connection.statements,[])
        self.assertEqual(self.calls,[])

    def test_content_pin_failure_prevents_second_stage_and_reservation(self):
        wrong=[self.units[0],unit("101202501245",b"WRONG_C3_BYTES")]
        with self.assertRaisesRegex(ValueError,"EXACT_C3_BYTES_REQUIRED"):
            self.run_units(wrong)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.connection.statements,
                         ["SET CONSTRAINTS public.z_b02_complete_unit DEFERRED"]*2)

    def test_second_unit_exception_propagates_no_commit_or_retry(self):
        def failing(conn,*,binding,start,read_cas,build_evidence,stage_authenticity):
            self.calls.append(("attempt",binding["acquisition_execution_id"]))
            if len(self.calls)==2:raise RuntimeError("SIGNATURE_OR_ORIGIN_REJECTED")
            return {"artifact_hash":hashlib.sha256(read_cas()).hexdigest()}
        with mock.patch.object(self.module,"C3_DOCUMENTS",TEST_PINS),\
             mock.patch.object(self.module,"stage_completion",side_effect=failing):
            with self.assertRaisesRegex(RuntimeError,"SIGNATURE_OR_ORIGIN_REJECTED"):
                self.module.stage_two_real_c3_units(self.connection,units=self.units)
        self.assertEqual(len(self.calls),2)
        self.assertEqual(len(self.connection.statements),2)

if __name__=="__main__":
    import unittest
    unittest.main()
