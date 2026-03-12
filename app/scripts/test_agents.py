import asyncio
import sys

from app.agents.agent_executor import AgentExecutor
from app.database import SessionLocal
from app.services.insights_engine import InsightEngine
from app.services.tabela_normativa_service import listar_base_normativa


def _insights_para_contexto(resultado_engine: dict) -> list:
    """
    Converte output do InsightEngine em lista para context['insights'].
    Mapeia valor_estimado/tipo para restituicao_potencial e mva_distorcao,
    que o AuditorFiscalAgent espera.
    """
    insights_norm = []
    tipos_restituicao = {"ST_RESTITUICAO", "CREDITO_ST_ESTIMADO", "PRODUTO_COM_RESTITUICAO_RELEVANTE"}
    tipos_mva = {"DISTORCAO_MVA_REAL", "DISTORCAO_MARGEM_MVA", "MVA_OFICIAL_DIVERGENTE", "ANOMALIA_MVA"}

    def normalizar(i: dict) -> dict:
        out = dict(i)
        out.setdefault("restituicao_potencial", 0)
        out.setdefault("mva_distorcao", 0)
        v = i.get("valor_estimado", 0) or 0
        t = i.get("tipo", "")
        if t in tipos_restituicao:
            out["restituicao_potencial"] = v
        elif t in tipos_mva:
            out["mva_distorcao"] = v
        if "potencial_recuperacao" in i and i["potencial_recuperacao"]:
            out["restituicao_potencial"] = max(out["restituicao_potencial"], i["potencial_recuperacao"])
        return out

    oportunidades = resultado_engine.get("oportunidades", [])
    creditos = resultado_engine.get("creditos_detectados", [])
    for item in oportunidades + creditos:
        insights_norm.append(normalizar(item))

    return insights_norm


async def main(empresa_id: int = 1):
    db = SessionLocal()
    try:
        # InsightEngine → context["insights"]
        engine = InsightEngine(db)
        resultado_engine = engine.gerar_insights_empresa(empresa_id)

        context = {
            "empresa_id": empresa_id,
            "insights": _insights_para_contexto(resultado_engine),
            "tabela_normativa": listar_base_normativa(db),
            "risco_tributario": resultado_engine.get("risco_tributario"),
        }

        # AgentExecutor → AuditorFiscalAgent
        executor = AgentExecutor()
        resultados = await executor.run_all(context)

        print(resultados)
    finally:
        db.close()


if __name__ == "__main__":
    empresa_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    asyncio.run(main(empresa_id))
