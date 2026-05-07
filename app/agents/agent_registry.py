from typing import Dict

from app.agents.auditor_fiscal_agent import auditor_fiscal_agent
from app.agents.consistency_audit_agent import consistency_audit_agent
from app.agents.data_sanitization_agent import data_sanitization_agent
from app.agents.memorial_validator_agent import memorial_validator_agent
from app.agents.normative_watchdog_agent import normative_watchdog_agent
from app.agents.performance_agent import performance_agent
from app.agents.repair_agent import repair_agent
from app.agents.security_audit_agent import security_audit_agent
from app.agents.state_recovery_agent import state_recovery_agent
from app.agents.ag_abertura_agent import ag_abertura_agent
from app.agents.ag_encerramento_agent import ag_encerramento_agent


class AgentRegistry:
    """
    Registro central de agentes do sistema.
    """

    def __init__(self):
        self._agents: Dict[str, object] = {}

        # registro de agentes disponiveis
        self.register(data_sanitization_agent)
        self.register(auditor_fiscal_agent)
        self.register(repair_agent)
        self.register(performance_agent)
        self.register(normative_watchdog_agent)
        self.register(consistency_audit_agent)
        self.register(memorial_validator_agent)
        self.register(security_audit_agent)
        self.register(state_recovery_agent)
        self.register(ag_abertura_agent)
        self.register(ag_encerramento_agent)

    def register(self, agent):
        self._agents[agent.name] = agent

    def get_agents(self):
        return self._agents

    def get_agent(self, name: str):
        return self._agents.get(name)
