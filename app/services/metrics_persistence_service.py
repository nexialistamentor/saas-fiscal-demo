from sqlalchemy.orm import Session
from app.services.analysis_orchestrator import metrics_store
from app.models import MetricasSnapshot


def salvar_snapshot_metricas(db: Session):
    total_execucoes = metrics_store["total_execucoes"]
    total_erros = metrics_store["total_erros"]
    tempo_total = metrics_store["tempo_total"]

    tempo_medio = 0
    if total_execucoes > 0:
        tempo_medio = tempo_total / total_execucoes

    snapshot = MetricasSnapshot(
        total_execucoes=total_execucoes,
        total_erros=total_erros,
        tempo_total=tempo_total,
        tempo_medio=tempo_medio,
        por_tipo=metrics_store["por_tipo"]
    )

    db.add(snapshot)
    db.commit()
