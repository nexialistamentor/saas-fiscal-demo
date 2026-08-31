"""Criacao transacional de ordens a partir de ofertas publicadas."""

from dataclasses import dataclass
from decimal import Decimal
import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import (
    CheckoutOffer,
    Empresa,
    OrdemCheckout,
    OrdemCheckoutCapability,
    User,
)
from app.services.checkout_offer_catalog import checkout_offer_snapshot


_MENSAGEM_PUBLICA = "Nao foi possivel criar a ordem de checkout"
_CODIGO = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)


@dataclass(frozen=True)
class CheckoutOfferOrderSnapshot:
    id: int
    offer_id: int
    offer_code: str
    contract_version: int
    vertical: str
    commercial_model: str
    subject_type: str
    subject_id: int
    user_id: int
    valor: Decimal
    moeda: str
    billing_period: str | None
    usage_unit: str | None
    usage_limit: int | None
    capabilities: tuple[str, ...]
    idempotency_key: str
    estado: str
    plano_id: int | None


class CheckoutOfferOrderCompositionError(Exception):
    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutOfferOrderComposer:
    def __init__(self, session_factory) -> None:
        if not callable(session_factory):
            raise CheckoutOfferOrderCompositionError()
        self._session_factory = session_factory

    def iniciar_checkout_empresa(
        self, *, authenticated_user_id, empresa_id, offer_code, idempotency_key
    ):
        self._validar_id(authenticated_user_id)
        self._validar_id(empresa_id)
        self._validar_offer_code(offer_code)
        self._validar_chave(idempotency_key)

        sessao = None
        try:
            sessao = self._session_factory()
            existente = self._por_chave(sessao, idempotency_key)
            if existente is not None:
                return self._retry(
                    existente, authenticated_user_id, empresa_id, offer_code
                )

            user = sessao.get(User, authenticated_user_id)
            empresa = sessao.get(Empresa, empresa_id)
            if user is None or empresa is None or empresa.user_id != user.id:
                raise CheckoutOfferOrderCompositionError()

            entidade = sessao.execute(
                select(CheckoutOffer)
                .options(selectinload(CheckoutOffer.capabilities))
                .where(CheckoutOffer.codigo == offer_code)
            ).scalar_one_or_none()
            if entidade is None:
                raise CheckoutOfferOrderCompositionError()
            oferta = checkout_offer_snapshot(entidade)
            if (
                oferta.subject_type != "company"
                or oferta.checkout_mode != "automatic"
                or oferta.commercial_model not in {"monthly", "one_time"}
            ):
                raise CheckoutOfferOrderCompositionError()

            ordem = OrdemCheckout(
                user_id=user.id,
                empresa_id=empresa.id,
                plano_id=None,
                offer_id=oferta.id,
                offer_code=oferta.codigo,
                contract_version=oferta.contract_version,
                vertical=oferta.vertical,
                commercial_model=oferta.commercial_model,
                subject_type=oferta.subject_type,
                subject_id=empresa.id,
                valor=oferta.preco,
                moeda=oferta.moeda,
                billing_period=oferta.billing_period,
                usage_unit=oferta.usage_unit,
                usage_limit=oferta.usage_limit,
                idempotency_key=idempotency_key,
                estado="pending",
            )
            ordem.capabilities = [
                OrdemCheckoutCapability(codigo=codigo)
                for codigo in oferta.capabilities
            ]
            sessao.add(ordem)
            try:
                sessao.flush()
                resultado = self._snapshot(ordem)
                sessao.commit()
                return resultado
            except IntegrityError:
                sessao.rollback()
                existente = self._por_chave(sessao, idempotency_key)
                if existente is None:
                    raise CheckoutOfferOrderCompositionError()
                return self._retry(
                    existente, authenticated_user_id, empresa_id, offer_code
                )
        except CheckoutOfferOrderCompositionError:
            if sessao is not None and sessao.in_transaction():
                sessao.rollback()
            raise
        except Exception:
            if sessao is not None:
                try:
                    sessao.rollback()
                except Exception:
                    pass
            raise CheckoutOfferOrderCompositionError() from None
        finally:
            if sessao is not None:
                try:
                    sessao.close()
                except Exception:
                    pass

    @staticmethod
    def _por_chave(sessao, chave):
        return sessao.execute(
            select(OrdemCheckout)
            .options(selectinload(OrdemCheckout.capabilities))
            .where(OrdemCheckout.idempotency_key == chave)
        ).scalar_one_or_none()

    @classmethod
    def _retry(cls, ordem, user_id, empresa_id, offer_code):
        if (
            ordem.offer_id is None
            or ordem.user_id != user_id
            or ordem.empresa_id != empresa_id
            or ordem.offer_code != offer_code
        ):
            raise CheckoutOfferOrderCompositionError()
        return cls._snapshot(ordem)

    @staticmethod
    def _snapshot(ordem):
        return CheckoutOfferOrderSnapshot(
            id=ordem.id,
            offer_id=ordem.offer_id,
            offer_code=ordem.offer_code,
            contract_version=ordem.contract_version,
            vertical=ordem.vertical,
            commercial_model=ordem.commercial_model,
            subject_type=ordem.subject_type,
            subject_id=ordem.subject_id,
            user_id=ordem.user_id,
            valor=ordem.valor,
            moeda=ordem.moeda,
            billing_period=ordem.billing_period,
            usage_unit=ordem.usage_unit,
            usage_limit=ordem.usage_limit,
            capabilities=tuple(cap.codigo for cap in ordem.capabilities),
            idempotency_key=ordem.idempotency_key,
            estado=ordem.estado,
            plano_id=ordem.plano_id,
        )

    @staticmethod
    def _validar_id(valor):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise CheckoutOfferOrderCompositionError()

    @staticmethod
    def _validar_offer_code(valor):
        if not isinstance(valor, str) or _CODIGO.fullmatch(valor) is None:
            raise CheckoutOfferOrderCompositionError()

    @staticmethod
    def _validar_chave(valor):
        if (
            not isinstance(valor, str)
            or not valor
            or len(valor) > 255
            or valor != valor.strip()
            or "\r" in valor
            or "\n" in valor
        ):
            raise CheckoutOfferOrderCompositionError()


__all__ = [
    "CheckoutOfferOrderComposer",
    "CheckoutOfferOrderCompositionError",
    "CheckoutOfferOrderSnapshot",
]
