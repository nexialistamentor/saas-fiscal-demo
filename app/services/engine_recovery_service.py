import logging
import time

from app.services.analysis_orchestrator import degraded_engines
from app.services.analysis_orchestrator import metrics_store

logger = logging.getLogger(__name__)


def verificar_recuperacao_engines():
    agora = time.time()

    for tipo in list(degraded_engines.keys()):
        if agora < degraded_engines[tipo]:
            continue

        if tipo not in metrics_store["por_tipo"]:
            continue

        dados = metrics_store["por_tipo"][tipo]

        execucoes = dados["execucoes"]
        tempo_total = dados["tempo_total"]

        if execucoes == 0:
            continue

        tempo_medio = tempo_total / execucoes

        if tempo_medio < 1.5:
            del degraded_engines[tipo]

            logger.info(
                "engine_recuperada",
                extra={
                    "analysis_type": tipo,
                    "tempo_medio": tempo_medio
                }
            )
