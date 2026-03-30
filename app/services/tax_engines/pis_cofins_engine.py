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
        # Base de cálculo: faturamento líquido do ICMS (mesma lógica de bases_calculo.base_pis_cofins)
        base = context.get("base_pis_cofins")
        if base is None:
            icms = context.get("icms", 0)
            base = faturamento - icms

        if regime == "presumido":
            pis = base * 0.0065
            cofins = base * 0.03
        else:
            pis = base * 0.0165
            cofins = base * 0.076

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
    faturamento = dados_fiscais.get("faturamento", 0)
    icms = dados_fiscais.get("icms", 0)
    base_pis_cofins = faturamento - icms
    context = {
        "faturamento": faturamento,
        "icms": icms,
        "base_pis_cofins": base_pis_cofins,
        "regime": regime,
    }
    result = PISCOFINSEngine().execute(context)

    aliquota_pis = 0.0065 if regime == "presumido" else 0.0165
    aliquota_cofins = 0.03 if regime == "presumido" else 0.076

    base_com_icms = faturamento
    pis_com_icms = base_com_icms * aliquota_pis
    cofins_com_icms = base_com_icms * aliquota_cofins

    pis_sem_icms = result["pis"]
    cofins_sem_icms = result["cofins"]

    credito_pis_estimado = pis_com_icms - pis_sem_icms
    credito_cofins_estimado = cofins_com_icms - cofins_sem_icms
    credito_total_estimado = credito_pis_estimado + credito_cofins_estimado

    comparativo_icms_base = {
        "base_com_icms": base_com_icms,
        "base_sem_icms": base_pis_cofins,
        "pis_com_icms": pis_com_icms,
        "pis_sem_icms": pis_sem_icms,
        "cofins_com_icms": cofins_com_icms,
        "cofins_sem_icms": cofins_sem_icms,
        "credito_pis_estimado": credito_pis_estimado,
        "credito_cofins_estimado": credito_cofins_estimado,
        "credito_total_estimado": credito_total_estimado,
    }

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
        "comparativo_icms_base": comparativo_icms_base,
        "regime": regime,
        "alertas": [
            "Valores estimados sem considerar créditos fiscais.",
            "Apuração oficial depende da escrituração contábil."
        ]
    }
