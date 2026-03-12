import hashlib
import json
import logging
import random
import signal
import time

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
    "tax_planning": "v1",
    "tax_recovery": "v1",
    "empresa_tax": "v1"
}

engine_ab_testing = {
    "tax_recovery": {
        "enabled": False,
        "candidate_version": "v2",
        "traffic_percentage": 20
    }
}


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
    inicio_execucao = time.time()

    cache_input = {
        "tipo": tipo,
        "dados": dados,
        "empresa": getattr(empresa, "id", None)
    }
    cache_key = hashlib.sha256(
        json.dumps(cache_input, sort_keys=True, default=str).encode()
    ).hexdigest()

    if cache_key in analysis_cache:
        logger.info(
            "analysis_cache_hit",
            extra={"analysis_type": tipo}
        )
        return analysis_cache[cache_key]

    agora = time.time()
    if tipo in engine_blocked_until and agora < engine_blocked_until[tipo]:
        logger.warning(
            "engine_circuit_open",
            extra={"analysis_type": tipo}
        )
        return {
            "analysis_type": tipo,
            "erro": "engine_temporarily_disabled",
            "mensagem": "Engine temporariamente desativada por falhas recentes"
        }

    if tipo in degraded_engines and agora < degraded_engines[tipo]:
        fallback = gerar_fallback(tipo, dados)
        logger.warning(
            "engine_fallback_ativado",
            extra={"analysis_type": tipo}
        )
        return fallback

    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(3)

    if tipo == "tax_planning":
        try:
            versao = escolher_versao_engine(tipo)
            engine = ENGINE_REGISTRY[tipo][versao]
            resultado = engine(dados)
            if isinstance(resultado, dict):
                resultado["analysis_type"] = "tax_planning"

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": tipo,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[tipo] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(tipo, tempo_execucao, True)
            return resultado
        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(tipo, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": tipo}
            )
            return {
                "analysis_type": tipo,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[tipo] = engine_failures.get(tipo, 0) + 1
            if engine_failures[tipo] >= MAX_FAILURES:
                engine_blocked_until[tipo] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": tipo}
                )
            logger.exception("Erro no motor tax_planning")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": tipo,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(tipo, tempo_execucao, False)
            return {
                "analysis_type": "tax_planning",
                "erro": "tax_planning_engine",
                "mensagem": "Falha ao executar planejamento tributário"
            }

    if tipo == "tax_recovery":
        try:
            versao = escolher_versao_engine(tipo)
            engine = ENGINE_REGISTRY[tipo][versao]
            resultado = engine(dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = "tax_recovery"

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": tipo,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[tipo] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(tipo, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(tipo, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": tipo}
            )
            return {
                "analysis_type": tipo,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[tipo] = engine_failures.get(tipo, 0) + 1
            if engine_failures[tipo] >= MAX_FAILURES:
                engine_blocked_until[tipo] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": tipo}
                )
            logger.exception("Erro no motor tax_recovery")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": tipo,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(tipo, tempo_execucao, False)
            return {
                "analysis_type": "tax_recovery",
                "erro": "tax_recovery_engine",
                "mensagem": "Falha ao executar análise de recuperação tributária"
            }

    if tipo == "empresa_tax":
        try:
            versao = escolher_versao_engine(tipo)
            engine = ENGINE_REGISTRY[tipo][versao]
            resultado = engine(empresa, dados)

            if isinstance(resultado, dict):
                resultado["analysis_type"] = "empresa_tax"

            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)

            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.info(
                "engine_executada",
                extra={
                    "analysis_type": tipo,
                    "engine_version": versao,
                    "tempo_execucao": tempo_execucao
                }
            )
            engine_failures[tipo] = 0
            analysis_cache[cache_key] = resultado
            registrar_metricas(tipo, tempo_execucao, True)
            return resultado

        except EngineTimeout:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            registrar_metricas(tipo, tempo_execucao, False)
            logger.warning(
                "engine_timeout",
                extra={"analysis_type": tipo}
            )
            return {
                "analysis_type": tipo,
                "erro": "engine_timeout",
                "mensagem": "Tempo limite da análise excedido"
            }
        except Exception:
            if hasattr(signal, "SIGALRM"):
                signal.alarm(0)
            engine_failures[tipo] = engine_failures.get(tipo, 0) + 1
            if engine_failures[tipo] >= MAX_FAILURES:
                engine_blocked_until[tipo] = time.time() + BLOCK_TIME
                logger.warning(
                    "engine_circuit_breaker_activated",
                    extra={"analysis_type": tipo}
                )
            logger.exception("Erro no motor empresa_tax")
            tempo_execucao = round(time.time() - inicio_execucao, 4)
            logger.warning(
                "engine_falhou",
                extra={
                    "analysis_type": tipo,
                    "tempo_execucao": tempo_execucao
                }
            )
            registrar_metricas(tipo, tempo_execucao, False)
            return {
                "analysis_type": "empresa_tax",
                "erro": "empresa_tax_engine",
                "mensagem": "Falha ao executar cálculo tributário empresarial"
            }

    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)
    logger.warning(f"Tipo de análise desconhecido: {tipo}")
    return {
        "erro": "analysis_type_invalid",
        "mensagem": f"Tipo de análise '{tipo}' não suportado"
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
