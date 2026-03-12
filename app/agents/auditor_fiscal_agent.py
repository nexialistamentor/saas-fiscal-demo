from typing import Dict, List


class AuditorFiscalAgent:
    """
    Agente responsável por auditoria tributária automática.
    Analisa resultados produzidos pelos services e identifica riscos fiscais.
    """

    name = "auditor_fiscal_agent"

    permissions = [
        "read_insights",
        "read_operacoes"
    ]

    async def run(self, context) -> Dict:
        """
        Método principal executado pelo scheduler.
        O context será fornecido pela camada de sistema.
        """

        alertas: List[Dict] = []

        # estrutura padrão de alerta fiscal
        def criar_alerta(tipo: str, descricao: str, nivel: str):
            return {
                "tipo": tipo,
                "descricao": descricao,
                "nivel": nivel
            }

        # dados recebidos do contexto
        insights = context.get("insights", [])

        for item in insights:
            restit = item.get("restituicao_potencial", 0)
            mva_distorcao = item.get("mva_distorcao", 0)

            if restit > 10000:
                alertas.append(
                    criar_alerta(
                        "RISCO_FISCAL_ALTO",
                        "Possível restituição elevada de ST detectada",
                        "alto"
                    )
                )
            elif restit > 2000:
                alertas.append(
                    criar_alerta(
                        "RISCO_FISCAL_MEDIO",
                        "Restituição relevante identificada",
                        "medio"
                    )
                )

            if mva_distorcao > 20:
                alertas.append(
                    criar_alerta(
                        "OPERACAO_CRITICA",
                        "Distorção elevada de MVA detectada",
                        "critico"
                    )
                )

        resultado = {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado"
        }

        return resultado


# instância padrão do agente
auditor_fiscal_agent = AuditorFiscalAgent()
