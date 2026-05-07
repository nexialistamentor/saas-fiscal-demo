"""
AG-ENCERRAMENTO — Agente de encerramento de empresa.

Verifica pendências fiscais na BD e guia o utilizador na baixa MEI/ME/EPP.

Acede à BD (leitura apenas) — nunca altera dados oficiais.

Versão: 1.0 | Schema: HowTo | SEO: encerrar empresa baixa CNPJ MEI 2026
"""

from datetime import datetime
from typing import Any, Dict

from app.constants import (
    ANALYSIS_TYPE_ENCERRAMENTO,
    AVISO_ENCERRAMENTO_IRREVERSIVEL,
    CHECKLIST_ENCERRAMENTO,
)


class AgEncerramentoAgent:
    name = "ag_encerramento"
    permissions = ["read_context", "read_insights", "read_relatorios"]
    versao = "1.0"

    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        tipo = context.get("tipo_contribuinte", "mei").lower()
        empresa_id = context.get("empresa_id")
        db = context.get("db")

        alertas_bd = []

        # Verificar pendências na BD se disponível
        if db and empresa_id:
            try:
                from sqlalchemy import func

                from app.models import Insight, RelatorioAnalise

                # Insights não superseded = análises activas pendentes
                insights_activos = (
                    db.query(func.count(Insight.id))
                    .filter(
                        Insight.empresa_id == empresa_id,
                        Insight.superseded == False,  # noqa: E712
                    )
                    .scalar()
                    or 0
                )
                if insights_activos > 0:
                    alertas_bd.append(
                        {
                            "tipo": "INSIGHTS_ACTIVOS",
                            "descricao": (
                                f"{insights_activos} análise(s) fiscal(is) activa(s) "
                                "— revisar antes de encerrar."
                            ),
                            "severidade": "alta",
                        }
                    )

                # Último relatório — verificar data
                ultimo_relatorio = (
                    db.query(RelatorioAnalise)
                    .filter(RelatorioAnalise.empresa_id == empresa_id)
                    .order_by(RelatorioAnalise.created_at.desc())
                    .first()
                )
                if ultimo_relatorio and ultimo_relatorio.created_at:
                    meses = (datetime.utcnow() - ultimo_relatorio.created_at).days // 30
                    if meses > 3:
                        alertas_bd.append(
                            {
                                "tipo": "RELATORIO_DESACTUALIZADO",
                                "descricao": (
                                    f"Último relatório fiscal há {meses} meses — "
                                    "confirmar situação actual antes de encerrar."
                                ),
                                "severidade": "media",
                            }
                        )
            except Exception as exc:
                alertas_bd.append(
                    {
                        "tipo": "ERRO_BD",
                        "descricao": (
                            f"Não foi possível verificar pendências na BD: {exc}"
                        ),
                        "severidade": "baixa",
                    }
                )

        # Montar resposta
        titulo = "Como encerrar empresa em 2026 — Checklist Completo"
        if tipo == "mei":
            titulo = "Como encerrar o MEI em 2026 — Passo a Passo Oficial"

        resposta = f"**{titulo}**\n\n"
        resposta += f"⚠️ {AVISO_ENCERRAMENTO_IRREVERSIVEL}\n\n"

        if alertas_bd:
            resposta += "**Pendências detectadas na plataforma:**\n"
            for a in alertas_bd:
                icone = "🔴" if a["severidade"] == "alta" else "🟡"
                resposta += f"{icone} {a['descricao']}\n"
            resposta += "\n"

        resposta += "**Checklist de encerramento:**\n"
        for item in CHECKLIST_ENCERRAMENTO:
            icone = "🔴" if item.get("severidade") == "alta" else "🟡"
            link = f" → [Ver]({item['link']})" if item.get("link") else ""
            resposta += (
                f"{icone} **{item['passo']}.** {item['titulo']}: "
                f"{item['descricao']}{link}\n"
            )

        resposta += (
            "\n\n💡 *Os contadores parceiros desta plataforma podem acompanhar "
            "todo o processo de encerramento com assinatura digital.*"
        )

        return {
            "resposta": resposta,
            "requires_payment": False,
            "analysis_type": ANALYSIS_TYPE_ENCERRAMENTO,
            "schema_type": "HowTo",
            "versao": self.versao,
            "payload_estruturado": {
                "tipo_contribuinte": tipo,
                "checklist": CHECKLIST_ENCERRAMENTO,
                "alertas_plataforma": alertas_bd,
                "aviso_irreversivel": AVISO_ENCERRAMENTO_IRREVERSIVEL,
                "avisos_legais": [
                    "Débitos não quitados migram para o CPF do titular.",
                    "Documentos fiscais devem ser guardados 5 anos (CTN art. 195).",
                    "Consulte um contador antes de iniciar o encerramento.",
                ],
            },
        }


ag_encerramento_agent = AgEncerramentoAgent()
