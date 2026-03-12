import asyncio
from datetime import datetime

from app.agents.agent_executor import AgentExecutor
from app.services.analysis_orchestrator import analysis_cache
from app.database import SessionLocal
from app.services.insights_engine import InsightEngine
from app.services.tabela_normativa_service import listar_base_normativa
from app.services.metrics_persistence_service import salvar_snapshot_metricas
from app.services.metrics_alert_service import verificar_alertas_metricas, verificar_regressao_performance
from app.services.engine_recovery_service import verificar_recuperacao_engines


class AgentScheduler:
    """
    Responsável por executar agentes de forma periódica.
    """

    def __init__(self):

        self.executor = AgentExecutor()

    async def executar_ciclo(self, empresa_id: int = 1):
        db = SessionLocal()

        try:

            engine = InsightEngine(db)

            insights = engine.gerar_insights_empresa(empresa_id)

            context = {
                "empresa_id": empresa_id,
                "insights": insights.get("oportunidades", []),
                "tabela_normativa": listar_base_normativa(db)
            }

            resultados = await self.executor.run_all(context)

            print("Ciclo executado:", datetime.utcnow().isoformat())
            print(resultados)

            salvar_snapshot_metricas(db)
            verificar_alertas_metricas()
            verificar_regressao_performance(db)
            verificar_recuperacao_engines()

        finally:

            db.close()
            # limpeza do cache no final do ciclo (evita limpar durante execução ativa)
            analysis_cache.clear()

    async def iniciar_loop(self, empresa_id: int = 1, intervalo_segundos: int = 60):
        """
        Executa ciclos do scheduler continuamente em intervalos definidos.
        Usado apenas para testes fora da API.
        """
        print("Scheduler iniciado...")
        while True:
            try:
                await self.executar_ciclo(empresa_id)
            except Exception as e:
                print("Erro no scheduler:", str(e))
            await asyncio.sleep(intervalo_segundos)
