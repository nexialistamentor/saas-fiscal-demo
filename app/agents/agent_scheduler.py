import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agents.adapters.patrol import execute_patrol_mission
from app.agents.mission_factory import create_agent_mission
from app.database import SessionLocal
from app.models import Empresa
from app.services.analysis_orchestrator import analysis_cache
from app.services.insights_engine import InsightEngine
from app.services.metrics_alert_service import (
    verificar_alertas_metricas,
    verificar_regressao_performance,
)
from app.services.metrics_persistence_service import salvar_snapshot_metricas

logger = logging.getLogger(__name__)


def _listar_empresa_ids(db: Session) -> list[int]:
    rows = db.query(Empresa.id).order_by(Empresa.id.asc()).all()
    return [r[0] for r in rows]


class AgentScheduler:
    """
    Responsável por executar agentes de forma periódica.
    Suporta ciclo por empresa ou ciclo multi-tenant (todas as empresas).
    """

    async def _executar_agents_uma_empresa(
        self,
        empresa_id: int,
    ) -> None:
        db = SessionLocal()
        try:
            engine = InsightEngine(db)
            engine.gerar_insights_empresa(empresa_id)

            logger.info(
                "Ciclo tenant empresa_id=%s concluido - %s",
                empresa_id,
                datetime.utcnow().isoformat(),
            )
        finally:
            db.close()

    async def _finalizar_ciclo_metricas_e_cache(
        self,
    ) -> None:
        db = SessionLocal()
        try:
            salvar_snapshot_metricas(db)
            verificar_alertas_metricas()
            verificar_regressao_performance(db)

            db_watchdog = SessionLocal()
            try:
                from app.models import TabelaMVA

                regras = db_watchdog.query(TabelaMVA).all()
                tabela = [
                    {
                        "estado": r.estado,
                        "ncm": r.ncm,
                        "vigencia_fim": (
                            r.vigencia_fim.isoformat()
                            if r.vigencia_fim
                            else None
                        ),
                        "fonte_legal": r.fonte_legal,
                        "nivel_confianca_fonte": (
                            r.nivel_confianca_fonte
                        ),
                    }
                    for r in regras
                ]
            finally:
                db_watchdog.close()

            try:
                schedule_slot = (
                    datetime.now(timezone.utc)
                    .replace(second=0, microsecond=0)
                    .isoformat()
                )

                mission = create_agent_mission(
                    mission_type="patrulhar_base_normativa",
                    target_agent="normative_watchdog",
                    context={
                        "tabela_normativa": tabela,
                    },
                    context_schema="normative_watchdog.context",
                    output_schema="normative_watchdog.result",
                    scope="global",
                    requested_by="scheduler",
                    authority_level="leitura",
                    execution_mode="activo",
                    schedule_slot=schedule_slot,
                )

                await execute_patrol_mission(mission)

                logger.info(
                    "AG-WATCHDOG: missao global concluida"
                )
            except Exception:
                logger.error(
                    "AG-WATCHDOG falhou no ciclo global"
                )
        finally:
            db.close()

        analysis_cache.clear()

    async def executar_ciclo(self, empresa_id: int) -> None:
        await self._executar_agents_uma_empresa(empresa_id)
        await self._finalizar_ciclo_metricas_e_cache()

    async def executar_ciclo_multi_tenant(self) -> None:
        db = SessionLocal()
        try:
            empresa_ids = _listar_empresa_ids(db)
        finally:
            db.close()

        if not empresa_ids:
            logger.info(
                "Scheduler: nenhuma empresa cadastrada; "
                "executando apenas patrulha global."
            )
            await self._finalizar_ciclo_metricas_e_cache()
            return

        for eid in empresa_ids:
            try:
                await self._executar_agents_uma_empresa(eid)
            except Exception:
                logger.error(
                    "Scheduler: falha isolada no tenant "
                    "empresa_id=%s",
                    eid,
                )

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
