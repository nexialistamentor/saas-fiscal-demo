"""Decision provenance and R1 per-obligation provenance closure."""

from dataclasses import dataclass
from typing import Optional

from .proof_spec import ProofSpec
from .registry import RealizationBinding


RUN_INVALID_FOR_OBLIGATION = "RUN_INVALID_FOR_OBLIGATION"


@dataclass(frozen=True)
class DecisionRecord:
    obligation_id: str
    obligation_sha256: str
    proof_spec_id: str
    decision_atom_ref: str
    production_entrypoint_ref: str


@dataclass(frozen=True)
class R1Result:
    valid: bool
    invalid_family: Optional[str] = None


def check_r1_provenance_closure(
    target: ProofSpec,
    realization: RealizationBinding,
    decision_record: DecisionRecord,
) -> R1Result:
    """Check that decision provenance belongs to the target obligation."""
    if (
        decision_record.obligation_id != target.obligation_id
        or decision_record.obligation_sha256 != target.obligation_sha256
    ):
        return R1Result(valid=False, invalid_family=RUN_INVALID_FOR_OBLIGATION)

    expected_binding = (
        target.proof_spec_id,
        target.decision_atom_ref,
        target.production_entrypoint_ref,
    )
    registered_binding = (
        realization.proof_spec_id,
        realization.decision_atom_ref,
        realization.production_entrypoint_ref,
    )
    recorded_binding = (
        decision_record.proof_spec_id,
        decision_record.decision_atom_ref,
        decision_record.production_entrypoint_ref,
    )

    if registered_binding != expected_binding or recorded_binding != registered_binding:
        return R1Result(valid=False, invalid_family=RUN_INVALID_FOR_OBLIGATION)

    return R1Result(valid=True)
