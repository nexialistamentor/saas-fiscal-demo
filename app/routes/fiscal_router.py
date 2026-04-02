import os

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from rq.exceptions import NoSuchJobError
from rq.job import Job

from app.database import get_db
from app.jobs.analysis_job import processar_xml_job
from app.models import Empresa
from app.security import get_usuario_atual, verificar_empresa_do_usuario
from app.services.analysis_orchestrator import executar_analise_xml
from app.xml_security import validar_upload_xml
from sqlalchemy.orm import Session
from app import models

router = APIRouter()

_SYNC_JOB = "__sync_analysis__"


def _enqueue_or_run_sync(conteudo: bytes, empresa_id: int) -> dict:
    inline = os.getenv("ANALISE_XML_INLINE", "").strip().lower() in ("1", "true", "yes", "on")
    if inline:
        resultado = processar_xml_job(conteudo, empresa_id)
        if not resultado:
            return {"job_id": None, "status": "erro", "detail": "Análise não pôde ser registrada"}
        return {
            "job_id": _SYNC_JOB,
            "status": "finished",
            "result": {
                "relatorio_id": resultado.get("relatorio_id"),
                "tem_resultado": bool(resultado.get("tem_resultado")),
            },
        }
    try:
        from app.queue.redis_queue import analysis_queue, redis_conn

        redis_conn.ping()
        job = analysis_queue.enqueue(processar_xml_job, conteudo, empresa_id)
        return {"job_id": job.id}
    except Exception:
        resultado = processar_xml_job(conteudo, empresa_id)
        if not resultado:
            return {"job_id": None, "status": "erro", "detail": "Análise não pôde ser registrada"}
        return {
            "job_id": _SYNC_JOB,
            "status": "finished",
            "result": {
                "relatorio_id": resultado.get("relatorio_id"),
                "tem_resultado": bool(resultado.get("tem_resultado")),
            },
        }


@router.post("/analisar-xml")
async def analisar_xml_fiscal(
    file: UploadFile = File(...),
    empresa_id: int | None = None,
    db: Session = Depends(get_db),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """Analisa XML de NF-e. Persiste em relatorios_analise quando empresa_id informado."""
    conteudo = await validar_upload_xml(file)
    if empresa_id and db:
        verificar_empresa_do_usuario(empresa_id, usuario_atual, db)
        emp = db.query(Empresa).filter(Empresa.id == empresa_id).first()
        if emp:
            return _enqueue_or_run_sync(conteudo, empresa_id)
    resultado = executar_analise_xml(conteudo)
    return {
        "status": "XML analisado",
        "resultado": resultado,
    }


@router.get("/analise/status/{job_id}")
def status_job(job_id: str, usuario_atual: models.User = Depends(get_usuario_atual)):
    if job_id == _SYNC_JOB:
        return {
            "job_id": job_id,
            "status": "finished",
            "result": {"relatorio_id": None, "tem_resultado": False},
            "detail": "Use o resultado retornado no POST /analisar-xml (modo síncrono).",
        }
    from app.queue.redis_queue import redis_conn

    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.meta.get("owner_id") != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado a este job")

    resultado = job.result or {}
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": {
            "relatorio_id": resultado.get("relatorio_id"),
            "tem_resultado": True if resultado else False
        }
    }


@router.delete("/analise/cancelar/{job_id}")
def cancelar_job(job_id: str, usuario_atual: models.User = Depends(get_usuario_atual)):
    if job_id == _SYNC_JOB:
        return {"job_id": job_id, "status": "não aplicável (análise síncrona)"}
    from app.queue.redis_queue import redis_conn

    try:
        job = Job.fetch(job_id, connection=redis_conn)
    except NoSuchJobError:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    if job.meta.get("owner_id") != usuario_atual.id:
        raise HTTPException(status_code=403, detail="Acesso negado a este job")

    if job.is_finished:
        return {"status": "job já finalizado"}
    job.cancel()
    return {
        "job_id": job_id,
        "status": "cancelado",
    }
