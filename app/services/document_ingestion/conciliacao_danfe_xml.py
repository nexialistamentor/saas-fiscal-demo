"""
app/services/document_ingestion/conciliacao_danfe_xml.py

B5-03b — Conciliação entre evidências documentais.

Hierarquia soberana:
  1. chave_nfe       → identificador único SEFAZ (peso máximo)
  2. cnpj_emitente   → emissor do documento
  3. numero_nota     → número fiscal
  4. serie           → série da NF
  5. valor_total     → tolerância ±0.01 (alerta, não divergência crítica)
  6. protocolo       → auxiliar

Regras de status:
  chave coincide                         → conciliado (mesmo com alertas)
  chave diverge                          → divergente
  chave ausente + 3 críticos (CNPJ+nº+série) todos coincidem → conciliado
  chave ausente + qualquer crítico diverge → divergente
  chave ausente + campos insuficientes   → inconclusivo

Fora de escopo:
  - Sem ORM, sem banco, sem motor fiscal, sem OCR, sem persistência
"""

from dataclasses import dataclass, field
from decimal import Decimal
import re

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel

_TOLERANCIA_VALOR = Decimal("0.01")
_CAMPOS_CRITICOS_SEM_CHAVE = {"cnpj_emitente", "numero_nota", "serie"}


@dataclass
class ResultadoConciliacao:
    """
    status:
      "conciliado"   → campos críticos coincidem
      "divergente"   → campos críticos presentes mas não coincidem
      "inconclusivo" → campos críticos ausentes numa ou ambas as evidências
    """
    status: str
    score_confianca: float
    campos_conciliados: list[str] = field(default_factory=list)
    divergencias: list[str] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)


def conciliar(
    evidencia_xml: EvidenciaFiscalComparavel,
    evidencia_danfe: EvidenciaFiscalComparavel,
) -> ResultadoConciliacao:
    """Concilia duas EvidenciaFiscalComparavel (XML e DANFE PDF)."""
    conciliados: list[str] = []
    divergencias: list[str] = []
    alertas: list[str] = []
    faltantes: list[str] = []

    # 1. Chave NF-e (peso máximo)
    chave_resultado = _comparar_campo(
        "chave_nfe",
        evidencia_xml.chave_nfe, evidencia_danfe.chave_nfe,
        conciliados, divergencias, faltantes,
    )

    # 2. CNPJ emitente (normalizado — remove formatação)
    _comparar_normalizado(
        "cnpj_emitente",
        evidencia_xml.cnpj_emitente, evidencia_danfe.cnpj_emitente,
        conciliados, divergencias, faltantes,
    )

    # 3. Número da nota
    _comparar_campo(
        "numero_nota",
        evidencia_xml.numero_nota, evidencia_danfe.numero_nota,
        conciliados, divergencias, faltantes,
    )

    # 4. Série
    _comparar_campo(
        "serie",
        evidencia_xml.serie, evidencia_danfe.serie,
        conciliados, divergencias, faltantes,
    )

    # 5. Valor total (tolerância ±0.01 → alerta, não divergência crítica)
    _comparar_valor(
        evidencia_xml.valor_total, evidencia_danfe.valor_total,
        conciliados, alertas, faltantes,
    )

    # 6. Protocolo (auxiliar)
    _comparar_campo(
        "protocolo",
        evidencia_xml.protocolo, evidencia_danfe.protocolo,
        conciliados, divergencias, faltantes,
    )

    status = _determinar_status(chave_resultado, conciliados, divergencias, faltantes)

    total_avaliados = len(conciliados) + len(divergencias)
    score = round(len(conciliados) / total_avaliados * 100, 1) if total_avaliados > 0 else 0.0

    return ResultadoConciliacao(
        status=status,
        score_confianca=score,
        campos_conciliados=conciliados,
        divergencias=divergencias,
        alertas=alertas,
        faltantes=faltantes,
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _comparar_campo(
    nome: str,
    val_xml: str | None, val_danfe: str | None,
    conciliados: list, divergencias: list, faltantes: list,
) -> str:
    if val_xml is None or val_danfe is None:
        faltantes.append(nome)
        return "faltante"
    if val_xml.strip() == val_danfe.strip():
        conciliados.append(nome)
        return "conciliado"
    divergencias.append(f"{nome}: xml='{val_xml}' danfe='{val_danfe}'")
    return "divergente"


def _comparar_normalizado(
    nome: str,
    val_xml: str | None, val_danfe: str | None,
    conciliados: list, divergencias: list, faltantes: list,
) -> str:
    """Compara após remover não-dígitos (CNPJ com/sem formatação)."""
    norm = lambda v: re.sub(r"\D", "", v) if v else None
    return _comparar_campo(nome, norm(val_xml), norm(val_danfe), conciliados, divergencias, faltantes)


def _comparar_valor(
    val_xml: Decimal | None, val_danfe: Decimal | None,
    conciliados: list, alertas: list, faltantes: list,
) -> None:
    """Valor total com tolerância ±0.01 → alerta (não divergência crítica)."""
    if val_xml is None or val_danfe is None:
        faltantes.append("valor_total")
        return
    if abs(val_xml - val_danfe) <= _TOLERANCIA_VALOR:
        conciliados.append("valor_total")
    else:
        alertas.append(
            f"valor_total: xml={val_xml} danfe={val_danfe} diff={abs(val_xml - val_danfe)}"
        )


def _determinar_status(
    chave_resultado: str,
    conciliados: list,
    divergencias: list,
    faltantes: list,
) -> str:
    # Chave presente e coincide → conciliado (regra soberana)
    if chave_resultado == "conciliado":
        return "conciliado"

    # Chave presente mas diverge → divergente
    if chave_resultado == "divergente":
        return "divergente"

    # Chave ausente → exige TODOS os 3 campos críticos conciliados
    criticos_conciliados = _CAMPOS_CRITICOS_SEM_CHAVE.issubset(set(conciliados))
    criticos_divergentes = any(
        any(c in d for c in _CAMPOS_CRITICOS_SEM_CHAVE)
        for d in divergencias
    )

    if criticos_conciliados and not criticos_divergentes:
        return "conciliado"

    if criticos_divergentes:
        return "divergente"

    return "inconclusivo"
