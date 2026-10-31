"""B02 G5 0064: isolated RED contracts for same-policy multi-version coexistence.

V1 decisions must remain immutable but cannot veto a new properly authorized V2/V3
chain merely by sharing policy_id. Same-version wrong-hash/extra/adverse decisions
still MUST veto. Static SQL guards only: no PostgreSQL or policy activation.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
PATH=ROOT/"migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py"
V1_INVENTORY=ROOT/"tools/b02_g5_v5_current_inventory_readonly.py"
BASELINE=ROOT/"B02_G5_V5_AUTHORIZATION_MANIFEST_DRAFT.json"

def sql():
    node=ast.parse(PATH.read_text(encoding="utf-8-sig"))
    candidates=[ast.literal_eval(x.value) for x in node.body
                if isinstance(x,ast.Assign)
                and any(isinstance(t,ast.Name) and t.id=="_SQL" for t in x.targets)]
    if len(candidates)!=1 or not isinstance(candidates[0],str):
        raise ValueError("STOP_0064_SQL_NOT_EXACT_LITERAL")
    return candidates[0]

def g5_guard():
    source=sql()
    start=source.index("IF EXISTS(SELECT 1 FROM public.policy_decisions q WHERE q.policy_type=p.policy_type AND q.policy_id=p.policy_id")
    end=source.index("THEN RAISE EXCEPTION 'G5_CURRENT_DECISION_AMBIGUOUS';",start)
    return source[start:end]

def g4_guard():
    source=sql()
    start=source.index("IF cardinality(ancestor_ids)<>4 OR EXISTS(SELECT 1 FROM public.policy_decisions q WHERE q.policy_type=gp.policy_type")
    end=source.index("OR EXISTS(SELECT 1 FROM public.policy_activations q WHERE",start)
    return source[start:end]

class G5MultiVersionDecisionScopeRED(unittest.TestCase):
    def test_historical_v1_and_v2_same_policy_id_coexist_in_source(self):
        inventory=V1_INVENTORY.read_text(encoding="utf-8-sig")
        self.assertIn("SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE",inventory)
        self.assertIn("57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa",inventory)
        source=BASELINE.read_text(encoding="utf-8-sig")
        self.assertIn('"policy_version": 1',source)
        self.assertIn('"policy_version": 2',source)

    def test_g5_extra_decisions_must_be_scoped_to_same_version(self):
        guard=g5_guard()
        self.assertIn("q.policy_version=p.policy_version",guard)

    def test_g5_same_version_wrong_hash_fails_closed(self):
        guard=g5_guard()
        self.assertIn("q.policy_hash IS DISTINCT FROM p.policy_hash",guard)
        self.assertIn("NOT(q.decision_id=ANY(ancestor_ids))",guard)

    def test_g5_adverse_or_extra_decision_in_same_version_remains_veto(self):
        guard=g5_guard()
        self.assertIn("'auditada_desfavoravelmente','rejeitada','cancelada'",guard)
        self.assertIn("q.policy_type=p.policy_type",guard)
        self.assertIn("q.policy_id=p.policy_id",guard)

    def test_original_g4_same_policy_historical_versions_do_not_veto(self):
        guard=g4_guard()
        self.assertIn("q.policy_version=gp.policy_version",guard)
        self.assertIn("q.policy_hash IS DISTINCT FROM gp.policy_hash",guard)
        self.assertIn("NOT(q.decision_id=ANY(ancestor_ids))",guard)

    def test_approved_root_and_own_ratification_gates_unmodified(self):
        source=sql()
        for predicate in (
            "G5_TRUSTED_FINALIZATION_NOT_IMPLEMENTED_OR_APPROVED",
            "G5_EXACT_SEGREGATED_CHAIN_REQUIRED",
            "G5_RATIFICATION_REQUIRED",
            "G5_ORIGINAL_G4_AUTHORITY_NOT_CURRENT",
            "G5_ONE_EXACT_AUTHENTICITY_RECORD_REQUIRED",
        ):
            with self.subTest(gate=predicate):
                self.assertIn(predicate,source)

if __name__=="__main__":
    unittest.main()
