from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.lucro_presumido_engine import calcular_lucro_presumido
from app.services.tax_engines.lucro_real_engine import calcular_lucro_real


def _total_tributos_resposta_tributaria(resultado: dict) -> float:
    """Soma tributos a partir de formatar_resposta_tributaria (data.tributos) ou payload legado."""
    payload = resultado.get("data", resultado)
    trib = payload.get("tributos") or {}
    return float(sum(trib.values()))


class TaxPlanningEngine(BaseTaxEngine):
    """
    Engine de planejamento tributário.
    Compara regimes e identifica menor carga tributária.
    """

    name = "tax_planning"

    def execute(self, context: dict):
        ano_referencia = self.resolver_ano_referencia(context)
        resultado = simular_regimes(context)
        resultado["_ano_referencia"] = ano_referencia
        resultado["_estado_temporal"] = "resolvido"
        return resultado


def simular_regimes(dados_fiscais: dict):

    resultado_presumido = calcular_lucro_presumido(dados_fiscais)
    resultado_real = calcular_lucro_real(dados_fiscais)

    total_presumido = _total_tributos_resposta_tributaria(resultado_presumido)
    total_real = _total_tributos_resposta_tributaria(resultado_real)

    if total_presumido < total_real:
        melhor_regime = "lucro_presumido"
        economia = total_real - total_presumido
    else:
        melhor_regime = "lucro_real"
        economia = total_presumido - total_real

    return {
        "comparacao": {
            "lucro_presumido": total_presumido,
            "lucro_real": total_real
        },
        "melhor_regime": melhor_regime,
        "economia_estimada": economia,
        "alertas": [
            "Simulação baseada em dados informados.",
            "Planejamento tributário deve considerar contabilidade completa."
        ]
    }
