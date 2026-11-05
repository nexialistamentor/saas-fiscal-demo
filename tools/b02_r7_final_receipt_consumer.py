"""SOLVERIS B02 R7 -- consume new independently verified final receipts.

Preserves the older R7 V2 read-only projection, its G4/A2 completion and the
149-proof boundary without rerunning them. This produces *decision input*, never
the competent B02 CLOSED act and never a B03 release.
"""
from __future__ import annotations
import hashlib
import json
import re
from collections.abc import Callable, Mapping

C3_DOCUMENTS = {
    "101202501245": "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
    "101201900571": "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d",
}
R6_NCMS = {"12119090", "27121000", "28142000"}
HEXDIGEST = re.compile("[0-9a-f]{64}\\Z")

def stop(code):
    raise ValueError("STOP_B02_R7_FINAL_INPUT_" + code)

def _hash(x):
    return isinstance(x, str) and bool(HEXDIGEST.fullmatch(x))

def _pure_digest(item):
    """Digest of an in-memory copy; not a signature or authentication."""
    return hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()

def incomplete():
    return {
        "status": "B02_OPEN_B03_BLOCKED",
        "missing_final_receipts": ["G5_V3_R1", "R5_REAL_0064_0065", "R6_REAL_FISCAL"],
        "b02_closed": False, "b03_released": False,
        "competent_r7_act_produced": False,
    }

def assemble_decision_input(*, historical_r7: Mapping, g5: Mapping,
                            r5: Mapping, r6: Mapping,
                            verify_g5: Callable, verify_r5: Callable,
                            verify_r6: Callable):
    """Require *external*, separately competent evidence verification.

    Each verify_* must independently authenticate the complete corresponding
    receipt and its institutional/physical provenance, returning exactly
    {'verified': True, 'act_sha256': <verified original act hash>}.
    These callbacks are not generated here and cannot be replaced by a status
    label or the historic synthetic test fixtures.
    """
    if not isinstance(historical_r7, Mapping) or (
        historical_r7.get("status") != "B02_OPEN_B03_BLOCKED"
        or historical_r7.get("r7_closed") is not False
        or historical_r7.get("b03_released") is not False
        or historical_r7.get("protected_writes") != 0
        or historical_r7.get("successor_proofs_count") != 149
        or set(historical_r7.get("closed_gates_only_in_scope", ())) !=
           {"CURRENT_G4_V3_SUCCESSOR", "RCV31_A2_V4_OWN_REVIEW"}
    ):
        stop("HISTORICAL_READONLY_FENCE_NOT_CONSUMABLE")
    if not all(isinstance(i, Mapping) for i in (g5, r5, r6)):
        stop("ALL_THREE_FINAL_RECEIPTS_REQUIRED")
    if not all(callable(i) for i in (verify_g5, verify_r5, verify_r6)):
        stop("INDEPENDENT_VALIDATORS_REQUIRED")

    policy = g5.get("final_policy_sha256")
    if (not _hash(policy)
            or not _hash(g5.get("native_root_sha256"))
            or not _hash(g5.get("native_elf_sha256"))
            or not _hash(g5.get("ratification_act_sha256"))
            or not _hash(g5.get("review_act_sha256"))):
        stop("G5_FINAL_POLICY_ROOT_REVIEW_RATIFICATION_REQUIRED")
    if (r5.get("status") != "R5_COMMITTED_INDEPENDENT_READBACK_EXACT"
            or r5.get("alembic_revision") != "0065_b02_g5_one_shot_real"
            or r5.get("database") != "solveris_b02_r4g_test"
            or r5.get("g5_policy_hash") != policy
            or not r5.get("assigned_txid")
            or r5.get("b02_closed") is not False):
        stop("R5_PHYSICAL_READBACK_CURRENT_G5_LINK_MISSING")
    rows = r5.get("units")
    if not isinstance(rows, list) or len(rows) != 2 or (
       {r.get("document_id") for r in rows if isinstance(r, Mapping)}
            != set(C3_DOCUMENTS)):
        stop("R5_TWO_C3_UNITS_NOT_EXACT")
    receipts = {}
    for r in rows:
        if (not isinstance(r, Mapping)
                or r.get("artifact_hash") != C3_DOCUMENTS[r["document_id"]]
                or not r.get("normative_artifact_id")
                or not _hash(r.get("normative_artifact_record_hash"))
                or not _hash(r.get("authenticity_record_hash"))
                or r.get("assigned_txid") != r5["assigned_txid"]):
            stop("R5_SOURCE_ARTIFACT_OR_ORIGIN_NOT_PROVEN")
        receipts[r["document_id"]] = r

    # R6 must bind BOTH real PDFs to conclusive extraction and rule-version
    # receipts, and at least one real fiscal item with independent tax review.
    if (r6.get("g5_policy_hash") != policy or
        r6.get("fiscal_authority_verified") is not True):
        stop("R6_COMPETENT_FISCAL_REVIEW_MISSING")
    links = r6.get("source_links")
    if not isinstance(links, list) or len(links) != 2 or (
       {p.get("document_id") for p in links if isinstance(p, Mapping)}
            != set(C3_DOCUMENTS)):
        stop("R6_TWO_NORMATIVE_SOURCES_REQUIRED")
    for p in links:
        if not isinstance(p, Mapping):
            stop("R6_SOURCE_LINK_NOT_OBJECT")
        original = receipts[p["document_id"]]
        if (p.get("normative_artifact_id") != original["normative_artifact_id"]
                or p.get("normative_artifact_record_hash") != original["normative_artifact_record_hash"]
                or p.get("artifact_hash") != original["artifact_hash"]
                or not p.get("extraction_result_id")
                or not _hash(p.get("extraction_result_record_hash"))
                or not p.get("rule_version_record_id")
                or not _hash(p.get("rule_version_record_hash"))):
            stop("R6_NORMATIVE_EXTRACTION_RULE_LINK_MISSING")
    item = r6.get("nfe_item")
    if (not isinstance(item, Mapping) or item.get("ncm") not in R6_NCMS
            or not _hash(item.get("xml_sha256"))
            or not isinstance(item.get("nItem"), int) or item["nItem"] < 1
            or not item.get("cest") or not item.get("cfop")
            or not item.get("cst_or_csosn") or not item.get("regime")
            or not item.get("uf") or not item.get("operation_date")
            or not item.get("product_description")
            or "xml_bytes" in item or "xml_original" in item):
        stop("R6_REAL_PRIVATE_NFE_ITEM_NOT_COTEJADO")

    provenance = {}
    for name, receipt, callback in [
        ("G5_V3_R1", g5, verify_g5),
        ("R5_0064_0065", r5, verify_r5),
        ("R6_FISCAL", r6, verify_r6),
    ]:
        result = callback(receipt)
        if (not isinstance(result, Mapping) or result.get("verified") is not True
                or not _hash(result.get("act_sha256"))):
            stop("INDEPENDENT_VERIFICATION_NOT_COMPLETED_" + name)
        provenance[name] = {
            "receipt_json_sha256": _pure_digest(receipt),
            "competent_act_sha256": result["act_sha256"],
        }

    return {
        "schema": "SOLVERIS_B02_R7_FINAL_DECISION_INPUT_V1",
        "status": "R7_DECISION_INPUT_COMPLETE_NO_RELEASE",
        "g5_final_policy_sha256": policy,
        "r5_assigned_txid": r5["assigned_txid"],
        "source_pdf_artifacts": [{
            "document_id": x["document_id"],
            "normative_artifact_id": x["normative_artifact_id"],
            "normative_artifact_record_hash": x["normative_artifact_record_hash"],
        } for x in sorted(rows, key=lambda x: x["document_id"])],
        "r6_item": {"xml_sha256": item["xml_sha256"], "nItem": item["nItem"],
                    "ncm": item["ncm"], "cest": item["cest"]},
        "independently_verified_receipts": provenance,
        "r7_competent_decision": None,
        "b02_closed": False,
        "b03_released": False,
        "protected_database_writes_by_this_consumer": 0,
    }

if __name__ == "__main__":
    print(json.dumps(incomplete(), sort_keys=True))
