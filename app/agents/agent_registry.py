from typing import Dict

from app.agents.auditor_fiscal_agent import auditor_fiscal_agent
from app.agents.normative_agent import normative_agent
from app.agents.performance_agent import performance_agent
from app.agents.repair_agent import repair_agent


class AgentRegistry:
    """
    Registro central de agentes do sistema.
    """

    def __init__(self):
        self._agents: Dict[str, object] = {}

        # registro de agentes disponíveis
        self.register(auditor_fiscal_agent)
        self.register(repair_agent)
        self.register(performance_agent)
        self.register(normative_agent)

    def register(self, agent):
        self._agents[agent.name] = agent

    def get_agents(self):
        return self._agents

    def get_agent(self, name: str):
        return self._agents.get(name)
