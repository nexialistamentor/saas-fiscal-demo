from fastapi import APIRouter
from pydantic import BaseModel
from app.services.cpf_dashboard_service import CPFDashboardService

router = APIRouter(prefix="/cpf", tags=["CPF"])


class CPFRequest(BaseModel):
    faturamento_mensal: float
    despesas: float = 0


@router.post("/dashboard")
def dashboard_cpf(dados: CPFRequest):
    service = CPFDashboardService()
    return service.calcular_resumo(
        faturamento_mensal=dados.faturamento_mensal,
        despesas=dados.despesas
    )
