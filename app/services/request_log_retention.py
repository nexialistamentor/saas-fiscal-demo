"""
Retenção de request_logs: remove registos mais antigos que N dias (T4).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import delete

from app.database import SessionLocal
from app.models import RequestLog

logger = logging.getLogger(__name__)


def purga_request_logs_mais_antigos_que(dias: int) -> int:
    """
    Apaga linhas em request_logs com criado_em anterior a (agora - dias).
    dias <= 0 não apaga nada.
    Retorna o número de linhas removidas (0 se nada a apagar ou dias inválido).
    """
    if dias <= 0:
        return 0
    cutoff = datetime.utcnow() - timedelta(days=dias)
    db = SessionLocal()
    try:
        result = db.execute(delete(RequestLog).where(RequestLog.criado_em < cutoff))
        db.commit()
        n = result.rowcount
        if n is None:
            return 0
        return int(n)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
