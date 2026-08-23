"""RED: a statically proven OAuth2PasswordBearer object is not an app callee."""

from __future__ import annotations


def test_oauth2_password_bearer_dependency_object_is_qualified_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()

    assert census_module._is_inert_fastapi_security_dependency_object(
        modules,
        "app.security.oauth2_scheme",
    )

def test_logout_route_is_classified_after_oauth2_dependency_qualification_red():
    import app.scripts.mei_publication_reachability_census as census_module

    census = census_module.build_census()
    matches = [
        item
        for item in census["paths"]
        if item["entrypoint"] == "/auth/logout"
    ]

    assert len(matches) == 1
    path = matches[0]
    assert path["mei_reachability"] == "NO_CANONICAL_MEI_PRODUCER"
    assert path["producer_ids"] == []
    assert path["unresolved_app_callees"] == []
    assert path["downstream_scan_complete"] is True
