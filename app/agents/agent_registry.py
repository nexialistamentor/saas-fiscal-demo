from collections.abc import Awaitable, Callable
from typing import Dict

from app.agents.adapters.ag_abertura import execute_ag_abertura_mission
from app.agents.adapters.agent_erro_operacional import (
    execute_agent_erro_operacional_mission,
)
from app.agents.adapters.agent_erro_operacional_llm_fallback import (
    execute_agent_erro_operacional_llm_fallback_mission,
)
from app.agents.adapters.consistency_audit import (
    execute_consistency_audit_mission,
)
from app.agents.adapters.data_sanitization import (
    execute_data_sanitization_mission,
)
from app.agents.adapters.memorial_validator import (
    execute_memorial_validator_mission,
)
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission

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

        self._l3_adapters: dict[
            str,
            dict[str, Callable[[AgentMission], Awaitable[AgentExecutionResult]]],
        ] = {
            "data_sanitization_agent": {
                "sanitizar_contexto_fiscal": execute_data_sanitization_mission,
            },
            "consistency_audit_agent": {
                "auditar_consistencia_fiscal": execute_consistency_audit_mission,
            },
            "memorial_validator_agent": {
                "validar_memorial_fiscal": execute_memorial_validator_mission,
            },
            "ag_abertura": {
                "orientar_abertura_empresa": execute_ag_abertura_mission,
            },
            "agent_erro_operacional": {
                "diagnosticar_evento_operacional": (
                    execute_agent_erro_operacional_mission
                ),
                "diagnosticar_evento_operacional_llm_fallback": (
                    execute_agent_erro_operacional_llm_fallback_mission
                ),
            },
        }
        self._l3_classifications = {
            "data_sanitization_agent": "ADVISORY",
            "consistency_audit_agent": "READ_ONLY",
            "memorial_validator_agent": "READ_ONLY",
            "ag_abertura": "ADVISORY",
            "agent_erro_operacional": "READ_ONLY",
        }

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

    def resolve_l3_adapter(
        self,
        target_agent: str,
        mission_type: str,
    ) -> Callable[[AgentMission], Awaitable[AgentExecutionResult]]:
        """Resolve apenas adapters L3 explicitamente allowlisted."""
        adapters = self._l3_adapters.get(target_agent)
        if adapters is None:
            raise LookupError("L3_TARGET_NOT_ALLOWLISTED")

        classification = self._l3_classifications.get(target_agent)
        if classification not in {"READ_ONLY", "ADVISORY"}:
            raise PermissionError("L3_AGENT_CLASSIFICATION_NOT_ALLOWED")

        adapter = adapters.get(mission_type)
        if adapter is None:
            raise LookupError("L3_MISSION_TYPE_NOT_ALLOWLISTED")
        return adapter
