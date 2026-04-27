"""
Serviço central do Sprint 1 — Memorial de Cálculo.

Orquestra os dados necessários a um relatório/PDF auditável: resultado da análise,
execuções das engines, alertas, insights e referências legais. O motor continua a ser
a fonte de verdade; este serviço apenas agrega e prepara a narrativa exportável.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    AlertaFiscal,
    EngineResultado,
    Insight,
    ReferenciaLegal,
    RelatorioAnalise,
)


def _serializar_referencia(r: ReferenciaLegal) -> dict[str, Any]:
    return {
        "codigo": r.codigo,
        "titulo": r.titulo,
        "fundamento": r.fundamento,
        "descricao": r.descricao,
        "uf": r.uf,
        "vigencia_inicio": r.vigencia_inicio.isoformat() if r.vigencia_inicio else None,
        "vigencia_fim": r.vigencia_fim.isoformat() if r.vigencia_fim else None,
        "fonte_url": r.fonte_url,
    }


def listar_referencias_legais(
    db: Session,
    *,
    uf: str | None = None,
    limite: int = 200,
) -> list[dict[str, Any]]:
    """
    Base normativa para o memorial. Se `uf` for informado, inclui dispositivos
    federais (uf nulo) e do estado; caso contrário, devolve um recorte geral.
    """
    q = db.query(ReferenciaLegal)
    if uf:
        u = uf.strip().upper()[:2]
        q = q.filter((ReferenciaLegal.uf.is_(None)) | (ReferenciaLegal.uf == u))
    return [
        _serializar_referencia(r)
        for r in q.order_by(ReferenciaLegal.codigo).limit(limite).all()
    ]


def coletar_contexto_memorial(
    db: Session,
    relatorio_id: int,
    *,
    uf_referencias: str | None = None,
) -> dict[str, Any] | None:
    """
    Agrega tudo o que o gerador de PDF/memorial precisa para um `relatorios_analise.id`.
    Retorna None se o relatório não existir.
    """
    rel = (
        db.query(RelatorioAnalise)
        .filter(RelatorioAnalise.id == relatorio_id)
        .first()
    )
    if not rel:
        return None

    engine_rows = (
        db.query(EngineResultado)
        .filter(EngineResultado.relatorio_analise_id == relatorio_id)
        .order_by(EngineResultado.criado_em.asc())
        .all()
    )
    engines = [
        {
            "engine_nome": e.engine_nome,
            "resultado": e.resultado,
            "criado_em": e.criado_em.isoformat() if e.criado_em else None,
        }
        for e in engine_rows
    ]

    alertas = (
        db.query(AlertaFiscal)
        .filter(AlertaFiscal.relatorio_analise_id == relatorio_id)
        .order_by(AlertaFiscal.criado_em.asc())
        .all()
    )
    alertas_list = [
        {
            "id": a.id,
            "agente": a.agente,
            "tipo": a.tipo,
            "descricao": a.descricao,
            "nivel": a.nivel,
        }
        for a in alertas
    ]

    insights = (
        db.query(Insight)
        .filter(
            Insight.relatorio_analise_id == relatorio_id,
            Insight.superseded == False,
        )
        .order_by(Insight.criado_em.asc())
        .all()
    )
    insights_list = [
        {
            "tipo": i.tipo,
            "descricao": i.descricao,
            "valor_estimado": i.valor_estimado,
            "impacto": i.impacto,
            "recomendacao": i.recomendacao,
        }
        for i in insights
    ]

    referencias = listar_referencias_legais(db, uf=uf_referencias)

    return {
        "relatorio": {
            "id": rel.id,
            "user_id": rel.user_id,
            "empresa_id": rel.empresa_id,
            "analysis_type": rel.analysis_type,
            "xml_chave": rel.xml_chave,
            "status": rel.status,
            "tempo_execucao": rel.tempo_execucao,
            "total_alertas": rel.total_alertas,
            "score_resultante": rel.score_resultante,
            "resultado_json": rel.resultado_json,
            "pago": rel.pago,
            "memorial_gerado": rel.memorial_gerado,
            "created_at": rel.created_at.isoformat() if rel.created_at else None,
        },
        "engines": engines,
        "alertas": alertas_list,
        "insights": insights_list,
        "referencias_legais": referencias,
    }


def marcar_memorial_gerado(db: Session, relatorio_id: int) -> bool:
    """Define `memorial_gerado=True` após exportação bem-sucedida. Retorna False se não achar o registro."""
    rel = (
        db.query(RelatorioAnalise)
        .filter(RelatorioAnalise.id == relatorio_id)
        .first()
    )
    if not rel:
        return False
    rel.memorial_gerado = True
    db.commit()
    return True
