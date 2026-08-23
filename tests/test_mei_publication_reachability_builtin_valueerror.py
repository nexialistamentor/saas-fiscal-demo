from app.scripts.mei_publication_reachability_census import build_census


def test_simples_nacional_valueerror_subclasses_are_inert_callees():
    census = build_census()
    path = next(
        item for item in census["paths"]
        if item["entrypoint"] == "/imposto/simples-nacional"
    )
    assert path["mei_reachability"] != "UNRESOLVED_MEI", path.get("unresolved_app_callees")
