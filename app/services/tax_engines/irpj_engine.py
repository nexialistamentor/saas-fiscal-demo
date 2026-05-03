from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.irpj_adicional import calcular_adicional_irpj_presumido


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
        adicional_irpj = calcular_adicional_irpj_presumido(base_calculo, context)

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
