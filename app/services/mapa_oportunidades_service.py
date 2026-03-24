from sqlalchemy.orm import Session
from sqlalchemy import text

from app.services.risco_tributario_service import calcular_risco_tributario
from app.services.score_global_tributario_service import calcular_score_global_tributario
from app import models


def normalizar_risco(score_risco_raw: float) -> float:
    """Normaliza score de risco para escala 0-100. Nunca envia valor bruto."""
    if score_risco_raw is None:
        return 0.0
    risco = (float(score_risco_raw) / 1000.0) * 100.0
    return max(0.0, min(round(risco, 2), 100.0))


def normalizar_pontuacao(score_global: float) -> float:
    """Normaliza score global tributário para escala 0-100."""
    MIN_SCORE = -50000
    MAX_SCORE = 60000

    if score_global is None:
        return 0.0

    score_norm = (float(score_global) - MIN_SCORE) / (MAX_SCORE - MIN_SCORE) * 100
    return max(0.0, min(round(score_norm, 2), 100.0))


def gerar_mapa_oportunidades(db: Session, empresa_id: int):

    mapa = {
        "restituicao_st": 0,
        "mva_distorcida": 0,
        "estoque_st": 0,
        "estoque_fantasma": 0,
        "anomalia_preco": 0,
        "impacto_financeiro_anual": 0,
        "risco_tributario_percentual": 0,
        "pontuacao_fiscal": 0,
    }

    try:
        query = text("""
            SELECT
                tipo,
                SUM(valor_estimado) as impacto_total
            FROM insights
            WHERE empresa_id = :empresa_id
            GROUP BY tipo
        """)
        resultado = db.execute(query, {"empresa_id": empresa_id}).fetchall()
    except Exception:
        return mapa

    tipos_monetarios = {
        "PRODUTO_COM_RESTITUICAO_RELEVANTE",
        "ESTOQUE_COM_ST",
        "CREDITO_ST_ESTIMADO",
        "ST_RESTITUICAO",
        "CONCENTRACAO_ST_NCM",
        "IMPACTO_FINANCEIRO_TRIBUTARIO",
    }

    for row in resultado:

        tipo = row.tipo
        valor = float(row.impacto_total or 0)

        if tipo in ("PRODUTO_COM_RESTITUICAO_RELEVANTE", "ST_RESTITUICAO"):
            mapa["restituicao_st"] += valor

        if tipo in ("DISTORCAO_MVA", "DISTORCAO_MVA_REAL"):
            mapa["mva_distorcida"] += valor

        if tipo == "ESTOQUE_COM_ST":
            mapa["estoque_st"] += valor

        if tipo == "ST_SEM_SAIDA":
            mapa["estoque_fantasma"] += valor

        if tipo == "ANOMALIA_PRECO":
            mapa["anomalia_preco"] += valor

        if tipo in tipos_monetarios:
            mapa["impacto_financeiro_anual"] += valor

    # Se não houver insights monetários, usa restituicao_st como base para estimativa anual
    if mapa["impacto_financeiro_anual"] == 0 and mapa["restituicao_st"] > 0:
        mapa["impacto_financeiro_anual"] = mapa["restituicao_st"] * 12

    # Métricas normalizadas 0-100 (nunca envia valor bruto)
    try:
        risco_data = calcular_risco_tributario(db, empresa_id)
        risco_raw = risco_data.get("score_risco_tributario", 0) or 0
        mapa["risco_tributario_percentual"] = normalizar_risco(risco_raw)

        score_data = calcular_score_global_tributario(db, empresa_id)
        score_raw = score_data.get("score_global_tributario", 0) or 0
        mapa["pontuacao_fiscal"] = normalizar_pontuacao(score_raw)
    except Exception:
        pass

    # Insights reais da empresa
    rows = (
        db.query(models.Insight)
        .filter(models.Insight.empresa_id == empresa_id)
        .order_by(models.Insight.id.desc())
        .limit(50)
        .all()
    )
    mapa["insights"] = [r.descricao or r.tipo for r in rows if r.descricao or r.tipo]
    mapa["total_insights"] = len(mapa["insights"])

    return mapa
