"""
Serviço de actualização normativa — fecha o ciclo AG3 → operador.
Regra de ouro: detecta e sinaliza; nunca altera dados 'oficial' automaticamente.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import AlertaFiscal, TabelaMVA, TabelaPMPF

logger = logging.getLogger(__name__)


def listar_alertas_normativos_pendentes(db: Session) -> list[dict]:
    """Lista AlertaFiscal de origem normativa não processados."""
    tipos_normativos = {
        "NOVIDADE_DOU_ICMS_ST",
        "VIGENCIA_EXPIRADA_SEM_SUBSTITUTO",
        "REGRAS_SEM_FONTE_LEGAL",
        "UFS_SEM_COBERTURA_MVA",
        "INSIGHTS_COM_NCM_EXPIRADO",
    }
    alertas = (
        db.query(AlertaFiscal)
        .filter(
            AlertaFiscal.tipo.in_(tipos_normativos),
            AlertaFiscal.processado == False,  # noqa: E712
            AlertaFiscal.silenciado == False,  # noqa: E712
        )
        .order_by(AlertaFiscal.criado_em.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "tipo": a.tipo,
            "descricao": a.descricao,
            "nivel": a.nivel,
            "agente": a.agente,
            "criado_em": a.criado_em.isoformat() if a.criado_em else None,
        }
        for a in alertas
    ]


def marcar_alerta_processado(
    db: Session,
    alerta_id: int,
    processado_por: str,
    notas: str | None = None,
) -> bool:
    """Operador confirma que agiu sobre o alerta."""
    alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()
    if not alerta:
        return False
    alerta.processado = True
    alerta.processado_em = datetime.utcnow()
    alerta.processado_por = processado_por
    alerta.notas_resolucao = notas
    db.commit()
    logger.info(
        "Alerta %d marcado processado por %s: %s",
        alerta_id,
        processado_por,
        notas or "",
    )
    return True


def expirar_regras_revogadas(
    db: Session,
    estado: str,
    ncm: str,
    data_revogacao: str,
    processado_por: str,
    fonte_revogacao: str,
) -> dict:
    """
    Marca vigencia_fim em tabela_mva e tabela_pmpf para estado+ncm.
    Só actua em registos sem vigencia_fim (activos).
    Nunca remove dados — só encerra vigência.
    Requer operador identificado.
    """
    data = date.fromisoformat(data_revogacao)

    registos_mva = (
        db.query(TabelaMVA)
        .filter(
            TabelaMVA.estado == estado.upper(),
            TabelaMVA.ncm == ncm,
            TabelaMVA.vigencia_fim.is_(None),
        )
        .all()
    )
    for r in registos_mva:
        r.vigencia_fim = data
        r.fonte_legal = (
            f"{r.fonte_legal or ''} | Revogado: {fonte_revogacao}".strip(" |")
        )

    registos_pmpf = (
        db.query(TabelaPMPF)
        .filter(
            TabelaPMPF.estado == estado.upper(),
            TabelaPMPF.ncm == ncm,
            TabelaPMPF.vigencia_fim.is_(None),
        )
        .all()
    )
    for r in registos_pmpf:
        r.vigencia_fim = data
        r.fonte_legal = (
            f"{r.fonte_legal or ''} | Revogado: {fonte_revogacao}".strip(" |")
        )

    mva_actualizados = len(registos_mva)
    pmpf_actualizados = len(registos_pmpf)
    db.commit()
    logger.warning(
        "Regras expiradas por %s: estado=%s ncm=%s data=%s mva=%d pmpf=%d fonte=%s",
        processado_por,
        estado,
        ncm,
        data_revogacao,
        mva_actualizados,
        pmpf_actualizados,
        fonte_revogacao,
    )
    return {
        "estado": estado,
        "ncm": ncm,
        "mva_expirados": mva_actualizados,
        "pmpf_expirados": pmpf_actualizados,
        "data_revogacao": data_revogacao,
        "processado_por": processado_por,
    }
