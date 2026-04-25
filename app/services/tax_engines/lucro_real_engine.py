from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.pis_cofins_engine import calcular_pis_cofins
from app.services.tax_engines.response_formatter import formatar_resposta_tributaria


def _resolver_lucro_e_receita(dados_fiscais: dict) -> tuple[float, float]:
    """
    Alinha o contrato de entrada com o restante do motor (faturamento / receita_bruta,
    custos, despesas) e com contextos que já trazem lucro_contabil (ex.: insights).
    Retorna (lucro_contabil para IRPJ/CSLL, faturamento para PIS/COFINS e bases).
    """
    if dados_fiscais.get("lucro_contabil") is not None:
        try:
            lc = float(dados_fiscais["lucro_contabil"])
        except (TypeError, ValueError):
            lc = 0.0
        lucro = max(0.0, lc)
        faturamento = dados_fiscais.get("faturamento")
        if faturamento is None:
            faturamento = dados_fiscais.get("receita_bruta", 0)
        fat = float(faturamento or 0)
        return lucro, fat

    rec = dados_fiscais.get("faturamento")
    if rec is None:
        rec = dados_fiscais.get("receita_bruta", 0)
    receita = float(rec or 0)
    custos = float(dados_fiscais.get("custos", 0) or 0)
    despesas = float(dados_fiscais.get("despesas", 0) or 0)
    lucro = max(0.0, receita - custos - despesas)
    return lucro, receita


class LucroRealEngine(BaseTaxEngine):

    def execute(self, context: dict):
        return calcular_lucro_real(context)

    @staticmethod
    def calcular_irpj_csll(lucro_contabil: float) -> tuple[float, float, float]:
        base = max(0.0, float(lucro_contabil or 0))
        return base * 0.15, base * 0.09, base


def calcular_lucro_real(dados_fiscais: dict):
    lucro_contabil, faturamento = _resolver_lucro_e_receita(dados_fiscais)
    irpj, csll, base = LucroRealEngine.calcular_irpj_csll(lucro_contabil)

    dados_pis = {**dados_fiscais, "faturamento": faturamento}
    resultado_pis_cofins = calcular_pis_cofins(dados_pis, regime="real")

    tributos = {
        "irpj": irpj,
        "csll": csll,
        "pis": resultado_pis_cofins["tributos"]["pis"],
        "cofins": resultado_pis_cofins["tributos"]["cofins"],
    }

    bases_calculo = {
        "base_irpj": base,
        "base_csll": base,
        "faturamento": faturamento,
        "lucro_contabil": lucro_contabil,
        **resultado_pis_cofins.get("bases_calculo", {}),
    }

    return formatar_resposta_tributaria(
        regime="lucro_real",
        tributos=tributos,
        bases_calculo=bases_calculo,
        alertas=[
            "Cálculo estimado baseado em dados informados.",
            "Apuração oficial depende da escrituração contábil completa.",
        ],
    )
