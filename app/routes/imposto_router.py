import base64
import binascii
from datetime import date, datetime
from functools import lru_cache
import json
import math
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.rate_limit import limiter
from app.security import tenant_empresa
from app.services.analysis_orchestrator import executar_analise
from app.services.imposto_service import calcular_imposto_simples, calcular_imposto_simples_nacional
from app.services.serpro_pgmei_composition import compose_serpro_pgmei
from app.services.tax_engines.base_tax_engine import (
    LimiteSimplesNacionalExcedidoError,
    TempoNormativoAusenteError,
)
from app.services.tax_engines.mei_constants import (
    MEI_LIMITE_ANUAL_FATURAMENTO,
    atividade_mei_reconhecida,
)

router = APIRouter()

_CNPJ_CANONICO = re.compile(r"[A-Z0-9]{12}[0-9]{2}", flags=re.ASCII)
_CNPJ_MASCARADO = re.compile(
    r"([A-Z0-9]{2})\.([A-Z0-9]{3})\.([A-Z0-9]{3})/([A-Z0-9]{4})-([0-9]{2})",
    flags=re.ASCII,
)
_SERVICOS_PGMEI = {
    "pdf": "GERARDASPDF21",
    "codigo_barras": "GERARDASCODBARRA22",
}
_MOTIVOS_NAO_EMISSAO = {
    "[Aviso-PGMEI-MSG_13011]": "DEBITO_EM_DIVIDA_ATIVA",
    "[Aviso-PGMEI-MSG_23017]": "VALOR_INFERIOR_MINIMO",
    "[Aviso-PGMEI-MSG_23018]": "PERIODO_JA_PAGO",
    "[Aviso-PGMEI-MSG_23019]": "SEM_DAS_A_EMITIR",
}
_NUMERO_DOCUMENTO = re.compile(r"[0-9]{17}", flags=re.ASCII)
_CODIGO_BARRAS = re.compile(r"[0-9]{12}", flags=re.ASCII)


class MeiDasOficialRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    periodo_apuracao: str
    formato: Literal["pdf", "codigo_barras"]

    @field_validator("periodo_apuracao")
    @classmethod
    def validar_periodo_apuracao(cls, value: str) -> str:
        if (
            not isinstance(value, str)
            or len(value) != 6
            or not value.isascii()
            or not value.isdigit()
            or not 1 <= int(value[4:]) <= 12
        ):
            raise ValueError("periodo_apuracao invalido")
        return value


@lru_cache(maxsize=1)
def _get_serpro_pgmei_client():
    """Compose lazily and retain the OAuth-backed client across requests."""
    return compose_serpro_pgmei()


def _bloqueio(status_code: int, tipo_bloqueio: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "bloqueado": True,
            "estado_l3": "bloqueado",
            "tipo_bloqueio": tipo_bloqueio,
        },
    )


def _cnpj_canonico(value: object) -> str | None:
    if not isinstance(value, str) or not value.isascii():
        return None
    upper = value.upper()
    if _CNPJ_CANONICO.fullmatch(upper):
        return upper
    match = _CNPJ_MASCARADO.fullmatch(upper)
    if match is None:
        return None
    return "".join(match.groups())


def _data_oficial(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 8 or not value.isascii() or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return False
    return True


def _normalizar_documento_oficial(
    dados_oficiais: str,
    formato: str,
    cnpj: str,
    periodo_apuracao: str,
) -> dict:
    payload = json.loads(dados_oficiais)
    if type(payload) is not list or len(payload) != 1 or type(payload[0]) is not dict:
        raise ValueError("resposta oficial divergente")

    documento = payload[0]
    if documento.get("cnpjCompleto") != cnpj:
        raise ValueError("cnpj oficial divergente")

    detalhamento = documento.get("detalhamento")
    if formato == "pdf":
        if type(detalhamento) is not dict:
            raise ValueError("detalhamento oficial divergente")
    else:
        if type(detalhamento) is not list or len(detalhamento) != 1 or type(detalhamento[0]) is not dict:
            raise ValueError("detalhamento oficial divergente")
        detalhamento = detalhamento[0]

    valores = detalhamento.get("valores")
    if type(valores) is not dict:
        raise ValueError("valores oficiais divergentes")
    total = valores.get("total")
    if isinstance(total, bool) or not isinstance(total, (int, float)) or not math.isfinite(total) or total < 0:
        raise ValueError("total oficial divergente")

    numero_documento = detalhamento.get("numeroDocumento")
    if not isinstance(numero_documento, str) or _NUMERO_DOCUMENTO.fullmatch(numero_documento) is None:
        raise ValueError("numero oficial divergente")
    if detalhamento.get("periodoApuracao") != periodo_apuracao:
        raise ValueError("periodo oficial divergente")
    data_vencimento = detalhamento.get("dataVencimento")
    data_limite = detalhamento.get("dataLimiteAcolhimento")
    if not _data_oficial(data_vencimento) or not _data_oficial(data_limite):
        raise ValueError("data oficial divergente")

    normalizado = {
        "cnpj": cnpj,
        "periodo_apuracao": periodo_apuracao,
        "numero_documento": numero_documento,
        "data_vencimento": data_vencimento,
        "data_limite_acolhimento": data_limite,
        "valor_total": total,
    }
    if formato == "pdf":
        pdf_base64 = documento.get("pdf")
        if not isinstance(pdf_base64, str):
            raise ValueError("pdf oficial divergente")
        try:
            pdf = base64.b64decode(pdf_base64, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("pdf oficial divergente") from None
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("pdf oficial divergente")
        normalizado["pdf_base64"] = pdf_base64
    else:
        codigo_barras = detalhamento.get("codigoDeBarras")
        if (
            type(codigo_barras) is not list
            or len(codigo_barras) != 4
            or any(
                not isinstance(bloco, str) or _CODIGO_BARRAS.fullmatch(bloco) is None
                for bloco in codigo_barras
            )
        ):
            raise ValueError("codigo de barras oficial divergente")
        normalizado["codigo_barras"] = codigo_barras
    return normalizado


def _motivo_nao_emissao(messages: object) -> str:
    if type(messages) is not list or len(messages) != 1 or type(messages[0]) is not dict:
        raise ValueError("mensagem oficial divergente")
    codigo = messages[0].get("codigo")
    if not isinstance(codigo, str) or codigo not in _MOTIVOS_NAO_EMISSAO:
        raise ValueError("mensagem oficial divergente")
    return _MOTIVOS_NAO_EMISSAO[codigo]


@router.post("/mei/{empresa_id}/das")
@limiter.limit("5/minute")
def obter_das_mei_oficial(
    request: Request,
    dados: MeiDasOficialRequest,
    empresa=Depends(tenant_empresa),
):
    if getattr(empresa, "status_empresa", None) != "ativa":
        raise _bloqueio(422, "EMPRESA_MEI_INATIVA")
    if getattr(empresa, "regime_tributario", None) != "mei":
        raise _bloqueio(422, "EMPRESA_NAO_MEI")

    cnpj = _cnpj_canonico(getattr(empresa, "cnpj", None))
    if cnpj is None:
        raise _bloqueio(422, "CNPJ_EMPRESA_INVALIDO")

    try:
        client = _get_serpro_pgmei_client()
    except Exception:
        raise _bloqueio(503, "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL") from None
    if client is None:
        raise _bloqueio(503, "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL")

    servico = _SERVICOS_PGMEI[dados.formato]
    try:
        resultado = client.request(servico, cnpj, dados.periodo_apuracao)
        dados_oficiais = resultado.data
        if not isinstance(dados_oficiais, str):
            raise ValueError("resposta oficial divergente")
        if not dados_oficiais.strip():
            motivo = _motivo_nao_emissao(resultado.messages)
            return {
                "empresa_id": empresa.id,
                "periodo_apuracao": dados.periodo_apuracao,
                "formato": dados.formato,
                "servico": servico,
                "origem_oficial": "SERPRO_PGMEI",
                "estado_oficial": "nao_emitido",
                "motivo_oficial": motivo,
                "documento": None,
            }
        documento = _normalizar_documento_oficial(
            dados_oficiais,
            dados.formato,
            cnpj,
            dados.periodo_apuracao,
        )
    except Exception:
        raise _bloqueio(502, "AUTORIDADE_OFICIAL_MEI_FALHOU") from None

    return {
        "empresa_id": empresa.id,
        "periodo_apuracao": dados.periodo_apuracao,
        "formato": dados.formato,
        "servico": servico,
        "origem_oficial": "SERPRO_PGMEI",
        "estado_oficial": "emitido",
        "documento": documento,
    }


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
    if dados.tipo_usuario.upper() == "MEI":
        raise HTTPException(
            status_code=422,
            detail={
                "bloqueado": True,
                "tipo_bloqueio": "APLICABILIDADE_MEI_INSUFICIENTE",
                "estado_l3": "bloqueado",
            },
        )

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
