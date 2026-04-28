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

from app.models import TabelaMVA, TabelaPMPF
from app.services.atualizacao_normativa_service import atualizar_mva

logger = logging.getLogger(__name__)

NivelConfianca = Literal[
    "oficial",
    "candidata_oficial",
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
    # Campos opcionais — preenchidos por parsers PMPF (MG e similares)
    observacao: str | None = None
    pmpf_reais: float | None = None
    marca_produto: str | None = None
    embalagem_ml: int | None = None


@dataclass
class ResultadoImport:
    inseridos: int = 0
    atualizados: int = 0
    ignorados: int = 0
    erros: list[str] = field(default_factory=list)


def _validar_regra(r: RegraNormativa) -> list[str]:
    """Retorna lista de erros. Vazio = válido."""
    erros: list[str] = []
    if not r.fonte_legal or len(r.fonte_legal.strip()) < 10:
        erros.append(f"{r.estado}/{r.ncm}: fonte_legal ausente ou insuficiente")
    if not r.url_fonte or not r.url_fonte.startswith("http"):
        erros.append(f"{r.estado}/{r.ncm}: url_fonte ausente ou inválida")
    if r.mva <= 0:
        erros.append(f"{r.estado}/{r.ncm}: mva inválido ({r.mva})")
    if not (0 < r.aliquota_interna < 1):
        erros.append(f"{r.estado}/{r.ncm}: aliquota_interna fora do intervalo (0,1)")
    return erros


def _validar_regra_pmpf(r: RegraNormativa) -> list[str]:
    """Validação para persistência em `tabela_pmpf` (MVA ignorado)."""
    erros: list[str] = []
    if not r.ncm or len(r.ncm.strip()) < 4:
        erros.append(f"{r.estado}: ncm ausente ou inválido para PMPF")
    if not r.fonte_legal or len(r.fonte_legal.strip()) < 10:
        erros.append(f"{r.estado}/{r.ncm}: fonte_legal ausente ou insuficiente")
    if not r.url_fonte or not r.url_fonte.startswith("http"):
        erros.append(f"{r.estado}/{r.ncm}: url_fonte ausente ou inválida")
    if r.pmpf_reais is None or r.pmpf_reais <= 0:
        erros.append(f"{r.estado}/{r.ncm}: pmpf_reais ausente ou inválido")
    if not (0 < r.aliquota_interna < 1):
        erros.append(f"{r.estado}/{r.ncm}: aliquota_interna fora do intervalo (0,1)")
    marca = (r.marca_produto or "").strip()
    if not marca:
        erros.append(f"{r.estado}/{r.ncm}: marca_produto obrigatória para PMPF")
    return erros


def importar_regras_pmpf(
    db: Session,
    regras: list[RegraNormativa],
    *,
    dry_run: bool = False,
    sobrescrever_oficial: bool = False,
) -> ResultadoImport:
    """
    Importa regras com `pmpf_reais` preenchido para `tabela_pmpf`.

    - Ignora `mva` (pode ser 0.0).
    - `embalagem_ml` 0 ou None → NULL na BD.
    """
    resultado = ResultadoImport()

    for r in regras:
        if r.pmpf_reais is None:
            resultado.ignorados += 1
            continue
        try:
            erros_validacao = _validar_regra_pmpf(r)
            if erros_validacao:
                resultado.erros.extend(erros_validacao)
                resultado.ignorados += 1
                continue

            emb_db = r.embalagem_ml if r.embalagem_ml and r.embalagem_ml > 0 else None

            q = (
                db.query(TabelaPMPF)
                .filter(
                    TabelaPMPF.estado == r.estado.upper(),
                    TabelaPMPF.ncm == r.ncm,
                    TabelaPMPF.marca == (r.marca_produto or "").strip(),
                    TabelaPMPF.vigencia_inicio == r.vigencia_inicio,
                )
            )
            if emb_db is None:
                q = q.filter(TabelaPMPF.embalagem_ml.is_(None))
            else:
                q = q.filter(TabelaPMPF.embalagem_ml == emb_db)
            existente = q.first()

            if existente:
                if existente.nivel_confianca_fonte == "oficial" and not sobrescrever_oficial:
                    resultado.ignorados += 1
                    continue
                if not dry_run:
                    existente.pmpf_reais = float(r.pmpf_reais or 0)
                    existente.aliquota_interna = r.aliquota_interna
                    existente.fonte_legal = r.fonte_legal
                    existente.url_fonte = r.url_fonte
                    existente.nivel_confianca_fonte = r.nivel_confianca
                    existente.importado_por = r.importado_por
                    existente.vigencia_fim = r.vigencia_fim
                resultado.atualizados += 1
            else:
                if not dry_run:
                    db.add(
                        TabelaPMPF(
                            estado=r.estado.upper(),
                            ncm=r.ncm,
                            marca=(r.marca_produto or "").strip(),
                            embalagem_ml=emb_db,
                            pmpf_reais=float(r.pmpf_reais or 0),
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
            logger.error("importar_regras_pmpf erro %s/%s: %s", r.estado, r.ncm, exc)

    if not dry_run and not resultado.erros:
        db.commit()
    elif not dry_run and resultado.erros:
        db.rollback()

    return resultado


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
    - Regras inválidas (sem fonte_legal/url, mva<=0, alíquota fora de (0,1))
      vão para resultado.erros e não são persistidas.
    """
    resultado = ResultadoImport()

    for r in regras:
        try:
            erros_validacao = _validar_regra(r)
            if erros_validacao:
                resultado.erros.extend(erros_validacao)
                resultado.ignorados += 1
                continue

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
