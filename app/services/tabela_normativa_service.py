from datetime import date

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from app.models import TabelaMVA

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


def buscar_mva(
    db: Session,
    estado: str,
    ncm: str,
    data_referencia: date | None = None,
):
    q = (
        db.query(TabelaMVA)
        .filter(TabelaMVA.estado == estado)
        .filter(TabelaMVA.ncm == ncm)
    )
    if data_referencia is not None:
        q = q.filter(
            or_(
                TabelaMVA.vigencia_inicio.is_(None),
                TabelaMVA.vigencia_inicio <= data_referencia,
            )
        ).filter(
            or_(
                TabelaMVA.vigencia_fim.is_(None),
                TabelaMVA.vigencia_fim >= data_referencia,
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
