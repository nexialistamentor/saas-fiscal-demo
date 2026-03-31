from app.services.imposto_service import calcular_imposto_simples


class CPFEngine:
    def execute(self, context: dict):
        faturamento = context.get("faturamento", 0)
        despesas = context.get("custos", 0)  # reaproveitar custos como despesas

        resultado = calcular_imposto_simples(
            faturamento,
            despesas,
            tipo="cpf"
        )

        return {
            "regime": "cpf",
            "imposto_mensal": resultado.get("imposto"),
            "base_calculo": resultado.get("base_calculo"),
            "alertas": resultado.get("alertas"),
            "aliquota_info": resultado.get("aliquota_info")
        }
