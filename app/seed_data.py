"""Dados mínimos para o primeiro uso (sem depender de endpoints manuais)."""
from sqlalchemy.orm import Session

from app import models


def ensure_planos(db: Session) -> None:
    if db.query(models.Plano).first() is not None:
        return
    for nome, limite_cnpjs, limite_analises in (
        ("Basico", 5, 100),
        ("Pro", 10, 500),
        ("Ilimitado", 999999, 999999),
        ("Teste", 2, 2),
    ):
        db.add(
            models.Plano(
                nome=nome,
                limite_cnpjs=limite_cnpjs,
                limite_analises=limite_analises,
            )
        )
    db.commit()
