"""
Router de formalização empresarial soberana — stateless V1.

Endpoints:
    POST /formalizacao/recomendar-cnae    — recomendação CNAE por actividade
    POST /formalizacao/comparar-regimes   — comparação tributária por regime
    POST /formalizacao/simular-empresa    — orquestração completa sem persistência

Princípio: router stateless — recomenda, não persiste.
Persistência é responsabilidade do utilizador via empresa_router.
"""

from decimal import Decimal
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.models import User
from app.security import get_usuario_atual
from app.services.cnae_engine import recomendar_cnaes
from app.services.regime_engine import comparar_regimes
from app.services.tax_engines.base_tax_engine import BaseTaxEngine, TempoNormativoAusenteError
from app.services.tax_engines.mei_constants import MEI_LIMITE_ANUAL_FATURAMENTO

router = APIRouter(prefix="/formalizacao", tags=["formalizacao"])


def _exigir_tempo_normativo(
    ano_referencia: Optional[int] = None,
    data_referencia: Optional[date] = None,
) -> int:
    """Resolve ano normativo — bloqueia se ausente (B13-OPS-13A)."""
    ctx: dict = {}
    if ano_referencia is not None:
        ctx["ano_referencia"] = ano_referencia
    if data_referencia is not None:
        ctx["data_referencia"] = data_referencia
    return BaseTaxEngine().resolver_ano_referencia(ctx)


def _validar_faturamento_positivo(cls, v: Decimal) -> Decimal:
    if v is None or v <= 0:
        raise ValueError("O faturamento anual deve ser maior que zero")
    return v


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------
class RecomendarCnaeRequest(BaseModel):
    descricao_actividade: str = Field(..., min_length=3, max_length=500)
    porte: str = Field(default="me", pattern="^(mei|me|epp|medio|grande)$")
    max_resultados: int = Field(default=5, ge=1, le=20)


class CompararRegimesRequest(BaseModel):
    faturamento_anual: Decimal = Field(...)
    folha_anual: Decimal = Field(default=Decimal("0"), ge=0)
    lucro_contabil: Optional[Decimal] = None
    secao_cnae: str = Field(default="J", min_length=1, max_length=2)
    atividade: str = Field(default="servicos")
    regimes_permitidos: Optional[list[str]] = None
    ano_referencia: Optional[int] = Field(default=None, ge=2000, le=2100)
    data_referencia: Optional[date] = None

    _validar_faturamento = field_validator("faturamento_anual")(_validar_faturamento_positivo)


class SimularEmpresaRequest(BaseModel):
    descricao_actividade: str = Field(..., min_length=3, max_length=500)
    porte: str = Field(default="me", pattern="^(mei|me|epp|medio|grande)$")
    faturamento_anual: Decimal = Field(default=Decimal("0"), ge=0)
    folha_anual: Decimal = Field(default=Decimal("0"), ge=0)
    lucro_contabil: Optional[Decimal] = None
    atividade: str = Field(default="servicos")
    ano_referencia: Optional[int] = Field(default=None, ge=2000, le=2100)
    data_referencia: Optional[date] = None
    data_referencia: Optional[date] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/recomendar-cnae")
def recomendar_cnae(
    body: RecomendarCnaeRequest,
    usuario: User = Depends(get_usuario_atual),
):
    """
    Recomenda CNAEs com score heurístico dado perfil do utilizador.
    Stateless — não persiste nada.
    """
    resultado = recomendar_cnaes(
        descricao_actividade=body.descricao_actividade,
        porte=body.porte,
        max_resultados=body.max_resultados,
    )

    return {
        "cnae_principal": _serializar_cnae(resultado.cnae_principal_sugerido),
        "cnaes_secundarios": [_serializar_cnae(c) for c in resultado.cnaes_secundarios_sugeridos],
        "score_confianca": resultado.score_confianca,
        "permite_mei": resultado.permite_mei,
        "motivo_nao_mei": resultado.motivo_nao_mei,
        "regimes_compativeis": resultado.regimes_compativeis,
        "palavras_detectadas": resultado.palavras_detectadas,
        "justificativa": resultado.justificativa,
    }


@router.post("/comparar-regimes")
def comparar_regimes_endpoint(
    body: CompararRegimesRequest,
    usuario: User = Depends(get_usuario_atual),
):
    """
    Compara regimes tributários e recomenda o mais vantajoso.
    Stateless — não persiste nada.
    """
    try:
        ano_referencia = _exigir_tempo_normativo(body.ano_referencia, body.data_referencia)
        resultado = comparar_regimes(
            faturamento_anual=body.faturamento_anual,
            folha_anual=body.folha_anual,
            lucro_contabil=body.lucro_contabil,
            secao_cnae=body.secao_cnae,
            atividade=body.atividade,
            regimes_permitidos=body.regimes_permitidos,
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

    return {
        "regime_recomendado": resultado.regime_recomendado,
        "economia_anual_vs_pior": str(resultado.economia_anual_vs_pior),
        "justificativa": resultado.justificativa,
        "regimes_inelegiveis": resultado.regimes_inelegiveis,
        "regimes_nao_avaliados": resultado.regimes_nao_avaliados,
        "resultados": {
            regime: _serializar_resultado_regime(r)
            for regime, r in resultado.resultados.items()
        },
    }


@router.post("/simular-empresa")
def simular_empresa(
    body: SimularEmpresaRequest,
    usuario: User = Depends(get_usuario_atual),
):
    """
    Orquestra CNAE + regime tributário numa simulação completa.
    Stateless — não persiste nada.
    Frontend nunca deve fazer esta orquestração.
    """
    # 1. Recomendar CNAE
    resultado_cnae = recomendar_cnaes(
        descricao_actividade=body.descricao_actividade,
        porte=body.porte,
    )

    if not resultado_cnae.cnae_principal_sugerido:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Não foi possível identificar CNAE para a actividade descrita",
        )

    secao_cnae = resultado_cnae.cnae_principal_sugerido.secao

    # 2. Filtrar regimes pelo CNAE
    regimes_para_comparar = [
        r for r in resultado_cnae.regimes_compativeis
        if r != "mei" or body.porte == "mei"
    ]

    # 3. Comparar regimes
    try:
        ano_referencia = _exigir_tempo_normativo(body.ano_referencia, body.data_referencia)
        resultado_regime = comparar_regimes(
            faturamento_anual=body.faturamento_anual,
            folha_anual=body.folha_anual,
            lucro_contabil=body.lucro_contabil,
            secao_cnae=secao_cnae,
            atividade=body.atividade,
            regimes_permitidos=regimes_para_comparar,
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

    permite_mei = resultado_cnae.permite_mei
    motivo_nao_mei = resultado_cnae.motivo_nao_mei
    alertas_mei: list[str] = []

    if body.porte == "mei" and body.faturamento_anual >= MEI_LIMITE_ANUAL_FATURAMENTO:
        alertas_mei.append(
            f"Faturamento anual (R$ {body.faturamento_anual:,.2f}) ultrapassa o limite MEI "
            f"de R$ {MEI_LIMITE_ANUAL_FATURAMENTO:,.2f}"
        )
        permite_mei = False
        motivo_nao_mei = motivo_nao_mei or "Faturamento acima do limite anual permitido para MEI"

    return {
        "cnae_recomendado": _serializar_cnae(resultado_cnae.cnae_principal_sugerido),
        "secao_cnae": secao_cnae,
        "permite_mei": permite_mei,
        "motivo_nao_mei": motivo_nao_mei,
        "alertas_mei": alertas_mei,
        "regime_recomendado": resultado_regime.regime_recomendado,
        "economia_anual_vs_pior": str(resultado_regime.economia_anual_vs_pior),
        "regimes_compativeis": resultado_cnae.regimes_compativeis,
        "regimes_inelegiveis": resultado_regime.regimes_inelegiveis,
        "regimes_nao_avaliados": resultado_regime.regimes_nao_avaliados,
        "resultados_regime": {
            regime: _serializar_resultado_regime(r)
            for regime, r in resultado_regime.resultados.items()
        },
        "justificativa_cnae": resultado_cnae.justificativa,
        "justificativa_regime": resultado_regime.justificativa,
        "palavras_detectadas": resultado_cnae.palavras_detectadas,
    }


# ---------------------------------------------------------------------------
# Helpers de serialização
# ---------------------------------------------------------------------------
def _serializar_cnae(cnae) -> Optional[dict]:
    if cnae is None:
        return None
    return {
        "codigo": cnae.codigo_subclasse,
        "descricao": cnae.descricao,
        "secao": cnae.secao,
        "codigo_classe": cnae.codigo_classe,
        "versao_cnae": cnae.versao_cnae,
    }


def _serializar_resultado_regime(r) -> dict:
    return {
        "regime": r.regime,
        "carga_anual": str(r.carga_anual),
        "carga_mensal": str(r.carga_mensal),
        "aliquota_efetiva_pct": r.aliquota_efetiva_pct,
        "anexo_simples": r.anexo_simples,
        "fator_r": r.fator_r,
        "alertas": r.alertas,
    }
