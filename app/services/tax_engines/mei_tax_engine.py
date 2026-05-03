from datetime import datetime

from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.mei_constants import (
    MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE,
    MEI_LIMITE_ANUAL_FATURAMENTO,
    calcular_das_mei,
    normalizar_atividade_mei,
    obter_salario_minimo,
)


class MEITaxEngine(BaseTaxEngine):
    """
    Engine MEI extraída do legado (imposto_service).

    Regras:
    - DAS: 5% do salário mínimo + parcela fixa (ICMS comércio/indústria ou ISS serviços)
    - Limite anual: R$ 81.000
    """

    name = "mei_tax"

    def execute(self, context: dict):
        faturamento_mensal = float(context.get("faturamento", 0))
        faturamento_anual = faturamento_mensal * 12
        atividade = context.get("atividade") or context.get(
            "atividade_mei", "comercio"
        )

        ano_atual = datetime.now().year
        sal_min = obter_salario_minimo(ano_atual)
        imposto = calcular_das_mei(sal_min, atividade)

        alertas = []

        # Limite legal é anual — comparar sempre com projeção anual (12 × mensal).
        if faturamento_anual >= MEI_LIMITE_ANUAL_FATURAMENTO:
            alertas.append("faturamento excedeu o limite anual do MEI")
        elif faturamento_anual >= MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE:
            alertas.append("faturamento próximo do limite anual")

        return {
            "regime": "mei",
            "tributos": {
                "das": imposto
            },
            "bases_calculo": {
                "faturamento_mensal": faturamento_mensal,
                "faturamento_anual": faturamento_anual,
                "atividade": normalizar_atividade_mei(atividade),
            },
            "alertas": alertas
        }
