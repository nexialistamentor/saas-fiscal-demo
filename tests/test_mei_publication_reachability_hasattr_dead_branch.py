"""RED: a missing method behind a matching hasattr guard is not reachable."""

from __future__ import annotations


def test_missing_method_behind_matching_hasattr_guard_is_not_a_direct_callee_red():
    import app.scripts.mei_publication_reachability_census as census_module

    modules = census_module._parse_app()
    found = census_module._function_node(
        modules,
        "app.auth_router.eliminar_meus_dados",
    )
    assert found is not None
    module, node = found

    callees = census_module._direct_callees(module, node)

    assert (
        "app.token_revocation.RevogacaoJti.revogar_todos_do_user"
        not in callees
    )
