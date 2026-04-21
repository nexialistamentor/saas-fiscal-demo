from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import get_usuario_atual, tenant_empresa
from app.services.ranking_restituicao_service import gerar_ranking_restituicao
from app.services.mapa_oportunidades_service import gerar_mapa_oportunidades
from app.services.detector_creditos_service import detectar_creditos
from app.services.analisador_distorcao_service import detectar_distorcoes
from app.services.motor_preditivo_service import calcular_potencial_recuperacao
from app.services.ranking_estrategico_service import gerar_ranking_estrategico
from app.services.impacto_financeiro_service import calcular_impacto_financeiro
from app.services.indice_inteligencia_service import calcular_indice_inteligencia
from app.services.score_tributario_service import calcular_score_tributario
from app.services.radar_tributario_service import gerar_radar_tributario
from app.services.benchmark_fiscal_service import gerar_benchmark_empresas
from app.services.anomalias_tributarias_service import detectar_anomalias_tributarias
from app.services.prioridade_auditoria_service import calcular_prioridade_auditoria
from app.services.projecao_recuperacao_service import projetar_recuperacao_tributaria
from app.services.risco_tributario_service import calcular_risco_tributario
from app.services.oportunidades_recuperacao_service import ranking_oportunidades_recuperacao
from app.services.eficiencia_tributaria_service import calcular_eficiencia_tributaria
from app.services.complexidade_tributaria_service import calcular_complexidade_tributaria
from app.services.maturidade_tributaria_service import calcular_maturidade_tributaria
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app.services.historico_inteligencia_service import obter_historico_inteligencia
from app.services.tendencia_inteligencia_service import analisar_tendencia_inteligencia
from app.services.comparacao_temporal_service import comparar_periodos_inteligencia

inteligencia_router = APIRouter(
    prefix="/inteligencia",
    tags=["Inteligência Tributária"]
)


@inteligencia_router.get("/oportunidades-recuperacao/{empresa_id}")
def oportunidades_recuperacao(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return ranking_oportunidades_recuperacao(db, empresa.id)


@inteligencia_router.get("/ranking-restituicao/{empresa_id}")
def ranking_restituicao(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return gerar_ranking_restituicao(db, empresa.id)


@inteligencia_router.get("/mapa-oportunidades/{empresa_id}")
def mapa_oportunidades(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    mapa = gerar_mapa_oportunidades(db, empresa.id)
    mapa["consulta_paga"] = usuario_atual.consulta_paga
    return mapa


@inteligencia_router.get("/creditos/{empresa_id}")
def creditos_fiscais(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return detectar_creditos(db, empresa.id)


@inteligencia_router.get("/distorcoes/{empresa_id}")
def distorcoes_tributarias(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return detectar_distorcoes(db, empresa.id)


@inteligencia_router.get("/oportunidades-preditivas/{empresa_id}")
def oportunidades_preditivas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_potencial_recuperacao(db, empresa.id)


@inteligencia_router.get("/ranking-estrategico/{empresa_id}")
def ranking_estrategico(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return gerar_ranking_estrategico(db, empresa.id)


@inteligencia_router.get("/impacto-financeiro/{empresa_id}")
def impacto_financeiro(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_impacto_financeiro(db, empresa.id)


@inteligencia_router.get("/indice-inteligencia/{empresa_id}")
def indice_inteligencia(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_indice_inteligencia(db, empresa.id)


@inteligencia_router.get("/score-tributario/{empresa_id}")
def score_tributario(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_score_tributario(db, empresa.id)


@inteligencia_router.get("/radar-tributario/{empresa_id}")
def radar_tributario(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return gerar_radar_tributario(db, empresa.id)


@inteligencia_router.get("/benchmark-empresas")
def benchmark_empresas(
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    empresa_ids = [e.id for e in usuario_atual.empresas] if usuario_atual.empresas else []
    return gerar_benchmark_empresas(db, empresa_ids=empresa_ids)


@inteligencia_router.get("/anomalias-tributarias/{empresa_id}")
def anomalias_tributarias(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return detectar_anomalias_tributarias(db, empresa.id)


@inteligencia_router.get("/prioridade-auditoria/{empresa_id}")
def prioridade_auditoria(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_prioridade_auditoria(db, empresa.id)


@inteligencia_router.get("/projecao-recuperacao/{empresa_id}")
def projecao_recuperacao(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return projetar_recuperacao_tributaria(db, empresa.id)


@inteligencia_router.get("/risco-tributario/{empresa_id}")
def risco_tributario(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_risco_tributario(db, empresa.id)


@inteligencia_router.get("/eficiencia-tributaria/{empresa_id}")
def eficiencia_tributaria(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_eficiencia_tributaria(db, empresa.id)


@inteligencia_router.get("/complexidade-tributaria/{empresa_id}")
def complexidade_tributaria(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_complexidade_tributaria(db, empresa.id)


@inteligencia_router.get("/maturidade-tributaria/{empresa_id}")
def maturidade_tributaria(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_maturidade_tributaria(db, empresa.id)


@inteligencia_router.get("/score-global-tributario/{empresa_id}")
def score_global_tributario(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return calcular_score_global_tributario(db, empresa.id)


@inteligencia_router.get("/historico-inteligencia/{empresa_id}")
def historico_inteligencia(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return obter_historico_inteligencia(db, empresa.id)


@inteligencia_router.get("/tendencia-inteligencia/{empresa_id}")
def tendencia_inteligencia(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return analisar_tendencia_inteligencia(db, empresa.id)


@inteligencia_router.get("/comparacao-temporal/{empresa_id}")
def comparacao_temporal(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    return comparar_periodos_inteligencia(db, empresa.id)
