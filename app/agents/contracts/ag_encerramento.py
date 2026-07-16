
"""

app/agents/contracts/ag_encerramento.py — ADR-010 B14.3B.



Contratos Pydantic específicos do canário AgEncerramentoAgent (MEI).

Módulo puro: não importa agentes operacionais, ORM, BD, HTTP, serviços ou providers.

"""



from __future__ import annotations



from datetime import datetime, timedelta

from types import MappingProxyType

from typing import Literal, Protocol, Self



from pydantic import (

    AwareDatetime,

    BaseModel,

    ConfigDict,

    StrictInt,

    field_validator,

    model_validator,

)



from app.constants import (

    AVISO_ENCERRAMENTO_IRREVERSIVEL,

    CHECKLIST_ENCERRAMENTO,

)





TIPOS_VALIDOS_ENCERRAMENTO: frozenset[str] = frozenset({"mei"})



AVISOS_LEGAIS_ENCERRAMENTO: tuple[str, ...] = (

    "Débitos não quitados migram para o CPF do titular.",

    "Documentos fiscais devem ser guardados 5 anos (CTN art. 195).",

    "Consulte um contador antes de iniciar o encerramento.",

)





class AgEncerramentoContext(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    empresa_id: StrictInt

    tipo_contribuinte: str = "mei"



    @field_validator("empresa_id")

    @classmethod

    def validar_empresa_id(cls, value: int) -> int:

        if value <= 0:

            raise ValueError("empresa_id deve ser positivo")

        return value



    @field_validator("tipo_contribuinte", mode="before")

    @classmethod

    def validar_tipo_contribuinte(cls, value: object) -> str:

        if value is None:

            raise ValueError("tipo_contribuinte não pode ser None")

        if isinstance(value, bool) or not isinstance(value, str):

            raise ValueError("tipo_contribuinte deve ser string")

        normalizado = value.strip().casefold()

        if not normalizado:

            raise ValueError("tipo_contribuinte não pode ser vazio")

        if normalizado != "mei":

            raise ValueError("tipo_contribuinte não suportado neste canário")

        return normalizado





class EncerramentoAccessDeniedError(Exception):

    """Empresa inexistente ou não autorizada para o tenant."""

    pass





class EncerramentoDataUnavailableError(Exception):

    """Dados não puderam ser obtidos ou validados com segurança."""

    pass





class EncerramentoPendenciaSnapshot(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    empresa_id: StrictInt

    reference_at: AwareDatetime

    total_insights_ativos: StrictInt



    estado_ultimo_relatorio: Literal[

        "ausente",

        "timestamp_ausente",

        "timestamp_naive",

        "timestamp_aware",

    ]

    ultimo_relatorio_em: AwareDatetime | None



    @model_validator(mode="after")

    def validar_invariantes(self) -> Self:

        if self.empresa_id <= 0:

            raise ValueError("empresa_id deve ser positivo")

        if self.total_insights_ativos < 0:

            raise ValueError("total_insights_ativos não pode ser negativo")

        if self.reference_at.utcoffset() != timedelta(0):

            raise ValueError("reference_at deve estar em UTC")

        if self.estado_ultimo_relatorio in {

            "ausente",

            "timestamp_ausente",

            "timestamp_naive",

        }:

            if self.ultimo_relatorio_em is not None:

                raise ValueError(

                    "estado sem timestamp não admite ultimo_relatorio_em"

                )

        if self.estado_ultimo_relatorio == "timestamp_aware":

            if self.ultimo_relatorio_em is None:

                raise ValueError("timestamp_aware exige ultimo_relatorio_em")

            if self.ultimo_relatorio_em.utcoffset() != timedelta(0):

                raise ValueError("ultimo_relatorio_em deve estar em UTC")

            if self.ultimo_relatorio_em > self.reference_at:

                raise ValueError("ultimo_relatorio_em não pode ser futuro")

        return self


# ---------------------------------------------------------------------------
# Porta read-only do reader
# ---------------------------------------------------------------------------

class EncerramentoPendenciaReader(Protocol):
    """
    Porta síncrona e read-only para obtenção do snapshot de encerramento.

    A implementação concreta pode conhecer SQLAlchemy, mas a porta não expõe
    sessão, ORM, transacção ou qualquer outro detalhe de persistência.
    """

    def obter_snapshot(
        self,
        *,
        tenant_id: int,
        actor_id: int,
        empresa_id: int,
        reference_at: datetime,
    ) -> EncerramentoPendenciaSnapshot:
        ...


class AgEncerramentoCommercialDisclosure(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    platform_service_requires_payment: Literal[True] = True

    official_process_cost_separate: Literal[True] = True

    pricing_status: Literal["pendente_ratificacao"] = "pendente_ratificacao"

    pricing_policy_id: None = None

    price_amount: None = None

    currency: Literal["BRL"] = "BRL"

    requires_explicit_consent: Literal[True] = True





class AgEncerramentoChecklistItem(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    passo: StrictInt

    titulo: str

    descricao: str

    severidade: Literal["alta", "media"] | None = None

    link: str | None = None





CHECKLIST_ENCERRAMENTO_CANONICO: tuple[AgEncerramentoChecklistItem, ...] = tuple(

    AgEncerramentoChecklistItem.model_validate(item)

    for item in CHECKLIST_ENCERRAMENTO

)





AlertaEncerramentoCode = Literal[

    "INSIGHTS_ATIVOS",

    "RELATORIO_AUSENTE",

    "RELATORIO_TIMESTAMP_AUSENTE",

    "RELATORIO_TIMESTAMP_NAIVE",

    "RELATORIO_DESACTUALIZADO",

]



ALERTAS_ENCERRAMENTO_CANONICOS: MappingProxyType[str, tuple[str, str]] = MappingProxyType({

    "INSIGHTS_ATIVOS": (

        "alto",

        "Existem análises fiscais activas que devem ser revistas antes do encerramento.",

    ),

    "RELATORIO_AUSENTE": (

        "medio",

        "Nenhum relatório fiscal foi encontrado para esta empresa.",

    ),

    "RELATORIO_TIMESTAMP_AUSENTE": (

        "medio",

        "Existe relatório fiscal sem data registada; confirme-o antes do encerramento.",

    ),

    "RELATORIO_TIMESTAMP_NAIVE": (

        "medio",

        "A data do relatório fiscal não pôde ser validada temporalmente.",

    ),

    "RELATORIO_DESACTUALIZADO": (

        "medio",

        "O relatório fiscal tem pelo menos 120 dias; confirme a situação actual.",

    ),

})





class AgEncerramentoAlertaPlataforma(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    code: AlertaEncerramentoCode

    severidade: Literal["alto", "medio"]

    descricao_publica: str

    quantidade: StrictInt | None = None



    @model_validator(mode="after")

    def validar_contrato(self) -> Self:

        severidade_esperada, mensagem_esperada = ALERTAS_ENCERRAMENTO_CANONICOS[self.code]

        if self.severidade != severidade_esperada:

            raise ValueError("severidade diverge da tabela canónica")

        if self.descricao_publica != mensagem_esperada:

            raise ValueError("descricao_publica diverge da tabela canónica")

        if self.code == "INSIGHTS_ATIVOS":

            if self.quantidade is None or self.quantidade <= 0:

                raise ValueError("INSIGHTS_ATIVOS exige quantidade positiva")

        elif self.quantidade is not None:

            raise ValueError("apenas INSIGHTS_ATIVOS admite quantidade")

        return self





ReviewReasonEncerramento = Literal[

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

    "TEMPORAL_EVIDENCE_INCOMPLETE",

]



BASE_REVIEW_REASONS_ENCERRAMENTO: tuple[ReviewReasonEncerramento, ...] = (

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

)



TEMPORAL_REVIEW_REASONS_ENCERRAMENTO: tuple[ReviewReasonEncerramento, ...] = (

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

    "TEMPORAL_EVIDENCE_INCOMPLETE",

)





class AgEncerramentoPayload(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    resposta: str

    analysis_type: Literal["encerramento_empresa"] = "encerramento_empresa"

    schema_type: Literal["HowTo"] = "HowTo"

    versao: Literal["1.0"] = "1.0"

    tipo_contribuinte: Literal["mei"] = "mei"



    checklist: tuple[AgEncerramentoChecklistItem, ...]

    avisos_legais: tuple[str, ...]

    alertas_plataforma: tuple[AgEncerramentoAlertaPlataforma, ...]

    aviso_irreversivel: str



    commercial_disclosure: AgEncerramentoCommercialDisclosure

    review_reasons: tuple[ReviewReasonEncerramento, ...]

    publication_allowed: Literal[False] = False



    @model_validator(mode="after")

    def validar_alertas_e_review_reasons(self) -> Self:

        codigos = [a.code for a in self.alertas_plataforma]



        if len(codigos) != len(set(codigos)):

            raise ValueError("alertas_plataforma contém códigos duplicados")



        if len(self.alertas_plataforma) > 2:

            raise ValueError("no máximo dois alertas de plataforma")



        if codigos and "INSIGHTS_ATIVOS" in codigos and codigos[0] != "INSIGHTS_ATIVOS":

            raise ValueError("INSIGHTS_ATIVOS deve ser o primeiro alerta")



        codigos_relatorio = {

            "RELATORIO_AUSENTE",

            "RELATORIO_TIMESTAMP_AUSENTE",

            "RELATORIO_TIMESTAMP_NAIVE",

            "RELATORIO_DESACTUALIZADO",

        }

        alertas_relatorio = [c for c in codigos if c in codigos_relatorio]

        if len(alertas_relatorio) > 1:

            raise ValueError("no máximo um alerta de relatório")



        tem_alerta_temporal = bool(

            set(codigos) & {"RELATORIO_TIMESTAMP_AUSENTE", "RELATORIO_TIMESTAMP_NAIVE"}

        )

        if tem_alerta_temporal:

            if self.review_reasons != TEMPORAL_REVIEW_REASONS_ENCERRAMENTO:

                raise ValueError(

                    "alertas temporais exigem TEMPORAL_REVIEW_REASONS_ENCERRAMENTO"

                )

        else:

            if self.review_reasons != BASE_REVIEW_REASONS_ENCERRAMENTO:

                raise ValueError(

                    "ausência de alertas temporais exige BASE_REVIEW_REASONS_ENCERRAMENTO"

                )



        return self





AdapterEncerramentoPreExecutionErrorCode = Literal[

    "MISSION_TARGET_MISMATCH",

    "MISSION_TYPE_UNSUPPORTED",

    "CONTEXT_SCHEMA_UNSUPPORTED",

    "CONTEXT_VERSION_UNSUPPORTED",

    "OUTPUT_SCHEMA_UNSUPPORTED",

    "OUTPUT_VERSION_UNSUPPORTED",

    "MISSION_SCOPE_UNSUPPORTED",

    "MISSION_TENANT_REQUIRED",

    "MISSION_ACTOR_UNSUPPORTED",

    "MISSION_ACTOR_TENANT_MISMATCH",

    "MISSION_REFERENCE_AT_REQUIRED",

    "MISSION_AUTHORITY_UNSUPPORTED",

    "MISSION_ORIGIN_UNSUPPORTED",

    "MISSION_BUDGET_UNSUPPORTED",

    "MISSION_SOURCES_UNSUPPORTED",

    "AG_ENCERRAMENTO_TIPO_UNSUPPORTED",

    "AG_ENCERRAMENTO_CONTEXT_INVALID",

]





class AgEncerramentoPreExecutionError(Exception):

    def __init__(self, code: AdapterEncerramentoPreExecutionErrorCode) -> None:

        self.code = code

        super().__init__(code)





class AgEncerramentoResultValidationError(Exception):

    def __init__(self) -> None:

        self.code = "RESULT_MISSION_VALIDATION_FAILED"

        super().__init__(self.code)





class AgEncerramentoResultSafetyError(Exception):

    def __init__(self) -> None:

        self.code = "RESULT_SANITIZATION_FAILED"

        super().__init__(self.code)





RELATORIO_DESACTUALIZADO_APOS_DIAS: int = 120
