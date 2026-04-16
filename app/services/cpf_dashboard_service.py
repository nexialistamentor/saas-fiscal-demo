from app.services.imposto_service import calcular_imposto_simples


class CPFDashboardService:
    def __init__(self):
        pass

    def calcular_resumo(self, faturamento_mensal: float, despesas: float):
        resultado = calcular_imposto_simples(
            faturamento=faturamento_mensal,
            despesas=despesas,
            tipo="CPF"
        )

        imposto_mensal = resultado.get("imposto", 0)

        return {
            "tipo": "cpf",
            "imposto_mensal": imposto_mensal,
            "imposto_anual": imposto_mensal * 12,
            "alertas": resultado.get("alertas", []),
        }
