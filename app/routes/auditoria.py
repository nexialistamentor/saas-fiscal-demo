from fastapi import APIRouter
from app.agents.agent_estoque import salvar_auditoria

router = APIRouter()


@router.get("/auditar")
def auditar_estoque():

    salvar_auditoria(empresa_id=1)

    return {"status": "auditoria executada"}
