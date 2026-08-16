"""Minimal public surface for the first L3 enforcement vertical."""

from .decision_record import (
    RUN_INVALID_FOR_OBLIGATION,
    DecisionRecord,
    R1Result,
    check_r1_provenance_closure,
)
from .proof_spec import ProofSpec
from .registry import RealizationBinding

__all__ = [
    "RUN_INVALID_FOR_OBLIGATION",
    "DecisionRecord",
    "ProofSpec",
    "R1Result",
    "RealizationBinding",
    "check_r1_provenance_closure",
]
