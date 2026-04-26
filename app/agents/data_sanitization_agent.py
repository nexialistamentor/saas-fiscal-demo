"""
DataSanitizationAgent — Soberana L2

Valida domínio de parâmetros fiscais antes de qualquer cálculo.
Detecta valores absurdos (negativos, infinitos, NaN, fora de intervalo)
que chegam ao motor e os regista como alertas antes de contaminarem
os resultados persistidos.
"""
from typing import Dict

import math


class DataSanitizationAgent:
    """
    Agente de sanitização de dados fiscais.
    Corre antes das engines — bloqueia valores patológicos no contexto.
    """

    name = "data_sanitization_agent"
    permissions = ["read_context", "validate_inputs"]

    # Limites razoáveis para dados fiscais brasileiros
    LIMITE_FATURAMENTO = 1_000_000_000.0  # R$ 1 bilhão/mês — acima disso é erro
    LIMITE_ALIQUOTA = 1.0  # alíquota decimal nunca > 100%
    LIMITE_MVA = 5.0  # MVA decimal nunca > 500%

    async def run(self, context: dict) -> Dict:
        alertas = []

        campos_monetarios = [
            "faturamento",
            "custos",
            "lucro_contabil",
            "lucro",
            "base_calculo",
            "icms_pago",
            "icms_devido",
            "custo_fiscal_entradas",
        ]

        for campo in campos_monetarios:
            valor = context.get(campo)
            if valor is None:
                continue
            try:
                v = float(valor)
            except (TypeError, ValueError):
                alertas.append(
                    self._alerta(
                        f"Campo '{campo}' não é numérico: {valor!r}",
                        "critico",
                    )
                )
                continue

            if math.isnan(v) or math.isinf(v):
                alertas.append(
                    self._alerta(
                        f"Campo '{campo}' contém valor inválido (NaN/Inf): {v}",
                        "critico",
                    )
                )
            elif v < 0:
                alertas.append(
                    self._alerta(
                        f"Campo '{campo}' é negativo ({v:.2f}) — verifique a origem do dado.",
                        "alto",
                    )
                )
            elif campo == "faturamento" and v > self.LIMITE_FATURAMENTO:
                alertas.append(
                    self._alerta(
                        f"Faturamento ({v:.2f}) excede limite razoável ({self.LIMITE_FATURAMENTO:.0f}).",
                        "alto",
                    )
                )

        # Valida empresa_id
        empresa_id = context.get("empresa_id")
        if empresa_id is not None:
            try:
                eid = int(empresa_id)
                if eid <= 0:
                    alertas.append(
                        self._alerta(
                            f"empresa_id inválido: {empresa_id}",
                            "critico",
                        )
                    )
            except (TypeError, ValueError):
                alertas.append(
                    self._alerta(
                        f"empresa_id não é inteiro: {empresa_id!r}",
                        "critico",
                    )
                )

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "contexto_valido": len([a for a in alertas if a["nivel"] == "critico"])
            == 0,
        }

    @staticmethod
    def _alerta(descricao: str, nivel: str) -> dict:
        return {
            "tipo": "SANITIZACAO_DADOS",
            "descricao": descricao,
            "nivel": nivel,
            "agente": "data_sanitization_agent",
        }


data_sanitization_agent = DataSanitizationAgent()
