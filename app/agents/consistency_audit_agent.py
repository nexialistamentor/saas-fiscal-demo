"""
ConsistencyAuditAgent — Soberana L2 (AG2)

Audita coerência entre declaração (XML) e cálculo do motor fiscal
(ICMS-ST, MVA, base ST) reutilizando o TaxConsistencyEngine.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine


class ConsistencyAuditAgent:
    """
    Agente de auditoria de consistência tributária.
    Espera no contexto: `dados_xml` e `dados_motor` (chaves alinhadas ao engine).
    """

    name = "consistency_audit_agent"
    permissions = ["read_context", "compare_motor_xml"]

    def __init__(self) -> None:
        self._engine = TaxConsistencyEngine()

    async def run(self, context: dict) -> Dict[str, Any]:
        dados_xml = context.get("dados_xml") or {}
        dados_motor = context.get("dados_motor") or {}

        if not isinstance(dados_xml, dict):
            dados_xml = {}
        if not isinstance(dados_motor, dict):
            dados_motor = {}

        resumo = self._engine.verificar_consistencia(dados_xml, dados_motor)
        divergencias: List[Dict[str, Any]] = resumo.get("divergencias", [])

        alertas: List[Dict[str, Any]] = []
        for d in divergencias:
            alertas.append(self._divergencia_para_alerta(d))

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "dados_coerentes": resumo.get("consistente", True),
        }

    @staticmethod
    def _divergencia_para_alerta(d: dict) -> dict:
        tipo = d.get("tipo", "CONSISTENCIA_DESCONHECIDA")
        if tipo == "ICMS_ST_DIVERGENTE":
            desc = (
                f"ICMS-ST XML ({d.get('valor_xml')}) difere do motor "
                f"({d.get('valor_motor')})"
            )
        elif tipo == "MVA_DIVERGENTE":
            desc = (
                f"MVA XML ({d.get('mva_xml')}) difere da MVA do motor "
                f"({d.get('mva_motor')})"
            )
        elif tipo == "BASE_ST_DIVERGENTE":
            desc = (
                f"Base ST XML ({d.get('base_xml')}) difere da base calculada "
                f"({d.get('base_motor')})"
            )
        else:
            desc = str(d)

        return {
            "tipo": f"CONSISTENCIA_{tipo}",
            "descricao": desc,
            "nivel": "alto",
            "agente": ConsistencyAuditAgent.name,
        }


consistency_audit_agent = ConsistencyAuditAgent()
