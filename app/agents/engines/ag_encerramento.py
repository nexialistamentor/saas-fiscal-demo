"""
app/agents/engines/ag_encerramento.py — ADR-010 B14.3B.

Motor determinístico puro para o AgEncerramentoAgent, restrito a MEI.

Não acede a BD, ORM, Session, HTTP, LLM, serviços, relógio
ou agente legado.
"""

from __future__ import annotations

from datetime import timedelta

from app.agents.contracts.ag_encerramento import (
    ALERTAS_ENCERRAMENTO_CANONICOS,
    AVISOS_LEGAIS_ENCERRAMENTO,
    BASE_REVIEW_REASONS_ENCERRAMENTO,
    CHECKLIST_ENCERRAMENTO_CANONICO,
    RELATORIO_DESACTUALIZADO_APOS_DIAS,
    TEMPORAL_REVIEW_REASONS_ENCERRAMENTO,
    AgEncerramentoAlertaPlataforma,
    AgEncerramentoCommercialDisclosure,
    AgEncerramentoContext,
    AgEncerramentoPayload,
    AlertaEncerramentoCode,
    EncerramentoPendenciaSnapshot,
)
from app.constants import AVISO_ENCERRAMENTO_IRREVERSIVEL


def _criar_alerta(
    code: AlertaEncerramentoCode,
    *,
    quantidade: int | None = None,
) -> AgEncerramentoAlertaPlataforma:
    """
    Materializa um alerta exclusivamente a partir da tabela canónica.
    """
    severidade, descricao_publica = ALERTAS_ENCERRAMENTO_CANONICOS[code]

    return AgEncerramentoAlertaPlataforma(
        code=code,
        severidade=severidade,
        descricao_publica=descricao_publica,
        quantidade=quantidade,
    )


def derivar_alertas_encerramento(
    snapshot: EncerramentoPendenciaSnapshot,
) -> tuple[AgEncerramentoAlertaPlataforma, ...]:
    """
    Deriva os alertas na ordem canónica:

    1. INSIGHTS_ATIVOS, quando presente.
    2. No máximo um alerta relativo ao relatório.
    """
    alertas: list[AgEncerramentoAlertaPlataforma] = []

    if snapshot.total_insights_ativos > 0:
        alertas.append(
            _criar_alerta(
                "INSIGHTS_ATIVOS",
                quantidade=snapshot.total_insights_ativos,
            )
        )

    estado = snapshot.estado_ultimo_relatorio

    if estado == "ausente":
        alertas.append(_criar_alerta("RELATORIO_AUSENTE"))

    elif estado == "timestamp_ausente":
        alertas.append(
            _criar_alerta("RELATORIO_TIMESTAMP_AUSENTE")
        )

    elif estado == "timestamp_naive":
        alertas.append(
            _criar_alerta("RELATORIO_TIMESTAMP_NAIVE")
        )

    elif estado == "timestamp_aware":
        ultimo_relatorio_em = snapshot.ultimo_relatorio_em

        if ultimo_relatorio_em is None:
            raise ValueError(
                "snapshot timestamp_aware sem ultimo_relatorio_em"
            )

        idade = snapshot.reference_at - ultimo_relatorio_em

        if idade >= timedelta(
            days=RELATORIO_DESACTUALIZADO_APOS_DIAS
        ):
            alertas.append(
                _criar_alerta("RELATORIO_DESACTUALIZADO")
            )

    else:
        raise ValueError("estado_ultimo_relatorio nao reconhecido")

    return tuple(alertas)


def derivar_review_reasons_encerramento(
    snapshot: EncerramentoPendenciaSnapshot,
) -> tuple[str, ...]:
    """
    A revisao temporal so e acrescentada quando o relatorio existe,
    mas a sua temporalidade nao pode ser comprovada.
    """
    if snapshot.estado_ultimo_relatorio in {
        "timestamp_ausente",
        "timestamp_naive",
    }:
        return TEMPORAL_REVIEW_REASONS_ENCERRAMENTO

    return BASE_REVIEW_REASONS_ENCERRAMENTO


def renderizar_resposta_encerramento(
    *,
    ano: int,
    checklist=CHECKLIST_ENCERRAMENTO_CANONICO,
    alertas: tuple[
        AgEncerramentoAlertaPlataforma,
        ...,
    ],
    aviso_irreversivel: str = AVISO_ENCERRAMENTO_IRREVERSIVEL,
    avisos_legais: tuple[
        str,
        ...,
    ] = AVISOS_LEGAIS_ENCERRAMENTO,
) -> str:
    """
    Renderizacao textual canonica e deterministica.

    O ano vem exclusivamente de snapshot.reference_at.
    """
    titulo = f"Como encerrar o MEI em {ano} — Orientação Preliminar"

    partes: list[str] = [
        f"**{titulo}**",
        "",
        f"⚠️ {aviso_irreversivel}",
        "",
    ]

    if alertas:
        partes.append(
            "**Pendências detectadas na plataforma:**"
        )

        for alerta in alertas:
            icone = (
                "🔴"
                if alerta.severidade == "alto"
                else "🟡"
            )

            texto = f"{icone} {alerta.descricao_publica}"

            if alerta.code == "INSIGHTS_ATIVOS":
                texto += f" Quantidade: {alerta.quantidade}."

            partes.append(texto)

        partes.append("")

    partes.append("**Checklist de encerramento:**")

    for item in checklist:
        if item.severidade == "alta":
            icone = "🔴"
        elif item.severidade == "media":
            icone = "🟡"
        else:
            icone = "•"

        link = (
            f" → [Ver]({item.link})"
            if item.link
            else ""
        )

        partes.append(
            f"{icone} **{item.passo}.** "
            f"{item.titulo}: {item.descricao}{link}"
        )

    partes.extend(
        [
            "",
            "**Avisos sujeitos a revisão humana:**",
        ]
    )

    for aviso in avisos_legais:
        partes.append(f"• {aviso}")

    return "\n".join(partes)


def construir_orientacao_encerramento(
    context: AgEncerramentoContext,
    snapshot: EncerramentoPendenciaSnapshot,
) -> AgEncerramentoPayload:
    """
    Motor puro:

    AgEncerramentoContext + EncerramentoPendenciaSnapshot
    -> AgEncerramentoPayload.
    """
    if context.tipo_contribuinte != "mei":
        raise ValueError(
            "motor de encerramento restrito a MEI"
        )

    if context.empresa_id != snapshot.empresa_id:
        raise ValueError(
            "contexto e snapshot pertencem a empresas diferentes"
        )

    alertas = derivar_alertas_encerramento(snapshot)
    review_reasons = derivar_review_reasons_encerramento(
        snapshot
    )

    resposta = renderizar_resposta_encerramento(
        ano=snapshot.reference_at.year,
        checklist=CHECKLIST_ENCERRAMENTO_CANONICO,
        alertas=alertas,
        aviso_irreversivel=AVISO_ENCERRAMENTO_IRREVERSIVEL,
        avisos_legais=AVISOS_LEGAIS_ENCERRAMENTO,
    )

    return AgEncerramentoPayload(
        resposta=resposta,
        analysis_type="encerramento_empresa",
        schema_type="HowTo",
        versao="1.0",
        tipo_contribuinte="mei",
        checklist=CHECKLIST_ENCERRAMENTO_CANONICO,
        avisos_legais=AVISOS_LEGAIS_ENCERRAMENTO,
        alertas_plataforma=alertas,
        aviso_irreversivel=AVISO_ENCERRAMENTO_IRREVERSIVEL,
        commercial_disclosure=(
            AgEncerramentoCommercialDisclosure()
        ),
        review_reasons=review_reasons,
        publication_allowed=False,
    )


def validate_ag_encerramento_payload_against_snapshot(
    *,
    context: AgEncerramentoContext,
    snapshot: EncerramentoPendenciaSnapshot,
    payload: AgEncerramentoPayload,
) -> None:
    """
    Reconstroi os valores esperados a partir do snapshot e compara
    integralmente com o payload recebido.

    Nao chama construir_orientacao_encerramento().
    """
    if context.tipo_contribuinte != "mei":
        raise ValueError(
            "contexto fora do escopo MEI"
        ) from None

    if context.empresa_id != snapshot.empresa_id:
        raise ValueError(
            "contexto e snapshot divergentes"
        ) from None

    alertas_esperados = derivar_alertas_encerramento(
        snapshot
    )

    review_reasons_esperadas = (
        derivar_review_reasons_encerramento(snapshot)
    )

    disclosure_esperada = (
        AgEncerramentoCommercialDisclosure()
    )

    resposta_esperada = renderizar_resposta_encerramento(
        ano=snapshot.reference_at.year,
        checklist=CHECKLIST_ENCERRAMENTO_CANONICO,
        alertas=alertas_esperados,
        aviso_irreversivel=AVISO_ENCERRAMENTO_IRREVERSIVEL,
        avisos_legais=AVISOS_LEGAIS_ENCERRAMENTO,
    )

    if payload.tipo_contribuinte != "mei":
        raise ValueError("tipo_contribuinte divergente") from None

    if payload.analysis_type != "encerramento_empresa":
        raise ValueError("analysis_type divergente") from None

    if payload.schema_type != "HowTo":
        raise ValueError("schema_type divergente") from None

    if payload.versao != "1.0":
        raise ValueError("versao divergente") from None

    if payload.publication_allowed is not False:
        raise ValueError(
            "publication_allowed divergente"
        ) from None

    if payload.checklist != CHECKLIST_ENCERRAMENTO_CANONICO:
        raise ValueError("checklist divergente") from None

    if payload.avisos_legais != AVISOS_LEGAIS_ENCERRAMENTO:
        raise ValueError("avisos_legais divergentes") from None

    if (
        payload.aviso_irreversivel
        != AVISO_ENCERRAMENTO_IRREVERSIVEL
    ):
        raise ValueError(
            "aviso_irreversivel divergente"
        ) from None

    if payload.commercial_disclosure != disclosure_esperada:
        raise ValueError(
            "commercial_disclosure divergente"
        ) from None

    if payload.alertas_plataforma != alertas_esperados:
        raise ValueError(
            "alertas_plataforma divergentes"
        ) from None

    if payload.review_reasons != review_reasons_esperadas:
        raise ValueError(
            "review_reasons divergentes"
        ) from None

    if payload.resposta != resposta_esperada:
        raise ValueError("resposta divergente") from None
