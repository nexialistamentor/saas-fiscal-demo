from datetime import datetime

from app.agents.agent_registry import AgentRegistry


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

                result["executado_em"] = datetime.utcnow().isoformat()
                resultados.append(result)
            except Exception as e:
                resultados.append({
                    "agent": agent.name,
                    "status": "erro",
                    "erro": str(e)
                })
        return resultados
