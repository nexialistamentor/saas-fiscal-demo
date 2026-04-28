"""
AG-VALIDACAO — NormativeValidationAgent.

Promove RegraNormativa de 'candidata_oficial' para 'oficial'
após validação cruzada automática.

Critérios de promoção automática:

1. fonte_legal preenchida (≥ 10 chars)
2. url_fonte válida (startswith http)
3. mva > 0 OU pmpf_reais > 0 (pelo menos um valor concreto na tabela respectiva)
4. vigencia_inicio não nula
5. Não existe regra 'oficial' conflituante para (estado, ncm, vigencia_inicio)

Se todos os critérios passam → promove para 'oficial' e regista AG-VALIDACAO em importado_por.

Se algum falha → alerta nível 'alto' no resultado do agente (persistido pelo AgentExecutor).

Promoção é global (tabelas normativas não são por tenant): quando o AgentExecutor corre
por empresa, só executamos em empresa_id == 1 ou quando o contexto não traz empresa_id,
para não duplicar alertas de rejeição.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TabelaMVA, TabelaPMPF

logger = logging.getLogger(__name__)


def _criar_alerta(tipo: str, descricao: str, nivel: str) -> Dict:
    return {"tipo": tipo, "descricao": descricao, "nivel": nivel}


def _validar_regra_mva(reg: TabelaMVA) -> list[str]:
    falhas = []
    if not reg.fonte_legal or len(reg.fonte_legal.strip()) < 10:
        falhas.append("fonte_legal_minima")
    if not reg.url_fonte or not reg.url_fonte.startswith("http"):
        falhas.append("url_fonte_valida")
    if not reg.mva or float(reg.mva) <= 0:
        falhas.append("valor_concreto")
    if not reg.vigencia_inicio:
        falhas.append("vigencia_inicio_presente")
    return falhas


def _validar_regra_pmpf(reg: TabelaPMPF) -> list[str]:
    falhas = []
    if not reg.fonte_legal or len(reg.fonte_legal.strip()) < 10:
        falhas.append("fonte_legal_minima")
    if not reg.url_fonte or not reg.url_fonte.startswith("http"):
        falhas.append("url_fonte_valida")
    if not reg.pmpf_reais or float(reg.pmpf_reais) <= 0:
        falhas.append("valor_concreto")
    if not reg.vigencia_inicio:
        falhas.append("vigencia_inicio_presente")
    return falhas


def _tem_conflito_oficial_mva(db: Session, reg: TabelaMVA) -> bool:
    """Verifica se já existe regra 'oficial' conflituante (mesmo estado/ncm e vigência sobreposta)."""
    ref_ini = reg.vigencia_inicio or date.today()
    return (
        db.query(TabelaMVA)
        .filter(
            TabelaMVA.estado == reg.estado,
            TabelaMVA.ncm == reg.ncm,
            TabelaMVA.nivel_confianca_fonte == "oficial",
            TabelaMVA.id != reg.id,
            or_(
                TabelaMVA.vigencia_fim.is_(None),
                TabelaMVA.vigencia_fim >= ref_ini,
            ),
        )
        .first()
        is not None
    )


def _tem_conflito_oficial_pmpf(db: Session, reg: TabelaPMPF) -> bool:
    return (
        db.query(TabelaPMPF)
        .filter(
            TabelaPMPF.estado == reg.estado,
            TabelaPMPF.ncm == reg.ncm,
            TabelaPMPF.marca == reg.marca,
            TabelaPMPF.nivel_confianca_fonte == "oficial",
            TabelaPMPF.id != reg.id,
        )
        .first()
        is not None
    )


class NormativeValidationAgent:
    """
    Valida e promove regras 'candidata_oficial' para 'oficial'.
    Executado pelo AgentScheduler após cada ciclo de parsers.
    """

    name = "normative_validation_agent"
    permissions = ["read_tabela_mva", "read_tabela_pmpf", "write_nivel_confianca"]

    async def run(self, context: Dict) -> Dict:
        empresa_id = context.get("empresa_id")
        if empresa_id is not None and empresa_id != 1:
            logger.debug("AG-VALIDACAO: skip para empresa_id=%s", empresa_id)
            return {
                "agent": self.name,
                "total_alertas": 0,
                "alertas": [],
                "status": "pulado_multi_empresa",
                "promovidas_mva": 0,
                "promovidas_pmpf": 0,
                "rejeitadas": 0,
            }

        alertas: List[Dict] = []
        promovidas_mva = 0
        promovidas_pmpf = 0
        rejeitadas = 0

        db: Session = SessionLocal()
        try:
            candidatas_mva = (
                db.query(TabelaMVA)
                .filter(TabelaMVA.nivel_confianca_fonte == "candidata_oficial")
                .all()
            )

            for reg in candidatas_mva:
                falhas = _validar_regra_mva(reg)
                conflito = _tem_conflito_oficial_mva(db, reg)
                if not falhas and not conflito:
                    reg.nivel_confianca_fonte = "oficial"
                    _suffix = f"AG-VALIDACAO {datetime.utcnow().strftime('%Y-%m-%d')}"
                    reg.importado_por = (
                        f"{reg.importado_por} | {_suffix}" if reg.importado_por else _suffix
                    )
                    promovidas_mva += 1
                else:
                    if conflito:
                        falhas.append("sem_conflito_oficial")
                    alertas.append(
                        _criar_alerta(
                            "CANDIDATA_REJEITADA_MVA",
                            f"Regra MVA {reg.estado}/{reg.ncm} não promovida: "
                            f"{', '.join(falhas)}",
                            "alto",
                        )
                    )
                    rejeitadas += 1

            candidatas_pmpf = (
                db.query(TabelaPMPF)
                .filter(TabelaPMPF.nivel_confianca_fonte == "candidata_oficial")
                .all()
            )

            for reg in candidatas_pmpf:
                falhas = _validar_regra_pmpf(reg)
                conflito = _tem_conflito_oficial_pmpf(db, reg)
                if not falhas and not conflito:
                    reg.nivel_confianca_fonte = "oficial"
                    _suffix = f"AG-VALIDACAO {datetime.utcnow().strftime('%Y-%m-%d')}"
                    reg.importado_por = (
                        f"{reg.importado_por} | {_suffix}" if reg.importado_por else _suffix
                    )
                    promovidas_pmpf += 1
                else:
                    if conflito:
                        falhas.append("sem_conflito_oficial")
                    alertas.append(
                        _criar_alerta(
                            "CANDIDATA_REJEITADA_PMPF",
                            f"Regra PMPF {reg.estado}/{reg.ncm}/{getattr(reg, 'marca', '?')} "
                            f"não promovida: {', '.join(falhas)}",
                            "alto",
                        )
                    )
                    rejeitadas += 1

            db.commit()
            logger.info(
                "AG-VALIDACAO: MVA promovidas=%d, PMPF promovidas=%d, rejeitadas=%d",
                promovidas_mva,
                promovidas_pmpf,
                rejeitadas,
            )

        except Exception as exc:
            db.rollback()
            alertas.append(
                _criar_alerta(
                    "AG_VALIDACAO_ERRO",
                    f"Erro crítico no AG-VALIDACAO: {exc}",
                    "critico",
                )
            )
            logger.exception("AG-VALIDACAO falhou: %s", exc)
        finally:
            db.close()

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "promovidas_mva": promovidas_mva,
            "promovidas_pmpf": promovidas_pmpf,
            "rejeitadas": rejeitadas,
        }


normative_validation_agent = NormativeValidationAgent()
