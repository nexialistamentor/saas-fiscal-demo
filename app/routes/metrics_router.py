import time

from fastapi import APIRouter, Depends

from app.security import get_usuario_atual
from app.services.analysis_orchestrator import (
    analysis_cache,
    degraded_engines,
    engine_ab_testing,
    engine_blocked_until,
    engine_failures,
    engine_versions,
    metrics_store,
)

router = APIRouter(prefix="/system", tags=["system"])

ERRO_LIMITE = 0.05  # 5%
TEMPO_LIMITE = 2.0  # segundos


def _calcular_alertas():
    """Calcula alertas ativos baseado nas métricas atuais."""
    alertas = []
    total_execucoes = metrics_store["total_execucoes"]
    total_erros = metrics_store["total_erros"]
    tempo_total = metrics_store["tempo_total"]

    if total_execucoes == 0:
        return alertas

    taxa_erro = total_erros / total_execucoes
    tempo_medio = tempo_total / total_execucoes

    if taxa_erro > ERRO_LIMITE:
        alertas.append({
            "tipo": "TAXA_ERRO_GLOBAL",
            "nivel": "warning",
            "valor": round(taxa_erro * 100, 2),
            "limite": f"{ERRO_LIMITE * 100}%",
            "descricao": f"Taxa de erro global em {taxa_erro * 100:.1f}%"
        })
    if tempo_medio > TEMPO_LIMITE:
        alertas.append({
            "tipo": "TEMPO_MEDIO_ELEVADO",
            "nivel": "warning",
            "valor": round(tempo_medio, 2),
            "limite": f"{TEMPO_LIMITE}s",
            "descricao": f"Tempo médio de execução em {tempo_medio:.2f}s"
        })

    for tipo, dados in metrics_store["por_tipo"].items():
        execucoes = dados["execucoes"]
        erros = dados["erros"]
        tempo_total_tipo = dados["tempo_total"]
        if execucoes == 0:
            continue
        taxa_erro_tipo = erros / execucoes
        tempo_medio_tipo = tempo_total_tipo / execucoes
        if taxa_erro_tipo > ERRO_LIMITE:
            alertas.append({
                "tipo": "TAXA_ERRO_ENGINE",
                "nivel": "warning",
                "engine": tipo,
                "valor": round(taxa_erro_tipo * 100, 2),
                "descricao": f"Engine {tipo} com {taxa_erro_tipo * 100:.1f}% de erros"
            })
        if tempo_medio_tipo > TEMPO_LIMITE:
            alertas.append({
                "tipo": "ENGINE_LENTA",
                "nivel": "warning",
                "engine": tipo,
                "valor": round(tempo_medio_tipo, 2),
                "descricao": f"Engine {tipo} com tempo médio de {tempo_medio_tipo:.2f}s"
            })
    return alertas


def _status_engines():
    """Retorna status detalhado de cada engine."""
    agora = time.time()
    engines = {}
    for tipo in ["tax_planning", "tax_recovery", "empresa_tax"]:
        bloqueado_ate = engine_blocked_until.get(tipo)
        degradado_ate = degraded_engines.get(tipo)
        falhas = engine_failures.get(tipo, 0)
        versao = engine_versions.get(tipo, "v1")
        ab_config = engine_ab_testing.get(tipo)

        status = "ok"
        if bloqueado_ate and agora < bloqueado_ate:
            status = "circuit_open"
        elif degradado_ate and agora < degradado_ate:
            status = "degraded"

        engines[tipo] = {
            "status": status,
            "versao": versao,
            "falhas_consecutivas": falhas,
            "circuit_breaker": {
                "aberto": status == "circuit_open",
                "bloqueado_ate": bloqueado_ate if bloqueado_ate and agora < bloqueado_ate else None,
            },
            "autoprotecao": {
                "degradada": status == "degraded",
                "degradada_ate": degradado_ate if degradado_ate and agora < degradado_ate else None,
            },
            "ab_testing": ab_config if ab_config else None,
        }
    return engines


@router.get("/metrics")
def obter_metricas(usuario_atual=Depends(get_usuario_atual)):
    """
    Retorna o estado arquitetural completo da plataforma:
    - métricas operacionais
    - status das engines
    - circuit breaker
    - cache
    - alertas
    - detecção de regressão / autoproteção
    - fallback automático (indicado no status das engines degradadas)
    """
    total_execucoes = metrics_store["total_execucoes"]
    total_erros = metrics_store["total_erros"]
    tempo_total = metrics_store["tempo_total"]
    tempo_medio = tempo_total / total_execucoes if total_execucoes > 0 else 0

    metricas_operacionais = {
        "total_execucoes": total_execucoes,
        "total_erros": total_erros,
        "tempo_total": round(tempo_total, 4),
        "tempo_medio": round(tempo_medio, 4),
        "por_tipo": metrics_store["por_tipo"],
    }

    engines = _status_engines()
    alertas = _calcular_alertas()

    return {
        "metricas_operacionais": metricas_operacionais,
        "engines": engines,
        "circuit_breaker": {
            "engines_bloqueadas": [
                t for t, s in engines.items()
                if s["status"] == "circuit_open"
            ],
            "bloqueios_ativos": {
                t: s["circuit_breaker"]["bloqueado_ate"]
                for t, s in engines.items()
                if s["circuit_breaker"]["bloqueado_ate"]
            },
        },
        "cache": {
            "entradas": len(analysis_cache),
            "ativo": True,
        },
        "alertas": alertas,
        "deteccao_regressao": {
            "engines_degradadas": [
                t for t, s in engines.items()
                if s["status"] == "degraded"
            ],
            "autoprotecao_ativada": any(s["status"] == "degraded" for s in engines.values()),
            "fallback_automatico": "Engines degradadas retornam resposta simplificada via engine_fallback_service",
        },
    }
