"""RED: every mounted route must be classified or keep Gate A unresolved."""

from __future__ import annotations


def test_unclassified_mounted_routes_keep_gate_a_unresolved_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    mounted = census_module._mounted_routers(modules)

    mounted_entrypoints: set[str] = set()
    for module_name, (router_object, prefix) in sorted(mounted.items()):
        module = modules[module_name]
        router_prefix = census_module._router_intrinsic_prefix(module, router_object)
        for local_name, node in sorted(module.functions.items()):
            if "." in local_name:
                continue
            route_path = census_module._route_decorator(
                node,
                router_object=router_object,
            )
            if route_path is None:
                continue
            mounted_entrypoints.add(f"{prefix}{router_prefix}{route_path}" or "/")

    census = census_module.build_census()
    classified_entrypoints = {
        item["entrypoint"] for item in census["paths"]
    }
    expected_unclassified = sorted(mounted_entrypoints - classified_entrypoints)

    assert expected_unclassified
    assert census["unclassified_entrypoints"] == expected_unclassified
    assert census["route_coverage_complete"] is False
    assert census["scan_complete"] is False
    assert census["status"] == "UNRESOLVED"
