from sqlalchemy.orm import Session
from app.models import TabelaMVA


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
        }
        for r in registros
    ]


def buscar_mva(db: Session, estado: str, ncm: str):

    registro = (
        db.query(TabelaMVA)
        .filter(TabelaMVA.estado == estado)
        .filter(TabelaMVA.ncm == ncm)
        .first()
    )

    if not registro:
        return None

    return {
        "mva": registro.mva,
        "aliquota_interna": registro.aliquota_interna,
        "vigencia_inicio": registro.vigencia_inicio,
        "vigencia_fim": registro.vigencia_fim
    }
