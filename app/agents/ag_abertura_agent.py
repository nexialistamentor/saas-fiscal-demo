"""
AG-ABERTURA — Agente de abertura de empresa.

Guia o utilizador no processo de abertura MEI/ME/EPP.

Não acede à BD — é um agente de orientação pura.

Versão: 1.0 | Schema: HowTo | SEO: abertura empresa CNPJ MEI REDESIM 2026
"""

from typing import Any, Dict

from app.constants import (
    ANALYSIS_TYPE_ABERTURA,
    CHECKLIST_ABERTURA_MEI,
    CHECKLIST_ABERTURA_ME_EPP,
)


class AgAberturaAgent:
    name = "ag_abertura"
    permissions = ["read_context"]
    versao = "1.0"

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tipo = context.get("tipo_contribuinte", "mei").lower()

        if tipo in ("me", "epp", "empresa", "ltda", "slu", "ei"):
            checklist = CHECKLIST_ABERTURA_ME_EPP
            titulo = "Como abrir uma empresa (ME/EPP) em 2026"
            descricao = (
                "Para abrir uma ME ou EPP em 2026, o processo passa pela REDESIM "
                "e requer contador obrigatório. Siga os passos abaixo:"
            )
        else:
            checklist = CHECKLIST_ABERTURA_MEI
            titulo = "Como abrir MEI em 2026 — Passo a Passo Completo"
            descricao = (
                "Abrir o MEI é gratuito, 100% online e o CNPJ sai na hora. "
                "Siga o checklist oficial para se formalizar sem erros:"
            )

        resposta = f"**{titulo}**\n\n{descricao}\n\n"
        for item in checklist:
            link = f" → [Ver]({item['link']})" if item.get("link") else ""
            resposta += f"**{item['passo']}.** {item['titulo']}: {item['descricao']}{link}\n"

        resposta += (
            "\n\n💡 *Esta plataforma tem contadores parceiros com assinatura digital "
            "que podem acompanhar todo o processo remotamente.*"
        )

        return {
            "resposta": resposta,
            "requires_payment": False,
            "analysis_type": ANALYSIS_TYPE_ABERTURA,
            "schema_type": "HowTo",
            "versao": self.versao,
            "payload_estruturado": {
                "tipo_contribuinte": tipo,
                "checklist": checklist,
                "avisos_legais": [
                    "Este guia não substitui a consulta a um contador.",
                    "Verifique requisitos específicos do seu município.",
                ],
                "links_uteis": {
                    "portal_empreendedor": (
                        "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor"
                    ),
                    "redesim": "https://redesim.gov.br",
                    "receita_federal": "https://www.gov.br/receitafederal",
                },
            },
        }


ag_abertura_agent = AgAberturaAgent()
