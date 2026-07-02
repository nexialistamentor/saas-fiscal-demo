from datetime import date

from app.services.analysis_orchestrator import executar_analise


class CPFDashboardService:
    def __init__(self):
        pass

    def calcular_resumo(
        self,
        faturamento_mensal: float,
        despesas: float,
        ano_referencia: int | None = None,
        data_referencia: date | None = None,
    ):
        ctx: dict = {
            "faturamento": faturamento_mensal,
            "despesas": despesas,
        }
        if ano_referencia is not None:
            ctx["ano_referencia"] = ano_referencia
        if data_referencia is not None:
            ctx["data_referencia"] = data_referencia
        resultado = executar_analise("cpf_tax", ctx)

        if resultado.get("erro"):
            return {
                "tipo": "cpf",
                "erro": resultado.get("mensagem"),
                "alertas": []
            }

        imposto_mensal = resultado.get("tributos", {}).get("imposto", 0)

        return {
            "tipo": "cpf",
            "imposto_mensal": imposto_mensal,
            "imposto_anual": imposto_mensal * 12,
            "alertas": resultado.get("alertas", []),
            "_ano_referencia": resultado.get("_ano_referencia"),
            "_estado_temporal": resultado.get("_estado_temporal"),
        }
