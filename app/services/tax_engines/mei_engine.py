# DEPRECATED: motor legado; usar MEITaxEngine em mei_tax_engine.py.



from app.services.tax_engines.base_tax_engine import BaseTaxEngine

from app.services.tax_engines.mei_constants import (

    MEI_LIMITE_ANUAL_FATURAMENTO,

    calcular_das_mei,

    obter_salario_minimo,

)



_base_temporal = BaseTaxEngine()





class MEIEngine:

    def execute(self, context: dict):

        faturamento = context.get("faturamento", 0)

        faturamento_anual_estimado = faturamento * 12

        alertas = []



        if faturamento_anual_estimado > MEI_LIMITE_ANUAL_FATURAMENTO:

            alertas.append("Desenquadramento do MEI por excesso de faturamento")



        # B13-OPS-12A: DAS MEI via fonte canónica mei_constants

        ano_referencia = _base_temporal.resolver_ano_referencia(context)

        das = calcular_das_mei(obter_salario_minimo(ano_referencia))



        return {

            "regime": "mei",

            "das_mensal": das,

            "faturamento_mensal": faturamento,

            "faturamento_anual_estimado": faturamento_anual_estimado,

            "alertas": alertas,

        }

