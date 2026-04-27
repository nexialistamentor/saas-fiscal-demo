"""
AG5 — StateRecoveryAgent: observa estado do orquestrador (circuit breaker,
engines degradadas) e tenta recuperação; alerta estados anómalos persistentes.
"""
from __future__ import annotations

import time
from typing import Dict, List

from app.services.analysis_orchestrator import (
    degraded_engines,
    engine_blocked_until,
    engine_failures,
    metrics_store,
)
from app.services.engine_recovery_service import verificar_recuperacao_engines


def _criar_alerta(tipo: str, descricao: str, nivel: str) -> Dict:
    return {"tipo": tipo, "descricao": descricao, "nivel": nivel}


class StateRecoveryAgent:
    """Monitoriza e reconcilia estado de engines no processo (memória)."""

    name = "state_recovery_agent"
    permissions = ["read_orchestrator_state", "trigger_engine_recovery"]

    async def run(self, context: Dict) -> Dict:
        alertas: List[Dict] = []
        agora = time.time()

        try:
            verificar_recuperacao_engines()
        except Exception as exc:
            alertas.append(
                _criar_alerta(
                    "recovery_exec_falhou",
                    f"StateRecoveryAgent não pôde executar verificar_recuperacao_engines: {exc}",
                    "medio",
                )
            )

        for tipo, bloqueado_ate in list(engine_blocked_until.items()):
            if agora >= bloqueado_ate:
                continue
            seg_restantes = int(bloqueado_ate - agora)
            falhas = engine_failures.get(tipo, 0)
            alertas.append(
                _criar_alerta(
                    "circuit_breaker_aberto",
                    f"Engine '{tipo}' com circuit breaker activo (~{seg_restantes}s); falhas acumuladas: {falhas}.",
                    "alto",
                )
            )

        por_tipo = metrics_store.get("por_tipo") or {}

        for tipo, ate in list(degraded_engines.items()):
            if agora < ate:
                continue
            if tipo not in por_tipo:
                alertas.append(
                    _criar_alerta(
                        "degraded_sem_metricas",
                        f"Engine '{tipo}' em mapa degradado após cooldown, sem entrada em métricas — verificar estado.",
                        "alto",
                    )
                )
                continue
            dados = por_tipo[tipo]
            ex = dados.get("execucoes", 0)
            if ex == 0:
                alertas.append(
                    _criar_alerta(
                        "degraded_sem_execucoes",
                        f"Engine '{tipo}' marcada como degradada mas sem execuções registadas após cooldown.",
                        "medio",
                    )
                )
                continue
            tempo_medio = dados["tempo_total"] / ex
            alertas.append(
                _criar_alerta(
                    "degraded_persistente",
                    f"Engine '{tipo}' continua em fallback (tempo médio {tempo_medio:.2f}s; limite recuperação 1.5s).",
                    "alto",
                )
            )

        return {
            "agent": self.name,
            "total_alertas": len(alertas),
            "alertas": alertas,
            "status": "executado",
            "engines_em_degraded": list(degraded_engines.keys()),
            "circuits_abertos": [t for t, u in engine_blocked_until.items() if agora < u],
        }


state_recovery_agent = StateRecoveryAgent()
