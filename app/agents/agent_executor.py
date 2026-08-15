from datetime import datetime

from app.agents.agent_registry import AgentRegistry
from app.agents.contracts.execution_result import AgentExecutionResult
from app.agents.contracts.mission import AgentMission
from app.agents.contracts.validation import validate_result_against_mission


class AgentExecutor:
    """
    Responsável por executar agentes registrados.
    """

    def __init__(self):
        self.registry = AgentRegistry()

    async def execute_mission(
        self,
        mission: AgentMission,
    ) -> AgentExecutionResult:
        """Executa exclusivamente uma missão L3 allowlisted e read-only."""
        if not isinstance(mission, AgentMission):
            raise TypeError("L3_MISSION_INVALID")
        try:
            mission = AgentMission.model_validate(
                mission.model_dump(mode="python")
            )
        except Exception as exc:
            raise ValueError("L3_MISSION_INVALID") from exc

        if mission.target_agent in {
            "normative_watchdog",
            "patrol",
            "repair",
            "repair_agent",
            "state_recovery",
            "state_recovery_agent",
        }:
            raise PermissionError("L3_TARGET_EXCLUDED")

        if mission.authority_level != "leitura":
            raise PermissionError("L3_AUTHORITY_NOT_READ_ONLY")

        adapter = self.registry.resolve_l3_adapter(
            mission.target_agent,
            mission.mission_type,
        )
        result = await adapter(mission)

        if not isinstance(result, AgentExecutionResult):
            raise TypeError("L3_RESULT_INVALID")

        try:
            validate_result_against_mission(mission, result)
        except (TypeError, ValueError) as exc:
            raise ValueError("L3_RESULT_MISSION_MISMATCH") from exc

        return result

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
