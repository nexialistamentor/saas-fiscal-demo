"""Human-ratified realization bindings used by L3 enforcement."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RealizationBinding:
    proof_spec_id: str
    decision_atom_ref: str
    production_entrypoint_ref: str
