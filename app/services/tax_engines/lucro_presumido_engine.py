from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.csll_engine import CSLLEngine
from app.services.tax_engines.irpj_adicional import calcular_adicional_irpj_presumido
from app.services.tax_engines.pis_cofins_engine import calcular_pis_cofins
from app.services.tax_engines.response_formatter import formatar_resposta_tributaria


class AtividadeFiscalIndisponivelError(ValueError):
    """Sem actividade suportada, não existe base presumida calculável."""


def _atividade_explicita(dados_fiscais):
    atividade = dados_fiscais.get("atividade")
    if not isinstance(atividade, str) or atividade not in ("comercio", "industria", "servicos"):
        raise AtividadeFiscalIndisponivelError("Atividade fiscal ausente ou não suportada.")
    return atividade


class LucroPresumidoEngine(BaseTaxEngine):

    def execute(self, context: dict):
        ano_referencia = self.resolver_ano_referencia(context)
        regime = context.get("regime")
        if not isinstance(regime, str) or regime not in (
            "presumido", "real", "simples", "simples_nacional", "mei",
        ):
            return {
                "erro": "Regime fiscal ausente ou não suportado.",
                "codigo": "REGIME_FISCAL_INDISPONIVEL",
                "estado_l3": "bloqueado",
                "calculo_autorizado": False,
            }
        try:
            resultado = calcular_lucro_presumido(context)
        except AtividadeFiscalIndisponivelError as exc:
            return {
                "erro": str(exc),
                "codigo": "ATIVIDADE_FISCAL_INDISPONIVEL",
                "estado_l3": "bloqueado",
                "calculo_autorizado": False,
            }
        resultado["_ano_referencia"] = ano_referencia
        resultado["_estado_temporal"] = "resolvido"
        return resultado


def calcular_lucro_presumido(dados_fiscais: dict):
    faturamento = dados_fiscais.get("faturamento", 0)
    atividade = _atividade_explicita(dados_fiscais)

    percentuais_presuncao = {
        "comercio": 0.08,
        "industria": 0.08,
        "servicos": 0.32
    }

    percentual = percentuais_presuncao[atividade]

    base_calculo_irpj = faturamento * percentual

    irpj = base_calculo_irpj * 0.15

    adicional_irpj = calcular_adicional_irpj_presumido(
        base_calculo_irpj, dados_fiscais
    )

    total_irpj = irpj + adicional_irpj

    percentuais_csll = {"comercio": 0.12, "industria": 0.12, "servicos": 0.32}
    base_calculo_csll = faturamento * percentuais_csll[atividade]
    resultado_csll = CSLLEngine().execute({
        "lucro": base_calculo_csll,
        "data_referencia": dados_fiscais.get("data_referencia"),
        "ano_referencia": dados_fiscais.get("ano_referencia"),
    })
    resultado_pis_cofins = calcular_pis_cofins(dados_fiscais, regime="presumido")

    tributos = {
        "irpj": total_irpj,
        "csll": resultado_csll["valor"],
        "pis": resultado_pis_cofins["tributos"]["pis"],
        "cofins": resultado_pis_cofins["tributos"]["cofins"]
    }

    bases_calculo = {
        "base_irpj": base_calculo_irpj,
        "base_csll": base_calculo_csll,
        "faturamento": faturamento,
        **resultado_pis_cofins.get("bases_calculo", {}),
    }

    alertas = [
        "Valores estimados com base no faturamento informado.",
        "Apuração oficial depende da escrituração contábil."
    ]

    return formatar_resposta_tributaria(
        regime="lucro_presumido",
        tributos=tributos,
        bases_calculo=bases_calculo,
        alertas=alertas
    )
