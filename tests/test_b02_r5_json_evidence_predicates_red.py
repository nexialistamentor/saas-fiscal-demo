"""B02 R5: exact PostgreSQL JSON/JSONB type-safe security predicates.

Static RED-before/GREEN-after regression. No database, Docker, signed origin,
policy activation, test fixtures, or protected tables are changed.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SERVICE=ROOT/"app/services/enterprise_b02_noncredential_acquisition.py"
CANDIDATE=ROOT/"migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py"
MODELS=ROOT/"app/models.py"
EXPECTED_VERIFIER="SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN"

def candidate_sql():
    tree=ast.parse(CANDIDATE.read_text(encoding="utf-8-sig"))
    assignments=[a for a in tree.body if isinstance(a,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=="_SQL" for t in a.targets)]
    if len(assignments)!=1:
        raise AssertionError("STOP_G5_CANDIDATE_SQL_NOT_PINNED")
    value=ast.literal_eval(assignments[0].value)
    assert isinstance(value,str)
    return value

class PG17EvidenceJSONSemantics(unittest.TestCase):
    def test_orm_authenticity_evidence_has_json_not_jsonb_contract(self):
        src=MODELS.read_text(encoding="utf-8-sig")
        start=src.index("class ArtifactVerificationRecord(")
        end=src.index("\nclass ",start+10)
        decl=src[start:end]
        self.assertIn("evidence = Column(JSON, nullable=False)",decl)

    def test_r5_readback_explicit_jsonb_semantic_cast_for_boolean(self):
        src=SERVICE.read_text(encoding="utf-8-sig")
        self.assertIn("v.evidence::jsonb->'synthetic_only'='false'::jsonb",src)
        self.assertNotIn("v.evidence->'synthetic_only'='false'::jsonb",src)

    def test_r5_readback_explicit_jsonb_cast_for_structural_g4_binding(self):
        src=SERVICE.read_text(encoding="utf-8-sig")
        self.assertIn(
            "v.evidence::jsonb->'g4_origin_report_binding'=doc->'g4'->'origin_report_binding'",
            src,
        )
        self.assertIn(
            "v.evidence->>'authorized_verifier_hash'=doc->'g4'->'verifier'->>'hash'",
            src,
        )
        self.assertIn(EXPECTED_VERIFIER,src)

    def test_0064_exact_authenticity_predicate_casts_match_service(self):
        sql=candidate_sql()
        for expression in (
            "v.evidence::jsonb->'synthetic_only'='false'::jsonb",
            "v.evidence::jsonb->'g4_origin_report_binding'=doc->'g4'->'origin_report_binding'",
            "v.evidence->>'authorized_verifier_hash'=doc->'g4'->'verifier'->>'hash'",
        ):
            with self.subTest(predicate=expression):
                self.assertIn(expression,sql)
        self.assertIn("G5_ONE_EXACT_AUTHENTICITY_RECORD_REQUIRED",sql)

    def test_preexisting_two_exact_c3_ids_and_real_stop_remain(self):
        sql=candidate_sql()
        for value in (
            "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
            "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d",
            "G5_TRUSTED_FINALIZATION_NOT_IMPLEMENTED_OR_APPROVED",
            "REAL_PROFILE_COMPILED_APPROVED_ROOTS",
        ):
            self.assertIn(value,sql)

    def test_no_false_jsonb_storage_migration_is_attempted(self):
        src=SERVICE.read_text(encoding="utf-8-sig")
        sql=candidate_sql()
        self.assertNotIn("ALTER TABLE public.artifact_verification_records",sql)
        self.assertNotIn("ALTER TABLE public.artifact_verification_records",src)
        self.assertIn("SET CONSTRAINTS ALL IMMEDIATE",src)

if __name__=="__main__":
    unittest.main()
