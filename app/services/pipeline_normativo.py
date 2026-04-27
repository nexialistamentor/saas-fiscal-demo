"""
Pipeline normativo nacional — L2.

Substitui importador/monitor/verificador legado PA.

Princípio: fonte oficial → validação → BD com rastreabilidade completa.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from app.models import TabelaMVA
from app.services.atualizacao_normativa_service import atualizar_mva

logger = logging.getLogger(__name__)

NivelConfianca = Literal[
    "oficial",
    "convenio_base",
    "convenio_base_sem_aliquota",
    "estimativa",
    "sem_fonte",
]


@dataclass
class RegraNormativa:
    estado: str
    ncm: str
    mva: float
    aliquota_interna: float
    vigencia_inicio: date
    vigencia_fim: date | None
    fonte_legal: str
    url_fonte: str | None
    nivel_confianca: NivelConfianca
    importado_por: str


@dataclass
class ResultadoImport:
    inseridos: int = 0
    atualizados: int = 0
    ignorados: int = 0
    erros: list[str] = field(default_factory=list)


def importar_regras(
    db: Session,
    regras: list[RegraNormativa],
    *,
    dry_run: bool = False,
    sobrescrever_oficial: bool = False,
) -> ResultadoImport:
    """
    Importa lista de RegraNormativa para tabela_mva.

    - Nunca sobrescreve 'oficial' por padrão.
    - dry_run=True: valida sem gravar.
    """
    resultado = ResultadoImport()

    for r in regras:
        try:
            existente = (
                db.query(TabelaMVA)
                .filter(
                    TabelaMVA.estado == r.estado.upper(),
                    TabelaMVA.ncm == r.ncm,
                    TabelaMVA.vigencia_inicio == r.vigencia_inicio,
                )
                .first()
            )

            if existente:
                if existente.nivel_confianca_fonte == "oficial" and not sobrescrever_oficial:
                    resultado.ignorados += 1
                    continue
                if not dry_run:
                    atualizar_mva(
                        db,
                        r.estado.upper(),
                        r.ncm,
                        r.mva,
                        r.aliquota_interna,
                        fonte_legal=r.fonte_legal,
                        url_fonte=r.url_fonte,
                        nivel_confianca_fonte=r.nivel_confianca,
                        importado_por=r.importado_por,
                        vigencia_inicio=r.vigencia_inicio,
                        vigencia_fim=r.vigencia_fim,
                        commit=False,
                    )
                resultado.atualizados += 1
            else:
                if not dry_run:
                    db.add(
                        TabelaMVA(
                            estado=r.estado.upper(),
                            ncm=r.ncm,
                            mva=r.mva,
                            aliquota_interna=r.aliquota_interna,
                            vigencia_inicio=r.vigencia_inicio,
                            vigencia_fim=r.vigencia_fim,
                            fonte_legal=r.fonte_legal,
                            url_fonte=r.url_fonte,
                            nivel_confianca_fonte=r.nivel_confianca,
                            importado_por=r.importado_por,
                        )
                    )
                resultado.inseridos += 1
        except Exception as exc:
            resultado.erros.append(f"{r.estado}/{r.ncm}: {exc}")
            logger.error("pipeline_normativo erro %s/%s: %s", r.estado, r.ncm, exc)

    if not dry_run and not resultado.erros:
        db.commit()
    elif not dry_run and resultado.erros:
        db.rollback()

    return resultado


def verificar_divergencias(
    db: Session,
    regras: list[RegraNormativa],
) -> list[dict]:
    """
    Compara regras com BD. Retorna divergências com detalhe completo.

    Não modifica BD.
    """
    divergencias = []
    for r in regras:
        existente = (
            db.query(TabelaMVA)
            .filter(TabelaMVA.estado == r.estado.upper(), TabelaMVA.ncm == r.ncm)
            .order_by(TabelaMVA.vigencia_inicio.desc())
            .first()
        )
        if not existente:
            divergencias.append({
                "tipo": "REGRA_AUSENTE",
                "estado": r.estado,
                "ncm": r.ncm,
                "mva_esperado": r.mva,
                "mva_bd": None,
                "nivel_confianca_bd": None,
            })
        elif abs(float(existente.mva) - r.mva) > 0.001:
            divergencias.append({
                "tipo": "MVA_DIVERGENTE",
                "estado": r.estado,
                "ncm": r.ncm,
                "mva_esperado": r.mva,
                "mva_bd": float(existente.mva),
                "nivel_confianca_bd": existente.nivel_confianca_fonte,
                "fonte_bd": existente.fonte_legal,
            })
        elif abs(float(existente.aliquota_interna or 0) - r.aliquota_interna) > 0.001:
            divergencias.append({
                "tipo": "ALIQUOTA_DIVERGENTE",
                "estado": r.estado,
                "ncm": r.ncm,
                "aliquota_esperada": r.aliquota_interna,
                "aliquota_bd": float(existente.aliquota_interna or 0),
                "nivel_confianca_bd": existente.nivel_confianca_fonte,
            })
    return divergencias
