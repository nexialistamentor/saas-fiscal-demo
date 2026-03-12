from fastapi import APIRouter, Depends, File, UploadFile
from rq.job import Job

from app.database import get_db
from app.jobs.analysis_job import processar_xml_job
from app.models import Empresa
from app.queue.redis_queue import analysis_queue, redis_conn
from app.security import get_usuario_atual, verificar_empresa_do_usuario
from app.services.analysis_orchestrator import executar_analise_xml
from app.xml_security import validar_upload_xml
from sqlalchemy.orm import Session
from app import models

router = APIRouter()


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
            job = analysis_queue.enqueue(processar_xml_job, conteudo, empresa_id)
            return {"job_id": job.id}
    resultado = executar_analise_xml(conteudo)
    return {
        "status": "XML analisado",
        "resultado": resultado,
    }


@router.get("/analise/status/{job_id}")
def status_job(job_id: str, usuario_atual: models.User = Depends(get_usuario_atual)):
    job = Job.fetch(job_id, connection=redis_conn)
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result,
    }


@router.delete("/analise/cancelar/{job_id}")
def cancelar_job(job_id: str, usuario_atual: models.User = Depends(get_usuario_atual)):
    job = Job.fetch(job_id, connection=redis_conn)
    if job.is_finished:
        return {"status": "job já finalizado"}
    job.cancel()
    return {
        "job_id": job_id,
        "status": "cancelado",
    }
