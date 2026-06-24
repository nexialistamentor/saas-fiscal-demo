"""
fiscal_utils.py — camada L2 de resolução MVA/ST

DT-MVA-01: escopo normativo do piloto = Pará.

Campos soberanos do retorno:
  calculo_autorizado  — True só se alíquota E MVA são canónicos
  calculo_parcial     — True quando MVA é real mas alíquota é estimada
  mva_autorizada      — True quando MVA vem de fonte normativa real
  aliquota_autorizada — True quando alíquota vem de fonte normativa real

Ramos:
  UF vazia              → fallback_uf_desconhecida, tudo False
  UF ≠ PA               → fora_de_escopo_normativo_piloto, tudo False
  PA sem dados MVA       → fallback_uf_sem_dados, tudo False
  PA + NCM sem regra     → lacuna_normativa, tudo False (I-MVA-06)
  PA + NCM sem NCM       → ncm_ausente, tudo False
  PA + convenio_base     → tabela, parcial (mva_autorizada=True, aliquota_autorizada=False)
  PA + regra completa    → tabela, tudo True

Princípio: fallback pode existir para compatibilidade de contrato.
Fallback não pode produzir autoridade fiscal.
"""

from datetime import date
from sqlalchemy.orm import Session
from app.services.tabela_normativa_service import buscar_mva, uf_tem_dados_mva

_ALIQUOTA_ICMS_FALLBACK = 0.18
_MVA_FALLBACK = 0.40

# UF canónica do piloto V1
_UF_PILOTO = "PA"


def uf_do_documento(documento) -> str:
    """Prioriza uf_dest sobre uf_emit."""
    if hasattr(documento, "uf_dest") and documento.uf_dest:
        return documento.uf_dest.strip().upper()[:2]
    if hasattr(documento, "uf_emit") and documento.uf_emit:
        return documento.uf_emit.strip().upper()[:2]
    return ""


def _bloqueio(fonte: str, uf: str, ncm: str, motivo: str, aviso: str) -> dict:
    """Helper para ramos sem autorização normativa."""
    return {
        "aliquota": _ALIQUOTA_ICMS_FALLBACK,
        "mva": _MVA_FALLBACK,
        "fonte": fonte,
        "uf": uf,
        "ncm": ncm,
        "confianca": "indisponivel",
        "aviso": aviso,
        "calculo_autorizado": False,
        "calculo_parcial": False,
        "mva_autorizada": False,
        "aliquota_autorizada": False,
        "bloqueio_normativo": True,
        "motivo_bloqueio": motivo,
    }


def resolver_aliquota_e_mva(
    db: Session,
    uf: str,
    ncm: str,
    data_referencia: date | None = None,
) -> dict:
    """
    Resolve alíquota ICMS e MVA para UF + NCM.

    Retorna dict com campos:
      aliquota, mva, fonte, uf, ncm, confianca, aviso (opcional),
      calculo_autorizado, calculo_parcial,
      mva_autorizada, aliquota_autorizada,
      bloqueio_normativo, motivo_bloqueio

    Regras de uso pelos callers:
      Cálculo financeiro com alíquota:
        if not res["calculo_autorizado"] or res["calculo_parcial"]: skip
      Análise de MVA (sem alíquota):
        if not res["mva_autorizada"]: skip
    """
    uf_norm = (uf or "").strip().upper()[:2]
    ncm_norm = (ncm or "").strip()

    # --- Ramo 1: UF desconhecida ---
    if not uf_norm:
        return _bloqueio(
            "fallback_uf_desconhecida", uf_norm, ncm_norm,
            "uf_desconhecida",
            "UF não identificada no documento fiscal. Cálculo não autorizado.",
        )

    # --- Ramo 2: UF fora do escopo do piloto (≠ PA) ---
    if uf_norm != _UF_PILOTO:
        return _bloqueio(
            "fora_de_escopo_normativo_piloto", uf_norm, ncm_norm,
            "fora_de_escopo_normativo_piloto",
            f"UF '{uf_norm}' fora do escopo normativo do piloto ({_UF_PILOTO}). "
            "Cálculo não autorizado — sem cobertura normativa validada.",
        )

    # --- A partir daqui: UF == PA ---

    # --- Ramo 3: PA sem NCM ---
    if not ncm_norm:
        return _bloqueio(
            "ncm_ausente", uf_norm, ncm_norm,
            "ncm_ausente",
            "NCM não informado. Cálculo não autorizado.",
        )

    # --- Ramo 4: PA sem dados MVA cadastrados ---
    if not uf_tem_dados_mva(db, uf_norm):
        return _bloqueio(
            "fallback_uf_sem_dados", uf_norm, ncm_norm,
            "uf_sem_dados_mva",
            f"UF '{uf_norm}' sem dados MVA cadastrados. Cálculo não autorizado.",
        )

    # --- Ramo 5: PA + NCM — buscar regra ---
    regra = buscar_mva(db, uf_norm, ncm_norm, data_referencia=data_referencia)

    if not regra:
        # PA + NCM sem regra → lacuna normativa (I-MVA-06)
        return _bloqueio(
            "lacuna_normativa", uf_norm, ncm_norm,
            "lacuna_normativa",
            f"NCM '{ncm_norm}' sem cobertura normativa para {uf_norm}. "
            "Cálculo não autorizado — lacuna de dados MVA/ST.",
        )

    mva_val = (
        float(regra["mva"]) / 100 if regra["mva"] > 1 else float(regra["mva"])
    )
    nivel = regra.get("nivel_confianca_fonte", "desconhecido")

    # --- Ramo 6: convenio_base_sem_aliquota — MVA real, alíquota estimada ---
    if nivel == "convenio_base_sem_aliquota":
        return {
            "aliquota": _ALIQUOTA_ICMS_FALLBACK,
            "mva": mva_val,
            "fonte": "tabela",
            "uf": uf_norm,
            "ncm": ncm_norm,
            "confianca": "estimativa",
            "aviso": (
                "MVA de convênio base; alíquota ICMS estimada (RICMS PA não mapeado). "
                "MVA autorizada para análise de margem; alíquota não autorizada para cálculo financeiro."
            ),
            "calculo_autorizado": False,  # alíquota não autorizada → cálculo financeiro bloqueado
            "calculo_parcial": True,       # MVA é real — análise de margem permitida
            "mva_autorizada": True,
            "aliquota_autorizada": False,
            "bloqueio_normativo": False,   # não é bloqueio normativo total
            "motivo_bloqueio": None,
        }

    # --- Ramo 7: regra completa ---
    return {
        "aliquota": float(regra["aliquota_interna"]),
        "mva": mva_val,
        "fonte": "tabela",
        "uf": uf_norm,
        "ncm": ncm_norm,
        "confianca": nivel,
        "calculo_autorizado": True,
        "calculo_parcial": False,
        "mva_autorizada": True,
        "aliquota_autorizada": True,
        "bloqueio_normativo": False,
        "motivo_bloqueio": None,
    }
