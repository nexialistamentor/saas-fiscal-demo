"""Regressoes da unidade transacional de inteligencia sob escritor XML."""
from unittest.mock import MagicMock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Empresa, RelatorioAnalise, Insight, UsoPlataforma, AlertaFiscal
from app.services import memoria_estrategica_service as memoria
from app.services import insights_engine as insights_mod
from app.services import registro_analise_service as registro


def test_snapshot_sem_commit_autonomo():
    db = MagicMock()
    db.execute.return_value.fetchone.return_value = (1, 1)
    memoria.registrar_snapshot_inteligencia(db, 10, 100, "baixo", "iniciante",  )
    assert db.execute.call_count == 2
    db.commit.assert_not_called()


def test_insight_engine_nao_confirma_ao_ser_controlada_pelo_escritor(monkeypatch):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    engine = insights_mod.InsightEngine(db)
    monkeypatch.setattr(engine, "_montar_contexto_engines", lambda empresa_id: {"context_flags": {}})
    for name in (
        "_analisar_restituicao_st", "_analisar_anomalia_mva",
        "_analisar_concentracao_ncm", "_analisar_margem_real",
        "_analisar_st_sem_saida", "_analisar_st_sem_saida_por_ncm",
        "_analisar_mva_oficial_divergente", "_analisar_decisao_st",
        "_analisar_ranking_restituicao", "_analisar_creditos",
        "_analisar_distorcoes", "_obter_radar_tributario",
        "_analisar_oportunidades_preditivas", "_analisar_ranking_estrategico",
        "_analisar_impacto_financeiro",
    ):
        monkeypatch.setattr(engine, name, lambda *a, **kw: [])
    monkeypatch.setattr(insights_mod, "prever_impacto_st", lambda *a: [])
    monkeypatch.setattr(insights_mod, "calcular_score_global_tributario",
                        lambda *a: {"score_global_tributario": 10})
    monkeypatch.setattr(insights_mod, "calcular_risco_tributario",
                        lambda *a: {"nivel_risco": "baixo"})
    monkeypatch.setattr(insights_mod, "calcular_maturidade_tributaria",
                        lambda *a: {"nivel_maturidade": "iniciante"})
    snapshot = MagicMock()
    monkeypatch.setattr(insights_mod, "registrar_snapshot_inteligencia", snapshot)
    monkeypatch.setattr(insights_mod, "executar_engines", lambda *a: {})
    monkeypatch.setattr(insights_mod, "gerar_mapa_oportunidades",
                        lambda *a: {"context_flags": {}, "decomposicao_impacto": {}})
    r = engine.gerar_insights_empresa(10, relatorio_analise_id=20, commit=False)
    assert r["empresa_id"] == 10
    db.commit.assert_not_called()
    assert snapshot.call_args.kwargs == {}


@pytest.mark.parametrize("cenario", ["falha_selo", "falha_uso", "sucesso"])
def test_writer_atomicidade_insights_relatorio_e_uso(monkeypatch, cenario):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    models = (User, Empresa, RelatorioAnalise, Insight, UsoPlataforma, AlertaFiscal)
    Base.metadata.create_all(engine, tables=[m.__table__ for m in models])
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        db.add(User(id=7, email="writer-atomicidade@synthetic.invalid", hashed_password="!"))
        db.add(Empresa(id=41, user_id=7, cnpj="12345678000190",
                       regime_tributario="real", optante_mei=False))
        db.commit()
        monkeypatch.setattr(registro, "executar_analise_xml", lambda _: {"dados_fiscais": {}})
        monkeypatch.setattr(registro, "processar_e_persistir_xml", lambda **kw: None)
        monkeypatch.setattr(registro, "calcular_score_global_tributario", lambda *a: {})
        chamadas = []

        def stage_insight(self, empresa_id, relatorio_analise_id=None, *, commit=True):
            chamadas.append(commit)
            db.add(Insight(empresa_id=empresa_id, relatorio_analise_id=relatorio_analise_id,
                           tipo="TESTE_ATOMICIDADE"))
            db.flush()
            return {"empresa_id": empresa_id}

        monkeypatch.setattr(insights_mod.InsightEngine, "gerar_insights_empresa", stage_insight)

        if cenario == "falha_selo":
            def falha_apos_insights(*args, **kwargs):
                raise ValueError("FALHA_SELO_INJETADA")
            monkeypatch.setattr(registro, "selar_resultado_nao_mei", falha_apos_insights)
        elif cenario == "falha_uso":
            def falha_contabilizacao(*args, **kwargs):
                raise ValueError("FALHA_USO_INJETADA")
            monkeypatch.setattr(registro, "incrementar_uso_analise", falha_contabilizacao)

        if cenario == "sucesso":
            rel, _ = registro.executar_e_registrar_analise_xml(db, b"<xml/>", 7, 41)
            assert rel.status == "ok"
            assert db.query(Insight).count() == 1
            assert db.query(UsoPlataforma).filter_by(empresa_id=41).one().analises_mes == 1
        else:
            with pytest.raises(ValueError, match="FALHA_SELO_INJETADA|FALHA_USO_INJETADA"):
                registro.executar_e_registrar_analise_xml(db, b"<xml/>", 7, 41)
            assert db.query(Insight).count() == 0
            assert db.query(UsoPlataforma).count() == 0
        assert chamadas == [False]
    finally:
        db.close()
        engine.dispose()
