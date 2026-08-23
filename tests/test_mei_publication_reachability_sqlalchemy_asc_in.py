from app.scripts.mei_publication_reachability_census import build_census


def test_real_sqlalchemy_asc_and_in_routes_are_resolved():
    census = build_census()
    paths = {item["entrypoint"]: item for item in census["paths"]}
    targets = {
        "/contador/homologacoes/pendentes",
        "/contador/homologacoes/{documento_id}/assumir",
        "/dashboard/alertas/timeline/{empresa_id}",
        "/documentos/",
        "/relatorio/memorial/{relatorio_id}",
        "/relatorio/memorial/{relatorio_id}/pdf",
    }
    for entrypoint in sorted(targets):
        assert paths[entrypoint]["mei_reachability"] != "UNRESOLVED_MEI", (
            entrypoint,
            paths[entrypoint].get("unresolved_app_callees"),
        )
