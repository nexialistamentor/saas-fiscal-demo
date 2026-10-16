"""P1-04C3: read-only Enterprise transactional order binding (not payment consent).

P1-04C1 keeps checkout closed. The dispatcher has an additional hard hold,
including when a durable intent is perfectly valid. No transaction mutation.
"""
from __future__ import annotations

from datetime import datetime
import hmac
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    CheckoutOffer,
    DocumentoFiscal,
    Empresa,
    EnterpriseDocumentalCheckoutIntent,
    RelatorioAnalise,
)
from app.services.checkout_offer_catalog import checkout_offer_snapshot
from app.services.enterprise_documental_commercial_candidate import (
    CAPABILITY,
    OFFER_CODE,
)
from app.services.enterprise_xml_evidence_binding import (
    validar_vinculo_documento_relatorio,
)

_KEY = re.compile(r"[!-~]{1,255}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ERROR = "autoridade transacional Enterprise recusada"


class EnterpriseDocumentalCheckoutOrderAuthorityError(Exception):
    """Opaque rejection; no provider, payment, or ledger details."""


def _id(value):
    return type(value) is int and value > 0


def _same(left, right):
    return type(left) is str and type(right) is str and hmac.compare_digest(left, right)


class EnterpriseDocumentalCheckoutOrderAuthority:
    def __init__(self, db):
        self._db = db

    def require(
        self, *, authenticated_user_id, empresa_id, offer_code,
        idempotency_key, offer_id, offer_contract_version, capabilities,
        order=None, for_dispatch=False,
    ):
        # Other offers retain their pre-existing gates, unchanged.
        if offer_code != OFFER_CODE:
            return None
        if (
            self._db is None
            or not all(_id(v) for v in (
                authenticated_user_id, empresa_id, offer_id,
                offer_contract_version,
            ))
            or type(idempotency_key) is not str
            or _KEY.fullmatch(idempotency_key) is None
            or type(capabilities) is not tuple
            or capabilities != (CAPABILITY,)
            or type(for_dispatch) is not bool
        ):
            self._fail()

        try:
            intent = self._db.scalar(
                select(EnterpriseDocumentalCheckoutIntent).where(
                    EnterpriseDocumentalCheckoutIntent.checkout_idempotency_key
                    == idempotency_key
                )
            )
            if (
                intent is None
                or not _id(getattr(intent, "id", None))
                or intent.user_id != authenticated_user_id
                or intent.empresa_id != empresa_id
                or intent.offer_id != offer_id
                or intent.offer_code != OFFER_CODE
                or intent.offer_contract_version != offer_contract_version
                or intent.capability != CAPABILITY
                or not _id(intent.relatorio_analise_id)
                or not _id(intent.documento_fiscal_id)
                or not _same(intent.checkout_idempotency_key, idempotency_key)
                or type(intent.request_fingerprint) is not str
                or _HASH.fullmatch(intent.request_fingerprint) is None
                or type(intent.xml_sha256) is not str
                or _HASH.fullmatch(intent.xml_sha256) is None
                or type(intent.created_at) is not datetime
            ):
                self._fail()

            company = self._db.get(Empresa, empresa_id)
            report = self._db.get(RelatorioAnalise, intent.relatorio_analise_id)
            document = self._db.get(DocumentoFiscal, intent.documento_fiscal_id)
            if (
                company is None or company.user_id != authenticated_user_id
                or report is None
                or report.id != intent.relatorio_analise_id
                or report.user_id != authenticated_user_id
                or report.empresa_id != empresa_id
                or report.analysis_type != "xml_analise"
                or report.status != "ok"
                or not _same(report.fingerprint, intent.request_fingerprint)
                or document is None
                or document.id != intent.documento_fiscal_id
                or document.empresa_id != empresa_id
                or document.usuario_id != authenticated_user_id
                or not _same(document.conteudo_sha256, intent.xml_sha256)
                or not validar_vinculo_documento_relatorio(
                    report, document, empresa_id=empresa_id
                )
            ):
                self._fail()

            offer_entity = self._db.scalar(
                select(CheckoutOffer)
                .options(selectinload(CheckoutOffer.capabilities))
                .where(CheckoutOffer.id == offer_id)
            )
            if offer_entity is None:
                self._fail()
            offer = checkout_offer_snapshot(offer_entity)
            if (
                offer.id != offer_id
                or offer.codigo != OFFER_CODE
                or offer.contract_version != offer_contract_version
                or offer.estado != "published"
                or offer.vertical != "tax"
                or offer.commercial_model != "one_time"
                or offer.subject_type != "company"
                or offer.checkout_mode != "automatic"
                or offer.moeda != "BRL"
                or offer.billing_period is not None
                or offer.usage_unit != "diagnostic"
                or offer.usage_limit != 1
                or offer.capabilities != (CAPABILITY,)
            ):
                self._fail()

            if order is not None and (
                order.user_id != authenticated_user_id
                or order.empresa_id != empresa_id
                or order.offer_id != offer_id
                or order.offer_code != OFFER_CODE
                or order.contract_version != offer_contract_version
                or order.idempotency_key != idempotency_key
                or order.vertical != "tax"
                or order.commercial_model != "one_time"
                or order.subject_type != "company"
                or order.subject_id != empresa_id
                or order.estado != "pending"
                or order.moeda != "BRL"
                or order.valor != offer.preco
                or order.billing_period is not None
                or order.usage_unit != "diagnostic"
                or order.usage_limit != 1
            ):
                self._fail()

            # Explicit independent provider hold. Even an eligible persisted
            # intent MUST NOT release a billing dispatch in P1-04C3.
            if for_dispatch:
                self._fail()
            return None
        except EnterpriseDocumentalCheckoutOrderAuthorityError:
            raise
        except Exception:
            raise EnterpriseDocumentalCheckoutOrderAuthorityError(_ERROR) from None

    @staticmethod
    def _fail():
        raise EnterpriseDocumentalCheckoutOrderAuthorityError(_ERROR)


__all__ = [
    "EnterpriseDocumentalCheckoutOrderAuthority",
    "EnterpriseDocumentalCheckoutOrderAuthorityError",
]
