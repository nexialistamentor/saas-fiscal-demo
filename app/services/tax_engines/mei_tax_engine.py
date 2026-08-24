from decimal import Decimal

from app.schemas.source_authority_schema import SourceAuthorityRequest
from app.services.source_authority_guard import verificar
from app.services.tax_engines.base_tax_engine import BaseTaxEngine
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


def _exigir_autoridade_normativa_mei() -> None:
    raise AutoridadeNormativaMEIIndisponivelError(
        motivo="BINDING_MISSING",
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
        ano_referencia = self.resolver_ano_referencia(context)
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

        _exigir_autoridade_normativa_mei()

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
