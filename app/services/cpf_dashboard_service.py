from app.services.analysis_orchestrator import executar_analise


class CPFDashboardService:
    def __init__(self):
        pass

    def calcular_resumo(self, faturamento_mensal: float, despesas: float):
        resultado = executar_analise(
            "cpf_tax",
            {
                "faturamento": faturamento_mensal,
                "despesas": despesas
            }
        )

        if resultado.get("erro"):
            return {
                "tipo": "cpf",
                "erro": resultado.get("mensagem"),
                "alertas": []
            }

        imposto_mensal = resultado.get("tributos", {}).get("imposto", 0)

        return {
            "tipo": "cpf",
            "imposto_mensal": imposto_mensal,
            "imposto_anual": imposto_mensal * 12,
            "alertas": resultado.get("alertas", []),
        }
