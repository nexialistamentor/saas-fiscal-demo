"""Reserva atomica de capacidade de campanha para uma ordem de checkout."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import DateTime, and_, cast, func, or_, select

_PUBLIC_ERROR = "Nao foi possivel reservar a campanha de checkout"


class CheckoutOfferCampaignReservationError(Exception):
    """Falha publica deliberadamente opaca da reserva de campanha."""

    def __init__(self):
        super().__init__(_PUBLIC_ERROR)


@dataclass(frozen=True)
class CheckoutOfferCampaignReservationProjection:
    reservation_id: int
    ordem_id: int
    campaign_id: int
    campaign_code: str
    campaign_contract_version: int
    campaign_purchase_limit: int
    estado: str
    reserved_at: datetime
    expires_at: datetime


def _fail():
    raise CheckoutOfferCampaignReservationError()


def _positive_integer(value):
    return type(value) is int and value > 0


def _canonical_campaign_code(value):
    return (
        type(value) is str
        and bool(value)
        and len(value) <= 120
        and value == value.strip()
        and value == value.lower()
        and "--" not in value
    )


class CheckoutOfferCampaignReservationAuthority:
    def __init__(self, session):
        self._session = session

    def reservar_para_ordem(
        self,
        *,
        authenticated_user_id,
        empresa_id,
        ordem_id,
    ):
        try:
            from app import models

            self._validate_input_ids(
                authenticated_user_id,
                empresa_id,
                ordem_id,
            )
            order = self._session.scalar(
                select(models.OrdemCheckout)
                .where(models.OrdemCheckout.id == ordem_id)
                .with_for_update()
            )
            self._validate_order_identity(
                order,
                authenticated_user_id,
                empresa_id,
                ordem_id,
            )

            reservation = self._session.scalar(
                select(models.CheckoutOfferCampaignReservation).where(
                    models.CheckoutOfferCampaignReservation.ordem_id
                    == order.id
                )
            )
            if reservation is not None:
                database_now = self._database_now()
                self._validate_existing_reservation(
                    order,
                    reservation,
                    database_now,
                )
                return self._projection(order, reservation)

            self._validate_new_order(order)
            campaign = self._session.scalar(
                select(models.CheckoutOfferCampaign)
                .where(
                    models.CheckoutOfferCampaign.offer_id == order.offer_id,
                    models.CheckoutOfferCampaign.estado == "active",
                )
                .with_for_update()
            )
            if campaign is None:
                return None

            self._validate_campaign(campaign, order.offer_id)
            database_now = self._database_now()
            occupied = self._occupied_capacity(
                models,
                campaign.id,
                database_now,
            )
            if type(occupied) is not int or occupied >= campaign.purchase_limit:
                _fail()

            expires_at = database_now + timedelta(
                seconds=campaign.reservation_ttl_seconds
            )
            reservation = models.CheckoutOfferCampaignReservation(
                campaign_id=campaign.id,
                ordem_id=order.id,
                estado="reserved",
                reserved_at=database_now,
                expires_at=expires_at,
                confirmed_at=None,
                released_at=None,
                expired_at=None,
            )
            order.campaign_id = campaign.id
            order.campaign_code = campaign.codigo
            order.campaign_contract_version = campaign.contract_version
            order.campaign_purchase_limit = campaign.purchase_limit
            order.campaign_reservation_expires_at = expires_at
            self._session.add(reservation)
            self._session.flush()
            return self._projection(order, reservation)
        except CheckoutOfferCampaignReservationError:
            raise
        except Exception:
            raise CheckoutOfferCampaignReservationError() from None

    @staticmethod
    def _validate_input_ids(authenticated_user_id, empresa_id, ordem_id):
        if not all(
            _positive_integer(value)
            for value in (authenticated_user_id, empresa_id, ordem_id)
        ):
            _fail()

    @staticmethod
    def _validate_order_identity(order, user_id, empresa_id, ordem_id):
        if (
            order is None
            or not _positive_integer(order.id)
            or order.id != ordem_id
            or order.user_id != user_id
            or order.empresa_id != empresa_id
            or order.estado != "pending"
        ):
            _fail()

    @staticmethod
    def _validate_new_order(order):
        snapshot = (
            order.campaign_id,
            order.campaign_code,
            order.campaign_contract_version,
            order.campaign_purchase_limit,
            order.campaign_reservation_expires_at,
        )
        if (
            order.offer_id is None
            or order.provider_order_id is not None
            or order.checkout_url is not None
            or order.payment_id is not None
            or snapshot != (None, None, None, None, None)
        ):
            _fail()

    @staticmethod
    def _validate_existing_reservation(order, reservation, database_now):
        if (
            not _positive_integer(reservation.id)
            or reservation.ordem_id != order.id
            or reservation.estado != "reserved"
            or reservation.confirmed_at is not None
            or reservation.released_at is not None
            or reservation.expired_at is not None
            or type(reservation.reserved_at) is not datetime
            or type(reservation.expires_at) is not datetime
            or reservation.expires_at <= reservation.reserved_at
            or reservation.expires_at <= database_now
            or not _positive_integer(order.campaign_id)
            or order.campaign_id != reservation.campaign_id
            or not _canonical_campaign_code(order.campaign_code)
            or not _positive_integer(order.campaign_contract_version)
            or not _positive_integer(order.campaign_purchase_limit)
            or type(order.campaign_reservation_expires_at) is not datetime
            or order.campaign_reservation_expires_at != reservation.expires_at
        ):
            _fail()

    @staticmethod
    def _validate_campaign(campaign, offer_id):
        if (
            not _positive_integer(campaign.id)
            or campaign.offer_id != offer_id
            or campaign.estado != "active"
            or not _positive_integer(campaign.purchase_limit)
            or not _positive_integer(campaign.reservation_ttl_seconds)
            or not _positive_integer(campaign.contract_version)
            or not _canonical_campaign_code(campaign.codigo)
        ):
            _fail()

    def _database_now(self):
        value = self._session.scalar(
            select(cast(func.current_timestamp(), DateTime))
        )
        if type(value) is not datetime:
            _fail()
        return value

    def _occupied_capacity(self, models, campaign_id, database_now):
        reservation = models.CheckoutOfferCampaignReservation
        return self._session.scalar(
            select(func.count())
            .select_from(reservation)
            .where(
                reservation.campaign_id == campaign_id,
                or_(
                    reservation.estado == "confirmed",
                    and_(
                        reservation.estado == "reserved",
                        reservation.expires_at > database_now,
                    ),
                ),
            )
        )

    @staticmethod
    def _projection(order, reservation):
        return CheckoutOfferCampaignReservationProjection(
            reservation_id=reservation.id,
            ordem_id=reservation.ordem_id,
            campaign_id=reservation.campaign_id,
            campaign_code=order.campaign_code,
            campaign_contract_version=order.campaign_contract_version,
            campaign_purchase_limit=order.campaign_purchase_limit,
            estado=reservation.estado,
            reserved_at=reservation.reserved_at,
            expires_at=reservation.expires_at,
        )


__all__ = [
    "CheckoutOfferCampaignReservationAuthority",
    "CheckoutOfferCampaignReservationError",
    "CheckoutOfferCampaignReservationProjection",
]
