"""Motor determinístico L3 — ConsistencyAuditEngine.

ADR-012 v1.3 — Migração L3 B14.3D: ConsistencyAuditAgent em Sombra.
Ratificada: Miguel e GPT — 2026-07-17.

Responsabilidades exclusivas:
    1. Receber ConsistencyAuditContext;
    2. Identificar pares aplicáveis;
    3. Construir os dois dicionários mínimos;
    4. Chamar o serviço protegido TaxConsistencyEngine;
    5. Validar integralmente a resposta literal em fail-closed;
    6. Extrair somente códigos canónicos;
    7. Descartar todos os valores fiscais brutos;
    8. Construir ConsistencyAuditAlert;
    9. Construir ConsistencyAuditPayload.

O motor L3:
    — não recebe missão;
    — não usa relógio;
    — não importa adapter;
    — não usa BD, ORM, HTTP, LLM ou filesystem;
    — não chama o agente legado;
    — não persiste;
    — não publica;
    — não propõe nem executa acções.

Serviço protegido por hash:
    SHA256: 29389DB6FEC85C25A6D28153EA108044B4951B9EA49E979A05466DD88198A774
    Ficheiro: app/services/tax_consistency/tax_consistency_engine.py
    Classe: TaxConsistencyEngine
    Método: verificar_consistencia(dados_xml, dados_motor)
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import cast

from app.agents.contracts.consistency_audit import (
    ALERTAS_CONSISTENCY_CANONICOS,
    ConsistencyAuditAlert,
    ConsistencyAuditAlertCode,
    ConsistencyAuditContext,
    ConsistencyAuditPayload,
    INDICE_ALERTA_CONSISTENCY,
    PARES_CANONICOS,
)
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine


# ──────────────────────────────────────────────────────────────────────────────
# Tabelas imutáveis próprias do motor — MappingProxyType
# ──────────────────────────────────────────────────────────────────────────────

_MAPEAMENTO_SERVICO: Mapping[str, tuple[str, str]] = MappingProxyType({
    "icms_st_xml":   ("dados_xml", "valor_st"),
    "icms_st_motor": ("dados_motor", "icms_st"),
    "mva_xml":       ("dados_xml", "mva_xml"),
    "mva_motor":     ("dados_motor", "mva_utilizada"),
    "base_st_xml":   ("dados_xml", "base_st"),
    "base_st_motor": ("dados_motor", "base_st_calculada"),
})

_MAPEAMENTO_CODIGO_PAR: Mapping[str, tuple[str, str]] = MappingProxyType({
    "ICMS_ST_DIVERGENTE": ("icms_st_xml", "icms_st_motor"),
    "MVA_DIVERGENTE":     ("mva_xml", "mva_motor"),
    "BASE_ST_DIVERGENTE": ("base_st_xml", "base_st_motor"),
})

_CHAVES_DIVERGENCIA: Mapping[str, frozenset[str]] = MappingProxyType({
    "ICMS_ST_DIVERGENTE": frozenset({"tipo", "valor_xml", "valor_motor"}),
    "MVA_DIVERGENTE":     frozenset({"tipo", "mva_xml", "mva_motor"}),
    "BASE_ST_DIVERGENTE": frozenset({"tipo", "base_xml", "base_motor"}),
})


# ═══════════════════════════════════════════════════════════════════════════════
# CAMINHO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════

def construir_payload_consistency_audit(
    context: ConsistencyAuditContext,
) -> ConsistencyAuditPayload:
    """Constrói o payload de auditoria de consistência a partir do contexto L3."""
    pares_aplicaveis = _identificar_pares_aplicaveis(context)
    dados_xml, dados_motor = _construir_dicionarios_minimos(
        context, pares_aplicaveis
    )
    resultado = TaxConsistencyEngine().verificar_consistencia(
        dados_xml,
        dados_motor,
    )
    codigos = _validar_resposta_protegida(resultado, context, pares_aplicaveis)
    alertas = _construir_alertas(codigos)

    return ConsistencyAuditPayload(
        analysis_type="auditoria_consistencia_fiscal",
        schema_type="ConsistencyAuditPayload",
        versao="1.0",
        empresa_id=context.empresa_id,
        documento_id=context.documento_id,
        dados_coerentes=(len(alertas) == 0),
        total_alertas=len(alertas),
        alertas=tuple(alertas),
        publication_allowed=False,
    )


# ── Helpers privados do caminho principal ─────────────────────────────────────

def _identificar_pares_aplicaveis(
    context: ConsistencyAuditContext,
) -> tuple[str, ...]:
    """Identifica quais pares canónicos estão presentes e válidos no contexto."""
    pares: list[str] = []
    for campo_xml, campo_motor in PARES_CANONICOS:
        prefixo = campo_xml.rsplit("_", 1)[0]
        if (
            campo_xml in context.model_fields_set
            and campo_motor in context.model_fields_set
        ):
            valor_xml = getattr(context, campo_xml)
            valor_motor = getattr(context, campo_motor)
            if valor_xml is not None and valor_motor is not None:
                pares.append(prefixo)

    if not pares:
        raise ValueError("contexto sem par comparável aplicável")

    return tuple(pares)


def _construir_dicionarios_minimos(
    context: ConsistencyAuditContext,
    pares_aplicaveis: tuple[str, ...],
) -> tuple[dict[str, int | float], dict[str, int | float]]:
    """Constrói os dois dicionários mínimos para o serviço protegido."""
    dados_xml: dict[str, int | float] = {}
    dados_motor: dict[str, int | float] = {}

    for campo_xml, campo_motor in PARES_CANONICOS:
        prefixo = campo_xml.rsplit("_", 1)[0]
        if prefixo not in pares_aplicaveis:
            continue

        valor_xml = getattr(context, campo_xml)
        valor_motor = getattr(context, campo_motor)

        if type(valor_xml) not in (int, float) or isinstance(valor_xml, bool):
            raise ValueError("par aplicável contém valor inválido")
        if type(valor_motor) not in (int, float) or isinstance(valor_motor, bool):
            raise ValueError("par aplicável contém valor inválido")

        valor_xml_tipado = cast(int | float, valor_xml)
        valor_motor_tipado = cast(int | float, valor_motor)

        _, chave_xml = _MAPEAMENTO_SERVICO[campo_xml]
        dados_xml[chave_xml] = valor_xml_tipado

        _, chave_motor = _MAPEAMENTO_SERVICO[campo_motor]
        dados_motor[chave_motor] = valor_motor_tipado

    return dados_xml, dados_motor


def _validar_resposta_protegida(
    resultado: object,
    context: ConsistencyAuditContext,
    pares_aplicaveis: tuple[str, ...],
) -> tuple[ConsistencyAuditAlertCode, ...]:
    """Valida integralmente a resposta e devolve códigos canónicos atómicos."""
    if not isinstance(resultado, Mapping):
        raise ValueError("Resultado raiz não é Mapping")

    chaves_raiz = set(resultado.keys())
    if chaves_raiz != {"consistente", "divergencias"}:
        raise ValueError("Chaves raiz inválidas")

    consistente = resultado["consistente"]
    divergencias = resultado["divergencias"]

    if type(consistente) is not bool:
        raise ValueError("'consistente' não é bool exacto")
    if type(divergencias) is not list:
        raise ValueError("'divergencias' não é list exacta")

    if consistente is not (len(divergencias) == 0):
        raise ValueError("Incoerência entre 'consistente' e tamanho de divergencias")

    codigos_vistos: set[str] = set()
    indice_anterior: int | None = None
    codigos_extraidos: list[str] = []

    for item in divergencias:
        if not isinstance(item, Mapping):
            raise ValueError("Item de divergência não é Mapping")

        if "tipo" not in item:
            raise ValueError("Chave 'tipo' ausente na divergência")
        tipo = item["tipo"]
        if not isinstance(tipo, str):
            raise ValueError("'tipo' não é textual")

        if tipo not in _CHAVES_DIVERGENCIA:
            raise ValueError("Código de divergência desconhecido")

        if tipo in codigos_vistos:
            raise ValueError("Código de divergência duplicado")
        codigos_vistos.add(tipo)

        codigo = cast(ConsistencyAuditAlertCode, tipo)
        indice_actual = INDICE_ALERTA_CONSISTENCY[codigo]

        if indice_anterior is not None and indice_actual <= indice_anterior:
            raise ValueError("Código fora da ordem canónica")
        indice_anterior = indice_actual

        if tipo not in _MAPEAMENTO_CODIGO_PAR:
            raise ValueError("Código sem par mapeado")
        campo_xml, campo_motor = _MAPEAMENTO_CODIGO_PAR[tipo]
        prefixo = campo_xml.rsplit("_", 1)[0]
        if prefixo not in pares_aplicaveis:
            raise ValueError("Código relativo a par não aplicável")

        chaves_esperadas = _CHAVES_DIVERGENCIA[tipo]
        if set(item.keys()) != chaves_esperadas:
            raise ValueError("Conjunto de chaves inválido na divergência")

        _validar_valores_brutos(item, tipo, context, campo_xml, campo_motor)
        codigos_extraidos.append(tipo)

    return cast(tuple[ConsistencyAuditAlertCode, ...], tuple(codigos_extraidos))


def _validar_valores_brutos(
    item: Mapping[str, object],
    tipo: str,
    context: ConsistencyAuditContext,
    campo_xml: str,
    campo_motor: str,
) -> None:
    """Valida os valores brutos internos devolvidos pelo serviço protegido."""
    mapeamento_chaves: dict[str, tuple[str, str]] = {
        "ICMS_ST_DIVERGENTE": ("valor_xml", "valor_motor"),
        "MVA_DIVERGENTE":     ("mva_xml", "mva_motor"),
        "BASE_ST_DIVERGENTE": ("base_xml", "base_motor"),
    }
    chave_xml, chave_motor = mapeamento_chaves[tipo]

    for chave_item, campo_ctx in [(chave_xml, campo_xml), (chave_motor, campo_motor)]:
        valor_bruto = item[chave_item]
        valor_ctx = getattr(context, campo_ctx)

        if valor_ctx is None:
            raise ValueError("Valor de contexto inesperadamente nulo")

        if type(valor_bruto) not in (int, float) or isinstance(valor_bruto, bool):
            raise ValueError("Valor bruto não é int/float estrito")

        try:
            convertido = float(valor_bruto)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Valor bruto não convertível")
        if not math.isfinite(convertido):
            raise ValueError("Valor bruto não finito")

        if type(valor_bruto) is not type(valor_ctx):
            raise ValueError("Tipo do valor bruto diverge do contexto")
        if valor_bruto != valor_ctx:
            raise ValueError("Valor bruto diverge do contexto")


def _construir_alertas(
    codigos: tuple[ConsistencyAuditAlertCode, ...],
) -> list[ConsistencyAuditAlert]:
    """Constrói alertas canónicos a partir dos códigos extraídos."""
    alertas: list[ConsistencyAuditAlert] = []
    for codigo in codigos:
        if codigo not in ALERTAS_CONSISTENCY_CANONICOS:
            raise ValueError("Código ausente na tabela canónica")
        severidade, mensagem = ALERTAS_CONSISTENCY_CANONICOS[codigo]
        alertas.append(
            ConsistencyAuditAlert(
                codigo=codigo,
                severidade=severidade,
                mensagem=mensagem,
            )
        )
    return alertas


# ═══════════════════════════════════════════════════════════════════════════════
# VALIDAÇÃO INDEPENDENTE — caminho deliberadamente separado (ADR-012 §13)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_consistency_audit_payload_against_context(
    *,
    context: ConsistencyAuditContext,
    payload: ConsistencyAuditPayload,
) -> None:
    """Valida independentemente o payload contra o contexto.

    Esta validação:
        — não chama construir_payload_consistency_audit();
        — não reutiliza o helper principal de transformação dos pares;
        — não reutiliza o parser principal da resposta protegida;
        — instancia separadamente TaxConsistencyEngine;
        — reconstrói independentemente os dois dicionários mínimos;
        — inspecciona independentemente a estrutura raiz;
        — inspecciona independentemente cada divergência;
        — deriva independentemente a sequência esperada de códigos;
        — reconstrói a estrutura primitiva esperada do payload;
        — compara integralmente todos os campos do payload;
        — levanta ValueError sem dados fiscais perante qualquer divergência.

    Pode reutilizar somente:
        — contratos tipados;
        — constantes imutáveis;
        — tabela canónica de alertas;
        — serviço protegido por hash.
    """
    pares_aplicaveis = _identificar_pares_aplicaveis_independente(context)
    dados_xml, dados_motor = _reconstruir_dicionarios_independente(
        context, pares_aplicaveis
    )
    resultado = TaxConsistencyEngine().verificar_consistencia(
        dados_xml,
        dados_motor,
    )
    codigos_esperados = _inspecionar_resposta_independente(
        resultado, context, pares_aplicaveis
    )
    alertas_esperados = _reconstruir_alertas_independentes(codigos_esperados)

    _comparar_payload_primitivo(payload, context, alertas_esperados)


# ── Helpers privados do caminho independente ──────────────────────────────────

def _identificar_pares_aplicaveis_independente(
    context: ConsistencyAuditContext,
) -> tuple[str, ...]:
    """Identifica pares aplicáveis — caminho independente."""
    pares: list[str] = []
    for campo_xml, campo_motor in PARES_CANONICOS:
        prefixo = campo_xml.rsplit("_", 1)[0]
        if (
            campo_xml in context.model_fields_set
            and campo_motor in context.model_fields_set
        ):
            valor_xml = getattr(context, campo_xml)
            valor_motor = getattr(context, campo_motor)
            if valor_xml is not None and valor_motor is not None:
                pares.append(prefixo)

    if not pares:
        raise ValueError("contexto sem par comparável aplicável")

    return tuple(pares)


def _reconstruir_dicionarios_independente(
    context: ConsistencyAuditContext,
    pares_aplicaveis: tuple[str, ...],
) -> tuple[dict[str, int | float], dict[str, int | float]]:
    """Reconstrói os dois dicionários mínimos — caminho independente."""
    dados_xml: dict[str, int | float] = {}
    dados_motor: dict[str, int | float] = {}

    for campo_xml, campo_motor in PARES_CANONICOS:
        prefixo = campo_xml.rsplit("_", 1)[0]
        if prefixo not in pares_aplicaveis:
            continue

        valor_xml = getattr(context, campo_xml)
        valor_motor = getattr(context, campo_motor)

        if type(valor_xml) not in (int, float) or isinstance(valor_xml, bool):
            raise ValueError("par aplicável contém valor inválido")
        if type(valor_motor) not in (int, float) or isinstance(valor_motor, bool):
            raise ValueError("par aplicável contém valor inválido")

        valor_xml_tipado = cast(int | float, valor_xml)
        valor_motor_tipado = cast(int | float, valor_motor)

        _, chave_xml = _MAPEAMENTO_SERVICO[campo_xml]
        dados_xml[chave_xml] = valor_xml_tipado

        _, chave_motor = _MAPEAMENTO_SERVICO[campo_motor]
        dados_motor[chave_motor] = valor_motor_tipado

    return dados_xml, dados_motor


def _inspecionar_resposta_independente(
    resultado: object,
    context: ConsistencyAuditContext,
    pares_aplicaveis: tuple[str, ...],
) -> tuple[ConsistencyAuditAlertCode, ...]:
    """Inspecciona a resposta e devolve códigos — caminho independente."""
    if not isinstance(resultado, Mapping):
        raise ValueError("Resultado raiz não é Mapping")

    chaves_raiz = set(resultado.keys())
    if chaves_raiz != {"consistente", "divergencias"}:
        raise ValueError("Chaves raiz inválidas")

    consistente = resultado["consistente"]
    divergencias = resultado["divergencias"]

    if type(consistente) is not bool:
        raise ValueError("'consistente' não é bool exacto")
    if type(divergencias) is not list:
        raise ValueError("'divergencias' não é list exacta")

    if consistente is not (len(divergencias) == 0):
        raise ValueError("Incoerência entre 'consistente' e tamanho de divergencias")

    codigos_vistos: set[str] = set()
    indice_anterior: int | None = None
    codigos_extraidos: list[str] = []

    for item in divergencias:
        if not isinstance(item, Mapping):
            raise ValueError("Item de divergência não é Mapping")

        if "tipo" not in item:
            raise ValueError("Chave 'tipo' ausente na divergência")
        tipo = item["tipo"]
        if not isinstance(tipo, str):
            raise ValueError("'tipo' não é textual")

        if tipo not in _CHAVES_DIVERGENCIA:
            raise ValueError("Código de divergência desconhecido")

        if tipo in codigos_vistos:
            raise ValueError("Código de divergência duplicado")
        codigos_vistos.add(tipo)

        codigo = cast(ConsistencyAuditAlertCode, tipo)
        indice_actual = INDICE_ALERTA_CONSISTENCY[codigo]

        if indice_anterior is not None and indice_actual <= indice_anterior:
            raise ValueError("Código fora da ordem canónica")
        indice_anterior = indice_actual

        if tipo not in _MAPEAMENTO_CODIGO_PAR:
            raise ValueError("Código sem par mapeado")
        campo_xml, campo_motor = _MAPEAMENTO_CODIGO_PAR[tipo]
        prefixo = campo_xml.rsplit("_", 1)[0]
        if prefixo not in pares_aplicaveis:
            raise ValueError("Código relativo a par não aplicável")

        chaves_esperadas = _CHAVES_DIVERGENCIA[tipo]
        if set(item.keys()) != chaves_esperadas:
            raise ValueError("Conjunto de chaves inválido na divergência")

        _validar_valores_brutos_independente(item, tipo, context, campo_xml, campo_motor)
        codigos_extraidos.append(tipo)

    return cast(tuple[ConsistencyAuditAlertCode, ...], tuple(codigos_extraidos))


def _validar_valores_brutos_independente(
    item: Mapping[str, object],
    tipo: str,
    context: ConsistencyAuditContext,
    campo_xml: str,
    campo_motor: str,
) -> None:
    """Valida valores brutos — caminho independente."""
    mapeamento_chaves: dict[str, tuple[str, str]] = {
        "ICMS_ST_DIVERGENTE": ("valor_xml", "valor_motor"),
        "MVA_DIVERGENTE":     ("mva_xml", "mva_motor"),
        "BASE_ST_DIVERGENTE": ("base_xml", "base_motor"),
    }
    chave_xml, chave_motor = mapeamento_chaves[tipo]

    for chave_item, campo_ctx in [(chave_xml, campo_xml), (chave_motor, campo_motor)]:
        valor_bruto = item[chave_item]
        valor_ctx = getattr(context, campo_ctx)

        if valor_ctx is None:
            raise ValueError("Valor de contexto inesperadamente nulo")

        if type(valor_bruto) not in (int, float) or isinstance(valor_bruto, bool):
            raise ValueError("Valor bruto não é int/float estrito")

        try:
            convertido = float(valor_bruto)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Valor bruto não convertível")
        if not math.isfinite(convertido):
            raise ValueError("Valor bruto não finito")

        if type(valor_bruto) is not type(valor_ctx):
            raise ValueError("Tipo do valor bruto diverge do contexto")
        if valor_bruto != valor_ctx:
            raise ValueError("Valor bruto diverge do contexto")


def _reconstruir_alertas_independentes(
    codigos: tuple[ConsistencyAuditAlertCode, ...],
) -> list[ConsistencyAuditAlert]:
    """Reconstrói alertas canónicos — caminho independente."""
    alertas: list[ConsistencyAuditAlert] = []
    for codigo in codigos:
        if codigo not in ALERTAS_CONSISTENCY_CANONICOS:
            raise ValueError("Código ausente na tabela canónica")
        severidade, mensagem = ALERTAS_CONSISTENCY_CANONICOS[codigo]
        alertas.append(
            ConsistencyAuditAlert(
                codigo=codigo,
                severidade=severidade,
                mensagem=mensagem,
            )
        )
    return alertas


def _comparar_payload_primitivo(
    payload: ConsistencyAuditPayload,
    context: ConsistencyAuditContext,
    alertas_esperados: list[ConsistencyAuditAlert],
) -> None:
    """Compara campos primitivos do payload recebido contra valores esperados.

    Não constrói um segundo ConsistencyAuditPayload.
    Compara cada campo directamente.
    """
    if payload.empresa_id != context.empresa_id:
        raise ValueError("Divergência no campo 'empresa_id' do payload")
    if payload.documento_id != context.documento_id:
        raise ValueError("Divergência no campo 'documento_id' do payload")

    if payload.analysis_type != "auditoria_consistencia_fiscal":
        raise ValueError("Divergência no campo 'analysis_type' do payload")
    if payload.schema_type != "ConsistencyAuditPayload":
        raise ValueError("Divergência no campo 'schema_type' do payload")
    if payload.versao != "1.0":
        raise ValueError("Divergência no campo 'versao' do payload")

    dados_coerentes_esperado = len(alertas_esperados) == 0
    if payload.dados_coerentes is not dados_coerentes_esperado:
        raise ValueError("Divergência no campo 'dados_coerentes' do payload")

    total_alertas_esperado = len(alertas_esperados)
    if payload.total_alertas != total_alertas_esperado:
        raise ValueError("Divergência no campo 'total_alertas' do payload")

    if payload.publication_allowed is not False:
        raise ValueError("Divergência no campo 'publication_allowed' do payload")

    if len(payload.alertas) != total_alertas_esperado:
        raise ValueError("Divergência no número de alertas")

    for idx, (alerta_obtido, alerta_esperado) in enumerate(
        zip(payload.alertas, alertas_esperados)
    ):
        if alerta_obtido.codigo != alerta_esperado.codigo:
            raise ValueError(f"Divergência no código do alerta {idx}")
        if alerta_obtido.severidade != alerta_esperado.severidade:
            raise ValueError(f"Divergência na severidade do alerta {idx}")
        if alerta_obtido.mensagem != alerta_esperado.mensagem:
            raise ValueError(f"Divergência na mensagem do alerta {idx}")
