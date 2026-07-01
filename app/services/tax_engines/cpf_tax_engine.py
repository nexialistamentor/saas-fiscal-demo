from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class CPFTaxEngine(BaseTaxEngine):
    """
    Engine inicial para cálculo tributário de CPF (autônomo).

    Primeira versão:
    - Base: faturamento - despesas
    - Regra simples (temporária): 6%
    - Estrutura já compatível com L2
    """

    name = "cpf_tax"

    def execute(self, context: dict):
        ano_referencia = self.resolver_ano_referencia(context)
        faturamento = float(context.get("faturamento", 0))
        despesas = float(context.get("despesas", 0))

        base_calculo = max(0, faturamento - despesas)

        # REGRA TEMPORÁRIA (substituir depois por IRPF real)
        aliquota = 0.06
        imposto = round(base_calculo * aliquota, 2)

        return {
            "regime": "cpf_autonomo",
            "tributos": {
                "imposto": imposto
            },
            "bases_calculo": {
                "faturamento": faturamento,
                "despesas": despesas,
                "base_calculo": base_calculo
            },
            "alertas": [
                "Cálculo simplificado (6%) — motor IRPF ainda não implementado"
            ],
            "_ano_referencia": ano_referencia,
            "_estado_temporal": "resolvido",
        }
