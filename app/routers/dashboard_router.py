from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.models import AlertaFiscal, RelatorioAnalise, EngineResultado
from app.security import get_usuario_atual, tenant_empresa, verificar_empresa_do_usuario, verificar_acesso_relatorio
from app.services.resultado_provenance_service import (
    ResultadoProvenanceError,
    verificar_resultado_persistido,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/analises/{empresa_id}")
def listar_analises_empresa(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Histórico de análises da empresa. Dashboard usa para histórico, status, score,
    número de alertas e tempo de processamento.
    """
    analises = (
        db.query(RelatorioAnalise)
        .filter(RelatorioAnalise.empresa_id == empresa.id)
        .order_by(RelatorioAnalise.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": a.id,
            "xml_chave": a.xml_chave,
            "status": a.status,
            "tempo_execucao": a.tempo_execucao,
            "total_alertas": a.total_alertas,
            "score": a.score_resultante,
            "data": a.created_at
        }
        for a in analises
    ]


@router.get("/relatorio/{relatorio_id}")
def detalhe_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Detalhe da análise por ID. Inclui tempo de processamento, status, score.
    Alimenta header/card de resumo das telas de alertas e oportunidades.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    return {
        "id": rel.id,
        "empresa_id": rel.empresa_id,
        "analysis_type": rel.analysis_type,
        "xml_chave": rel.xml_chave,
        "status": rel.status,
        "tempo_execucao": rel.tempo_execucao,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "total_alertas": rel.total_alertas,
        "score_resultante": rel.score_resultante,
        "created_at": rel.created_at,
    }


@router.get("/relatorio/{relatorio_id}/alertas")
def alertas_por_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Alertas vinculados a um relatório de análise específico.
    Alimenta a tela principal de alertas do dashboard.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    alertas = (
        db.query(AlertaFiscal)
        .filter(
            AlertaFiscal.relatorio_analise_id == relatorio_id,
            AlertaFiscal.silenciado != True,
        )
        .order_by(AlertaFiscal.criado_em.desc())
        .all()
    )
    return {
        "relatorio_id": relatorio_id,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "total_alertas": len(alertas),
        "alertas": [
            {
                "id": a.id,
                "agente": a.agente,
                "tipo": a.tipo,
                "descricao": a.descricao,
                "nivel": a.nivel,
                "data": a.criado_em,
            }
            for a in alertas
        ],
    }


@router.get("/relatorio/{relatorio_id}/oportunidades")
def oportunidades_por_relatorio(
    relatorio_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """
    Oportunidades vinculadas a um relatório de análise específico.
    Alimenta a tela principal de oportunidades do dashboard.
    Extrai de resultado_json ou engine_resultados.
    """
    rel = db.query(RelatorioAnalise).filter(RelatorioAnalise.id == relatorio_id).first()
    if not rel:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    verificar_acesso_relatorio(rel, usuario_atual, db)
    oportunidades = []
    creditos = []
    try:
        rj = verificar_resultado_persistido(rel)
    except ResultadoProvenanceError:
        raise HTTPException(
            status_code=409,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "RESULTADO_PERSISTIDO_PROVENIENCIA_NAO_COMPROVADA",
                "estado_l3": "bloqueado",
            },
        ) from None
    oportunidades = rj.get("oportunidades") or []
    creditos = rj.get("creditos_detectados") or []
    engines = (
        db.query(EngineResultado)
        .filter(EngineResultado.relatorio_analise_id == relatorio_id)
        .all()
    )
    oportunidades_engines = []
    for e in engines:
        r = (e.resultado or {}) if hasattr(e, "resultado") else {}
        if isinstance(r, dict):
            oportunidades_engines.extend(r.get("oportunidades") or [])
    if not oportunidades and oportunidades_engines:
        oportunidades = oportunidades_engines
    return {
        "relatorio_id": relatorio_id,
        "tempo_processamento_segundos": rel.tempo_execucao,
        "oportunidades": oportunidades,
        "creditos_detectados": creditos,
        "total_oportunidades": len(oportunidades) + len(creditos),
    }


@router.get("/risco/{empresa_id}")
def score_risco(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    score = 0

    for alerta in alertas:
        if alerta.nivel == "critico":
            score += 40
        elif alerta.nivel == "alto":
            score += 20
        elif alerta.nivel == "medio":
            score += 10

    score = min(score, 100)

    return {
        "empresa_id": empresa.id,
        "score_risco": score
    }


@router.get("/resumo/{empresa_id}")
def resumo_dashboard(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    total_alertas = len(alertas)

    criticos = len([a for a in alertas if a.nivel == "critico"])
    altos = len([a for a in alertas if a.nivel == "alto"])
    medios = len([a for a in alertas if a.nivel == "medio"])

    return {
        "empresa_id": empresa.id,
        "total_alertas": total_alertas,
        "alertas_criticos": criticos,
        "alertas_altos": altos,
        "alertas_medios": medios
    }


@router.get("/alertas/{empresa_id}")
def listar_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id, AlertaFiscal.silenciado != True)
        .order_by(AlertaFiscal.criado_em.desc())
        .all()
    )

    return [
        {
            "id": a.id,
            "agente": a.agente,
            "tipo": a.tipo,
            "descricao": a.descricao,
            "nivel": a.nivel,
            "data": a.criado_em
        }
        for a in alertas
    ]


@router.get("/alertas/timeline/{empresa_id}")
def timeline_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Retorna linha do tempo de alertas da empresa.
    Alimenta: gráfico de linha, evolução do risco, histórico operacional,
    quando os problemas começaram, picos de atividade fiscal.
    """
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .order_by(AlertaFiscal.criado_em.asc())
        .all()
    )

    return [
        {
            "data": a.criado_em,
            "nivel": a.nivel,
            "tipo": a.tipo
        }
        for a in alertas
    ]


@router.get("/alertas/agentes/{empresa_id}")
def alertas_por_agente(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    """
    Retorna alertas agrupados por agente.
    Alimenta: gráfico de origem dos alertas, saúde da plataforma, análise operacional.
    Tipos: alertas fiscais, alertas de sistema, alertas normativos, alertas de performance.
    """
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    resultado = {}

    for alerta in alertas:
        agente = alerta.agente or "nao_definido"
        if agente not in resultado:
            resultado[agente] = 0
        resultado[agente] += 1

    return {
        "empresa_id": empresa.id,
        "alertas_por_agente": resultado
    }


@router.patch("/alertas/silenciar/{alerta_id}")
def silenciar_alerta(
    alerta_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()

    if not alerta:
        raise HTTPException(status_code=404, detail="alerta não encontrado")

    verificar_empresa_do_usuario(alerta.empresa_id, usuario_atual, db)
    alerta.silenciado = True
    db.commit()

    return {
        "status": "alerta silenciado",
        "alerta_id": alerta_id
    }


@router.patch("/alertas/restaurar/{alerta_id}")
def restaurar_alerta(
    alerta_id: int,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()

    if not alerta:
        raise HTTPException(status_code=404, detail="alerta não encontrado")

    verificar_empresa_do_usuario(alerta.empresa_id, usuario_atual, db)
    alerta.silenciado = False
    db.commit()

    return {
        "status": "alerta restaurado",
        "alerta_id": alerta_id
    }


@router.get("/alertas/grafico/{empresa_id}")
def grafico_alertas(
    empresa: models.Empresa = Depends(tenant_empresa),
    db: Session = Depends(get_db),
):
    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.empresa_id == empresa.id)
        .all()
    )

    critico = len([a for a in alertas if a.nivel == "critico"])
    alto = len([a for a in alertas if a.nivel == "alto"])
    medio = len([a for a in alertas if a.nivel == "medio"])

    return {
        "empresa_id": empresa.id,
        "grafico_alertas": {
            "critico": critico,
            "alto": alto,
            "medio": medio
        }
    }
