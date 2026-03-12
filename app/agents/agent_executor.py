from datetime import datetime

from app.agents.agent_registry import AgentRegistry
from app.database import SessionLocal
from app.models import AlertaFiscal


class AgentExecutor:
    """
    Responsável por executar agentes registrados.
    """

    def __init__(self):
        self.registry = AgentRegistry()

    async def run_all(self, context):
        resultados = []
        for agent in self.registry.get_agents().values():
            try:
                result = await agent.run(context)

                # salvar alertas no banco
                db = SessionLocal()
                try:
                    for alerta in result.get("alertas", []):
                        registro = AlertaFiscal(
                            agente=result.get("agent", agent.name),
                            tipo=alerta["tipo"],
                            descricao=alerta["descricao"],
                            nivel=alerta["nivel"],
                            empresa_id=context.get("empresa_id", 1),
                            relatorio_analise_id=context.get("relatorio_analise_id"),
                        )
                        db.add(registro)
                    db.commit()
                finally:
                    db.close()

                result["executado_em"] = datetime.utcnow().isoformat()
                resultados.append(result)
            except Exception as e:
                resultados.append({
                    "agent": agent.name,
                    "status": "erro",
                    "erro": str(e)
                })
        return resultados
