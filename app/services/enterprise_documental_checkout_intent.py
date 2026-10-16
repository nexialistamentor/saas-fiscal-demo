"""P1-04C2: append-only documentary Enterprise intent; NEVER permits checkout.

Only the caller owns the SQLAlchemy transaction. P1-04C1 remains fail-closed:
a persisted intent cannot make an order or authorize payments in this phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.models import (
    CheckoutOffer,
    DocumentoFiscal,
    Empresa,
    EnterpriseDocumentalCheckoutIntent as _IntentModel,
    RelatorioAnalise,
)
from app.services.checkout_offer_catalog import checkout_offer_snapshot
from app.services.enterprise_documental_commercial_candidate import (
    CAPABILITY,
    OFFER_CODE,
    avaliar_candidatura_comercial_documental,
)
from app.services.enterprise_xml_evidence_binding import KEY as EVIDENCE_KEY
from app.services.resultado_provenance_service import verificar_resultado_persistido

_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_KEY = re.compile(r"[!-~]{1,255}\Z", re.ASCII)
_PUBLIC_ERROR = "intencao documental Enterprise recusada"


class EnterpriseDocumentalCheckoutIntentError(Exception):
    """Opaque fail-closed error; no payments or underlying data are exposed."""


@dataclass(frozen=True)
class EnterpriseDocumentalCheckoutIntentResult:
    intent_id: int
    checkout_idempotency_key: str
    user_id: int
    empresa_id: int
    relatorio_analise_id: int
    documento_fiscal_id: int
    offer_id: int
    offer_code: str
    offer_contract_version: int
    capability: str
    request_fingerprint: str
    xml_sha256: str
    created_at: datetime


def _id(value):
    return type(value) is int and value > 0


def _same(left, right):
    return type(left) is str and type(right) is str and hmac.compare_digest(left, right)


class EnterpriseDocumentalCheckoutIntent:
    def __init__(self, db):
        self._db = db

    def persist(
        self, *, user_id, empresa_id, relatorio_id, offer_code,
        checkout_idempotency_key, request_fingerprint, xml_bytes,
    ):
        if (
            self._db is None
            or any(not _id(x) for x in (user_id, empresa_id, relatorio_id))
            or type(offer_code) is not str or offer_code != OFFER_CODE
            or type(checkout_idempotency_key) is not str
            or _KEY.fullmatch(checkout_idempotency_key) is None
            or type(request_fingerprint) is not str
            or _HASH.fullmatch(request_fingerprint) is None
            or type(xml_bytes) is not bytes
            or not (0 < len(xml_bytes) <= 2 * 1024 * 1024)
        ):
            self._fail()
        xml_sha256 = hashlib.sha256(xml_bytes).hexdigest()

        try:
            # Query and validate current canonical data even for an exact replay.
            empresa = self._db.get(Empresa, empresa_id)
            relatorio = self._db.get(RelatorioAnalise, relatorio_id)
            if (
                empresa is None or empresa.user_id != user_id
                or relatorio is None or relatorio.user_id != user_id
                or relatorio.empresa_id != empresa_id
                or relatorio.analysis_type != "xml_analise"
                or relatorio.status != "ok"
                or not _same(relatorio.fingerprint, request_fingerprint)
            ):
                self._fail()

            # Read the sealed provenance, not an unverified raw JSON pointer.
            evidence = verificar_resultado_persistido(relatorio)
            if type(evidence) is not dict or evidence.get("empresa_id") != empresa_id:
                self._fail()
            binding = evidence.get(EVIDENCE_KEY)
            if type(binding) is not dict:
                self._fail()
            doc_id = binding.get("documento_id")
            if not _id(doc_id):
                self._fail()
            documento = self._db.get(DocumentoFiscal, doc_id)
            if (
                documento is None or documento.empresa_id != empresa_id
                or documento.usuario_id != user_id
                or not _same(documento.conteudo_sha256, xml_sha256)
            ):
                self._fail()

            offer_entity = self._db.scalar(
                select(CheckoutOffer)
                .options(selectinload(CheckoutOffer.capabilities))
                .where(CheckoutOffer.codigo == offer_code)
            )
            if offer_entity is None:
                self._fail()
            oferta = checkout_offer_snapshot(offer_entity)
            candidate = avaliar_candidatura_comercial_documental(
                self._db, authenticated_user_id=user_id, empresa_id=empresa_id,
                relatorio_id=relatorio_id, xml_bytes=xml_bytes, oferta=oferta,
            )
            if (
                type(candidate) is not dict
                or candidate != {
                    "oferta_documental_valida": True,
                    "candidatura_comercial": True,
                    "checkout_autorizado": False,
                }
                or any(type(v) is not bool for v in candidate.values())
                or not _id(oferta.id)
                or not _id(oferta.contract_version)
                or oferta.capabilities != (CAPABILITY,)
            ):
                self._fail()

            existing = self._db.scalar(
                select(_IntentModel).where(
                    _IntentModel.checkout_idempotency_key == checkout_idempotency_key
                )
            )
            if existing is not None:
                if not self._matches(
                    existing, user_id=user_id, empresa_id=empresa_id,
                    relatorio_id=relatorio_id, documento_id=doc_id, oferta=oferta,
                    key=checkout_idempotency_key, request_fingerprint=request_fingerprint,
                    xml_sha256=xml_sha256,
                ):
                    self._fail()
                return self._project(existing)

            intent = _IntentModel(
                checkout_idempotency_key=checkout_idempotency_key,
                user_id=user_id, empresa_id=empresa_id,
                relatorio_analise_id=relatorio_id, documento_fiscal_id=doc_id,
                offer_id=oferta.id, offer_code=OFFER_CODE,
                offer_contract_version=oferta.contract_version,
                capability=CAPABILITY, request_fingerprint=request_fingerprint,
                xml_sha256=xml_sha256,
            )
            self._db.add(intent)
            self._db.flush()
            if not _id(intent.id) or type(intent.created_at) is not datetime:
                self._fail()
            return self._project(intent)
        except EnterpriseDocumentalCheckoutIntentError:
            raise
        except Exception:
            # SQL errors, provenance errors and malformed data fail closed.
            # Intentionally never commit or roll back the caller's transaction.
            raise EnterpriseDocumentalCheckoutIntentError(_PUBLIC_ERROR) from None

    @staticmethod
    def _matches(existing, *, user_id, empresa_id, relatorio_id, documento_id,
                 oferta, key, request_fingerprint, xml_sha256):
        return (
            _id(getattr(existing, "id", None))
            and existing.checkout_idempotency_key == key
            and existing.user_id == user_id
            and existing.empresa_id == empresa_id
            and existing.relatorio_analise_id == relatorio_id
            and existing.documento_fiscal_id == documento_id
            and existing.offer_id == oferta.id
            and existing.offer_code == OFFER_CODE
            and existing.offer_contract_version == oferta.contract_version
            and existing.capability == CAPABILITY
            and _same(existing.request_fingerprint, request_fingerprint)
            and _same(existing.xml_sha256, xml_sha256)
            and type(existing.created_at) is datetime
        )

    @staticmethod
    def _project(intent):
        return EnterpriseDocumentalCheckoutIntentResult(
            intent_id=intent.id,
            checkout_idempotency_key=intent.checkout_idempotency_key,
            user_id=intent.user_id,
            empresa_id=intent.empresa_id,
            relatorio_analise_id=intent.relatorio_analise_id,
            documento_fiscal_id=intent.documento_fiscal_id,
            offer_id=intent.offer_id,
            offer_code=intent.offer_code,
            offer_contract_version=intent.offer_contract_version,
            capability=intent.capability,
            request_fingerprint=intent.request_fingerprint,
            xml_sha256=intent.xml_sha256,
            created_at=intent.created_at,
        )

    @staticmethod
    def _fail():
        raise EnterpriseDocumentalCheckoutIntentError(_PUBLIC_ERROR)


__all__ = [
    "EnterpriseDocumentalCheckoutIntent",
    "EnterpriseDocumentalCheckoutIntentError",
    "EnterpriseDocumentalCheckoutIntentResult",
]
