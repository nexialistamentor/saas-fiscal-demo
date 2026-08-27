from decimal import Decimal

from app.schemas.source_authority_schema import SourceAuthorityRequest
from app.services.source_authority_guard import (
    carregar_binding_normativo_mei_das_2026,
    validar_bindings_normativos,
    verificar,
)
from app.services.tax_engines.base_tax_engine import BaseTaxEngine
from app.services.tax_engines.mei_temporal import (
    resolver_data_referencia_mei,
)
from app.services.tax_engines.mei_constants import (
    MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE,
    MEI_LIMITE_ANUAL_FATURAMENTO,
    calcular_das_mei,
    normalizar_atividade_mei,
    obter_salario_minimo,
)


class AutoridadeFiscalIndisponivelError(RuntimeError):
    codigo = "AUTORIDADE_OFICIAL_MEI_INDISPONIVEL"

    def __init__(self, *, fonte_id: str, motivo: str):
        self.fonte_id = fonte_id
        self.motivo = motivo
        super().__init__(f"{self.codigo}: {fonte_id}: {motivo}")


class AutoridadeNormativaMEIIndisponivelError(RuntimeError):
    codigo = "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL"

    def __init__(self, *, motivo: str):
        self.motivo = motivo
        super().__init__(f"{self.codigo}: {motivo}")


def _exigir_autoridade_normativa_mei(
    *,
    modo: str,
    data_referencia,
) -> None:
    if data_referencia.year != 2026:
        raise AutoridadeNormativaMEIIndisponivelError(
            motivo="BINDING_FORA_DO_ANO_2026",
        )

    payload = carregar_binding_normativo_mei_das_2026()
    contexto_binding = payload.get("contexto")
    if not isinstance(contexto_binding, dict):
        raise AutoridadeNormativaMEIIndisponivelError(
            motivo="CONTEXTO_BINDING_INVALIDO",
        )

    uso_binding = contexto_binding.get("uso_solicitado")
    if uso_binding != modo:
        raise AutoridadeNormativaMEIIndisponivelError(
            motivo=f"BINDING_INCOMPATIVEL_COM_MODO_{modo.upper()}",
        )

    bindings = payload.get("bindings")
    if not isinstance(bindings, (list, tuple)) or len(bindings) != 3:
        raise AutoridadeNormativaMEIIndisponivelError(
            motivo="QUANTIDADE_BINDINGS_INVALIDA",
        )

    contexto_binding["data_referencia"] = data_referencia.isoformat()
    resultado = validar_bindings_normativos(payload)
    if (
        not resultado.autorizado_fundamentar_decisao
        or resultado.bindings_validados != 3
    ):
        raise AutoridadeNormativaMEIIndisponivelError(
            motivo="BINDING_NAO_AUTORIZADO",
        )


class MEITaxEngine(BaseTaxEngine):
    """
    Engine MEI extraída do legado (imposto_service).

    Regras:
    - DAS: 5% do salário mínimo + parcela fixa (ICMS comércio/indústria ou ISS serviços)
    - Limite anual: R$ 81.000
    """

    name = "mei_tax"

    def execute(self, context: dict):
        if "modo" not in context:
            modo = "decisao_definitiva"
        else:
            modo = context["modo"]
            if not isinstance(modo, str) or modo not in {
                "estimativa",
                "decisao_definitiva",
            }:
                raise ValueError("modo MEI invalido")

        data_referencia = resolver_data_referencia_mei(context)
        ano_referencia = data_referencia.year
        faturamento = context.get("faturamento")
        if faturamento is None:
            raise ValueError("faturamento ausente")
        faturamento_mensal = float(faturamento)

        faturamento_anual_informado = context.get("faturamento_anual")
        if faturamento_anual_informado is None:
            # Retrocompatibilidade: callers mensais antigos mantêm a projeção existente.
            faturamento_anual = faturamento_mensal * 12
            faturamento_anual_para_limite = Decimal(str(faturamento_anual))
        else:
            # Quando o fato anual existe, ele é a autoridade para decisões anuais.
            faturamento_anual_para_limite = Decimal(str(faturamento_anual_informado))
            faturamento_anual = float(faturamento_anual_para_limite)

        atividade = context.get("atividade")
        if atividade is None:
            atividade = context.get("atividade_mei")

        if modo == "decisao_definitiva":
            autoridade = verificar(
                SourceAuthorityRequest(
                    fonte_id="PGMEI-001",
                    uso_pretendido="validar_fato_operacional",
                )
            )
            if not autoridade.permitido:
                raise AutoridadeFiscalIndisponivelError(
                    fonte_id=autoridade.fonte_id,
                    motivo=autoridade.motivo,
                )

        _exigir_autoridade_normativa_mei(
            modo=modo,
            data_referencia=data_referencia,
        )

        sal_min = obter_salario_minimo(ano_referencia)
        imposto = calcular_das_mei(sal_min, atividade)

        alertas = []

        # Limite legal é anual. Se o anual foi informado, ele prevalece sobre projeções.
        limite_anual = Decimal(str(MEI_LIMITE_ANUAL_FATURAMENTO))
        alerta_proximo_limite = Decimal(str(MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE))
        if faturamento_anual_para_limite >= limite_anual:
            alertas.append("faturamento excedeu o limite anual do MEI")
        elif faturamento_anual_para_limite >= alerta_proximo_limite:
            alertas.append("faturamento próximo do limite anual")

        return {
            "regime": "mei",
            "modo": modo,
            "tributos": {
                "das": imposto
            },
            "bases_calculo": {
                "faturamento_mensal": faturamento_mensal,
                "faturamento_anual": faturamento_anual,
                "atividade": normalizar_atividade_mei(atividade),
            },
            "alertas": alertas,
            "_ano_referencia": ano_referencia,
            "_estado_temporal": "resolvido",
        }
