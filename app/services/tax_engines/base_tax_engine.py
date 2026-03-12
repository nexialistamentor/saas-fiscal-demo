"""
Classe base para engines tributárias.
Garante padronização de execução, logging e tratamento de erro.
"""


class BaseTaxEngine:
    """
    Classe base para todas as engines tributárias.
    Padroniza execução, logging e tratamento de erro.
    """

    name = "base_tax_engine"

    def execute(self, context: dict):
        raise NotImplementedError("Engine deve implementar execute()")

    def log_inicio(self):
        pass

    def log_fim(self):
        pass
