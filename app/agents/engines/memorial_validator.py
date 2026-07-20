"""
Motor deterministico L3 para o MemorialValidatorAgent.

ADR-013 B14.3E.

Nao acede a BD, ORM, Session, HTTP, filesystem, LLM, servicos,
relogio, scheduler, registry, executor ou agente legado.
"""

from __future__ import annotations

from app.agents.contracts.memorial_validator import (
    ALERTAS_MEMORIAL_CANONICOS,
    INDICE_ALERTA_MEMORIAL,
    LIMIAR_ALERTAS_REVISAO,
    MemorialAlertCode,
    MemorialValidatorAlert,
    MemorialValidatorContext,
    MemorialValidatorPayload,
)


def _criar_alerta(
    codigo: MemorialAlertCode,
) -> MemorialValidatorAlert:
    """Constroi um alerta tipado a partir da tabela canonica."""
    severidade, mensagem = ALERTAS_MEMORIAL_CANONICOS[codigo]

    return MemorialValidatorAlert(
        codigo=codigo,
        severidade=severidade,
        mensagem=mensagem,
    )


def _fundamento_incompleto(
    fundamento: str | None,
) -> bool:
    """Avalia a completude do fundamento no caminho principal."""
    if fundamento is None:
        return True

    return fundamento.strip() == ""


def derivar_alertas_memorial(
    context: MemorialValidatorContext,
) -> tuple[MemorialValidatorAlert, ...]:
    """Deriva todos os alertas na ordem canonica, sem early return."""
    alertas: list[MemorialValidatorAlert] = []

    if context.relatorio is None:
        alertas.append(
            _criar_alerta("MEMORIAL_RELATORIO_AUSENTE")
        )

    if not context.engines:
        alertas.append(
            _criar_alerta("MEMORIAL_ENGINES_VAZIOS")
        )

    if not context.referencias_legais:
        alertas.append(
            _criar_alerta("MEMORIAL_REFERENCIAS_VAZIAS")
        )
    else:
        existe_referencia_incompleta = any(
            _fundamento_incompleto(referencia.fundamento)
            for referencia in context.referencias_legais
        )

        if existe_referencia_incompleta:
            alertas.append(
                _criar_alerta("MEMORIAL_REFERENCIA_INCOMPLETA")
            )

    if context.relatorio is not None:
        if context.relatorio.status == "erro":
            alertas.append(
                _criar_alerta("MEMORIAL_STATUS_ANALISE")
            )

        if (
            context.relatorio.total_alertas
            > LIMIAR_ALERTAS_REVISAO
        ):
            alertas.append(
                _criar_alerta("MEMORIAL_CONTAGEM_ALERTAS")
            )

    return tuple(alertas)


def construir_payload_memorial(
    context: MemorialValidatorContext,
) -> MemorialValidatorPayload:
    """Transforma o contexto no payload diagnostico canonico."""
    alertas = derivar_alertas_memorial(context)

    return MemorialValidatorPayload(
        analysis_type="validacao_memorial_fiscal",
        schema_type="MemorialValidatorPayload",
        versao="1.0",
        empresa_id=context.empresa_id,
        relatorio_id=context.relatorio_id,
        diagnostico_consistente=len(alertas) == 0,
        total_alertas=len(alertas),
        alertas=alertas,
        publication_allowed=False,
    )

def _reconstruir_codigos_independente(
    context: MemorialValidatorContext,
) -> tuple[MemorialAlertCode, ...]:
    """
    Reconstrói apenas os códigos esperados.

    Não chama o caminho principal nem reutiliza os seus helpers de
    transformação.
    """
    codigos: list[MemorialAlertCode] = []

    if context.relatorio is None:
        codigos.append("MEMORIAL_RELATORIO_AUSENTE")

    if len(context.engines) == 0:
        codigos.append("MEMORIAL_ENGINES_VAZIOS")

    if len(context.referencias_legais) == 0:
        codigos.append("MEMORIAL_REFERENCIAS_VAZIAS")
    else:
        referencia_incompleta = False

        for referencia in context.referencias_legais:
            fundamento = referencia.fundamento

            if fundamento is None:
                referencia_incompleta = True
                break

            if fundamento.strip() == "":
                referencia_incompleta = True
                break

        if referencia_incompleta:
            codigos.append("MEMORIAL_REFERENCIA_INCOMPLETA")

    relatorio = context.relatorio

    if relatorio is not None:
        if relatorio.status == "erro":
            codigos.append("MEMORIAL_STATUS_ANALISE")

        if relatorio.total_alertas > LIMIAR_ALERTAS_REVISAO:
            codigos.append("MEMORIAL_CONTAGEM_ALERTAS")

    if len(codigos) != len(set(codigos)):
        raise ValueError(
            "reconstrucao independente produziu codigos duplicados"
        ) from None

    indice_anterior: int | None = None

    for codigo in codigos:
        indice_actual = INDICE_ALERTA_MEMORIAL[codigo]

        if (
            indice_anterior is not None
            and indice_actual <= indice_anterior
        ):
            raise ValueError(
                "reconstrucao independente fora da ordem canonica"
            ) from None

        indice_anterior = indice_actual

    return tuple(codigos)

def validate_memorial_validator_payload_against_context(
    *,
    context: MemorialValidatorContext,
    payload: MemorialValidatorPayload,
) -> None:
    """
    Valida integralmente o payload contra a reconstrucao independente.

    Nao constroi outro MemorialValidatorPayload e nao reutiliza o caminho
    principal.
    """
    codigos_esperados = _reconstruir_codigos_independente(context)
    total_esperado = len(codigos_esperados)
    diagnostico_esperado = total_esperado == 0

    if payload.analysis_type != "validacao_memorial_fiscal":
        raise ValueError("analysis_type divergente") from None

    if payload.schema_type != "MemorialValidatorPayload":
        raise ValueError("schema_type divergente") from None

    if payload.versao != "1.0":
        raise ValueError("versao divergente") from None

    if payload.empresa_id != context.empresa_id:
        raise ValueError("empresa_id divergente") from None

    if payload.relatorio_id != context.relatorio_id:
        raise ValueError("relatorio_id divergente") from None

    if payload.diagnostico_consistente is not diagnostico_esperado:
        raise ValueError(
            "diagnostico_consistente divergente"
        ) from None

    if payload.total_alertas != total_esperado:
        raise ValueError("total_alertas divergente") from None

    if len(payload.alertas) != total_esperado:
        raise ValueError(
            "quantidade de alertas divergente"
        ) from None

    for alerta, codigo_esperado in zip(
        payload.alertas,
        codigos_esperados,
        strict=True,
    ):
        if not isinstance(alerta, MemorialValidatorAlert):
            raise ValueError("alerta com tipo invalido") from None

        severidade_esperada, mensagem_esperada = (
            ALERTAS_MEMORIAL_CANONICOS[codigo_esperado]
        )

        if alerta.codigo != codigo_esperado:
            raise ValueError(
                "codigo de alerta divergente"
            ) from None

        if alerta.severidade != severidade_esperada:
            raise ValueError(
                "severidade de alerta divergente"
            ) from None

        if alerta.mensagem != mensagem_esperada:
            raise ValueError(
                "mensagem de alerta divergente"
            ) from None

    if payload.publication_allowed is not False:
        raise ValueError(
            "publication_allowed divergente"
        ) from None