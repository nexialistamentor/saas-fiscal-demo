import hashlib
import json
import logging
import random
import signal
import threading
import time

from app.services.analysis_types import (
    ANALYSIS_TYPE_CPF_TAX,
    ANALYSIS_TYPE_EMPRESA_TAX,
    ANALYSIS_TYPE_MEI_TAX,
    ANALYSIS_TYPE_TAX_PLANNING,
    ANALYSIS_TYPE_TAX_RECOVERY,
)
from app.motor_fiscal import analisar_xml
from app.services.engine_fallback_service import gerar_fallback
from app.services.engine_registry import ENGINE_REGISTRY

logger = logging.getLogger(__name__)

# Coletor passivo de métricas
metrics_store = {
    "total_execucoes": 0,
    "total_erros": 0,
    "tempo_total": 0.0,
    "por_tipo": {}
}


def registrar_metricas(tipo: str, tempo_execucao: float, sucesso: bool):
    metrics_store["total_execucoes"] += 1
    metrics_store["tempo_total"] += tempo_execucao

    if not sucesso:
        metrics_store["total_erros"] += 1

    if tipo not in metrics_store["por_tipo"]:
        metrics_store["por_tipo"][tipo] = {
            "execucoes": 0,
            "erros": 0,
            "tempo_total": 0.0
        }

    metrics_store["por_tipo"][tipo]["execucoes"] += 1
    metrics_store["por_tipo"][tipo]["tempo_total"] += tempo_execucao

    if not sucesso:
        metrics_store["por_tipo"][tipo]["erros"] += 1


# Circuit Breaker: memória de falhas e bloqueio temporário
engine_failures = {}
engine_blocked_until = {}

degraded_engines = {}
DEGRADED_TIME = 300  # 5 minutos

MAX_FAILURES = 5
BLOCK_TIME = 120  # segundos

analysis_cache = {}

engine_versions = {
    ANALYSIS_TYPE_TAX_PLANNING: "v1",
    ANALYSIS_TYPE_TAX_RECOVERY: "v1",
    ANALYSIS_TYPE_EMPRESA_TAX: "v1",
    ANALYSIS_TYPE_CPF_TAX: "v1",
    ANALYSIS_TYPE_MEI_TAX: "v1",
}

engine_ab_testing = {
    ANALYSIS_TYPE_TAX_RECOVERY: {
        "enabled": False,
        "candidate_version": "v2",
        "traffic_percentage": 20
    }
}


def _canonical_analysis_type(tipo: str) -> str:
    """Resolve o valor recebido para a constante canônica (L2: uma fonte por tipo)."""
    if tipo == ANALYSIS_TYPE_TAX_PLANNING:
        return ANALYSIS_TYPE_TAX_PLANNING
    if tipo == ANALYSIS_TYPE_TAX_RECOVERY:
        return ANALYSIS_TYPE_TAX_RECOVERY
    if tipo == ANALYSIS_TYPE_EMPRESA_TAX:
        return ANALYSIS_TYPE_EMPRESA_TAX
    if tipo == ANALYSIS_TYPE_CPF_TAX:
        return ANALYSIS_TYPE_CPF_TAX
    if tipo == ANALYSIS_TYPE_MEI_TAX:
        return ANALYSIS_TYPE_MEI_TAX
    return tipo


def escolher_versao_engine(tipo: str):
    config = engine_ab_testing.get(tipo)

    if not config or not config["enabled"]:
        return engine_versions.get(tipo, "v1")

    porcentagem = config["traffic_percentage"]

    if random.randint(1, 100) <= porcentagem:
        return config["candidate_version"]

    return engine_versions.get(tipo, "v1")


class EngineTimeout(Exception):
    pass


def timeout_handler(signum, frame):
    raise EngineTimeout("Tempo limite da engine excedido")


def executar_analise(tipo: str, dados: dict, empresa=None):
    """
    Orquestrador central: delega para o motor correto conforme o tipo de análise.
    Fluxo: assistente → analysis_orchestrator → motor específico
    """
    t = _canonical_analysis_type(tipo)
    inicio_execucao = time.time()

    cache_input = {
        "tipo": t,
        "dados": dados,
        "empresa": getattr(empresa, "id", None)
    }
    cache_key = hashlib.sha256(
        json.dumps(cache_input, sort_keys=True, default=str).encode()
    ).hexdigest()

    if cache_key in analysis_cache:
        logger.info(
            "analysis_cache_hit",
            extra={"analysis_type": t}
        )
        return analysis_cache[cache_key]

    agora = time.time()
    if t in engine_blocked_until and agora < engine_blocked_until[t]:
        logger.warning(
            "engine_circuit_open",
            extra={"analysis_type": t}
        )
        return {
            "analysis_type": t,
            "erro": "engine_temporarily_disabled",
            "mensagem": "Engine temporariamente desativada por falhas recentes"
        }

    if t in degraded_engines and agora < degraded_engines[t]:
        fallback = gerar_fallback(t, dados)
        logger.warning(
            "engine_fallback_ativado",
            extra={"analysis_type": t}
        )
        return fallback

    if hasattr(signal, "SIGALRM"):
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(3)

    if t == ANALYSIS_TYPE_TAX_PLANNING:
        try:
            versao = escolher_versao_engine(t)
            engine = ENGINE_REGISTRY[t][versao]
            resultado = engine(dados)
            if isinstance(resultado, dict):
                resultado["analysis_type"] = ANALYSIS_TYPE_TAX_PLANNING

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": ANALYSIS_TYPE_TAX_PLANNING,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[t] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(t, tempo_execucao, True)
            return resultado
        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(t, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": ANALYSIS_TYPE_TAX_PLANNING}
            )
            return {
                "analysis_type": ANALYSIS_TYPE_TAX_PLANNING,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[t] = engine_failures.get(t, 0) + 1
            if engine_failures[t] >= MAX_FAILURES:
                engine_blocked_until[t] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": ANALYSIS_TYPE_TAX_PLANNING}
                )
            logger.exception("Erro no motor tax_planning")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": ANALYSIS_TYPE_TAX_PLANNING,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_TAX_PLANNING,
                "erro": "tax_planning_engine",
                "mensagem": "Falha ao executar planejamento tributário"
            }

    if t == ANALYSIS_TYPE_TAX_RECOVERY:
        try:
            versao = escolher_versao_engine(t)
            engine = ENGINE_REGISTRY[t][versao]
            resultado = engine(dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = ANALYSIS_TYPE_TAX_RECOVERY

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": ANALYSIS_TYPE_TAX_RECOVERY,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[t] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(t, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(t, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": ANALYSIS_TYPE_TAX_RECOVERY}
            )
            return {
                "analysis_type": ANALYSIS_TYPE_TAX_RECOVERY,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[t] = engine_failures.get(t, 0) + 1
            if engine_failures[t] >= MAX_FAILURES:
                engine_blocked_until[t] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": ANALYSIS_TYPE_TAX_RECOVERY}
                )
            logger.exception("Erro no motor tax_recovery")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": ANALYSIS_TYPE_TAX_RECOVERY,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_TAX_RECOVERY,
                "erro": "tax_recovery_engine",
                "mensagem": "Falha ao executar análise de recuperação tributária"
            }

    if t == ANALYSIS_TYPE_EMPRESA_TAX:
        try:
            versao = escolher_versao_engine(t)
            engine = ENGINE_REGISTRY[t][versao]
            resultado = engine(empresa, dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = ANALYSIS_TYPE_EMPRESA_TAX

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": ANALYSIS_TYPE_EMPRESA_TAX,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[t] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(t, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(t, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": ANALYSIS_TYPE_EMPRESA_TAX}
            )
            return {
                "analysis_type": ANALYSIS_TYPE_EMPRESA_TAX,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[t] = engine_failures.get(t, 0) + 1
            if engine_failures[t] >= MAX_FAILURES:
                engine_blocked_until[t] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": ANALYSIS_TYPE_EMPRESA_TAX}
                )
            logger.exception("Erro no motor empresa_tax")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": ANALYSIS_TYPE_EMPRESA_TAX,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_EMPRESA_TAX,
                "erro": "empresa_tax_engine",
                "mensagem": "Falha ao executar cálculo tributário empresarial"
            }

    if t == ANALYSIS_TYPE_CPF_TAX:
        try:
            versao = escolher_versao_engine(t)
            engine = ENGINE_REGISTRY[t][versao]
            resultado = engine(dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = ANALYSIS_TYPE_CPF_TAX

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": ANALYSIS_TYPE_CPF_TAX,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[t] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(t, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_CPF_TAX,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[t] = engine_failures.get(t, 0) + 1
            if engine_failures[t] >= MAX_FAILURES:
                engine_blocked_until[t] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": ANALYSIS_TYPE_CPF_TAX}
                )
            logger.exception("Erro no motor cpf_tax")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": ANALYSIS_TYPE_CPF_TAX,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_CPF_TAX,
                "erro": "cpf_tax_engine",
                "mensagem": "Falha ao executar cálculo tributário para CPF"
            }

    if t == ANALYSIS_TYPE_MEI_TAX:
        try:
            versao = escolher_versao_engine(t)
            engine = ENGINE_REGISTRY[t][versao]
            resultado = engine(dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = ANALYSIS_TYPE_MEI_TAX

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": ANALYSIS_TYPE_MEI_TAX,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[t] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(t, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_MEI_TAX,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[t] = engine_failures.get(t, 0) + 1
            if engine_failures[t] >= MAX_FAILURES:
                engine_blocked_until[t] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": ANALYSIS_TYPE_MEI_TAX}
                )
            logger.exception("Erro no motor mei_tax")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": ANALYSIS_TYPE_MEI_TAX,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(t, tempo_execucao, False)
            return {
                "analysis_type": ANALYSIS_TYPE_MEI_TAX,
                "erro": "mei_tax_engine",
                "mensagem": "Falha ao executar cálculo tributário para MEI"
            }

    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)
    logger.warning(f"Tipo de análise desconhecido: {t}")
    return {
        "erro": "analysis_type_invalid",
        "mensagem": f"Tipo de análise '{t}' não suportado"
    }


# --- Análise de XML (usada por fiscal_router, lote_router, relatorio_router) ---


def _gerar_insights_por_xml(dados_fiscais: dict) -> list:
    """
    Gera insights básicos a partir dos dados fiscais extraídos do XML.
    Para análise completa com empresa_id, use insights_engine.InsightEngine.
    """
    insights = []

    if dados_fiscais.get("erro"):
        return insights

    icms_st = _to_float(dados_fiscais.get("icms_st"))
    valor_total = _to_float(dados_fiscais.get("valor_total_nota"))
    mva = dados_fiscais.get("mva_percentual")

    if icms_st and icms_st > 0:
        insights.append({
            "tipo": "ICMS_ST_IDENTIFICADO",
            "impacto": "informativo",
            "valor_estimado": round(icms_st, 2),
            "descricao": f"ICMS-ST de R$ {round(icms_st, 2)} identificado na NF-e.",
            "recomendacao": "Verificar elegibilidade para crédito ou restituição."
        })

    if valor_total and valor_total > 0 and mva:
        insights.append({
            "tipo": "MVA_APLICADA",
            "impacto": "informativo",
            "descricao": f"MVA de {mva}% aplicada na operação.",
            "recomendacao": "Conferir MVA oficial do estado para o NCM."
        })

    return insights


def _calcular_previsao_por_xml(dados_fiscais: dict) -> dict:
    """
    Calcula estimativa de potencial de recuperação com base nos dados do XML.
    Para análise completa com empresa_id, use motor_preditivo_service.calcular_potencial_recuperacao.
    """
    icms_st = _to_float(dados_fiscais.get("icms_st"))

    if icms_st and icms_st > 0:
        potencial = round(icms_st * 0.15, 2)
        return {
            "potencial_recuperacao_nota": potencial,
            "icms_st_nota": round(icms_st, 2),
            "metodo": "estimativa_baseada_st_xml"
        }

    return {"potencial_recuperacao_nota": 0, "metodo": "sem_st_identificada"}


def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def executar_analise_xml(xml_bytes: bytes) -> dict:
    """
    Orquestra a análise fiscal completa: extrai dados do XML, gera insights
    e calcula previsão de recuperação.

    Fluxo: motor_fiscal -> insights -> previsão -> resultado final
    """
    dados_fiscais = analisar_xml(xml_bytes)
    insights = _gerar_insights_por_xml(dados_fiscais)
    previsao = _calcular_previsao_por_xml(dados_fiscais)

    resultado = {
        "dados_fiscais": dados_fiscais,
        "insights": insights,
        "previsao_recuperacao": previsao
    }

    return resultado
