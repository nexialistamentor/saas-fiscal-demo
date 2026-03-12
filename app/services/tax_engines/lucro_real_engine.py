from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.response_formatter import formatar_resposta_tributaria


class LucroRealEngine(BaseTaxEngine):

    def execute(self, context: dict):
        """
        Calcula tributos no regime de Lucro Real.
        """
        lucro_contabil = context.get("lucro_contabil", 0)

        irpj = lucro_contabil * 0.15
        csll = lucro_contabil * 0.09

        return {
            "regime": "lucro_real",
            "irpj": irpj,
            "csll": csll
        }


def calcular_lucro_real(dados_fiscais: dict):
    """Wrapper para compatibilidade: extrai lucro_contabil e formata resposta."""
    receita_bruta = dados_fiscais.get("receita_bruta", 0)
    custos = dados_fiscais.get("custos", 0)
    despesas = dados_fiscais.get("despesas", 0)
    lucro_contabil = receita_bruta - custos - despesas

    resultado = LucroRealEngine().execute({"lucro_contabil": lucro_contabil})

    return formatar_resposta_tributaria(
        regime="lucro_real",
        tributos={
            "irpj": resultado["irpj"],
            "csll": resultado["csll"],
            "pis": 0,
            "cofins": 0
        },
        bases_calculo={
            "base_irpj": lucro_contabil,
            "base_csll": lucro_contabil,
            "faturamento": receita_bruta,
        },
        alertas=[
            "Cálculo estimado baseado em dados informados.",
            "Apuração oficial depende da escrituração contábil completa.",
        ]
    )
