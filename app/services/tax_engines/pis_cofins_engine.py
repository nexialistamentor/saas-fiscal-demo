from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class PISCOFINSEngine(BaseTaxEngine):
    """
    Calcula PIS e COFINS conforme regime tributário.
    """

    def execute(self, context: dict):
        """
        Calcula PIS e COFINS conforme regime tributário.
        """
        faturamento = context.get("faturamento", 0)
        regime = context.get("regime", "presumido")

        if regime == "presumido":
            pis = faturamento * 0.0065
            cofins = faturamento * 0.03
        else:
            pis = faturamento * 0.0165
            cofins = faturamento * 0.076

        return {
            "tributo": "PIS_COFINS",
            "pis": pis,
            "cofins": cofins
        }


def calcular_pis_cofins(dados_fiscais: dict, regime="presumido"):
    """
    Função de compatibilidade para chamadores legados.
    Delega para PISCOFINSEngine e adapta o retorno ao formato anterior.
    """
    context = {
        "faturamento": dados_fiscais.get("faturamento", 0),
        "regime": regime
    }
    result = PISCOFINSEngine().execute(context)
    icms = dados_fiscais.get("icms", 0)
    faturamento = context["faturamento"]
    base_pis_cofins = faturamento - icms

    return {
        "tributos": {
            "pis": result["pis"],
            "cofins": result["cofins"]
        },
        "bases_calculo": {
            "faturamento": faturamento,
            "icms_excluido": icms,
            "base_pis_cofins": base_pis_cofins,
        },
        "regime": regime,
        "alertas": [
            "Valores estimados sem considerar créditos fiscais.",
            "Apuração oficial depende da escrituração contábil."
        ]
    }
