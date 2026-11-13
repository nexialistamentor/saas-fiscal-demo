"""Cotejo condicional PA/22021000, somente investigativo e sem calculo.

Nao consulta TabelaMVA, nao adapta contratos G12-G17 de saida interna
nem transforma custodia ADR-020 em autoridade tributaria.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

from app.models import ExtractionResult, NormativeArtifact, RuleVersion


_CEST = frozenset({"0301000", "0301001", "0301002", "0301100"})
_REMENTENTES = frozenset({
    "distribuidor_deposito_atacadista",
    "industrial_importador_arrematante_engarrafador",
})
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MODALIDADE = "antecipacao_na_entrada"
_MVA_DOCUMENTADA = {
    "0301000": (Decimal("40"), Decimal("140")),
    "0301001": (Decimal("40"), Decimal("140")),
    "0301002": (Decimal("40"), Decimal("140")),
    "0301100": (Decimal("70"), Decimal("140")),
}


def cotejar_candidato_pa_entrada(*, db, rule_version_record_id: str,
        uf_operacao: str, ncm: str, cest: str,
        categoria_remetente: str, tipo_operacao: str,
        data_referencia: date) -> dict:
    """Le vinculo documental exato; jamais autoriza calculo ou aplicacao legal.

    O chamador prova independentemente CEST, remetente e modalidade;
    esta funcao nao extrai nem presume nenhum desses atributos.
    """
    saida = {
        "estado": "ABSTENCAO", "motivo": "ENTRADA_CONDICIONAL_INVALIDA",
        "rule_version_record_id": None, "vinculos_declarados_cotejados": False,
        "autoridade_normativa_verificada": False, "calculo_autorizado": False,
        "norma_resolvida": None,
    }
    if (type(uf_operacao) is not str or uf_operacao != "PA"
        or type(ncm) is not str or ncm != "22021000"
        or type(cest) is not str or cest not in _CEST
        or type(categoria_remetente) is not str
        or categoria_remetente not in _REMENTENTES
        or tipo_operacao != _MODALIDADE
        or type(data_referencia) is not date
        or type(rule_version_record_id) is not str
        or not 1 <= len(rule_version_record_id) <= 64
        or rule_version_record_id.strip() != rule_version_record_id
        or db is None or not callable(getattr(db, "get", None))
        or getattr(db, "no_autoflush", None) is None):
        return saida

    try:
        with db.no_autoflush:
            rule = db.get(RuleVersion, rule_version_record_id)
            extraction = (db.get(ExtractionResult, rule.extraction_result_id)
                          if rule is not None else None)
            artifact = (db.get(NormativeArtifact, extraction.normative_artifact_id)
                        if extraction is not None else None)
    except Exception:
        return dict(saida, motivo="LEITURA_ADR020_INDISPONIVEL")
    if any(x is None for x in (rule, extraction, artifact)):
        return dict(saida, motivo="CADEIA_ADR020_INCOMPLETA")

    try:
        hashes = (rule.rule_hash, rule.record_hash,
                  rule.extraction_result_record_hash, extraction.record_hash,
                  extraction.artifact_hash, artifact.artifact_hash)
        coerente = (all(type(h) is str and _HASH.fullmatch(h) for h in hashes)
                    and rule.rule_version_record_id == rule_version_record_id
                    and rule.extraction_result_id == extraction.extraction_result_id
                    and rule.extraction_result_record_hash == extraction.record_hash
                    and extraction.normative_artifact_id == artifact.normative_artifact_id
                    and extraction.artifact_hash == artifact.artifact_hash
                    and extraction.outcome == "conclusivo")
        content = rule.structured_content
        observed = extraction.structured_content
    except (AttributeError, TypeError, ValueError):
        return dict(saida, motivo="IDENTIDADE_DOCUMENTAL_DIVERGENTE")
    if not coerente:
        return dict(saida, motivo="IDENTIDADE_DOCUMENTAL_DIVERGENTE")

    if (type(content) is not dict or type(observed) is not dict
        or type(content.get("pa_entrada_22021000_v1")) is not dict
        or observed.get("pa_entrada_22021000_v1")
            != content["pa_entrada_22021000_v1"]):
        return dict(saida, motivo="CONTRATO_REGRA_EXTRACAO_INCOMPATIVEL")
    item = content["pa_entrada_22021000_v1"]
    expected = {
        "uf_operacao": uf_operacao, "ncm": ncm, "cest": cest,
        "categoria_remetente": categoria_remetente,
        "tipo_operacao": tipo_operacao,
    }
    if any(item.get(k) != v for k, v in expected.items()):
        return dict(saida, motivo="CONDICOES_DA_OPERACAO_DIVERGENTES")
    try:
        start = date.fromisoformat(item["vigencia_inicio"])
        end = (date.fromisoformat(item["vigencia_fim"])
               if item.get("vigencia_fim") is not None else None)
        mva = Decimal(item["mva_percentual"])
        aliquota = Decimal(item["aliquota_interna_percentual"])
        grupo = 0 if categoria_remetente == "distribuidor_deposito_atacadista" else 1
        validade = rule.declared_material_validity
        if (type(item["vigencia_inicio"]) is not str
            or start.isoformat() != item["vigencia_inicio"]
            or (end is not None and
                (end.isoformat() != item["vigencia_fim"] or end < start))
            or not start <= data_referencia
            or (end is not None and data_referencia > end)
            or type(item["mva_percentual"]) is not str
            or type(item["aliquota_interna_percentual"]) is not str
            or not mva.is_finite() or mva != _MVA_DOCUMENTADA[cest][grupo]
            or not aliquota.is_finite() or aliquota != Decimal("21")
            or type(validade) is not dict
            or validade.get("vigencia_inicio") != item["vigencia_inicio"]
            or validade.get("vigencia_fim") != item.get("vigencia_fim")):
            raise ValueError("regra nao verificavel")
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return dict(saida, motivo="VIGENCIA_OU_PARAMETROS_NAO_COTEJADOS")

    return dict(
        saida, estado="CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE",
        motivo="PROVA_JURIDICA_EXTERNA_E_APLICABILIDADE_NAO_COMPROVADAS",
        rule_version_record_id=rule_version_record_id,
        vinculos_declarados_cotejados=True,
    )
