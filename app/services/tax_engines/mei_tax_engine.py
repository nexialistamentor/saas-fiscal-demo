from datetime import datetime

from app.services.imposto_service import _obter_salario_minimo
from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class MEITaxEngine(BaseTaxEngine):
    """
    Engine MEI extraída do legado (imposto_service).

    Regras:
    - DAS: 5% do salário mínimo + R$ 1 (ICMS)
    - Limite anual: R$ 81.000
    """

    name = "mei_tax"

    def execute(self, context: dict):
        faturamento_mensal = float(context.get("faturamento", 0))
        faturamento_anual = faturamento_mensal * 12

        ano_atual = datetime.now().year
        sal_min = _obter_salario_minimo(ano_atual)
        imposto = round(sal_min * 0.05 + 1.00, 2)

        alertas = []

        if faturamento_anual >= 81_000:
            alertas.append("faturamento excedeu o limite anual do MEI")
        elif faturamento_anual >= 75_000:
            alertas.append("faturamento próximo do limite anual")

        return {
            "regime": "mei",
            "tributos": {
                "das": imposto
            },
            "bases_calculo": {
                "faturamento_mensal": faturamento_mensal,
                "faturamento_anual": faturamento_anual
            },
            "alertas": alertas
        }
