"""Resolucao fail-closed da autoridade comercial por competencia MEI."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MeiCompetenciaAuthorityBinding, OrdemCheckout


_CAPABILITY_MEI_DAS = "mei.das"


def tem_autoridade_economica_mei_competencia(
    db: Session,
    *,
    empresa_id: int,
    competencia: str,
    capability: str,
) -> bool:
    """Retorna True somente para autoridade exata derivada de ordem paga."""

    if (
        type(empresa_id) is not int
        or empresa_id <= 0
        or type(competencia) is not str
        or len(competencia) != 6
        or not competencia.isascii()
        or not competencia.isdigit()
        or not 1 <= int(competencia[4:]) <= 12
        or capability != _CAPABILITY_MEI_DAS
    ):
        return False

    statement = (
        select(MeiCompetenciaAuthorityBinding.id)
        .join(
            OrdemCheckout,
            OrdemCheckout.id == MeiCompetenciaAuthorityBinding.ordem_id,
        )
        .where(
            MeiCompetenciaAuthorityBinding.empresa_id == empresa_id,
            MeiCompetenciaAuthorityBinding.competencia == competencia,
            MeiCompetenciaAuthorityBinding.capability == capability,
            OrdemCheckout.empresa_id == empresa_id,
            OrdemCheckout.estado == "paid",
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


__all__ = ["tem_autoridade_economica_mei_competencia"]
