"""
fiscal_utils.py — camada L2 de resolução MVA/ST

DC-003: autoridade nacional por UF + NCM + data + fonte vigente.

Campos soberanos do retorno:
  calculo_autorizado  — True só se alíquota E MVA são canónicos
  calculo_parcial     — True quando MVA é real mas alíquota é estimada
  mva_autorizada      — True quando MVA vem de fonte normativa real
  aliquota_autorizada — True quando alíquota vem de fonte normativa real

Autoridade financeira: regra oficial, fonte legal identificada, vigência válida,
MVA positiva e alíquota decimal em (0, 1]. Convênio sem alíquota permite
apenas análise parcial de MVA. Lacunas e valores inválidos bloqueiam.

Princípio: fallback pode existir para compatibilidade de contrato.
Fallback não pode produzir autoridade fiscal.
"""

from datetime import date
from math import isfinite
from sqlalchemy.orm import Session
from app.services.tabela_normativa_service import buscar_mva, uf_tem_dados_mva

_ALIQUOTA_ICMS_FALLBACK = 0.18
_MVA_FALLBACK = 0.40

_UFS_VALIDAS = frozenset({
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT",
    "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO",
    "RR", "SC", "SP", "SE", "TO",
})


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
    uf_norm = uf.strip().upper() if isinstance(uf, str) else ""
    ncm_norm = ncm.strip() if isinstance(ncm, str) else ""

    # --- Ramo 1: UF desconhecida ---
    if not uf_norm:
        return _bloqueio(
            "fallback_uf_desconhecida", uf_norm, ncm_norm,
            "uf_desconhecida",
            "UF não identificada no documento fiscal. Cálculo não autorizado.",
        )

    if uf_norm not in _UFS_VALIDAS:
        return _bloqueio(
            "uf_invalida", uf_norm, ncm_norm, "uf_invalida",
            "UF inválida. Cálculo não autorizado.",
        )

    if not ncm_norm:
        return _bloqueio(
            "ncm_ausente", uf_norm, ncm_norm,
            "ncm_ausente",
            "NCM não informado. Cálculo não autorizado.",
        )

    if len(ncm_norm) != 8 or not ncm_norm.isascii() or not ncm_norm.isdigit():
        return _bloqueio(
            "ncm_invalido", uf_norm, ncm_norm, "ncm_invalido",
            "NCM deve conter oito dígitos. Cálculo não autorizado.",
        )

    if type(data_referencia) is not date:
        return _bloqueio(
            "data_referencia_invalida", uf_norm, ncm_norm, "data_referencia_invalida",
            "Data de referência explícita e válida obrigatória. Cálculo não autorizado.",
        )

    if not uf_tem_dados_mva(db, uf_norm):
        return _bloqueio(
            "fallback_uf_sem_dados", uf_norm, ncm_norm,
            "uf_sem_dados_mva",
            f"UF '{uf_norm}' sem dados MVA cadastrados. Cálculo não autorizado.",
        )

    # Cobertura da combinação exacta UF + NCM + data.
    regra = buscar_mva(db, uf_norm, ncm_norm, data_referencia=data_referencia)

    if not regra:
        # Ausência de regra vigente → lacuna normativa (I-MVA-06).
        return _bloqueio(
            "lacuna_normativa", uf_norm, ncm_norm,
            "lacuna_normativa",
            f"NCM '{ncm_norm}' sem cobertura normativa para {uf_norm}. "
            "Cálculo não autorizado — lacuna de dados MVA/ST.",
        )

    fonte_legal = regra.get("fonte_legal")
    nivel = regra.get("nivel_confianca_fonte")
    if (
        not isinstance(fonte_legal, str) or not fonte_legal.strip()
        or nivel not in ("oficial", "convenio_base_sem_aliquota")
    ):
        return _bloqueio(
            "fonte_normativa_invalida", uf_norm, ncm_norm, "fonte_normativa_invalida",
            "Fonte normativa ausente ou sem autoridade suficiente. Cálculo não autorizado.",
        )

    inicio = regra.get("vigencia_inicio")
    fim = regra.get("vigencia_fim")
    if (
        type(inicio) is not date
        or (fim is not None and type(fim) is not date)
        or inicio > data_referencia
        or (fim is not None and (fim < inicio or fim < data_referencia))
    ):
        return _bloqueio(
            "vigencia_invalida", uf_norm, ncm_norm, "vigencia_invalida",
            "Regra sem vigência válida na data de referência. Cálculo não autorizado.",
        )

    try:
        valor_mva = regra.get("mva")
        mva_val = float(valor_mva)
        if isinstance(valor_mva, bool) or not isfinite(mva_val) or mva_val <= 0:
            raise ValueError("MVA inválida")
    except (TypeError, ValueError, OverflowError):
        return _bloqueio(
            "mva_invalida", uf_norm, ncm_norm, "mva_invalida",
            "MVA deve ser positiva e finita. Cálculo não autorizado.",
        )
    # Compatibilidade: a tabela admite 0.40 ou 40.0 para quarenta por cento.
    if mva_val > 1:
        mva_val /= 100

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
                "MVA de convênio base; alíquota ICMS estimada (RICMS da UF não mapeado). "
                "MVA autorizada para análise de margem; alíquota não autorizada para cálculo financeiro."
            ),
            "calculo_autorizado": False,  # alíquota não autorizada → cálculo financeiro bloqueado
            "calculo_parcial": True,       # MVA é real — análise de margem permitida
            "mva_autorizada": True,
            "aliquota_autorizada": False,
            "bloqueio_normativo": False,   # não é bloqueio normativo total
            "motivo_bloqueio": None,
        }

    try:
        valor_aliquota = regra.get("aliquota_interna")
        aliquota = float(valor_aliquota)
        if isinstance(valor_aliquota, bool) or not isfinite(aliquota) or not 0 < aliquota <= 1:
            raise ValueError("Alíquota inválida")
    except (TypeError, ValueError, OverflowError):
        return _bloqueio(
            "aliquota_invalida", uf_norm, ncm_norm, "aliquota_invalida",
            "Alíquota decimal deve estar em (0, 1]. Cálculo não autorizado.",
        )

    # Regra oficial completa: autoridade financeira.
    return {
        "aliquota": aliquota,
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
