from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AliasChoices, BaseModel, Field
from app.services.analysis_orchestrator import executar_analise
from app.services.imposto_service import calcular_imposto_simples, calcular_imposto_simples_nacional
from app.services.tax_engines.base_tax_engine import (
    LimiteSimplesNacionalExcedidoError,
    TempoNormativoAusenteError,
)
from app.services.tax_engines.mei_constants import (
    MEI_LIMITE_ANUAL_FATURAMENTO,
    atividade_mei_reconhecida,
)

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
        ctx_cpf: dict = {
            "faturamento": dados.faturamento_mensal,
            "despesas": dados.despesas,
        }
        if dados.ano_referencia is not None:
            ctx_cpf["ano_referencia"] = dados.ano_referencia
        try:
            resultado = executar_analise("cpf_tax", ctx_cpf)
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

        imposto = resultado.get("tributos", {}).get("imposto", 0)

        return {
            "tipo": "cpf",
            "imposto_mensal": imposto,
            "imposto_anual": imposto * 12,
            "alertas": resultado.get("alertas", []),
            "_ano_referencia": resultado.get("_ano_referencia"),
            "_estado_temporal": resultado.get("_estado_temporal"),
        }

    if tipo == "mei":
        if (dados.atividade is None or dados.atividade == "") and dados.ano_referencia is not None:
            raise HTTPException(
                status_code=422,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": "ATIVIDADE_MEI_AUSENTE",
                    "estado_l3": "bloqueado",
                },
            )
        if (
            dados.atividade is not None
            and dados.atividade != ""
            and not atividade_mei_reconhecida(dados.atividade)
        ):
            raise HTTPException(
                status_code=422,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": "ATIVIDADE_MEI_INVALIDA",
                    "estado_l3": "bloqueado",
                },
            )
        if dados.ano_referencia is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "bloqueado": True,
                    "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
                    "estado_l3": "bloqueado",
                },
            )

        raise HTTPException(
            status_code=503,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL",
                "estado_l3": "bloqueado",
                "erro": (
                    "O DAS fiscal final do MEI nao pode ser publicado sem "
                    "autoridade operacional oficial."
                ),
            },
        )

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
        "alertas": alertas,
        "_ano_referencia": mensal.get("_ano_referencia"),
        "_estado_temporal": mensal.get("_estado_temporal"),
    }


class SimplesNacionalRequest(BaseModel):
    """Simulação DAS para empresa no Simples Nacional."""
    rbt12: float  # Receita bruta últimos 12 meses (R$)
    receita_mes: float | None = None  # Receita do mês (opcional, default: rbt12/12)
    anexo: Literal["I", "II", "III", "IV", "V"]
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
    except LimiteSimplesNacionalExcedidoError:
        raise HTTPException(
            status_code=422,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "LIMITE_SIMPLES_NACIONAL_EXCEDIDO",
                "estado_l3": "bloqueado",
                "erro": 'O faturamento informado excede o limite suportado por esta simulação do Simples Nacional.',
            },
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
