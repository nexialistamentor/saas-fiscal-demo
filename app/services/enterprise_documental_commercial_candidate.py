"""P1-04B — projecao PURA da candidatura comercial documental Enterprise.

Nao autoriza compra, nao emite oferta, nao persiste intencao, nao consulta
pagamentos, nao opera grants e nao escreve em base de dados. A oferta deve vir
de catalogo validado por autoridade de publicacao e o chamador deve autenticar
a identidade. P1-04C sera uma fronteira transacional distinta e obrigatoria.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.services.enterprise_diagnostic_readiness import (
    avaliar_prontidao_diagnostico_enterprise,
)

OFFER_CODE = "enterprise-documental-diagnostic-one-time-company"
CAPABILITY = "enterprise.diagnostic.documental"

_DENIED = {
    "oferta_documental_valida": False,
    "candidatura_comercial": False,
    "checkout_autorizado": False,
}
_READY_KEYS = frozenset({
    "documental_suficiente", "empresarial_completo",
    "st_nao_destacado_observado", "politica_diagnostico_elegivel",
    "diagnostico_documental_apresentavel", "checkout_autorizado",
})


def _id(value: object) -> bool:
    return type(value) is int and value > 0


def _price(value: object) -> bool:
    if type(value) is not Decimal or not value.is_finite() or value <= 0:
        return False
    try:
        return value == value.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return False


def _offer_is_valid(oferta: object) -> bool:
    """Conferencia de termos fechados; nao substitui o catalogo publicado."""
    return bool(
        _id(getattr(oferta, "id", None))
        and getattr(oferta, "codigo", None) == OFFER_CODE
        and type(getattr(oferta, "codigo", None)) is str
        and type(getattr(oferta, "nome_publico", None)) is str
        and 0 < len(oferta.nome_publico) <= 255
        and oferta.nome_publico == oferta.nome_publico.strip()
        and "\n" not in oferta.nome_publico and "\r" not in oferta.nome_publico
        and getattr(oferta, "estado", None) == "published"
        and getattr(oferta, "checkout_mode", None) == "automatic"
        and getattr(oferta, "vertical", None) == "tax"
        and getattr(oferta, "commercial_model", None) == "one_time"
        and getattr(oferta, "subject_type", None) == "company"
        and getattr(oferta, "moeda", None) == "BRL"
        and _price(getattr(oferta, "preco", None))
        and getattr(oferta, "billing_period", None) is None
        and getattr(oferta, "usage_unit", None) == "diagnostic"
        and type(getattr(oferta, "usage_limit", None)) is int
        and oferta.usage_limit == 1
        and _id(getattr(oferta, "contract_version", None))
        and type(getattr(oferta, "capabilities", None)) is tuple
        and oferta.capabilities == (CAPABILITY,)
    )


def _readiness_is_valid(readiness: object) -> bool:
    return bool(
        type(readiness) is dict
        and readiness.keys() == _READY_KEYS
        and all(type(value) is bool for value in readiness.values())
        and readiness["documental_suficiente"] is True
        and readiness["diagnostico_documental_apresentavel"] is True
        and readiness["empresarial_completo"] is False
        and readiness["checkout_autorizado"] is False
    )


def avaliar_candidatura_comercial_documental(
    db: object, *, authenticated_user_id: int, empresa_id: int,
    relatorio_id: int, xml_bytes: bytes, oferta: object,
) -> dict[str, bool]:
    """Projeta somente a possibilidade de candidatura; NUNCA checkout.

    P1-04A prova identidade documental. Mesmo uma candidatura positiva NAO
    e direito de compra nem pode servir como pre-requisito sozinho no checkout.
    """
    if (
        db is None
        or not all(_id(value) for value in
                   (authenticated_user_id, empresa_id, relatorio_id))
        or type(xml_bytes) is not bytes
        or not (0 < len(xml_bytes) <= 2 * 1024 * 1024)
    ):
        return dict(_DENIED)
    try:
        if not _offer_is_valid(oferta):
            return dict(_DENIED)
        readiness = avaliar_prontidao_diagnostico_enterprise(
            db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes,
        )
        if not _readiness_is_valid(readiness):
            return dict(_DENIED)
        return {
            "oferta_documental_valida": True,
            "candidatura_comercial": True,
            "checkout_autorizado": False,
        }
    except Exception:
        return dict(_DENIED)


__all__ = [
    "OFFER_CODE", "CAPABILITY", "avaliar_candidatura_comercial_documental",
]
