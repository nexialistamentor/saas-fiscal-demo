"""
Serviço de reparação semi-automática.

Princípio L2: dados oficiais NUNCA alterados automaticamente.
Insights (dados derivados) podem ser marcados superseded.
"""

from datetime import datetime
import logging

from app.database import SessionLocal
from app.models import AlertaFiscal, Insight, TabelaMVA

logger = logging.getLogger(__name__)


def executar_reparacao_sugerida(alerta_id: int) -> dict:
    db = SessionLocal()
    try:
        alerta = db.query(AlertaFiscal).filter(AlertaFiscal.id == alerta_id).first()
        if not alerta:
            return {"sucesso": False, "detalhe": "Alerta não encontrado"}

        if alerta.tipo == "INSIGHTS_COM_NCM_EXPIRADO":
            hoje = datetime.utcnow().date()
            ncms = [
                n[0]
                for n in db.query(TabelaMVA.ncm)
                .filter(TabelaMVA.vigencia_fim < hoje)
                .distinct()
                if n[0]
            ]
            if not ncms:
                return {"sucesso": False, "detalhe": "Nenhum NCM expirado encontrado"}
            atualizados = db.query(Insight).filter(
                Insight.ncm.in_(ncms), Insight.superseded == False  # noqa: E712
            ).update({"superseded": True}, synchronize_session=False)
            db.commit()
            return {"sucesso": True, "insights_atualizados": atualizados}

        if alerta.tipo in (
            "VIGENCIA_EXPIRADA_SEM_SUBSTITUTO",
            "UFS_SEM_COBERTURA_MVA",
            "REGRAS_SEM_FONTE_LEGAL",
            "NOVIDADE_DOU_ICMS_ST",
        ):
            return {"sucesso": False, "detalhe": "Requer intervenção manual — dados oficiais."}

        return {"sucesso": False, "detalhe": "Tipo de alerta desconhecido."}
    except Exception as exc:
        logger.exception("Erro na reparação alerta %s", alerta_id)
        return {"sucesso": False, "erro": str(exc)}
    finally:
        db.close()
