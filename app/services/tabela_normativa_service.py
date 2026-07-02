from datetime import date

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models import TabelaMVA, TabelaPMPF
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError


def _exigir_data_referencia_normativa(data_referencia):
    if data_referencia is None:
        raise TempoNormativoAusenteError(
            "Consulta normativa ST/PMPF/MVA requer data_referencia explícita. "
            "Bloqueado por B13-OPS-13E.1."
        )
    return data_referencia

_PRIORIDADE_FONTE = case(
    (TabelaMVA.nivel_confianca_fonte == "oficial", 0),
    (
        TabelaMVA.nivel_confianca_fonte.in_(("convenio_base", "convenio_base_sem_aliquota")),
        1,
    ),
    (TabelaMVA.nivel_confianca_fonte == "estimativa", 2),
    else_=3,
)


def uf_tem_dados_mva(db: Session, uf: str) -> bool:
    """Verifica se há pelo menos uma regra MVA activa para a UF."""
    return db.query(TabelaMVA).filter(TabelaMVA.estado == uf).limit(1).count() > 0


def listar_base_normativa(db: Session):
    """Retorna a base normativa (tabela MVA) para uso pelos agentes."""
    registros = db.query(TabelaMVA).all()
    return [
        {
            "estado": r.estado,
            "ncm": r.ncm,
            "mva": r.mva,
            "aliquota_interna": r.aliquota_interna,
            "vigencia_inicio": str(r.vigencia_inicio) if r.vigencia_inicio else None,
            "vigencia_fim": str(r.vigencia_fim) if r.vigencia_fim else None,
            "nivel_confianca_fonte": r.nivel_confianca_fonte or "sem_fonte",
            "fonte_legal": r.fonte_legal,
            "importado_por": r.importado_por,
        }
        for r in registros
    ]


def buscar_pmpf(
    db: Session,
    estado: str,
    ncm: str,
    marca: str | None = None,
    embalagem_ml: int | None = None,
    data_referencia: date | None = None,
) -> dict | None:
    """
    Busca PMPF para estado+ncm. Prioridade:
    1. Marca exacta + embalagem exacta
    2. Marca exacta + qualquer embalagem
    3. "DEMAIS MARCAS" + embalagem exacta
    4. "DEMAIS MARCAS" + qualquer embalagem
    Retorna None se não houver PMPF — caller usa buscar_mva como fallback.
    """
    ref = _exigir_data_referencia_normativa(data_referencia)
    uf = (estado or "").strip().upper()[:2]
    ncm_norm = (ncm or "").strip()
    if not uf or not ncm_norm:
        return None

    base_q = db.query(TabelaPMPF).filter(
        TabelaPMPF.estado == uf,
        TabelaPMPF.ncm == ncm_norm,
        TabelaPMPF.vigencia_inicio <= ref,
        or_(TabelaPMPF.vigencia_fim.is_(None), TabelaPMPF.vigencia_fim >= ref),
    )

    tentativas: list[tuple[str, int | None]] = []
    if marca:
        m = marca.strip().upper()
        if embalagem_ml is not None:
            tentativas.append((m, embalagem_ml))
        tentativas.append((m, None))
    if embalagem_ml is not None:
        tentativas.append(("DEMAIS MARCAS", embalagem_ml))
    tentativas.append(("DEMAIS MARCAS", None))

    for m, e in tentativas:
        q = base_q.filter(TabelaPMPF.marca == m)
        if e is not None:
            q = q.filter(TabelaPMPF.embalagem_ml == e)
        else:
            q = q.filter(TabelaPMPF.embalagem_ml.is_(None))
        reg = q.order_by(TabelaPMPF.vigencia_inicio.desc()).first()
        if reg:
            return {
                "pmpf_reais": reg.pmpf_reais,
                "aliquota_interna": reg.aliquota_interna,
                "marca": reg.marca,
                "embalagem_ml": reg.embalagem_ml,
                "estado": reg.estado,
                "ncm": reg.ncm,
                "fonte_legal": reg.fonte_legal,
                "nivel_confianca_fonte": reg.nivel_confianca_fonte or "oficial",
                "fonte": "pmpf",
            }
    return None


def verificar_cobertura_normativa_st(
    db: Session,
    uf: str,
    ncm: str,
    data_referencia: date,
) -> str:
    """
    Detecta cobertura normativa ST para UF/NCM na data_referencia.
    Retorna: "vigente" | "sem_regra" | "expirada_sem_substituto"
    """
    uf_norm = (uf or "").strip().upper()[:2]
    ncm_norm = (ncm or "").strip()
    if not uf_norm or not ncm_norm:
        return "sem_regra"

    if buscar_mva(db, uf_norm, ncm_norm, data_referencia):
        return "vigente"

    pmpf_vigente = (
        db.query(TabelaPMPF)
        .filter(
            TabelaPMPF.estado == uf_norm,
            TabelaPMPF.ncm == ncm_norm,
            TabelaPMPF.vigencia_inicio <= data_referencia,
            or_(
                TabelaPMPF.vigencia_fim.is_(None),
                TabelaPMPF.vigencia_fim >= data_referencia,
            ),
        )
        .first()
    )
    if pmpf_vigente:
        return "vigente"

    mva_expirada = (
        db.query(TabelaMVA)
        .filter(
            TabelaMVA.estado == uf_norm,
            TabelaMVA.ncm == ncm_norm,
            or_(
                TabelaMVA.vigencia_inicio.is_(None),
                TabelaMVA.vigencia_inicio <= data_referencia,
            ),
            TabelaMVA.vigencia_fim.isnot(None),
            TabelaMVA.vigencia_fim < data_referencia,
        )
        .first()
    )
    pmpf_expirada = (
        db.query(TabelaPMPF)
        .filter(
            TabelaPMPF.estado == uf_norm,
            TabelaPMPF.ncm == ncm_norm,
            TabelaPMPF.vigencia_inicio <= data_referencia,
            TabelaPMPF.vigencia_fim.isnot(None),
            TabelaPMPF.vigencia_fim < data_referencia,
        )
        .first()
    )
    if mva_expirada or pmpf_expirada:
        return "expirada_sem_substituto"

    return "sem_regra"


def resolver_base_calculo_st(
    db: Session,
    estado: str,
    ncm: str,
    valor_produto: float,
    marca: str | None = None,
    embalagem_ml: int | None = None,
    data_referencia: date | None = None,
) -> dict:
    """
    Resolve base de cálculo ST com hierarquia completa:
    1. PMPF (estado+ncm+marca+embalagem)
    2. IVA-ST% via buscar_mva
    3. Fallback indisponível
    Retorna dict com base_calculo, aliquota_interna, metodo, confianca, fonte_legal.
    """
    from app.services.fiscal_utils import _ALIQUOTA_ICMS_FALLBACK

    ref = _exigir_data_referencia_normativa(data_referencia)
    uf = (estado or "").strip().upper()[:2]
    ncm_norm = (ncm or "").strip()

    pmpf = buscar_pmpf(db, uf, ncm_norm, marca, embalagem_ml, ref)
    if pmpf:
        return {
            "base_calculo": pmpf["pmpf_reais"],
            "aliquota_interna": pmpf["aliquota_interna"],
            "metodo": "pmpf",
            "confianca": pmpf["nivel_confianca_fonte"],
            "fonte_legal": pmpf["fonte_legal"],
            "marca": pmpf["marca"],
        }

    cobertura = verificar_cobertura_normativa_st(db, uf, ncm_norm, ref)
    if cobertura == "expirada_sem_substituto":
        return {
            "base_calculo": None,
            "aliquota_interna": None,
            "metodo": "bloqueado_cobertura_expirada",
            "confianca": "indisponivel",
            "fonte_legal": None,
            "aviso": (
                f"Regra MVA/PMPF para {uf}/{ncm_norm} expirou sem substituto "
                f"na data {ref}."
            ),
        }

    if not uf or not uf_tem_dados_mva(db, uf):
        return {
            "base_calculo": None,
            "aliquota_interna": None,
            "metodo": "indisponivel",
            "confianca": "indisponivel",
            "fonte_legal": None,
            "aviso": (
                f"Sem PMPF e UF {uf or '(?)'} sem dados MVA cadastrados. "
                "Cálculo ST indisponível."
            ),
        }

    mva = buscar_mva(db, uf, ncm_norm, ref)
    if mva:
        nivel = mva.get("nivel_confianca_fonte") or "sem_fonte"
        mva_val = (
            float(mva["mva"]) / 100
            if float(mva["mva"]) > 1
            else float(mva["mva"])
        )
        base = round(float(valor_produto) * (1 + mva_val), 2)
        if nivel == "convenio_base_sem_aliquota":
            return {
                "base_calculo": base,
                "aliquota_interna": _ALIQUOTA_ICMS_FALLBACK,
                "metodo": "iva_st",
                "confianca": "estimativa",
                "fonte_legal": mva.get("fonte_legal"),
                "aviso": (
                    "MVA do Convênio ICMS 142/2018 (base convênio); alíquota interna "
                    "não cadastrada com fonte estadual verificada — aplicado fallback "
                    "documentado de ICMS."
                ),
            }
        return {
            "base_calculo": base,
            "aliquota_interna": float(mva["aliquota_interna"]),
            "metodo": "iva_st",
            "confianca": nivel,
            "fonte_legal": mva.get("fonte_legal"),
        }

    return {
        "base_calculo": None,
        "aliquota_interna": None,
        "metodo": "indisponivel",
        "confianca": "indisponivel",
        "fonte_legal": None,
        "aviso": f"Sem PMPF nem MVA para {uf}/{ncm_norm}. Cálculo ST indisponível.",
    }


def buscar_mva(
    db: Session,
    estado: str,
    ncm: str,
    data_referencia: date | None = None,
):
    ref = _exigir_data_referencia_normativa(data_referencia)
    q = (
        db.query(TabelaMVA)
        .filter(TabelaMVA.estado == estado)
        .filter(TabelaMVA.ncm == ncm)
        .filter(
            or_(
                TabelaMVA.vigencia_inicio.is_(None),
                TabelaMVA.vigencia_inicio <= ref,
            )
        )
        .filter(
            or_(
                TabelaMVA.vigencia_fim.is_(None),
                TabelaMVA.vigencia_fim >= ref,
            )
        )
    )
    registro = q.order_by(
        _PRIORIDADE_FONTE,
        TabelaMVA.vigencia_inicio.desc(),
        TabelaMVA.id.desc(),
    ).first()

    if not registro:
        return None

    return {
        "mva": registro.mva,
        "aliquota_interna": registro.aliquota_interna,
        "vigencia_inicio": registro.vigencia_inicio,
        "vigencia_fim": registro.vigencia_fim,
        "fonte_legal": getattr(registro, "fonte_legal", None),
        "url_fonte": getattr(registro, "url_fonte", None),
        "nivel_confianca_fonte": registro.nivel_confianca_fonte or "sem_fonte",
    }
