"""Focused R6 evidence/ACL tests; no DB connections and no normative authority."""
import contextlib
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import b02_r6_normative_linkage_readonly as r6


def privileges(readable=True):
    return {"database":r6.bridge.DATABASE,
        "role":r6.ROLE,"current_user":r6.ROLE,
        "revision":"0063_adr020_policy_activation_atomicity",
        "select_privileges":{k:readable for k in r6.TABLES}}


class R6EvidenceContract(unittest.TestCase):
    def test_all_sql_read_only_and_exact_document_hashes(self):
        for sql in (r6.PRIVILEGES,r6.CATALOGUE):
            self.assertIn("BEGIN READ ONLY;",sql)
            self.assertIn("ROLLBACK;",sql)
            for forbidden in ("INSERT INTO","UPDATE public.","DELETE FROM","GRANT ",
                              "CREATE TABLE","DROP TABLE"):
                self.assertNotIn(forbidden,sql)
        for sha in r6.SOURCE_HASHES.values():
            self.assertIn(sha,r6.CATALOGUE)
        self.assertIn("public.normative_artifacts",r6.CATALOGUE)
        self.assertIn("public.rule_versions",r6.CATALOGUE)
        self.assertIn("public.extraction_results",r6.CATALOGUE)
        self.assertIn("public.normative_relation_versions",r6.CATALOGUE)
        self.assertIn("public.tabela_mva",r6.CATALOGUE)


    def test_r6_source_has_no_duplicate_tail_or_truncated_sql(self):
        import ast
        source = (ROOT/"tools/b02_r6_normative_linkage_readonly.py").read_text(
            encoding="utf8")
        tree = ast.parse(source)
        definitions = [node.name for node in tree.body
                       if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))]
        self.assertEqual(definitions.count("inspect"),1)
        self.assertEqual(definitions.count("main"),1)
        self.assertEqual(source.count("CATALOGUE="),1)
        self.assertEqual(source.count('if __name__=="__main__":'),1)
        self.assertTrue(source.rstrip().endswith("raise SystemExit(2)"))
        self.assertIn("a.record_hash ~ '^[0-9a-f]{64}$'",r6.CATALOGUE)
        self.assertNotIn("a.record_hash ~ '^[0-9a-f]{64})",r6.CATALOGUE)

    def test_insufficient_acl_not_upgraded(self):
        with patch.object(r6.bridge,"managed_container",return_value=contextlib.nullcontext()),\
             patch.object(r6,"read",return_value=privileges(False)) as read:
            result=r6.inspect()
        self.assertEqual(result["status"],"R6_SOURCE_TABLES_INACCESSIBLE_WITH_EXISTING_ROLE")
        self.assertEqual(len(result["unreadable_tables"]),5)
        self.assertEqual(result["writes"],0)
        self.assertEqual(result["new_grants"],0)
        read.assert_called_once()

    def test_partial_acl_reads_only_allowed_sources(self):
        acl=privileges()
        for name in ("rule_versions","normative_relation_versions","tabela_mva"):
            acl["select_privileges"][name]=False
        data={
            "artifacts_total":1,
            "artifacts":[{"normative_artifact_id":"a","record_hash_shape_valid":True}],
            "extraction_results_total":1,
            "extraction_results":[{"extraction_result_id":"e","outcome":"inconclusivo"}],
        }
        with patch.object(r6.bridge,"managed_container",
                          return_value=contextlib.nullcontext()),\
             patch.object(r6,"read",side_effect=[acl,data]) as reads:
            result=r6.inspect()
        self.assertEqual(result["status"],
                         "R6_PARTIAL_SOURCE_READ_ONLY_RULE_TABLES_DENIED")
        self.assertEqual(result["unreadable_tables"],
                         ["rule_versions","normative_relation_versions","tabela_mva"])
        self.assertEqual(result["available_source_catalogue"],data)
        self.assertFalse(result["rule_or_item_binding_proven"])
        self.assertFalse(result["fiscal_authority"])
        self.assertEqual(result["writes"],0)
        self.assertEqual(result["new_grants"],0)
        self.assertEqual(reads.call_args_list[1].args[0],r6.SOURCE_ONLY_CATALOGUE)
        self.assertNotIn("public.rule_versions",r6.SOURCE_ONLY_CATALOGUE)
        self.assertNotIn("public.normative_relation_versions",r6.SOURCE_ONLY_CATALOGUE)
        self.assertNotIn("public.tabela_mva",r6.SOURCE_ONLY_CATALOGUE)

    def test_partial_query_rejects_wrong_artifact_or_unbounded_payload(self):
        acl=privileges()
        for name in ("rule_versions","normative_relation_versions","tabela_mva"):
            acl["select_privileges"][name]=False
        invalid={
            "artifacts_total":1,
            "artifacts":[{"record_hash_shape_valid":False}],
            "extraction_results_total":0,
            "extraction_results":[],
        }
        with patch.object(r6.bridge,"managed_container",
                          return_value=contextlib.nullcontext()),\
             patch.object(r6,"read",side_effect=[acl,invalid]):
            with self.assertRaisesRegex(RuntimeError,
                                        "ARTIFACT_RECORD_HASH_FORMAT_INVALID"):
                r6.inspect()
        self.assertIn("BEGIN READ ONLY;",r6.SOURCE_ONLY_CATALOGUE)
        self.assertIn("ROLLBACK;",r6.SOURCE_ONLY_CATALOGUE)

    def test_even_candidates_do_not_prove_fiscal_authority(self):
        data={"artifacts":[{"record_hash_shape_valid":True,"normative_artifact_id":"some"}],
              "rule_candidates":[{"rule_version_record_id":"some"}],
              "normative_relations_total":4,"rule_versions_total":3,
              "mva_pr_12119090":[{"id":12}]}
        with patch.object(r6.bridge,"managed_container",return_value=contextlib.nullcontext()),\
             patch.object(r6,"read",side_effect=[privileges(),data]):
            result=r6.inspect()
        self.assertFalse(result["canonical_l2_ruleversion_item_binding_proven"])
        self.assertFalse(result["legal_applicability_for_item_proven"])
        self.assertFalse(result["external_source_revisions_exhaustively_verified"])
        self.assertFalse(result["fiscal_authority"])
        self.assertFalse(result["checkout"])
        self.assertEqual(result["writes"],0)

    def test_corrupt_artifact_row_hash_stops(self):
        data={"artifacts":[{"record_hash_shape_valid":False}],
              "rule_candidates":[],"normative_relations_total":0,
              "rule_versions_total":0,"mva_pr_12119090":[]}
        with patch.object(r6.bridge,"managed_container",return_value=contextlib.nullcontext()),\
             patch.object(r6,"read",side_effect=[privileges(),data]):
            with self.assertRaisesRegex(RuntimeError,"ARTIFACT_RECORD_HASH_FORMAT_INVALID"):
                r6.inspect()

    def test_bridge_uses_existing_document_writer(self):
        self.assertIn(r6.PATH,r6.bridge.ALLOWED)
        self.assertEqual(r6.ROLE,"solveris_b02_writer")
        self.assertEqual(r6.bridge.DATABASE,"solveris_b02_r4g_test")


if __name__=="__main__":
    unittest.main()
