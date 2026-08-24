# DEPRECATED: motor legado; usar MEITaxEngine em mei_tax_engine.py.



from app.services.tax_engines.mei_tax_engine import MEITaxEngine





class MEIEngine:

    def execute(self, context: dict):
        resultado = MEITaxEngine().execute(context)
        bases = resultado["bases_calculo"]

        return {
            "regime": resultado["regime"],
            "das_mensal": resultado["tributos"]["das"],
            "faturamento_mensal": bases["faturamento_mensal"],
            "faturamento_anual_estimado": bases["faturamento_anual"],
            "alertas": resultado["alertas"],
        }
