from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AliasChoices, BaseModel, Field
from app.services.analysis_orchestrator import executar_analise
from app.services.imposto_service import calcular_imposto_simples, calcular_imposto_simples_nacional
from app.services.tax_engines.base_tax_engine import TempoNormativoAusenteError
from app.services.tax_engines.mei_constants import MEI_LIMITE_ANUAL_FATURAMENTO

router = APIRouter()


class DadosImposto(BaseModel):
    tipo_usuario: Literal["CPF", "MEI"]
    faturamento_mensal: float
    despesas: float = 0
    atividade: str | None = Field(
        default=None,
        validation_alias=AliasChoices("atividade", "atividade_mei"),
    )
    ano_referencia: int | None = Field(default=None, ge=2000, le=2100)


class SimulacaoAnual(BaseModel):
    tipo_usuario: Literal["CPF", "MEI"]
    faturamento_mensal: float
    despesas: float = 0
    atividade: str | None = Field(
        default=None,
        validation_alias=AliasChoices("atividade", "atividade_mei"),
    )
    ano_referencia: int | None = Field(default=None, ge=2000, le=2100)


@router.post("/calcular")
def calcular_imposto(dados: DadosImposto):

    tipo = dados.tipo_usuario.lower()

    if tipo == "cpf":
        resultado = executar_analise(
            "cpf_tax",
            {
                "faturamento": dados.faturamento_mensal,
                "despesas": dados.despesas
            }
        )

        imposto = resultado.get("tributos", {}).get("imposto", 0)

        return {
            "tipo": "cpf",
            "imposto_mensal": imposto,
            "imposto_anual": imposto * 12,
            "alertas": resultado.get("alertas", [])
        }

    if tipo == "mei":
        ctx_mei = {"faturamento": dados.faturamento_mensal}
        if dados.atividade:
            ctx_mei["atividade"] = dados.atividade
        if dados.ano_referencia is not None:
            ctx_mei["ano_referencia"] = dados.ano_referencia
        try:
            resultado = executar_analise(
                "mei_tax",
                ctx_mei,
            )
        except TempoNormativoAusenteError as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
                    "estado_l3": "bloqueado",
                    "erro": str(e),
                },
            )

        das = resultado.get("tributos", {}).get("das", 0)

        return {
            "tipo": "mei",
            "imposto_mensal": das,
            "imposto_anual": das * 12,
            "alertas": resultado.get("alertas", [])
        }

    return {
        "erro": "tipo_nao_suportado"
    }


@router.post("/simular-ano")
def simular_ano(dados: SimulacaoAnual):
    try:
        mensal = calcular_imposto_simples(
            faturamento=dados.faturamento_mensal,
            despesas=dados.despesas,
            tipo=dados.tipo_usuario,
            atividade=dados.atividade,
            ano_referencia=dados.ano_referencia,
        )
    except TempoNormativoAusenteError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
                "estado_l3": "bloqueado",
                "erro": str(e),
            },
        )

    imposto_mensal = mensal["imposto"]

    faturamento_anual = dados.faturamento_mensal * 12
    imposto_anual = imposto_mensal * 12

    alertas = mensal.get("alertas", [])

    # alerta adicional para limite do MEI
    if dados.tipo_usuario.upper() == "MEI" and faturamento_anual >= MEI_LIMITE_ANUAL_FATURAMENTO:
        alertas.append("Faturamento anual ultrapassa limite do MEI")

    percentual_limite_mei = round((faturamento_anual / MEI_LIMITE_ANUAL_FATURAMENTO) * 100, 2)
    valor_restante_limite = max(0, MEI_LIMITE_ANUAL_FATURAMENTO - faturamento_anual)

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
    anexo: Literal["I", "II", "III", "IV", "V"] = "I"
    ano_referencia: int | None = Field(default=None, ge=2000, le=2100)
    data_referencia: date | None = None


@router.post("/simples-nacional")
def calcular_simples_nacional(dados: SimplesNacionalRequest):
    """
    Calcula DAS estimado para empresa no Simples Nacional.
    Anexos: I (comércio), II (indústria), III (serviços), IV (INSS sep.), V (intelectual).
    """
    ano_referencia = dados.ano_referencia
    if ano_referencia is None and dados.data_referencia is not None:
        ano_referencia = dados.data_referencia.year
    try:
        resultado = calcular_imposto_simples_nacional(
            rbt12=dados.rbt12,
            receita_mes=dados.receita_mes,
            anexo=dados.anexo,
            ano_referencia=ano_referencia,
        )
    except TempoNormativoAusenteError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
                "estado_l3": "bloqueado",
                "erro": str(e),
            },
        )
    return resultado
