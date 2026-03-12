from datetime import datetime


class RepairAgent:
    """
    Agente responsável por detectar e registrar falhas estruturais do sistema.
    """

    name = "repair_agent"

    permissions = [
        "monitor_system",
        "log_repair"
    ]

    async def run(self, context):

        alertas = []

        # exemplo simples de verificação estrutural
        if "insights" not in context:

            alertas.append({
                "tipo": "ERRO_CONTEXTO",
                "descricao": "Contexto de insights ausente no ciclo do scheduler",
                "nivel": "critico"
            })

        resultado = {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "executado_em": datetime.utcnow().isoformat()
        }

        return resultado


# instância padrão
repair_agent = RepairAgent()
