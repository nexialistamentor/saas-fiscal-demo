"""Constructor classification guards for the MEI reachability census."""

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


def test_constructor_classification_clears_only_targeted_persistence_scans():
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
from pathlib import Path
import ast

from app.scripts import mei_publication_reachability_census as census


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
