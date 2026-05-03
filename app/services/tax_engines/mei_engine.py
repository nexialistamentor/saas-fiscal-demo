# DEPRECATED: motor legado; usar MEITaxEngine em mei_tax_engine.py.

class MEIEngine:
    def execute(self, context: dict):
        faturamento = context.get("faturamento", 0)

        # Limite anual MEI
        limite_anual = 81000
        faturamento_anual_estimado = faturamento * 12

        alertas = []

        if faturamento_anual_estimado > limite_anual:
            alertas.append("Desenquadramento do MEI por excesso de faturamento")

        # DAS simplificado (comércio)
        salario_minimo = 1412  # ajustar futuramente por ano
        das = salario_minimo * 0.05 + 1  # INSS + ICMS fixo

        return {
            "regime": "mei",
            "das_mensal": round(das, 2),
            "faturamento_mensal": faturamento,
            "faturamento_anual_estimado": faturamento_anual_estimado,
            "alertas": alertas
        }
