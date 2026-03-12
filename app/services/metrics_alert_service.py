import logging
import time

from sqlalchemy.orm import Session

from app.models import MetricasSnapshot
from app.services.analysis_orchestrator import degraded_engines, metrics_store

logger = logging.getLogger(__name__)

ERRO_LIMITE = 0.05   # 5%
TEMPO_LIMITE = 2.0   # segundos


def verificar_alertas_metricas():
    total_execucoes = metrics_store["total_execucoes"]
    total_erros = metrics_store["total_erros"]
    tempo_total = metrics_store["tempo_total"]

    if total_execucoes == 0:
        return

    taxa_erro = total_erros / total_execucoes
    tempo_medio = tempo_total / total_execucoes

    if taxa_erro > ERRO_LIMITE:
        logger.warning(
            "alerta_taxa_erro",
            extra={
                "taxa_erro": taxa_erro,
                "total_execucoes": total_execucoes
            }
        )

    if tempo_medio > TEMPO_LIMITE:
        logger.warning(
            "alerta_tempo_execucao",
            extra={
                "tempo_medio": tempo_medio
            }
        )

    for tipo, dados in metrics_store["por_tipo"].items():
        execucoes = dados["execucoes"]
        erros = dados["erros"]
        tempo_total = dados["tempo_total"]

        if execucoes == 0:
            continue

        taxa_erro = erros / execucoes
        tempo_medio = tempo_total / execucoes

        if taxa_erro > ERRO_LIMITE:
            logger.warning(
                "alerta_engine_taxa_erro",
                extra={
                    "analysis_type": tipo,
                    "taxa_erro": taxa_erro,
                    "execucoes": execucoes
                }
            )

        if tempo_medio > TEMPO_LIMITE:
            logger.warning(
                "alerta_engine_lentidao",
                extra={
                    "analysis_type": tipo,
                    "tempo_medio": tempo_medio
                }
            )


def verificar_regressao_performance(db: Session):
    """
    Detecta quando o tempo médio atual de uma engine piora significativamente
    em relação ao histórico salvo em metricas_snapshot.
    Regra: tempo_medio_atual > 2x tempo_medio_historico
    """
    snapshots = (
        db.query(MetricasSnapshot)
        .order_by(MetricasSnapshot.criado_em.desc())
        .limit(2)
        .all()
    )
    # Precisa do snapshot anterior como baseline (o mais recente é o atual)
    if len(snapshots) < 2:
        return
    historico = snapshots[1].por_tipo
    if not historico:
        return

    for tipo, dados in metrics_store["por_tipo"].items():
        execucoes = dados["execucoes"]
        tempo_total = dados["tempo_total"]

        if execucoes == 0:
            continue

        tempo_medio_atual = tempo_total / execucoes

        if tipo not in historico:
            continue

        exec_hist = historico[tipo]["execucoes"]
        tempo_hist = historico[tipo]["tempo_total"]

        if exec_hist == 0:
            continue

        tempo_medio_hist = tempo_hist / exec_hist

        if tempo_medio_atual > tempo_medio_hist * 2:
            degraded_engines[tipo] = time.time() + 300

            logger.warning(
                "alerta_regressao_performance",
                extra={
                    "analysis_type": tipo,
                    "tempo_medio_atual": tempo_medio_atual,
                    "tempo_medio_historico": tempo_medio_hist,
                },
            )
