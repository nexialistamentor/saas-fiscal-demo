from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BootstrapAuthorityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bootstrap_authority_record_id: Annotated[str, Field(min_length=1, max_length=64)]
    bootstrap_authority_record_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]


class ActivePolicyChainAuthorityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_authority_policy_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    activation_authority_policy_version: Annotated[int, Field(ge=1)]
    activation_authority_policy_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    activation_authority_policy_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]


class AutomaticDelegatedAuthorityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activation_authority_policy_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    activation_authority_policy_version: Annotated[int, Field(ge=1)]
    activation_authority_policy_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    activation_authority_policy_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    automation_envelope_id: Annotated[str, Field(min_length=1, max_length=64)]
    automation_envelope_version: Annotated[int, Field(ge=1)]
    automation_envelope_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    automation_envelope_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]


class BootstrapAutomaticAuthorityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bootstrap_authority_record_id: Annotated[str, Field(min_length=1, max_length=64)]
    bootstrap_authority_record_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    automation_envelope_id: Annotated[str, Field(min_length=1, max_length=64)]
    automation_envelope_version: Annotated[int, Field(ge=1)]
    automation_envelope_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    automation_envelope_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]


class PolicyBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_type: Literal[
        "activation_authority",
        "automation_envelope",
        "normative_precedence",
        "normative_continuity",
        "coverage_contract",
    ]
    policy_id: Annotated[str, Field(min_length=1, max_length=64)]
    policy_version: Annotated[int, Field(ge=1)]
    policy_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    policy_activation_id: Annotated[str, Field(min_length=1, max_length=64)]
    policy_activation_record_hash: Annotated[
        str, Field(min_length=64, max_length=64)
    ]


class CoverageContractBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coverage_subject_type: Literal["coverage_contract"]
    coverage_contract_id: Annotated[str, Field(min_length=1, max_length=64)]
    contract_version: Annotated[int, Field(ge=1)]
    contract_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    coverage_contract_record_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    coverage_contract_record_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]


class ContinuityBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    continuity_subject_type: Literal["normative_continuity"]
    continuity_policy_id: Annotated[str, Field(min_length=1, max_length=64)]
    continuity_policy_version: Annotated[int, Field(ge=1)]
    continuity_policy_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    continuity_policy_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    continuity_policy_activation_record_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]


class PrecedenceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    precedence_subject_type: Literal["normative_precedence"]
    precedence_policy_id: Annotated[str, Field(min_length=1, max_length=64)]
    precedence_policy_version: Annotated[int, Field(ge=1)]
    precedence_policy_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]
    precedence_policy_activation_id: Annotated[
        str, Field(min_length=1, max_length=64)
    ]
    precedence_policy_activation_record_hash: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    ]


class GateEvidenceBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: Annotated[str, Field(min_length=1, max_length=64)]
    gate_version: Annotated[int, Field(ge=1)]
    gate_hash: Annotated[
        str,
        Field(
            min_length=64,
            max_length=64,
            pattern=r"^[0-9a-f]{64}$",
        ),
    ]
    gate_outcome: Annotated[str, Field(min_length=1, max_length=64)]
    evidence_record_id: Annotated[str, Field(min_length=1, max_length=64)]
    evidence_record_hash: Annotated[
        str,
        Field(
            min_length=64,
            max_length=64,
            pattern=r"^[0-9a-f]{64}$",
        ),
    ]


class ADR020BindingsContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_bindings: (
        BootstrapAuthorityBinding
        | ActivePolicyChainAuthorityBinding
        | AutomaticDelegatedAuthorityBinding
        | BootstrapAutomaticAuthorityBinding
    )
    policy_bindings: Annotated[list[PolicyBinding], Field(min_length=1)]
    coverage_binding: CoverageContractBinding
    continuity_binding: ContinuityBinding
    precedence_binding: PrecedenceBinding
    gates_evidence: Annotated[list[GateEvidenceBinding], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_continuity_binding(self) -> "ADR020BindingsContract":
        continuity = self.continuity_binding
        matches = sum(
            1
            for policy in self.policy_bindings
            if policy.policy_type == continuity.continuity_subject_type
            and policy.policy_id == continuity.continuity_policy_id
            and policy.policy_version == continuity.continuity_policy_version
            and policy.policy_hash == continuity.continuity_policy_hash
            and policy.policy_activation_id
            == continuity.continuity_policy_activation_id
            and policy.policy_activation_record_hash
            == continuity.continuity_policy_activation_record_hash
        )
        if matches != 1:
            raise ValueError(
                "continuity_binding must match exactly one normative_continuity "
                "policy_binding"
            )
        return self

    @model_validator(mode="after")
    def validate_precedence_binding(self) -> "ADR020BindingsContract":
        precedence = self.precedence_binding
        matches = sum(
            1
            for policy in self.policy_bindings
            if policy.policy_type == precedence.precedence_subject_type
            and policy.policy_id == precedence.precedence_policy_id
            and policy.policy_version == precedence.precedence_policy_version
            and policy.policy_hash == precedence.precedence_policy_hash
            and policy.policy_activation_id
            == precedence.precedence_policy_activation_id
            and policy.policy_activation_record_hash
            == precedence.precedence_policy_activation_record_hash
        )
        if matches != 1:
            raise ValueError(
                "precedence_binding must match exactly one normative_precedence "
                "policy_binding"
            )
        return self
