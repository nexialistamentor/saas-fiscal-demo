"""
fiscal_utils.py — Utilitários fiscais centralizados (Soberana L2)

Regra: toda resolução de alíquota + MVA passa por aqui.
Nenhum serviço usa alíquota ou MVA hardcoded directamente.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.services.tabela_normativa_service import buscar_mva, uf_tem_dados_mva

# Fallbacks documentados — usados APENAS quando não há regra na tabela_mva
# Devem ser marcados como "fallback" no output para rastreabilidade
_ALIQUOTA_ICMS_FALLBACK = 0.18
_MVA_FALLBACK = 0.40


def resolver_aliquota_e_mva(
    db: Session,
    uf: str,
    ncm: str,
    data_referencia: date | None = None,
) -> dict:
    """
    Resolve alíquota interna e MVA para UF + NCM a partir da tabela_mva.

    Returns:
        {
            "aliquota": float,
            "mva": float,        # MVA decimal (ex: 0.40)
            "fonte": str,        # "tabela" | "fallback" | "fallback_uf_sem_dados"
            "uf": str,
            "ncm": str,
            "confianca": str,    # nível da fonte na tabela ou indisponível/estimativa (fallback)
            "aviso": str | None, # quando aplicável
        }
    """
    uf_norm = (uf or "PA").strip().upper()[:2]
    ncm_norm = (ncm or "").strip()

    if not uf_tem_dados_mva(db, uf_norm):
        return {
            "aliquota": _ALIQUOTA_ICMS_FALLBACK,
            "mva": _MVA_FALLBACK,
            "fonte": "fallback_uf_sem_dados",
            "uf": uf_norm,
            "ncm": ncm_norm,
            "confianca": "indisponivel",
            "aviso": (
                f"UF {uf_norm} sem dados MVA cadastrados. Cálculo ST indisponível."
            ),
        }

    regra = (
        buscar_mva(db, uf_norm, ncm_norm, data_referencia=data_referencia)
        if ncm_norm
        else None
    )

    if regra:
        return {
            "aliquota": float(regra["aliquota_interna"]),
            "mva": float(regra["mva"]) / 100 if regra["mva"] > 1 else float(regra["mva"]),
            "fonte": "tabela",
            "uf": uf_norm,
            "ncm": ncm_norm,
            "confianca": regra.get("nivel_confianca_fonte") or "sem_fonte",
        }

    return {
        "aliquota": _ALIQUOTA_ICMS_FALLBACK,
        "mva": _MVA_FALLBACK,
        "fonte": "fallback",
        "uf": uf_norm,
        "ncm": ncm_norm,
        "confianca": "estimativa",
        "aviso": "Sem regra MVA na tabela. Valores de fallback aplicados.",
    }


def uf_do_documento(documento) -> str:
    """
    Extrai a UF relevante de um DocumentoFiscal.
    Prioriza uf_dest (destino da operação) sobre uf_emit.
    Fallback: "PA".
    """
    if documento is None:
        return "PA"
    return (
        getattr(documento, "uf_dest", None)
        or getattr(documento, "uf_emit", None)
        or "PA"
    ).strip().upper()[:2]
