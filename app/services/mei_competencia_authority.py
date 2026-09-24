"""Resolucao fail-closed da autoridade comercial por competencia MEI."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    CheckoutOfferGrant,
    MeiCompetenciaAuthorityBinding,
    OrdemCheckout,
    OrdemCheckoutCapability,
    Pagamento,
)


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

    capability_exists = (
        select(OrdemCheckoutCapability.id)
        .where(
            OrdemCheckoutCapability.ordem_id == OrdemCheckout.id,
            OrdemCheckoutCapability.codigo == capability,
        )
        .exists()
    )

    approved_payment_exists = (
        select(Pagamento.id)
        .where(
            Pagamento.ordem_checkout_id == OrdemCheckout.id,
            Pagamento.user_id == OrdemCheckout.user_id,
            Pagamento.status == "approved",
            Pagamento.valor == OrdemCheckout.valor,
            Pagamento.confirmado_em.is_not(None),
        )
        .exists()
    )

    revoked_grant_exists = (
        select(CheckoutOfferGrant.id)
        .where(
            CheckoutOfferGrant.ordem_id == OrdemCheckout.id,
            CheckoutOfferGrant.estado == "revoked",
        )
        .exists()
    )

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
            OrdemCheckout.offer_id.is_not(None),
            OrdemCheckout.plano_id.is_(None),
            OrdemCheckout.vertical == "tax",
            OrdemCheckout.subject_type == "company",
            OrdemCheckout.subject_id == empresa_id,
            OrdemCheckout.contract_version.is_not(None),
            OrdemCheckout.offer_code.is_not(None),
            capability_exists,
            approved_payment_exists,
            ~revoked_grant_exists,
        )
        .limit(1)
    )

    return db.scalar(statement) is not None


__all__ = ["tem_autoridade_economica_mei_competencia"]
