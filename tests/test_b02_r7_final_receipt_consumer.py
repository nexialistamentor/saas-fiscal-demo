"""New R7 final receipt intake tests only; never rerun historical 11+2."""
import pytest
from tools import b02_r7_final_receipt_consumer as m

def test_missing_final_receipts_leave_b02_open():
    r=m.incomplete()
    assert r["status"]=="B02_OPEN_B03_BLOCKED"
    assert r["b02_closed"] is False and r["b03_released"] is False
    assert len(r["missing_final_receipts"])==3

def test_incomplete_r7_snapshot_cannot_be_promoted():
    prior={"status":"B02_OPEN_B03_BLOCKED","r7_closed":False,
           "b03_released":False,"protected_writes":0,
           "successor_proofs_count":149,
           "closed_gates_only_in_scope":["CURRENT_G4_V3_SUCCESSOR","RCV31_A2_V4_OWN_REVIEW"]}
    with pytest.raises(ValueError,match="G5_FINAL_POLICY_ROOT_REVIEW_RATIFICATION_REQUIRED"):
        m.assemble_decision_input(historical_r7=prior,g5={},r5={},r6={},
                                  verify_g5=lambda x:{},verify_r5=lambda x:{},verify_r6=lambda x:{})
