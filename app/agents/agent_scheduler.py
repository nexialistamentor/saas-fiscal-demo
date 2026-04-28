import asyncio
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.agents.agent_executor import AgentExecutor
from app.agents.normative_validation_agent import normative_validation_agent
from app.database import SessionLocal
from app.models import Empresa
from app.services.analysis_orchestrator import analysis_cache
from app.services.engine_recovery_service import verificar_recuperacao_engines
from app.services.insights_engine import InsightEngine
from app.services.metrics_alert_service import (
    verificar_alertas_metricas,
    verificar_regressao_performance,
)
from app.services.metrics_persistence_service import salvar_snapshot_metricas
from app.services.tabela_normativa_service import listar_base_normativa

logger = logging.getLogger(__name__)


def _listar_empresa_ids(db: Session) -> list[int]:
    rows = db.query(Empresa.id).order_by(Empresa.id.asc()).all()
    return [r[0] for r in rows]


class AgentScheduler:
    """
    Responsável por executar agentes de forma periódica.
    Suporta ciclo por empresa ou ciclo multi-tenant (todas as empresas).
    """

    def __init__(self):
        self.executor = AgentExecutor()

    async def _executar_agents_uma_empresa(self, empresa_id: int) -> None:
        """Insights + agentes para uma empresa (sessão própria)."""
        db = SessionLocal()
        try:
            engine = InsightEngine(db)
            insights = engine.gerar_insights_empresa(empresa_id)
            context = {
                "empresa_id": empresa_id,
                "insights": insights.get("oportunidades", []),
                "tabela_normativa": listar_base_normativa(db),
            }
            await self.executor.run_all(context)
            logger.info(
                "Ciclo agentes empresa_id=%s — %s",
                empresa_id,
                datetime.utcnow().isoformat(),
            )
        finally:
            db.close()

    async def _finalizar_ciclo_metricas_e_cache(self) -> None:
        """Persistência de métricas, alertas e limpeza de cache (escopo global)."""
        db = SessionLocal()
        try:
            salvar_snapshot_metricas(db)
            verificar_alertas_metricas()
            verificar_regressao_performance(db)
            verificar_recuperacao_engines()
            try:
                resultado_validacao = await normative_validation_agent.run({})
                logger.info(
                    "AG-VALIDACAO: promovidas_mva=%d promovidas_pmpf=%d rejeitadas=%d",
                    resultado_validacao.get("promovidas_mva", 0),
                    resultado_validacao.get("promovidas_pmpf", 0),
                    resultado_validacao.get("rejeitadas", 0),
                )
            except Exception as exc:
                logger.error("AG-VALIDACAO falhou no ciclo global: %s", exc)
        finally:
            db.close()
        analysis_cache.clear()

    async def executar_ciclo(self, empresa_id: int = 1) -> None:
        await self._executar_agents_uma_empresa(empresa_id)
        await self._finalizar_ciclo_metricas_e_cache()

    async def executar_ciclo_multi_tenant(self) -> None:
        db = SessionLocal()
        try:
            empresa_ids = _listar_empresa_ids(db)
        finally:
            db.close()

        if not empresa_ids:
            logger.info("Scheduler: nenhuma empresa cadastrada — ciclo ignorado.")
            return

        for eid in empresa_ids:
            await self._executar_agents_uma_empresa(eid)

        await self._finalizar_ciclo_metricas_e_cache()

    async def iniciar_loop(
        self,
        empresa_id: int | None = None,
        intervalo_segundos: int = 60,
    ) -> None:
        """
        Executa ciclos do scheduler continuamente em intervalos definidos.
        Usado apenas para testes fora da API.

        Se ``empresa_id`` for informado, executa só essa empresa por iteração.
        Caso contrário, executa todas as empresas (multi-tenant).
        """
        logger.info("Scheduler iniciado...")
        while True:
            try:
                if empresa_id is not None:
                    await self.executar_ciclo(empresa_id)
                else:
                    await self.executar_ciclo_multi_tenant()
            except Exception as e:
                logger.error("Erro no scheduler: %s", str(e))
            await asyncio.sleep(intervalo_segundos)
