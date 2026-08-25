from app.scripts import mei_publication_reachability_census as census


def test_dashboard_engine_resultado_mei_fallback_is_explicitly_guarded_red():
    result = census.build_census()

    matches = [
        item
        for item in result["paths"]
        if item["entrypoint"]
        == "/dashboard/relatorio/{relatorio_id}/oportunidades"
    ]

    assert len(matches) == 1
    path = matches[0]

    guard = path["engine_resultado_mei_fallback_guard"]

    assert guard == {
        "persistence_model": "app.models.EngineResultado",
        "persistence_field": "resultado",
        "engine_name_field": "engine_nome",
        "mei_engine_name": "mei_tax",
        "blocked_before_publication": True,
        "blocker_code": "PERSISTED_MEI_PROVENANCE_UNPROVEN",
    }
from pathlib import Path
import ast

import pytest

from app.scripts import mei_publication_reachability_census as census


def test_dashboard_engine_resultado_guard_rejects_detached_result_source():
    source = """
def oportunidades_por_relatorio(relatorio_id):
    engines = (
        db.query(EngineResultado)
        .filter(EngineResultado.relatorio_analise_id == relatorio_id)
        .all()
    )

    oportunidades_engines = []

    for e in engines:
        r = {"oportunidades": [{"detached": True}]}
        engine_oportunidades = r.get("oportunidades") or []

        if (
            getattr(e, "engine_nome", None) == ANALYSIS_TYPE_MEI_TAX
            and engine_oportunidades
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": (
                        "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA"
                    ),
                    "estado_l3": "bloqueado",
                },
            )

        oportunidades_engines.extend(engine_oportunidades)
"""

    tree = ast.parse(source)
    node = tree.body[0]

    module = census.ModuleInfo(
        name="app.routers.dashboard_router",
        path=Path("synthetic_dashboard_router.py"),
        tree=tree,
        imports={
            "EngineResultado": "app.models.EngineResultado",
            "ANALYSIS_TYPE_MEI_TAX": (
                "app.services.analysis_types.ANALYSIS_TYPE_MEI_TAX"
            ),
        },
        functions={
            "oportunidades_por_relatorio": node,
        },
    )

    modules = {
        "app.routers.dashboard_router": module,
    }

    with pytest.raises(
        RuntimeError,
        match=(
            "MEI_REACHABILITY_UNRESOLVED_DASHBOARD_ENGINE_RESULTADO:"
            "result_source"
        ),
    ):
        census._dashboard_engine_resultado_mei_fallback_guard(
            modules,
            route_function_id=(
                "app.routers.dashboard_router."
                "oportunidades_por_relatorio"
            ),
        )
