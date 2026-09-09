from app.scripts import mei_publication_reachability_census as census_module


def test_auth_register_current_constructor_topology_is_explicit():
    modules = census_module._parse_app()
    downstream = census_module._background_downstream_inventory(
        modules,
        function_id="app.auth_router.register_user",
    )

    assert downstream["producer_ids"] == []
    assert sorted(downstream["unresolved_app_callees"]) == sorted(
        [
            "app.models.User",
            "app.schemas.user_schema.UserResponse",
        ]
    )


def test_auth_register_has_no_canonical_mei_producer_after_qualified_constructors():
    census = census_module.build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/auth/register"
    )

    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["producer_ids"] == []
    assert path["sink_kinds"] == []
    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True
