"""
app/agents/engines/data_sanitization.py — ADR-011 B14.3C.

Motor determinístico puro para o DataSanitizationAgent.
Não acede a BD, ORM, Session, HTTP, LLM, serviços, relógio
ou agente legado.
"""

from __future__ import annotations

from app.agents.contracts.data_sanitization import (
    ALERTAS_SANITIZACAO_CANONICOS,
    CAMPOS_FISCAIS_CANONICOS,
    LIMITE_FATURAMENTO,
    DataSanitizationAlert,
    DataSanitizationAlertCode,
    DataSanitizationContext,
    DataSanitizationField,
    DataSanitizationPayload,
)


def _criar_alerta(
    codigo: DataSanitizationAlertCode,
    *,
    campo: DataSanitizationField | None,
) -> DataSanitizationAlert:
    """Materializa um alerta apenas a partir da tabela canónica."""
    severidade, mensagem = ALERTAS_SANITIZACAO_CANONICOS[codigo]
    return DataSanitizationAlert(
        codigo=codigo,
        severidade=severidade,
        campo=campo,
        mensagem=mensagem,
    )


def derivar_alertas_sanitizacao(
    context: DataSanitizationContext,
) -> tuple[DataSanitizationAlert, ...]:
    """
    Deriva alertas na ordem canónica dos campos.

    ``model_fields_set`` distingue campo ausente de campo enviado
    explicitamente como ``null``.
    """
    campos_fiscais_presentes = tuple(
        campo
        for campo in CAMPOS_FISCAIS_CANONICOS
        if campo in context.model_fields_set
    )

    if not campos_fiscais_presentes:
        return (
            _criar_alerta(
                "CONTEXTO_SEM_CAMPOS_FISCAIS",
                campo=None,
            ),
        )

    alertas: list[DataSanitizationAlert] = []

    for campo in campos_fiscais_presentes:
        valor = getattr(context, campo)

        if valor is None or type(valor) in (bool, str):
            alertas.append(
                _criar_alerta(
                    "CAMPO_NAO_NUMERICO",
                    campo=campo,
                )
            )
            continue

        # O contrato aceita, neste ponto, apenas int ou float estritos.
        # Não converter para float evita perda de precisão e overflow
        # em inteiros de grande magnitude.
        if type(valor) not in (int, float):
            alertas.append(
                _criar_alerta(
                    "CAMPO_NAO_NUMERICO",
                    campo=campo,
                )
            )
            continue

        if valor < 0:
            alertas.append(
                _criar_alerta(
                    "CAMPO_NEGATIVO",
                    campo=campo,
                )
            )
            continue

        if (
            campo == "faturamento"
            and valor > LIMITE_FATURAMENTO
        ):
            alertas.append(
                _criar_alerta(
                    "FATURAMENTO_ACIMA_LIMITE",
                    campo="faturamento",
                )
            )

    return tuple(alertas)


def calcular_contexto_valido(
    alertas: tuple[DataSanitizationAlert, ...],
) -> bool:
    """Qualquer alerta torna o contexto não validado."""
    return not alertas


def construir_payload_sanitizacao(
    context: DataSanitizationContext,
) -> DataSanitizationPayload:
    """Transforma contexto validado em payload canónico."""
    alertas = derivar_alertas_sanitizacao(context)

    return DataSanitizationPayload(
        analysis_type="sanitizacao_contexto_fiscal",
        schema_type="DataSanitizationPayload",
        versao="1.0",
        empresa_id=context.empresa_id,
        contexto_valido=calcular_contexto_valido(alertas),
        total_alertas=len(alertas),
        alertas=alertas,
        publication_allowed=False,
    )


def _reconstruir_alertas_esperados_independente(
    context: DataSanitizationContext,
) -> tuple[DataSanitizationAlert, ...]:
    """
    Reconstrói a expectativa sem chamar a derivação principal.

    A duplicação intencional reduz o risco de uma falha na função
    principal validar o próprio resultado.
    """
    campos_presentes = tuple(
        nome
        for nome in CAMPOS_FISCAIS_CANONICOS
        if nome in context.model_fields_set
    )

    if not campos_presentes:
        severidade, mensagem = ALERTAS_SANITIZACAO_CANONICOS[
            "CONTEXTO_SEM_CAMPOS_FISCAIS"
        ]
        return (
            DataSanitizationAlert(
                codigo="CONTEXTO_SEM_CAMPOS_FISCAIS",
                severidade=severidade,
                campo=None,
                mensagem=mensagem,
            ),
        )

    esperados: list[DataSanitizationAlert] = []

    for nome in campos_presentes:
        recebido = getattr(context, nome)
        codigo: DataSanitizationAlertCode | None = None

        if recebido is None or type(recebido) in (bool, str):
            codigo = "CAMPO_NAO_NUMERICO"
        elif type(recebido) not in (int, float):
            codigo = "CAMPO_NAO_NUMERICO"
        elif recebido < 0:
            codigo = "CAMPO_NEGATIVO"
        elif (
            nome == "faturamento"
            and recebido > LIMITE_FATURAMENTO
        ):
            codigo = "FATURAMENTO_ACIMA_LIMITE"

        if codigo is None:
            continue

        severidade, mensagem = ALERTAS_SANITIZACAO_CANONICOS[
            codigo
        ]
        campo_alerta: DataSanitizationField = nome

        esperados.append(
            DataSanitizationAlert(
                codigo=codigo,
                severidade=severidade,
                campo=campo_alerta,
                mensagem=mensagem,
            )
        )

    return tuple(esperados)


def validate_data_sanitization_payload_against_context(
    *,
    context: DataSanitizationContext,
    payload: DataSanitizationPayload,
) -> None:
    """
    Valida o payload contra uma reconstrução independente.

    Não chama ``derivar_alertas_sanitizacao`` nem
    ``construir_payload_sanitizacao``.
    """
    alertas_esperados = (
        _reconstruir_alertas_esperados_independente(context)
    )
    contexto_valido_esperado = not alertas_esperados

    if payload.analysis_type != "sanitizacao_contexto_fiscal":
        raise ValueError("analysis_type divergente") from None

    if payload.schema_type != "DataSanitizationPayload":
        raise ValueError("schema_type divergente") from None

    if payload.versao != "1.0":
        raise ValueError("versao divergente") from None

    if payload.empresa_id != context.empresa_id:
        raise ValueError("empresa_id divergente") from None

    if payload.contexto_valido is not contexto_valido_esperado:
        raise ValueError("contexto_valido divergente") from None

    if payload.total_alertas != len(alertas_esperados):
        raise ValueError("total_alertas divergente") from None

    if payload.alertas != alertas_esperados:
        raise ValueError("alertas divergentes") from None

    if payload.publication_allowed is not False:
        raise ValueError("publication_allowed divergente") from None
