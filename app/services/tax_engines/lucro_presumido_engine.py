from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.csll_engine import CSLLEngine
from app.services.tax_engines.pis_cofins_engine import calcular_pis_cofins
from app.services.tax_engines.response_formatter import formatar_resposta_tributaria


class LucroPresumidoEngine(BaseTaxEngine):
    """
    Engine de cálculo para regime de Lucro Presumido.
    """

    name = "lucro_presumido"

    def execute(self, context: dict):
        faturamento = context.get("faturamento", 0)
        atividade = context.get("atividade", "comercio")

        percentuais = {
            "comercio": 0.08,
            "industria": 0.08,
            "servico": 0.32
        }

        base_irpj = faturamento * percentuais.get(atividade, 0.08)
        irpj = base_irpj * 0.15

        base_csll = faturamento * 0.12
        csll = base_csll * 0.09

        return {
            "regime": "lucro_presumido",
            "base_irpj": base_irpj,
            "irpj": irpj,
            "base_csll": base_csll,
            "csll": csll
        }


def calcular_lucro_presumido(dados_fiscais: dict):
    faturamento = dados_fiscais.get("faturamento", 0)
    atividade = dados_fiscais.get("atividade", "comercio")

    percentuais_presuncao = {
        "comercio": 0.08,
        "industria": 0.08,
        "servicos": 0.32
    }

    percentual = percentuais_presuncao.get(atividade, 0.08)

    base_calculo_irpj = faturamento * percentual

    irpj = base_calculo_irpj * 0.15

    adicional_irpj = 0
    if base_calculo_irpj > 20000:
        adicional_irpj = (base_calculo_irpj - 20000) * 0.10

    total_irpj = irpj + adicional_irpj

    percentuais_csll = {"comercio": 0.12, "industria": 0.12, "servicos": 0.32}
    base_calculo_csll = faturamento * percentuais_csll.get(atividade, 0.12)
    resultado_csll = CSLLEngine().execute({"lucro": base_calculo_csll})
    resultado_pis_cofins = calcular_pis_cofins(dados_fiscais, regime="presumido")

    tributos = {
        "irpj": total_irpj,
        "csll": resultado_csll["valor"],
        "pis": resultado_pis_cofins["tributos"]["pis"],
        "cofins": resultado_pis_cofins["tributos"]["cofins"]
    }

    bases_calculo = {
        "base_irpj": base_calculo_irpj,
        "base_csll": base_calculo_csll,
        "faturamento": faturamento,
        **resultado_pis_cofins.get("bases_calculo", {}),
    }

    alertas = [
        "Valores estimados com base no faturamento informado.",
        "Apuração oficial depende da escrituração contábil."
    ]

    return formatar_resposta_tributaria(
        regime="lucro_presumido",
        tributos=tributos,
        bases_calculo=bases_calculo,
        alertas=alertas
    )
