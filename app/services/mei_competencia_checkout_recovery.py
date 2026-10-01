"""Read-only recovery of a durable MEI competence purchase."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Empresa, MeiCompetenciaCheckoutIntent, MeiCompetenciaAuthorityBinding,
    OrdemCheckout, OrdemCheckoutCapability, CheckoutOfferGrant, Pagamento,
)
from app.services.mei_competencia_authority import (
    tem_autoridade_economica_mei_competencia,
)


class MeiCompetenciaCheckoutRecoveryError(Exception):
    pass


class MeiCompetenciaCheckoutRecoveryNotFoundError(MeiCompetenciaCheckoutRecoveryError):
    pass


class MeiCompetenciaCheckoutRecoveryConflictError(MeiCompetenciaCheckoutRecoveryError):
    pass


class MeiCompetenciaCheckoutRecoveryStorageError(MeiCompetenciaCheckoutRecoveryError):
    pass


@dataclass(frozen=True)
class MeiCompetenciaCheckoutRecoveryResult:
    estado: str
    competencia: str
    checkout_idempotency_key: str
    checkout_url: str | None
    autorizado: bool


def _positive(value):
    return type(value) is int and value > 0


def _https(value):
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.fragment)
    except ValueError:
        return False


class MeiCompetenciaCheckoutRecovery:
    def __init__(self, db):
        self._db = db

    def resolve(self, *, user_id, empresa_id, competencia):
        if (not _positive(user_id) or not _positive(empresa_id)
            or type(competencia) is not str or len(competencia) != 6
            or not competencia.isascii() or not competencia.isdigit()
            or not 1 <= int(competencia[4:]) <= 12):
            raise MeiCompetenciaCheckoutRecoveryConflictError()
        try:
            # Recovery does not acquire write authority through ORM autoflush.
            with self._db.no_autoflush:
                return self._resolve(user_id, empresa_id, competencia)
        except SQLAlchemyError:
            raise MeiCompetenciaCheckoutRecoveryStorageError() from None

    def _resolve(self, user_id, empresa_id, competencia):
        empresa = self._db.get(Empresa, empresa_id)
        if (empresa is None or empresa.user_id != user_id
            or empresa.status_empresa != "ativa" or empresa.regime_tributario != "mei"):
            raise MeiCompetenciaCheckoutRecoveryNotFoundError()

        rows = self._db.scalars(
            select(MeiCompetenciaCheckoutIntent)
            .join(OrdemCheckout, OrdemCheckout.idempotency_key
                  == MeiCompetenciaCheckoutIntent.checkout_idempotency_key)
            .where(
                MeiCompetenciaCheckoutIntent.user_id == user_id,
                MeiCompetenciaCheckoutIntent.empresa_id == empresa_id,
                MeiCompetenciaCheckoutIntent.competencia == competencia,
                MeiCompetenciaCheckoutIntent.capability == "mei.das",
                OrdemCheckout.user_id == user_id,
                OrdemCheckout.empresa_id == empresa_id,
                OrdemCheckout.estado.in_(("pending", "paid")),
            )
            .order_by(OrdemCheckout.criado_em.desc(), OrdemCheckout.id.desc())
        ).all()
        if not rows:
            raise MeiCompetenciaCheckoutRecoveryNotFoundError()

        # Preserve a valid paid purchase even if a later pending attempt exists.
        selected_pending = None
        for intent in rows:
            ordem = self._db.scalar(select(OrdemCheckout).where(
                OrdemCheckout.idempotency_key == intent.checkout_idempotency_key))
            if (ordem is None or intent.offer_code != ordem.offer_code
                or not _positive(ordem.offer_id) or not _positive(ordem.contract_version)
                or ordem.plano_id is not None or ordem.vertical != "tax"
                or ordem.commercial_model != "one_time"
                or ordem.subject_type != "company" or ordem.subject_id != empresa_id):
                raise MeiCompetenciaCheckoutRecoveryConflictError()
            capabilities = self._db.scalars(select(OrdemCheckoutCapability).where(
                OrdemCheckoutCapability.ordem_id == ordem.id,
                OrdemCheckoutCapability.codigo == "mei.das")).all()
            if len(capabilities) != 1:
                raise MeiCompetenciaCheckoutRecoveryConflictError()
            if ordem.estado == "paid":
                binding = self._db.scalar(select(MeiCompetenciaAuthorityBinding.id).where(
                    MeiCompetenciaAuthorityBinding.ordem_id == ordem.id,
                    MeiCompetenciaAuthorityBinding.empresa_id == empresa_id,
                    MeiCompetenciaAuthorityBinding.competencia == competencia,
                    MeiCompetenciaAuthorityBinding.capability == "mei.das"))
                payment = self._db.scalar(select(Pagamento.id).where(
                    Pagamento.ordem_checkout_id == ordem.id,
                    Pagamento.user_id == user_id,
                    Pagamento.status == "approved",
                    Pagamento.valor == ordem.valor,
                    Pagamento.confirmado_em.is_not(None)))
                revoked = self._db.scalar(select(CheckoutOfferGrant.id).where(
                    CheckoutOfferGrant.ordem_id == ordem.id,
                    CheckoutOfferGrant.estado == "revoked"))
                if (binding is None or payment is None or revoked is not None
                    or not tem_autoridade_economica_mei_competencia(
                    self._db, empresa_id=empresa_id, competencia=competencia,
                    capability="mei.das")):
                    raise MeiCompetenciaCheckoutRecoveryConflictError()
                return MeiCompetenciaCheckoutRecoveryResult(
                    "paid", competencia, intent.checkout_idempotency_key, None, True)
            if selected_pending is None:
                selected_pending = (intent, ordem)

        intent, ordem = selected_pending
        grant = self._db.scalar(select(CheckoutOfferGrant.id).where(
            CheckoutOfferGrant.ordem_id == ordem.id))
        if ordem.payment_id is not None or grant is not None:
            raise MeiCompetenciaCheckoutRecoveryConflictError()
        if (ordem.provider_order_id is None) != (ordem.checkout_url is None):
            raise MeiCompetenciaCheckoutRecoveryConflictError()
        if ordem.checkout_url is not None and (
            not _https(ordem.checkout_url) or not ordem.provider_order_id.strip()):
            raise MeiCompetenciaCheckoutRecoveryConflictError()
        return MeiCompetenciaCheckoutRecoveryResult(
            "pending", competencia, intent.checkout_idempotency_key,
            ordem.checkout_url, False)
