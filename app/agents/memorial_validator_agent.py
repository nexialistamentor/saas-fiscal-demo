"""
MemorialValidatorAgent (AG6) — Soberana L2

Valida se o contexto do memorial tem dados suficientes para exportação.
Só actua quando o contexto contém chave 'contexto_memorial'.
"""
from __future__ import annotations

from typing import Any, Dict


class MemorialValidatorAgent:
    name = "memorial_validator_agent"
    permissions = ["read_contexto_memorial", "validate_memorial_export"]

    async def run(self, context: dict) -> Dict[str, Any]:
        alertas = []

        # Só actua quando explicitamente chamado com contexto de memorial
        contexto_memorial = (
            context.get("contexto_memorial")
            or (context if ("relatorio" in context and "engines" in context) else None)
        )

        if not contexto_memorial:
            return {
                "agent": self.name,
                "total_alertas": 0,
                "alertas": [],
                "status": "pulado",
                "memorial_validado": False,
                "pode_exportar": False,
            }

        rel = contexto_memorial.get("relatorio") or {}
        engines = contexto_memorial.get("engines") or []
        referencias = contexto_memorial.get("referencias_legais") or []
        insights = contexto_memorial.get("insights") or []

        if not rel:
            alertas.append(self._alerta("MEMORIAL_RELATORIO_AUSENTE", "Relatório não encontrado no contexto.", "critico"))

        if not engines:
            alertas.append(self._alerta("MEMORIAL_ENGINES_VAZIOS", "Nenhum resultado de engine no memorial.", "alto"))

        if not referencias:
            alertas.append(self._alerta("MEMORIAL_REFERENCIAS_VAZIAS", "Base normativa vazia — fundamentos legais ausentes.", "alto"))

        for r in referencias:
            if not r.get("fundamento"):
                alertas.append(self._alerta(
                    "MEMORIAL_REFERENCIA_INCOMPLETA",
                    f"Referência '{r.get('codigo')}' sem fundamento legal.",
                    "medio"
                ))

        if rel.get("status") == "erro":
            alertas.append(self._alerta("MEMORIAL_STATUS_ANALISE", "Análise com status de erro — memorial pode estar incompleto.", "alto"))

        total_alertas_criticos = rel.get("total_alertas", 0)
        if total_alertas_criticos and int(total_alertas_criticos) > 10:
            alertas.append(self._alerta(
                "MEMORIAL_CONTAGEM_ALERTAS",
                f"Relatório tem {total_alertas_criticos} alertas — revisão recomendada antes da exportação.",
                "medio"
            ))

        pode_exportar = not any(a["nivel"] == "critico" for a in alertas)

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "memorial_validado": len(alertas) == 0,
            "pode_exportar": pode_exportar,
        }

    @staticmethod
    def _alerta(tipo: str, descricao: str, nivel: str) -> dict:
        return {
            "tipo": tipo,
            "descricao": descricao,
            "nivel": nivel,
            "agente": "memorial_validator_agent",
        }


memorial_validator_agent = MemorialValidatorAgent()
