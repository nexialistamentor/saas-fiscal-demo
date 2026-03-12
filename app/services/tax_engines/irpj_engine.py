from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class IRPJEngine(BaseTaxEngine):
    """
    Engine para cálculo de IRPJ.
    """

    name = "irpj"

    def execute(self, context: dict):
        """
        Executa cálculo de IRPJ.
        """
        base_calculo = context.get("base_calculo", 0.0)

        irpj = base_calculo * 0.15
        adicional_irpj = 0
        if base_calculo > 20000:
            adicional_irpj = (base_calculo - 20000) * 0.10

        total_irpj = irpj + adicional_irpj

        return {
            "tributo": "IRPJ",
            "base_calculo": base_calculo,
            "irpj": irpj,
            "adicional_irpj": adicional_irpj,
            "total_irpj": total_irpj,
            "alertas": [
                "Cálculo estimado baseado na base informada.",
                "Apuração oficial depende da escrituração contábil."
            ]
        }
