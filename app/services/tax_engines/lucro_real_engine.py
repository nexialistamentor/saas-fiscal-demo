from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.csll_engine import CSLLEngine
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
        irpj = base * 0.15
        csll = CSLLEngine().execute({"lucro": base})["valor"]
        return irpj, csll, base


def _alertas_credito_excede_debito(
    pis_bruto: float, cofins_bruto: float, creditos_info: dict
) -> list[str]:
    total_cred = float(creditos_info.get("total") or 0)
    debito = pis_bruto + cofins_bruto
    if total_cred > debito and debito >= 0:
        return [
            "Créditos de PIS/COFINS superiores ao débito apurado — saldo credor pode ser "
            "compensado ou restituído."
        ]
    return []


def calcular_lucro_real(dados_fiscais: dict):
    lucro_contabil, faturamento = _resolver_lucro_e_receita(dados_fiscais)
    irpj, csll, base = LucroRealEngine.calcular_irpj_csll(lucro_contabil)

    dados_pis = {**dados_fiscais, "faturamento": faturamento}
    resultado_pis_cofins = calcular_pis_cofins(dados_pis, regime="real")

    pis_bruto = resultado_pis_cofins["tributos"]["pis"]
    cofins_bruto = resultado_pis_cofins["tributos"]["cofins"]
    liq = resultado_pis_cofins.get("tributos_liquidos") or resultado_pis_cofins["tributos"]
    pis_liq = liq["pis"]
    cofins_liq = liq["cofins"]
    creditos_info = resultado_pis_cofins.get("creditos") or {}
    creditos_total = float(creditos_info.get("total") or 0)

    alertas_pis = list(resultado_pis_cofins.get("alertas") or [])
    alertas_pis.extend(_alertas_credito_excede_debito(pis_bruto, cofins_bruto, creditos_info))

    tributos = {
        "irpj": irpj,
        "csll": csll,
        "pis": pis_liq,
        "cofins": cofins_liq,
    }

    bases_calculo = {
        "base_irpj": base,
        "base_csll": base,
        "faturamento": faturamento,
        "lucro_contabil": lucro_contabil,
        "pis_cofins_bruto": round(pis_bruto + cofins_bruto, 2),
        "creditos_pis_cofins": round(creditos_total, 2),
        "pis_cofins_liquido": round(pis_liq + cofins_liq, 2),
        **resultado_pis_cofins.get("bases_calculo", {}),
    }

    alertas = [
        "Regime não-cumulativo: PIS 1,65% e COFINS 7,6% sobre a receita bruta.",
        "IRPJ (15%) e CSLL (9%) calculados sobre o lucro contábil ajustado.",
        "Cálculo estimado — apuração oficial depende da escrituração contábil completa.",
        *alertas_pis,
    ]

    return formatar_resposta_tributaria(
        regime="lucro_real",
        tributos=tributos,
        bases_calculo=bases_calculo,
        alertas=alertas,
    )
