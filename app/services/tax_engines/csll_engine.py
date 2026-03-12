from app.services.tax_engines.base_tax_engine import BaseTaxEngine


class CSLLEngine(BaseTaxEngine):
    def execute(self, context: dict):
        """
        Executa cálculo de CSLL.
        """
        lucro = context.get("lucro", 0)

        csll = lucro * 0.09

        return {
            "tributo": "CSLL",
            "valor": csll
        }
