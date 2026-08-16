"""Minimal proof-spec model for the first L3 enforcement vertical."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProofSpec:
    proof_spec_id: str
    obligation_id: str
    obligation_sha256: str
    decision_atom_ref: str
    production_entrypoint_ref: str
