"""SOLVERIS Enterprise B02: cotejo read-only L2 -> ADR020 (sem vinculo canonico).

Leituras por identificadores exatos da mesma sessao, sem writes, sem consultas em
rede e sem fabricar NormativeRelationVersion. Entrada de snapshots do chamador
nao atesta por si origem externa ou execucao dos gates originais.

Estados sao exclusivamente investigativos. Nao existe promocao a autoridade
fiscal, aplicabilidade juridica demonstrada, credito ou checkout neste modulo.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import hmac
import re

from app.models import TabelaMVA, RuleVersion, ExtractionResult

SCHEMA = "SOLVERIS_ENTERPRISE_B02_NORMATIVE_BINDING_READONLY_V1"
C3_SCHEMA = "SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1"
C1_SCHEMA = "SOLVERIS_ENTERPRISE_G113_EXACT_PAGE_RULE_ITEM_V1"
C5_SCHEMA = "SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1"
C6_SCHEMA = "SOLVERIS_ENTERPRISE_G113_C6_L2_RECORD_PROVENANCE_V1"
G16_SCHEMA = "SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1"
G18_SCHEMA = "SOLVERIS_ENTERPRISE_G18_EXTERNAL_PUBLICATION_HASH_LINK_V1"
C4_SCHEMA = "SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1"
DENIED = ("autoridade_fiscal", "credito_confirmado", "checkout_autorizado", "usavel_comercialmente")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ISO = re.compile(r"\d{4}-\d\d-\d\d\Z")
NUM = re.compile(r"(?:0|[1-9]\d{0,11})(?:\.\d{1,8})?\Z")
HEX_NCM = re.compile(r"\d{8}\Z")
HEX_CEST = re.compile(r"\d{7}\Z")

class EnterpriseB02GateError(ValueError):
    """Dados, autoridade ou identidades inaceitaveis; falha fechada."""


def _stop(code):
    raise EnterpriseB02GateError("B02_" + code)


def _id(x):
    return type(x) is int and x > 0


def _sha(x):
    return type(x) is str and SHA.fullmatch(x) is not None


def _money(x):
    if type(x) is not str or NUM.fullmatch(x) is None:
        _stop("PARAMETRO_NAO_CANONICO")
    try:
        v = Decimal(x)
    except (InvalidOperation, ValueError):
        _stop("PARAMETRO_NAO_CANONICO")
    if not v.is_finite():
        _stop("PARAMETRO_NAO_FINITO")
    return v


def _date(x):
    if type(x) is not str or ISO.fullmatch(x) is None:
        _stop("DATA_NAO_CANONICA")
    try:
        d = date.fromisoformat(x)
        if d.isoformat() != x:
            _stop("DATA_NAO_CANONICA")
        return d
    except ValueError as e:
        raise EnterpriseB02GateError("B02_DATA_INVALIDA") from e


def _deny(x, name):
    non_authoritative = DENIED + (
        "fonte_primaria_autenticada", "vigencia_juridica_comprovada",
        "aplicabilidade_juridica_comprovada", "regra_normativa_persistida_vinculada",
        "vinculo_adr020_comprovado", "prova_aplicabilidade_juridica",
        "norma_juridicamente_ratificada", "checkout_autorizado",
    )
    if (type(x) is not dict or any(x.get(k) is not False for k in DENIED)
        or any(k in x and x[k] is not False for k in non_authoritative)):
        _stop("AUTORIDADE_OU_CONTRATO_INVALIDO_" + name)


def _same(*values):
    return len(values) > 0 and all(v == values[0] for v in values[1:])


def _get(db, cls, pk):
    try:
        return db.get(cls, pk)
    except Exception as exc:
        raise EnterpriseB02GateError("B02_LEITURA_ADR020_L2_INDISPONIVEL") from exc


def _result(state, reason, *, indice_item, c6, c3, c1, l2_id=None, rule=None):
    return {
        "schema_version": SCHEMA,
        "estado": state,
        "motivo": reason,
        "indice_item": indice_item,
        "documento_id": c6.get("documento_id"),
        "xml_sha256": c6.get("xml_sha256"),
        "registro_mva_id_observado": l2_id,
        "rule_version_record_id_observado": getattr(rule, "rule_version_record_id", None),
        "rule_id_declarado": c1.get("rule_id") if type(c1) is dict else None,
        "rule_version_declarada": c1.get("rule_version") if type(c1) is dict else None,
        "pdf_sha256": c3.get("pdf_sha256") if type(c3) is dict else None,
        "excerto_sha256": c3.get("excerto_sha256") if type(c3) is dict else None,
        "mva_motor_percentual": c6.get("mva_motor_percentual"),
        "mva_documental_percentual": c3.get("mva_original_percentual_observada") if type(c3) is dict else None,
        "identidade_documental_cotejada": False,
        "parametros_e_registo_l2_cotejados": False,
        "vinculo_l2_ruleversion_canonico_comprovado": False,
        "unicidade_l2_e_regra_comprovada": False,
        "autenticidade_institucional_independente_comprovada": False,
        "cobertura_alteracoes_revogacoes_exaustiva": False,
        "condicoes_juridicas_operacao_comprovadas": False,
        "aplicabilidade_juridica_comprovada": False,
        "decisao_fiscal_autorizada": False,
        "credito_recuperavel_demonstrado": False,
        "fonte_primaria_autenticada": False,
        **{k: False for k in DENIED},
    }


def cotejar_vinculo_normativo_b02(*, db, indice_item: int,
        rule_version_record_id: str | None,
        c4_result: dict, c5_result: dict, c6_result: dict, c3_result: dict,
        c1_result: dict | None, g14_item: dict, g16_result: dict, g18_result: dict) -> dict:
    """Coteja ORM lido por db.get e resultados originais; nao adjudica norma.

    Este contrato nao cria ou interpreta relacoes 'referencia' ADR-020 entre
    TabelaMVA e RuleVersion: TabelaMVA nao possui sujeito ADR versionado.
    """
    if db is None or not callable(getattr(db, "get", None)) or not _id(indice_item):
        _stop("ENTRADA_INVALIDA")
    for n, row, schema in (("C4",c4_result,C4_SCHEMA), ("C5",c5_result,C5_SCHEMA),
                            ("C6",c6_result,C6_SCHEMA), ("C3",c3_result,C3_SCHEMA),
                            ("G16",g16_result,G16_SCHEMA), ("G18",g18_result,G18_SCHEMA)):
        _deny(row,n)
        if row.get("schema_version") != schema:
            _stop("SCHEMA_"+n)
    if type(g14_item) is not dict or g14_item.get("indice_item") != indice_item:
        _stop("ITEM_G14_INVALIDO")
    if any(x.get("indice_item") != indice_item for x in (c4_result,c5_result,c6_result,c3_result)):
        _stop("ITEM_UPSTREAM_DIVERGENTE")
    g16_items, g18_items = g16_result.get("itens"),g18_result.get("itens")
    if (type(g16_items) is not list or type(g18_items) is not list
        or not 1<=indice_item<=len(g16_items) or not 1<=indice_item<=len(g18_items)
        or g16_result.get("itens_total")!=len(g16_items)
        or g18_result.get("itens_total")!=len(g18_items)):
        _stop("CARDINALIDADE_G16_G18_INVALIDA")
    i16,i18=g16_items[indice_item-1],g18_items[indice_item-1]
    if (type(i16) is not dict or type(i18) is not dict
        or i16.get("indice_item")!=indice_item or i18.get("indice_item")!=indice_item):
        _stop("IDENTIDADE_ITEM_G16_G18")
    if (any(i16.get(k) is not False for k in ("fonte_oficial_autenticada", "vigencia_juridica_comprovada",
                                              "cobertura_publicacoes_completa", "ausencia_revogacao_comprovada", "excecoes_aplicadas"))
        or any(i18.get(k) is not False for k in ("fonte_primaria_autenticada", "revogacao_historica_comprovada",
                                                "cadeia_icp_brasil_verificada_neste_servico", "tempo_assinatura_confiavel"))):
        _stop("TRUST_EXTERNO_NAO_COMPROVADO")
    digest=c4_result.get("xml_sha256")
    if (not _sha(digest) or not _same(digest,c5_result.get("xml_sha256"),c6_result.get("xml_sha256"),
                                      g16_result.get("xml_sha256"),g18_result.get("xml_sha256"))
        or not _same(c4_result.get("documento_id"),c5_result.get("documento_id"),
                     c6_result.get("documento_id"),g16_result.get("documento_id"),
                     g18_result.get("documento_id"))
        or not _id(c4_result.get("documento_id"))):
        _stop("DOCUMENTO_OU_XML_DIVERGENTE")
    operation=_date(c4_result.get("data_operacao"))
    if not _same(operation,_date(c3_result.get("data_operacao_declarada")),
                 _date(g16_result.get("data_operacao_observada"))):
        _stop("DATA_OPERACAO_DIVERGENTE")
    if (not _same(c4_result.get("uf"),c6_result.get("uf"),c3_result.get("uf"),g14_item.get("uf_operacao"))
        or not _same(c4_result.get("ncm"),c6_result.get("ncm"),c3_result.get("ncm"),g14_item.get("ncm"))
        or not _same(c4_result.get("cest"),c6_result.get("cest"),c3_result.get("cest"),g14_item.get("cest_observado"))
        or type(c4_result.get("ncm")) is not str or HEX_NCM.fullmatch(c4_result["ncm"]) is None
        or type(c4_result.get("cest")) is not str or HEX_CEST.fullmatch(c4_result["cest"]) is None):
        _stop("CLASSIFICACAO_DOCUMENTAL_DIVERGENTE")
    if c6_result.get("estado") != "REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020":
        return _result("ABSTENCAO","C6_SEM_LINHA_L2_COMPROVADA",indice_item=indice_item,c6=c6_result,c3=c3_result,c1=c1_result)
    l2_id=c6_result.get("identificador_registo_l2_observado")
    if not _id(l2_id) or c6_result.get("vinculo_adr020_comprovado") is not False:
        _stop("ID_L2_OU_TRUST_INVALIDO")
    r0=_result("ABSTENCAO", "SEM_PROVA_CANONICA", indice_item=indice_item,
               c6=c6_result,c3=c3_result,c1=c1_result,l2_id=l2_id)
    row=_get(db,TabelaMVA,l2_id)
    if row is None:
        r0["motivo"]="REGISTO_L2_NAO_ENCONTRADO_NA_SESSAO"
        return r0
    if type(getattr(row,"id",None)) is not int or row.id!=l2_id:
        _stop("LINHA_L2_ID_DIVERGENTE")
    if (getattr(row,"estado",None)!=c4_result["uf"] or getattr(row,"ncm",None)!=c4_result["ncm"]
        or getattr(row,"fonte_legal",None)!=c6_result.get("fonte_legal_declarada")
        or getattr(row,"url_fonte",None)!=c6_result.get("url_fonte_declarada")
        or type(getattr(row,"url_fonte",None)) is not str or not row.url_fonte.startswith("https://")
        or getattr(row,"nivel_confianca_fonte",None)!="oficial"):
        return dict(r0,estado="CONTRADICAO",motivo="LINHA_L2_CLASSIFICACAO_OU_FONTE_DIVERGENTE")
    begin=getattr(row,"vigencia_inicio",None); end=getattr(row,"vigencia_fim",None)
    if (type(begin) is not date or (end is not None and type(end) is not date)
        or begin>operation or (end is not None and end<operation)
        or begin.isoformat()!=c6_result.get("vigencia_inicio_registo")
        or (end.isoformat() if end else None)!=c6_result.get("vigencia_fim_registo")):
        return dict(r0,estado="CONTRADICAO",motivo="L2_VIGENCIA_DECLARADA_DIVERGENTE")
    try:
        mva_l2=Decimal(str(row.mva))
        ali_l2=Decimal(str(row.aliquota_interna))*100
        mva_motor=_money(c5_result.get("mva_motor_percentual"))
        ali_motor=_money(c5_result.get("aliquota_motor_percentual"))
        if not (mva_l2.is_finite() and ali_l2.is_finite() and mva_l2>0 and 0<ali_l2<=100):
            _stop("L2_PERCENTUAIS_INVALIDOS")
    except (ValueError, InvalidOperation, TypeError):
        _stop("L2_PERCENTUAIS_INVALIDOS")
    if (mva_l2!=mva_motor or ali_l2!=ali_motor
        or _money(c6_result.get("mva_motor_percentual"))!=mva_motor
        or _money(c6_result.get("aliquota_motor_percentual"))!=ali_motor):
        return dict(r0,estado="CONTRADICAO",motivo="L2_PARAMETROS_DIVERGENTES_DO_MOTOR")
    r0["parametros_e_registo_l2_cotejados"]=True
    # Mesma sessao e ambito de busca do cadastro vigente. Uma segunda linha
    # activa por UF/NCM/data impede declarar ate uma selecao L2 nao ambigua.
    # LIMIT 2 evita leitura de um universo amplo; nao prova ausencia de regras
    # ADR020 mais novas, de CEST/operacao/beneficios ou de mudanca concorrente.
    try:
        from sqlalchemy import or_
        seen = (db.query(TabelaMVA)
            .filter(TabelaMVA.estado == row.estado,
                    TabelaMVA.ncm == row.ncm,
                    TabelaMVA.vigencia_inicio <= operation,
                    or_(TabelaMVA.vigencia_fim.is_(None), TabelaMVA.vigencia_fim >= operation))
            .limit(2).all())
    except Exception:
        return dict(r0, motivo="L2_DUPLICIDADE_NAO_AUDITAVEL_NA_SESSAO")
    if (type(seen) is not list or len(seen) != 1
        or getattr(seen[0], "id", None) != l2_id):
        return dict(r0, motivo="L2_DUPLICIDADE_OU_SELECAO_CONCORRENTE")
    r0["identidade_l2_unica_na_consulta_atual"]=True
    if (c3_result.get("estado")!="CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE"
        or c3_result.get("verificacao_pdf_pagina_excerto") is not True):
        return dict(r0,motivo="C3_SEM_JANELA_TEMPORAL_DOCUMENTAL")
    if c1_result is None or rule_version_record_id is None:
        return dict(r0,motivo="C1_OU_RULEVERSION_NAO_FORNECIDOS")
    _deny(c1_result,"C1")
    if (c1_result.get("schema_version")!=C1_SCHEMA or type(rule_version_record_id) is not str
        or not 1<=len(rule_version_record_id)<=64 or rule_version_record_id.strip()!=rule_version_record_id):
        _stop("C1_OU_ID_RULEVERSION_INVALIDOS")
    if (c1_result.get("prova_de_relacao_semantica_entre_excerto_e_parametros") is not False
        or c1_result.get("fonte_primaria_autenticada") is not False
        or c1_result.get("vigencia_juridica_comprovada") is not False
        or c1_result.get("indice_item")!=indice_item
        or c1_result.get("documento_id")!=c4_result["documento_id"]
        or c1_result.get("xml_sha256")!=digest):
        _stop("C1_IDENTIDADE_OU_AUTORIDADE_INVALIDA")
    if (not _sha(c3_result.get("pdf_sha256")) or not _sha(c3_result.get("excerto_sha256"))
        or not _same(c3_result["pdf_sha256"],c1_result.get("pdf_sha256"),
                     g14_item.get("sha256_texto_normativo_declarado"),
                     i18.get("sha256_publicacao_observado"))
        or c1_result.get("excerto_sha256")!=c3_result["excerto_sha256"]):
        return dict(r0,estado="CONTRADICAO",motivo="PDF_OU_EXCERTO_NAO_CONCILIADOS")
    if (i16.get("estado")!="CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE"
        or i16.get("regra_interna_cotejada") is not True
        or i18.get("vinculo_hash_adr020") is not True
        or i18.get("pdf_bytes_recalculados") is not True):
        return dict(r0,motivo="G16_OU_G18_SEM_CADEIA_INTERNA_CONCILIADA")
    if i16.get("relacoes_declaradas"):
        return dict(r0,motivo="G16_RELACOES_ALTERACAO_REVOGACAO_OU_REFERENCIA_NAO_RESOLVIDAS")
    rule=_get(db,RuleVersion,rule_version_record_id)
    if rule is None:
        return dict(r0,motivo="RULEVERSION_NAO_ENCONTRADA_NA_SESSAO")
    if (getattr(rule,"rule_version_record_id",None)!=rule_version_record_id
        or not _sha(getattr(rule,"rule_hash",None)) or not _sha(getattr(rule,"record_hash",None))
        or not _same(getattr(rule,"rule_id",None),c1_result.get("rule_id"),i16.get("rule_id"))
        or not _same(getattr(rule,"rule_version",None),c1_result.get("rule_version"),i16.get("rule_version"))
        or not _same(getattr(rule,"rule_hash",None),c1_result.get("rule_hash"),i16.get("rule_hash"))):
        return dict(r0,estado="CONTRADICAO",motivo="RULEVERSION_IDENTIDADE_DIVERGENTE")
    r0["rule_version_record_id_observado"]=rule_version_record_id
    extraction_id=c1_result.get("extraction_result_id")
    if (type(extraction_id) is not str or not extraction_id
        or rule.extraction_result_id!=extraction_id
        or not _sha(getattr(rule,"extraction_result_record_hash",None))):
        return dict(r0,estado="CONTRADICAO",motivo="EXTRACTION_RESULT_REFERENCIA_DIVERGENTE")
    extraction=_get(db,ExtractionResult,extraction_id)
    if extraction is None:
        return dict(r0,motivo="EXTRACTION_RESULT_NAO_ENCONTRADO")
    if (getattr(extraction,"extraction_result_id",None)!=extraction_id
        or getattr(extraction,"record_hash",None)!=rule.extraction_result_record_hash
        or getattr(extraction,"artifact_hash",None)!=c3_result["pdf_sha256"]
        or getattr(extraction,"normative_artifact_id",None)!=c1_result.get("normative_artifact_id")
        or getattr(extraction,"outcome",None)!="conclusivo"):
        return dict(r0,estado="CONTRADICAO",motivo="EXTRACTION_RESULT_ARTEFACTO_DIVERGENTE")
    declared=getattr(rule,"structured_content",None)
    observed=getattr(extraction,"structured_content",None)
    if (type(declared) is not dict or type(declared.get("g113_v1")) is not dict
        or type(observed) is not dict or observed.get("g113_v1")!=declared["g113_v1"]):
        return dict(r0,estado="CONTRADICAO",motivo="PARAMETROS_REGRA_EXTRACAO_DIVERGENTES")
    values=declared["g113_v1"]
    dims=(("uf","uf_operacao"),("ncm","ncm"),("cest","cest_observado"),
          ("cfop","cfop"),("cst","cst_observado"),("regime","regime_empresa"))
    if any(values.get(k)!=g14_item.get(v) for k,v in dims):
        return dict(r0,estado="NAO_APLICAVEL_AO_ESCOPO_DECLARADO",motivo="DIMENSOES_REGRA_DIVERGEM_DA_OPERACAO")
    if (values.get("operacao")!="saida_interna" or values.get("metodo_base")!="iva_st"):
        return dict(r0,estado="NAO_APLICAVEL_AO_ESCOPO_DECLARADO",motivo="OPERACAO_OU_MODALIDADE_REGRA_DIVERGENTE")
    valid_start=_date(values.get("vigencia_inicio"))
    valid_end=_date(values["vigencia_fim"]) if values.get("vigencia_fim") is not None else None
    if operation<valid_start or valid_end is not None and operation>valid_end:
        return dict(r0,estado="NAO_APLICAVEL_AO_ESCOPO_DECLARADO",motivo="VIGENCIA_DECLARADA_FORA_DATA")
    if (not _same(_money(values.get("mva_percentual")),_money(c1_result.get("mva_percentual_declarada")),
                  _money(c3_result.get("mva_original_percentual_observada")),mva_motor)
        or not _same(_money(values.get("aliquota_percentual")),
                     _money(c1_result.get("aliquota_percentual_declarada")),ali_motor)):
        return dict(r0,estado="CONTRADICAO",motivo="PARAMETROS_RULEVERSION_C3_MOTOR_DIVERGENTES")
    if (g14_item.get("estado")!="COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST"
        or g14_item.get("url_fonte_candidata")!=row.url_fonte
        or g14_item.get("fonte_legal_candidata")!=row.fonte_legal
        or g14_item.get("competencia_declarada")!=operation.strftime("%Y-%m")):
        return dict(r0,estado="CONTRADICAO",motivo="G14_FONTE_COMPETENCIA_DIVERGENTE")
    return dict(r0,estado="CANDIDATO_DOCUMENTAL_COTEJADO",
                motivo="IDENTIDADE_INTERNA_E_PARAMETROS_COINCIDENTES_SEM_PROVA_JURIDICA",
                identidade_documental_cotejada=True)

__all__=("SCHEMA","EnterpriseB02GateError","cotejar_vinculo_normativo_b02")
