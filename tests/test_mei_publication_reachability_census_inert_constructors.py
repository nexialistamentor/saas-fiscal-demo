"""Constructor classification guards for the MEI reachability census."""

import ast
from pathlib import Path

from app.scripts import mei_publication_reachability_census as census


def test_mei_engine_orm_scan_does_not_treat_proven_constructors_as_unresolved():
    modules = census._parse_app()

    result = census._reachable_orm_persistence_sinks(
        modules,
        function_id=census.MEI_ENGINE_EXECUTE_ID,
    )

    assert result["unresolved_app_callees"] == []
    assert result["scan_complete"] is True


def test_inert_pydantic_constructor_qualification_is_narrow():
    modules = census._parse_app()

    helper = census._is_inert_pydantic_model_constructor

    assert helper(
        modules,
        "app.schemas.source_authority_schema.SourceAuthorityRequest",
    ) is True

    assert helper(
        modules,
        "app.schemas.source_authority_schema.SourceAuthorityResult",
    ) is True

    assert helper(
        modules,
        "app.schemas.source_authority_schema.NormativeBindingResult",
    ) is True

    assert helper(
        modules,
        "app.schemas.source_authority_schema.NormativeBindingReason",
    ) is False

    assert helper(
        modules,
        "app.schemas.source_authority_schema.NormativeBindingItem",
    ) is False


def test_inert_single_app_base_constructor_qualification_is_narrow():
    modules = census._parse_app()

    helper = census._is_inert_single_app_base_constructor

    assert helper(
        modules,
        "app.services.tax_engines.mei_tax_engine.MEITaxEngine",
    ) is True

    assert helper(
        modules,
        "app.schemas.source_authority_schema.SourceAuthorityRequest",
    ) is False


def test_constructor_classification_clears_targeted_persistence_scans():
    result = census.build_census()

    targets = {
        "/formalizacao/comparar-regimes",
        "/formalizacao/simular-empresa",
        "/perguntar",
    }

    paths = {
        item["entrypoint"]: item
        for item in result["paths"]
        if item["entrypoint"] in targets
    }

    assert set(paths) == targets

    for entrypoint in sorted(targets):
        inventory = paths[entrypoint]["persistence_inventory"]
        assert inventory["unresolved_app_callees"] == []
        assert inventory["scan_complete"] is True


def test_reason_constructor_discovers_and_follows_real_field_validator(monkeypatch):
    modules = census._parse_app()
    constructor_id = (
        "app.schemas.source_authority_schema.NormativeBindingReason"
    )
    validator_id = (
        "app.schemas.source_authority_schema.NormativeBindingReason."
        "_validate_reason_field_representation"
    )

    assert census._pydantic_model_constructor_validator_ids(
        modules,
        constructor_id,
    ) == (validator_id,)

    visited: list[str] = []
    original = census._orm_persistence_operations

    def record_visited(modules, *, function_id):
        visited.append(function_id)
        return original(modules, function_id=function_id)

    monkeypatch.setattr(census, "_orm_persistence_operations", record_visited)

    result = census._reachable_orm_persistence_sinks(
        modules,
        function_id=constructor_id,
    )

    assert validator_id in visited
    assert (
        "app.schemas.source_authority_schema."
        "_validate_normative_text_representation"
    ) in visited
    assert result["sink_operations"] == {}
    assert result["unresolved_app_callees"] == []
    assert result["scan_complete"] is True


def test_inert_pydantic_constructor_rejects_default_factory():
    source = """
class SyntheticRequest(BaseModel):
    payload: dict = Field(default_factory=build_payload)
"""

    tree = ast.parse(source)

    module = census.ModuleInfo(
        name="app.synthetic_schema",
        path=Path("synthetic_schema.py"),
        tree=tree,
        imports={
            "BaseModel": "pydantic.BaseModel",
            "Field": "pydantic.Field",
        },
        functions={},
    )

    modules = {
        "app.synthetic_schema": module,
    }

    assert (
        census._is_inert_pydantic_model_constructor(
            modules,
            "app.synthetic_schema.SyntheticRequest",
        )
        is False
    )


def test_inert_pydantic_constructor_rejects_construction_hook():
    source = """
class SyntheticRequest(BaseModel):
    payload: str

    def model_post_init(self, context: object) -> None:
        record_construction(self)
"""

    tree = ast.parse(source)
    module = census.ModuleInfo(
        name="app.synthetic_schema",
        path=Path("synthetic_schema.py"),
        tree=tree,
        imports={"BaseModel": "pydantic.BaseModel"},
        functions={},
    )

    assert (
        census._is_inert_pydantic_model_constructor(
            {"app.synthetic_schema": module},
            "app.synthetic_schema.SyntheticRequest",
        )
        is False
    )


def test_pydantic_constructor_rejects_unknown_decorator():
    source = """
class SyntheticRequest(BaseModel):
    payload: str

    @unknown_validator("payload")
    @classmethod
    def validate_payload(cls, value: str) -> str:
        return value
"""

    tree = ast.parse(source)
    module = census.ModuleInfo(
        name="app.synthetic_schema",
        path=Path("synthetic_schema.py"),
        tree=tree,
        imports={"BaseModel": "pydantic.BaseModel"},
        functions={},
    )

    assert census._pydantic_model_constructor_validator_ids(
        {"app.synthetic_schema": module},
        "app.synthetic_schema.SyntheticRequest",
    ) is None
