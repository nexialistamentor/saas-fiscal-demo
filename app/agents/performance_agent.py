from datetime import datetime


class PerformanceAgent:
    """
    Monitora métricas de execução do sistema.
    """

    name = "performance_agent"

    permissions = [
        "monitor_performance"
    ]

    async def run(self, context):

        alertas = []

        insights = context.get("insights", [])

        # exemplo simples: detectar volume anormal
        if len(insights) > 1000:

            alertas.append({
                "tipo": "VOLUME_INSIGHTS_ANORMAL",
                "descricao": "Volume de insights muito elevado",
                "nivel": "medio"
            })

        resultado = {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "executado_em": datetime.utcnow().isoformat()
        }

        return resultado


performance_agent = PerformanceAgent()
