"""Focused code-path applicability tests for G5 V5 / R2.

Static contract checks only. No DB, Docker, migrations, signed evidence or
historical suite. Failure means code-path attribution needs a fresh examination,
not that an immutable institutional decision should be edited or repeated.
"""
import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def candidate_sql(path):
    tree = ast.parse(read(path))
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "_SQL"
                   for target in statement.targets):
                return ast.literal_eval(statement.value)
    raise AssertionError("candidate SQL _SQL missing")


class G5R2ApplicabilityDelta(unittest.TestCase):
    def test_g5_stage_does_not_call_r2_but_checks_exact_policy_and_hash(self):
        code = read("app/services/enterprise_b02_policy_activation_atomicity.py")
        self.assertIn("def stage_policy_activation(", code)
        self.assertNotIn("validate_institutional_chain", code)
        self.assertNotIn("require_current_authority", code)
        self.assertNotIn("verify_exact_chain", code)
        self.assertIn("EXACT_DECISION_HASH_REQUIRED", code)
        self.assertIn("models._adr020_validate_policy_activation_execution_insert(", code)
        self.assertIn("models._adr020_validate_policy_activation_insert(", code)
        self.assertIn("b02p_require_complete", code)
        self.assertIn("Only the caller may commit/roll back", code)

    def test_physically_applied_0063_authority_is_ratified_and_segregated(self):
        sql = read("migrations/versions/0063_adr020_policy_activation_atomicity.py")
        self.assertIn("CREATE FUNCTION b02p_check_authority(", sql)
        self.assertIn("decision_event='ratificada'", sql)
        self.assertIn("institutional_role='autoridade_constitucional_final'", sql)
        self.assertIn("e.actor_or_worker=d.actor", sql)
        self.assertIn("B02P_EXACT_RATIFIED_DECISION_REQUIRED", sql)
        self.assertIn("B02P_EXACT_MANUAL_BOOTSTRAP_REQUIRED", sql)
        self.assertIn("B02P_EXACT_ACTIVE_SUPERIOR_REQUIRED", sql)
        self.assertNotIn("validate_institutional_chain", sql)
        self.assertNotIn("require_current_authority", sql)

    def test_g5_0064_chain_requires_predecessor_hash_not_r2_field_set(self):
        sql = candidate_sql("migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py")
        for clause in (
            "WITH RECURSIVE chain AS",
            "G5_EXACT_SEGREGATED_CHAIN_REQUIRED",
            "G5_CURRENT_DECISION_AMBIGUOUS",
            "G5_PREDECESSOR_DIVERGENCE",
            "G5_EXACT_DOCUMENT_OR_G4_MISSING",
            "q.evidence->'previous_decision_record_hash' IS DISTINCT FROM 'null'::jsonb",
            "q.evidence->>'previous_decision_record_hash' IS DISTINCT FROM prev.record_hash",
            "b02p_require_complete",
            "REAL_PROFILE_COMPILED_APPROVED_ROOTS",
        ):
            self.assertIn(clause, sql)
        for unrelated in (
            "validate_institutional_chain",
            "require_current_authority",
            "policy_subject",
            "actor_identity",
            "record_evidence",
            "technical_author",
        ):
            self.assertNotIn(unrelated, sql)

    def test_g5_0065_one_shot_is_candidate_not_r2_caller(self):
        path = "migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py"
        sql = candidate_sql(path)
        self.assertIn("b02_g5_assert_one_shot", sql)
        self.assertIn("REAL_PROFILE_COMPILED_APPROVED_ROOTS", sql)
        self.assertNotIn("validate_institutional_chain", sql)
        self.assertNotIn("require_current_authority", sql)
        self.assertTrue(path.startswith("migrations/candidates/"))

    def test_r2_caller_is_documentary_admission_g4_domain(self):
        admission = read("app/services/sefa_pr_documentary_admission.py")
        projection = read("app/services/sefa_pr_policy_projection.py")
        self.assertIn("require_current_authority(connection,b,row", admission)
        self.assertIn("row['domain']!='SEFA_PR_B02_DOCUMENTAL'", admission)
        self.assertIn("validate_institutional_chain(exact,binding", projection)
        self.assertIn("verify_institutional_evidence(proof_verifier", projection)
        self.assertIn("policy_subject", projection)
        self.assertIn("actor_identity", projection)
        self.assertIn("record_evidence", projection)
        self.assertIn("technical_author", projection)
        policy = json.loads(read(
            "POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json"
        ))["policy_candidate_body"]
        self.assertEqual(policy["domain"], "SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE")

    def test_committed_submission_does_satisfy_g5_genesis_predecessor_field(self):
        submission = json.loads(read("B02_G5_V5_SUBMISSAO_PROPONENTE_GPT6_20261029.json"))
        script = read("tools/b02_g5_v5_submission_runner.py")
        self.assertEqual(submission["decision_event"], "submetida")
        self.assertIsNone(submission["previous_decision_id"])
        self.assertIn('"previous_decision_record_hash":None', script)
        for key in ("policy_subject","actor_identity","record_evidence","technical_author"):
            self.assertNotIn(key + '"', script.split('def payload(s):',1)[1].split('def independent_readback(',1)[0])
        self.assertEqual(
            submission["policy"]["policy_hash"],
            "007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf",
        )

    def test_v5_declares_functional_not_material_segregation(self):
        policy = json.loads(read(
            "POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json"
        ))["policy_candidate_body"]
        duties = policy["segregation_of_duties"]
        self.assertTrue(duties["reviewer_not_author_or_integrator"])
        self.assertTrue(duties["no_internal_model_identity_or_material_independence_asserted"])
        self.assertTrue(duties["shared_context_infrastructure_limit_acknowledged"])


if __name__ == "__main__":
    unittest.main()
