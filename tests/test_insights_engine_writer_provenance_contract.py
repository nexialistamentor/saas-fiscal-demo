from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models import Empresa, EngineResultado, RelatorioAnalise
from app.services.insights_engine import InsightEngine
from app.services.resultado_provenance_service import (
    PROVENANCE_KEY,
    fingerprint_resultado_json,
    verificar_resultado_persistido,
)


PRODUCER_ID = "app.services.insights_engine.InsightEngine.gerar_insights_empresa"


def test_insight_engine_writer_persiste_empresa_tax_verificavel_sem_expor_proveniencia(
    monkeypatch,
):
    from app.services import insights_engine as module
    from app.services import registro_analise_service

    empresa_id = 731
    user_id = 419
    empresa = SimpleNamespace(
        id=empresa_id,
        user_id=user_id,
        regime_tributario="presumido",
    )
    added = []
    db = MagicMock()

    def query(model):
        result = MagicMock()
        if model is Empresa:
            result.filter.return_value.first.return_value = empresa
        else:
            result.filter.return_value.order_by.return_value.first.return_value = None
        return result

    def add(instance):
        added.append(instance)

    def flush():
        for instance in added:
            if isinstance(instance, RelatorioAnalise) and instance.id is None:
                instance.id = 991

    db.query.side_effect = query
    db.add.side_effect = add
    db.flush.side_effect = flush

    engine = InsightEngine(db)
    empty_analyses = (
        "_analisar_restituicao_st",
        "_analisar_anomalia_mva",
        "_analisar_concentracao_ncm",
        "_analisar_margem_real",
        "_analisar_st_sem_saida",
        "_analisar_st_sem_saida_por_ncm",
        "_analisar_mva_oficial_divergente",
        "_analisar_decisao_st",
        "_analisar_ranking_restituicao",
        "_analisar_creditos",
        "_analisar_distorcoes",
        "_obter_radar_tributario",
        "_analisar_oportunidades_preditivas",
        "_analisar_ranking_estrategico",
        "_analisar_impacto_financeiro",
    )
    for name in empty_analyses:
        monkeypatch.setattr(engine, name, lambda *args, **kwargs: [])

    context = {
        "empresa_id": empresa_id,
        "regime": "presumido",
        "context_flags": {
            "dados_incompletos": False,
            "valores_normalizados": False,
            "usa_estimativa": False,
            "base_presumida": True,
        },
    }
    resultados_engines = {
        "tax_planning": {
            "comparacao": {"lucro_real": 120.0, "lucro_presumido": 95.0},
            "melhor_regime": "lucro_presumido",
        }
    }
    monkeypatch.setattr(engine, "_montar_contexto_engines", lambda _id: deepcopy(context))
    monkeypatch.setattr(module, "prever_impacto_st", lambda _db, _id: [])
    monkeypatch.setattr(
        module,
        "calcular_score_global_tributario",
        lambda _db, _id: {"score_global_tributario": 87.5},
    )
    monkeypatch.setattr(
        module,
        "calcular_risco_tributario",
        lambda _db, _id: {"nivel_risco": "baixo"},
    )
    monkeypatch.setattr(
        module,
        "calcular_maturidade_tributaria",
        lambda _db, _id: {"nivel_maturidade": "alto"},
    )
    monkeypatch.setattr(module, "registrar_snapshot_inteligencia", lambda *args: None)
    monkeypatch.setattr(module, "executar_engines", lambda _context: deepcopy(resultados_engines))
    monkeypatch.setattr(
        module,
        "gerar_mapa_oportunidades",
        lambda _db, _id: {
            "context_flags": {},
            "decomposicao_impacto": {"oportunidades": 0},
        },
    )
    monkeypatch.setattr(
        module,
        "anexar_flags_nos_resultados_engines",
        lambda resultados, _flags: deepcopy(resultados),
    )
    monkeypatch.setattr(
        registro_analise_service,
        "contar_alertas_empresa",
        lambda _db, _id: 0,
    )

    retorno = engine.gerar_insights_empresa(empresa_id)

    relatorios = [item for item in added if isinstance(item, RelatorioAnalise)]
    assert len(relatorios) == 1
    relatorio = relatorios[0]
    assert relatorio.analysis_type == "empresa_tax"
    assert relatorio.user_id == user_id
    assert relatorio.empresa_id == empresa_id
    assert db.commit.call_count == 1
    db.rollback.assert_not_called()

    resultados_persistidos = [
        item for item in added if isinstance(item, EngineResultado)
    ]
    assert len(resultados_persistidos) == 1
    resultados_engines_enriquecidos = {
        resultados_persistidos[0].engine_nome: resultados_persistidos[0].resultado
    }
    assert resultados_engines_enriquecidos == {
        "tax_planning": {
            "comparacao": {"lucro_real": 120.0, "lucro_presumido": 95.0},
            "melhor_regime": "lucro_presumido",
            "_versao_engine": "1.0",
        }
    }
    assert retorno == {
        "empresa_id": empresa_id,
        "oportunidades": [],
        "creditos_detectados": [],
        "risco_tributario": {"nivel_risco": "baixo"},
        "resultados_engines": resultados_engines_enriquecidos,
        "comparativo_regime": {
            "lucro_real": 120.0,
            "lucro_presumido": 95.0,
            "diferenca": 25.0,
            "melhor_regime": "lucro_presumido",
        },
        "context_flags": {
            "dados_incompletos": False,
            "valores_normalizados": False,
            "usa_estimativa": False,
            "base_presumida": True,
        },
        "decomposicao_impacto": {
            "oportunidades": 0,
            "normalizacoes_aplicadas": 0,
        },
    }
    assert "comparativo_regime" not in relatorio.resultado_json
    retorno_sem_comparativo = deepcopy(retorno)
    retorno_sem_comparativo.pop("comparativo_regime")
    negocio_persistido = deepcopy(relatorio.resultado_json)
    negocio_persistido.pop(PROVENANCE_KEY, None)
    assert retorno_sem_comparativo == negocio_persistido
    assert PROVENANCE_KEY not in retorno

    relatorio_analise_id_fornecido = 177
    added.clear()
    db.reset_mock()
    engine.gerar_insights_empresa(
        empresa_id,
        relatorio_analise_id=relatorio_analise_id_fornecido,
    )
    assert not any(isinstance(item, RelatorioAnalise) for item in added)
    resultados_com_id_fornecido = [
        item for item in added if isinstance(item, EngineResultado)
    ]
    assert len(resultados_com_id_fornecido) == 1
    assert (
        resultados_com_id_fornecido[0].relatorio_analise_id
        == relatorio_analise_id_fornecido
    )
    assert db.commit.call_count == 1
    db.rollback.assert_not_called()

    payload_persistido = verificar_resultado_persistido(relatorio)
    assert relatorio.resultado_json[PROVENANCE_KEY]["producer_id"] == PRODUCER_ID
    assert relatorio.fingerprint == fingerprint_resultado_json(relatorio.resultado_json)
    assert payload_persistido == negocio_persistido
    assert PROVENANCE_KEY not in payload_persistido
    assert retorno == {
        **payload_persistido,
        "comparativo_regime": retorno["comparativo_regime"],
    }
