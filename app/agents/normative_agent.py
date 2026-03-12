from datetime import datetime


class NormativeAgent:
    """
    Detecta mudanças na base normativa tributária.
    """

    name = "normative_agent"

    permissions = [
        "monitor_normative"
    ]

    async def run(self, context):

        alertas = []

        tabela_normativa = context.get("tabela_normativa", [])

        # exemplo simples de verificação
        if not tabela_normativa:

            alertas.append({
                "tipo": "BASE_NORMATIVA_AUSENTE",
                "descricao": "Base normativa não carregada no contexto",
                "nivel": "critico"
            })

        resultado = {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "executado_em": datetime.utcnow().isoformat()
        }

        return resultado


normative_agent = NormativeAgent()
