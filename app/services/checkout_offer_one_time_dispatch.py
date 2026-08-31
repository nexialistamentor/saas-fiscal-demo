"""Despacho offline de ordens one-time baseadas em oferta persistida."""

from dataclasses import dataclass
from decimal import Decimal
import re
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models import OrdemCheckout


_MENSAGEM_PUBLICA = "Nao foi possivel despachar a ordem de checkout"
_OFFER_CODE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.ASCII)
_CAPABILITY = re.compile(
    r"[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*)+", re.ASCII
)


@dataclass(frozen=True)
class CheckoutOfferOneTimeDispatchProjection:
    ordem_id: int
    provider_order_id: str
    checkout_url: str


@dataclass(frozen=True)
class _OrderSnapshot:
    id: int
    user_id: int
    empresa_id: int
    offer_id: int
    offer_code: str
    contract_version: int
    vertical: str
    commercial_model: str
    subject_type: str
    subject_id: int
    valor: Decimal
    moeda: str
    billing_period: None
    usage_unit: str
    usage_limit: int
    capabilities: tuple[str, ...]
    idempotency_key: str
    estado: str
    plano_id: None
    provider_order_id: str | None
    checkout_url: str | None


class CheckoutOfferOneTimeDispatchError(Exception):
    """Falha publica deliberadamente opaca do despacho."""

    def __init__(self) -> None:
        super().__init__(_MENSAGEM_PUBLICA)


class CheckoutOfferOneTimeDispatcher:
    def __init__(self, session_factory, gateway) -> None:
        if (
            not callable(session_factory)
            or not callable(getattr(gateway, "criar_cobranca", None))
        ):
            raise CheckoutOfferOneTimeDispatchError()
        self._session_factory = session_factory
        self._gateway = gateway

    def despachar(self, *, authenticated_user_id, empresa_id, ordem_id):
        try:
            self._positive_id(authenticated_user_id)
            self._positive_id(empresa_id)
            self._positive_id(ordem_id)

            first = self._load_snapshot(
                ordem_id, authenticated_user_id, empresa_id
            )
            if first.provider_order_id is not None:
                return self._projection(first)

            response = self._gateway.criar_cobranca(
                ordem_id=first.id,
                user_id=first.user_id,
                empresa_id=first.empresa_id,
                offer_code=first.offer_code,
                valor=first.valor,
                moeda=first.moeda,
                idempotency_key=first.idempotency_key,
            )
            provider_order_id, checkout_url = self._gateway_response(response)
            return self._persist(
                first, authenticated_user_id, empresa_id,
                provider_order_id, checkout_url,
            )
        except CheckoutOfferOneTimeDispatchError:
            raise
        except Exception:
            raise CheckoutOfferOneTimeDispatchError() from None

    def _load_snapshot(self, ordem_id, user_id, empresa_id):
        session = None
        try:
            session = self._open_session()
            order = session.execute(
                select(OrdemCheckout)
                .options(selectinload(OrdemCheckout.capabilities))
                .where(OrdemCheckout.id == ordem_id)
            ).scalar_one_or_none()
            return self._snapshot(order, user_id, empresa_id)
        finally:
            self._close_session(session)

    def _persist(
        self, first, user_id, empresa_id, provider_order_id, checkout_url
    ):
        session = None
        try:
            session = self._open_session()
            order = session.execute(
                select(OrdemCheckout)
                .options(selectinload(OrdemCheckout.capabilities))
                .where(OrdemCheckout.id == first.id)
                .with_for_update()
            ).scalar_one_or_none()
            current = self._snapshot(order, user_id, empresa_id)
            if self._commercial_identity(current) != self._commercial_identity(first):
                raise CheckoutOfferOneTimeDispatchError()
            if current.provider_order_id is not None:
                if (
                    current.provider_order_id == provider_order_id
                    and current.checkout_url == checkout_url
                ):
                    return self._projection(current)
                raise CheckoutOfferOneTimeDispatchError()

            order.provider_order_id = provider_order_id
            order.checkout_url = checkout_url
            session.flush()
            session.commit()
            return CheckoutOfferOneTimeDispatchProjection(
                ordem_id=current.id,
                provider_order_id=provider_order_id,
                checkout_url=checkout_url,
            )
        except IntegrityError:
            if session is not None:
                self._rollback(session)
            return self._reconcile_collision(
                first, user_id, empresa_id, provider_order_id, checkout_url
            )
        except Exception:
            if session is not None:
                self._rollback(session)
            raise
        finally:
            self._close_session(session)

    def _reconcile_collision(
        self, first, user_id, empresa_id, provider_order_id, checkout_url
    ):
        session = None
        try:
            session = self._open_session()
            order = session.execute(
                select(OrdemCheckout)
                .options(selectinload(OrdemCheckout.capabilities))
                .where(OrdemCheckout.id == first.id)
            ).scalar_one_or_none()
            current = self._snapshot(order, user_id, empresa_id)
            if (
                self._commercial_identity(current)
                == self._commercial_identity(first)
                and current.provider_order_id == provider_order_id
                and current.checkout_url == checkout_url
            ):
                return self._projection(current)
            raise CheckoutOfferOneTimeDispatchError()
        finally:
            self._close_session(session)

    @classmethod
    def _snapshot(cls, order, user_id, empresa_id):
        if (
            order is None
            or order.user_id != user_id
            or order.empresa_id != empresa_id
        ):
            raise CheckoutOfferOneTimeDispatchError()
        for value in (
            order.id, order.user_id, order.empresa_id, order.offer_id,
            order.contract_version, order.subject_id, order.usage_limit,
        ):
            cls._positive_id(value)
        if (
            order.plano_id is not None
            or order.estado != "pending"
            or order.commercial_model != "one_time"
            or order.subject_type != "company"
            or order.subject_id != empresa_id
            or order.vertical not in {"tax", "document"}
            or not isinstance(order.offer_code, str)
            or _OFFER_CODE.fullmatch(order.offer_code) is None
            or order.moeda != "BRL"
            or order.billing_period is not None
        ):
            raise CheckoutOfferOneTimeDispatchError()
        cls._amount(order.valor)
        cls._canonical_text(order.usage_unit, 50)
        cls._canonical_text(order.idempotency_key, 255)

        capabilities = tuple(capability.codigo for capability in order.capabilities)
        if (
            not capabilities
            or capabilities != tuple(sorted(capabilities))
            or len(capabilities) != len(set(capabilities))
            or any(
                not isinstance(value, str)
                or _CAPABILITY.fullmatch(value) is None
                for value in capabilities
            )
        ):
            raise CheckoutOfferOneTimeDispatchError()

        provider = order.provider_order_id
        checkout_url = order.checkout_url
        if (provider is None) != (checkout_url is None):
            raise CheckoutOfferOneTimeDispatchError()
        if provider is not None:
            cls._provider_id(provider)
            cls._checkout_url(checkout_url)

        return _OrderSnapshot(
            id=order.id,
            user_id=order.user_id,
            empresa_id=order.empresa_id,
            offer_id=order.offer_id,
            offer_code=order.offer_code,
            contract_version=order.contract_version,
            vertical=order.vertical,
            commercial_model=order.commercial_model,
            subject_type=order.subject_type,
            subject_id=order.subject_id,
            valor=order.valor,
            moeda=order.moeda,
            billing_period=order.billing_period,
            usage_unit=order.usage_unit,
            usage_limit=order.usage_limit,
            capabilities=capabilities,
            idempotency_key=order.idempotency_key,
            estado=order.estado,
            plano_id=order.plano_id,
            provider_order_id=provider,
            checkout_url=checkout_url,
        )

    @staticmethod
    def _commercial_identity(snapshot):
        return (
            snapshot.id,
            snapshot.user_id,
            snapshot.empresa_id,
            snapshot.offer_id,
            snapshot.offer_code,
            snapshot.contract_version,
            snapshot.vertical,
            snapshot.commercial_model,
            snapshot.subject_type,
            snapshot.subject_id,
            snapshot.valor,
            snapshot.moeda,
            snapshot.billing_period,
            snapshot.usage_unit,
            snapshot.usage_limit,
            snapshot.capabilities,
            snapshot.idempotency_key,
            snapshot.estado,
            snapshot.plano_id,
        )

    @classmethod
    def _gateway_response(cls, response):
        if not isinstance(response, dict):
            raise CheckoutOfferOneTimeDispatchError()
        provider_order_id = response.get("provider_order_id")
        checkout_url = response.get("checkout_url")
        cls._provider_id(provider_order_id)
        cls._checkout_url(checkout_url)
        return provider_order_id, checkout_url

    @staticmethod
    def _positive_id(value):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise CheckoutOfferOneTimeDispatchError()

    @staticmethod
    def _amount(value):
        if (
            not isinstance(value, Decimal)
            or not value.is_finite()
            or value <= Decimal("0")
            or value != value.quantize(Decimal("0.01"))
        ):
            raise CheckoutOfferOneTimeDispatchError()

    @staticmethod
    def _canonical_text(value, limit):
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > limit
            or "\r" in value
            or "\n" in value
        ):
            raise CheckoutOfferOneTimeDispatchError()

    @classmethod
    def _provider_id(cls, value):
        cls._canonical_text(value, 255)

    @classmethod
    def _checkout_url(cls, value):
        cls._canonical_text(value, 2000)
        try:
            parsed = urlsplit(value)
            valid = (
                parsed.scheme == "https"
                and bool(parsed.netloc)
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
            )
        except (TypeError, ValueError):
            valid = False
        if not valid:
            raise CheckoutOfferOneTimeDispatchError()

    def _open_session(self):
        session = self._session_factory()
        if (
            not callable(getattr(session, "execute", None))
            or not callable(getattr(session, "close", None))
            or not callable(getattr(session, "rollback", None))
            or not callable(getattr(session, "commit", None))
        ):
            self._close_session(session)
            raise CheckoutOfferOneTimeDispatchError()
        return session

    @staticmethod
    def _rollback(session):
        try:
            session.rollback()
        except Exception:
            pass

    @staticmethod
    def _close_session(session):
        if session is not None:
            try:
                session.close()
            except Exception:
                pass

    @staticmethod
    def _projection(snapshot):
        return CheckoutOfferOneTimeDispatchProjection(
            ordem_id=snapshot.id,
            provider_order_id=snapshot.provider_order_id,
            checkout_url=snapshot.checkout_url,
        )


__all__ = [
    "CheckoutOfferOneTimeDispatcher",
    "CheckoutOfferOneTimeDispatchError",
    "CheckoutOfferOneTimeDispatchProjection",
]
