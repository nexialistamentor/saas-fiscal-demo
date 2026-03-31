import uuid
import time

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends, Request
from typing import List

from app.main import limiter
from app.security import get_usuario_atual
from app.services.analysis_orchestrator import executar_analise_xml
from app.xml_security import validar_upload_xml
from app import models

router = APIRouter()

jobs = {}
MAX_JOBS = 100


def processar_lote(job_id, files_bytes):
    jobs[job_id]["status"] = "processing"
    total = len(files_bytes)
    resultados = []
    try:
        for i, conteudo in enumerate(files_bytes):
            resultado = executar_analise_xml(conteudo)
            resultados.append(resultado)

            jobs[job_id]["processed_files"] = i + 1
            jobs[job_id]["progress"] = int((i + 1) / total * 100)

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["resultados"] = resultados
        jobs[job_id]["progress"] = 100
        jobs[job_id]["finished_at"] = time.time()
        jobs[job_id]["duration_seconds"] = int(
            jobs[job_id]["finished_at"] - jobs[job_id]["created_at"]
        )
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["finished_at"] = time.time()
        jobs[job_id]["duration_seconds"] = int(
            jobs[job_id]["finished_at"] - jobs[job_id]["created_at"]
        )


@router.post("/analisar-lote")
@limiter.limit("3/minute")
async def analisar_lote(
    request: Request,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    files_bytes = []

    for file in files:
        conteudo = await validar_upload_xml(file)
        files_bytes.append(conteudo)

    job_id = str(uuid.uuid4())

    # Remove jobs com mais de 1 hora para evitar crescimento infinito da memória
    for jid in list(jobs.keys()):
        created = jobs[jid].get("created_at", 0)
        if time.time() - created > 3600:
            del jobs[jid]

    if len(jobs) >= MAX_JOBS:
        raise HTTPException(
            status_code=503,
            detail="Servidor ocupado, tente novamente em alguns minutos."
        )

    jobs[job_id] = {
        "status": "pending",
        "progress": 0,
        "processed_files": 0,
        "total_files": len(files_bytes),
        "resultados": None,
        "error": None,
        "created_at": time.time(),
        "user_id": usuario_atual.id,
    }

    background_tasks.add_task(processar_lote, job_id, files_bytes)

    return {
        "job_id": job_id,
        "status": "pending",
        "total_arquivos": len(files_bytes)
    }


@router.get("/job/{job_id}")
def consultar_job(
    job_id: str,
    usuario_atual: models.User = Depends(get_usuario_atual),
):
    """Consulta o status e resultado de um job de análise em lote."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = jobs[job_id]
    if job.get("user_id") != usuario_atual.id:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    status = job["status"]

    if status == "completed":
        return {
            "status": "completed",
            "progress": 100,
            "processed_files": job.get("total_files", 0),
            "total_files": job.get("total_files", 0),
            "resultados": job["resultados"],
            "duration_seconds": job.get("duration_seconds"),
            "finished_at": job.get("finished_at"),
        }
    if status == "failed":
        return {
            "status": "failed",
            "progress": job.get("progress", 0),
            "processed_files": job.get("processed_files", 0),
            "total_files": job.get("total_files", 0),
            "error": job.get("error", "Erro desconhecido"),
            "duration_seconds": job.get("duration_seconds"),
            "finished_at": job.get("finished_at"),
        }
    # pending ou processing → retorna processing para o cliente
    return {
        "status": status if status == "processing" else "processing",
        "progress": job.get("progress", 0),
        "processed_files": job.get("processed_files", 0),
        "total_files": job.get("total_files", 0),
    }
