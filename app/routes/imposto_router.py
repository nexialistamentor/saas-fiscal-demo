from fastapi import APIRouter
from pydantic import BaseModel
from app.services.imposto_service import calcular_imposto_simples, calcular_imposto_simples_nacional

router = APIRouter()


class DadosImposto(BaseModel):
    tipo_usuario: str  # CPF ou MEI
    faturamento_mensal: float
    despesas: float = 0


class SimulacaoAnual(BaseModel):
    tipo_usuario: str
    faturamento_mensal: float
    despesas: float = 0


@router.post("/calcular")
def calcular_imposto(dados: DadosImposto):
    resultado = calcular_imposto_simples(
        faturamento=dados.faturamento_mensal,
        despesas=dados.despesas,
        tipo=dados.tipo_usuario,
    )

    preview = {
        "tipo_usuario": dados.tipo_usuario,
        "imposto_estimado": resultado["imposto"],
        "alertas": resultado.get("alertas", []),
    }

    return preview


@router.post("/simular-ano")
def simular_ano(dados: SimulacaoAnual):
    mensal = calcular_imposto_simples(
        faturamento=dados.faturamento_mensal,
        despesas=dados.despesas,
        tipo=dados.tipo_usuario
    )

    imposto_mensal = mensal["imposto"]

    faturamento_anual = dados.faturamento_mensal * 12
    imposto_anual = imposto_mensal * 12

    alertas = mensal.get("alertas", [])

    # alerta adicional para limite do MEI
    if dados.tipo_usuario.upper() == "MEI" and faturamento_anual > 81000:
        alertas.append("Faturamento anual ultrapassa limite do MEI")

    percentual_limite_mei = round((faturamento_anual / 81000) * 100, 2)
    valor_restante_limite = max(0, 81000 - faturamento_anual)

    return {
        "tipo_usuario": dados.tipo_usuario,
        "faturamento_anual": faturamento_anual,
        "imposto_anual_estimado": imposto_anual,
        "percentual_limite_mei": percentual_limite_mei,
        "valor_restante_limite": valor_restante_limite,
        "alertas": alertas
    }


class SimplesNacionalRequest(BaseModel):
    """Simulação DAS para empresa no Simples Nacional."""
    rbt12: float  # Receita bruta últimos 12 meses (R$)
    receita_mes: float | None = None  # Receita do mês (opcional, default: rbt12/12)
    anexo: str = "I"  # I, II, III, IV ou V


@router.post("/simples-nacional")
def calcular_simples_nacional(dados: SimplesNacionalRequest):
    """
    Calcula DAS estimado para empresa no Simples Nacional.
    Anexos: I (comércio), II (indústria), III (serviços), IV (INSS sep.), V (intelectual).
    """
    resultado = calcular_imposto_simples_nacional(
        rbt12=dados.rbt12,
        receita_mes=dados.receita_mes,
        anexo=dados.anexo,
    )
    return resultado
