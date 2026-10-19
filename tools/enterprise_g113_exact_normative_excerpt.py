"""G1.13-C1: exact PDF-page excerpt -> ADR-020 extraction/rule -> NF-e item.

Only physical/relational evidence, NOT legal interpretation, fiscal authority,
exhaustive freshness or commercial eligibility. Read-only, no network or DB.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
from io import BytesIO
import re
from typing import Any

from pypdf import PdfReader

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_EXACT_PAGE_RULE_ITEM_V1'
G16 = 'SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1'
G18 = 'SOLVERIS_ENTERPRISE_G18_EXTERNAL_PUBLICATION_HASH_LINK_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_NCM = re.compile(r'[0-9]{8}\Z')
_CEST = re.compile(r'[0-9]{7}\Z')
_CFOP = re.compile(r'5[0-9]{3}\Z')
_CST = re.compile(r'[0-9]{2}\Z')
_MONEY = re.compile(r'(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,2})?\Z')
_UNTRUSTED = (
    'fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'cest_aplicabilidade_juridica_comprovada', 'excecoes_e_beneficios_verificados',
    'formula_juridicamente_autorizada', 'icms_proprio_independente',
    'credito_confirmado', 'autoridade_fiscal', 'checkout_autorizado',
    'usavel_comercialmente',
)
_ANCHOR_FIELDS = frozenset({
    'pdf_sha256', 'pagina_1_based', 'pagina_texto_sha256', 'inicio_caracter',
    'excerto_exato', 'excerto_sha256', 'dispositivo_declarado',
})
_RULE_FIELDS = frozenset({
    'uf','ncm','cest','cfop','cst','regime','operacao','metodo_base',
    'vigencia_inicio','vigencia_fim','mva_percentual','aliquota_percentual',
})

class G113EvidenceError(ValueError):
    pass

def _stop(reason: str) -> None:
    raise G113EvidenceError('G113_' + reason)

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _sha(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None

def _ident(value: Any) -> bool:
    return type(value) is str and 1 <= len(value) <= 64 and value.strip() == value

def _percent(x):
    if type(x) is not str or not _MONEY.fullmatch(x):
        _stop('PERCENTUAL_FORMATO_INVALIDO')
    try:
        d = Decimal(x)
    except (InvalidOperation, ValueError):
        _stop('PERCENTUAL_INVALIDO')
    if not d.is_finite() or not 0 <= d <= 999:
        _stop('PERCENTUAL_FORA_LIMITE')
    return d

def _item(snapshot, index, schema):
    if (type(snapshot) is not dict or snapshot.get('schema_version') != schema
        or type(snapshot.get('itens')) is not list
        or snapshot.get('itens_total') != len(snapshot['itens'])
        or not 1 <= index <= len(snapshot['itens'])
        or type(snapshot['itens'][index-1]) is not dict
        or snapshot['itens'][index-1].get('indice_item') != index):
        _stop('UPSTREAM_SCHEMA_OU_ITEM_DIVERGENTE')
    return snapshot['itens'][index-1]

def cotejar_excerto_normativo_g113(*, pdf_bytes: bytes, pdf_sha256: str,
        indice_item: int, g14_item: dict, g16_result: dict, g18_result: dict,
        extraction_result: object, rule_version: object) -> dict:
    """Coteja bytes/paragrafo/texto/regra/item sem elevar autoridade.

    Caller must have obtained G14/G16/G18 from their gated original services
    and the two ADR-020 rows using read-only, identity-constrained db.get.
    Snapshots/rows supplied directly are not independent authentication.
    """
    if (type(pdf_bytes) is not bytes or not 1024 <= len(pdf_bytes) <= 16*1024*1024
        or not pdf_bytes.startswith(b'%PDF-') or not _sha(pdf_sha256)
        or not hmac.compare_digest(hashlib.sha256(pdf_bytes).hexdigest(), pdf_sha256)):
        _stop('PDF_BYTES_OU_HASH_INVALIDOS')
    if type(indice_item) is not int or indice_item < 1:
        _stop('INDICE_ITEM_INVALIDO')
    if type(g14_item) is not dict or g14_item.get('indice_item') != indice_item or g14_item.get('estado') != 'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST':
        _stop('G14_CANDIDATO_NAO_COTEJADO')
    if g14_item.get('sha256_texto_normativo_declarado') != pdf_sha256:
        _stop('G14_HASH_ARTEFACTO_DIVERGENTE')
    i16 = _item(g16_result, indice_item, G16)
    i18 = _item(g18_result, indice_item, G18)
    if (g16_result.get('xml_sha256') != g18_result.get('xml_sha256')
        or not _sha(g16_result.get('xml_sha256'))
        or g16_result.get('documento_id') != g18_result.get('documento_id')
        or g16_result.get('empresa_id') != g18_result.get('empresa_id')
        or g16_result.get('relatorio_id') != g18_result.get('relatorio_id')
        or type(g16_result.get('documento_id')) is not int
        or g16_result.get('documento_id') < 1
        or any(g16_result.get(k) is not False or g18_result.get(k) is not False
               for k in ('autoridade_fiscal','credito_confirmado','checkout_autorizado','fonte_primaria_autenticada'))):
        _stop('UPSTREAM_IDENTIDADE_OU_AUTORIDADE_DIVERGENTE')
    if (i16.get('regra_interna_cotejada') is not True
        or i16.get('estado') != 'CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE'
        or i18.get('vinculo_hash_adr020') is not True
        or i18.get('pdf_bytes_recalculados') is not True
        or i18.get('sha256_publicacao_observado') != pdf_sha256
        or i18.get('custodia_externa_revalidada') is not False
        or i18.get('fonte_primaria_autenticada') is not False):
        _stop('CADEIA_NAO_COTEJADA_OU_FALSO_TRUST')
    if (not _ident(getattr(extraction_result,'extraction_result_id',None))
        or not _ident(getattr(extraction_result,'normative_artifact_id',None))
        or getattr(extraction_result,'artifact_hash',None) != pdf_sha256
        or getattr(extraction_result,'outcome',None) != 'conclusivo'
        or not _sha(getattr(extraction_result,'record_hash',None))
        or not _ident(getattr(rule_version,'rule_version_record_id',None))
        or getattr(rule_version,'extraction_result_id',None) != extraction_result.extraction_result_id
        or getattr(rule_version,'extraction_result_record_hash',None) != extraction_result.record_hash
        or getattr(rule_version,'rule_id',None) != i16.get('rule_id')
        or getattr(rule_version,'rule_version',None) != i16.get('rule_version')
        or getattr(rule_version,'rule_hash',None) != i16.get('rule_hash')
        or not _sha(getattr(rule_version,'record_hash',None))):
        _stop('REGISTOS_EXTRACAO_REGRA_OU_VINCULO_INVALIDOS')
    anchor_e = getattr(extraction_result, 'evidence', None)
    anchor_r = getattr(rule_version, 'evidence', None)
    if type(anchor_e) is not dict or type(anchor_r) is not dict:
        _stop('ANCORAS_NAO_ESTRUTURADAS')
    anchor = anchor_e.get('g113_v1')
    if (type(anchor) is not dict or set(anchor) != _ANCHOR_FIELDS
        or anchor_r.get('g113_v1') != anchor
        or anchor.get('pdf_sha256') != pdf_sha256):
        _stop('ANCORAS_IMUTAVEIS_DIVERGENTES')
    page = anchor.get('pagina_1_based')
    start = anchor.get('inicio_caracter')
    quote = anchor.get('excerto_exato')
    if (type(page) is not int or page <= 0 or type(start) is not int or start < 0
        or type(quote) is not str or not 25 <= len(quote) <= 1600
        or not quote.strip() or type(anchor.get('dispositivo_declarado')) is not str
        or not 2 <= len(anchor['dispositivo_declarado']) <= 200
        or not _sha(anchor.get('excerto_sha256')) or not _sha(anchor.get('pagina_texto_sha256'))
        or not hmac.compare_digest(_hash(quote), anchor['excerto_sha256'])):
        _stop('ANCORA_EXCERTO_OU_DISPOSITIVO_INVALIDO')
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        count = len(reader.pages)
        if not 1 <= count <= 500 or page > count:
            _stop('PAGINA_FORA_DO_DOCUMENTO')
        page_text = reader.pages[page-1].extract_text(extraction_mode='plain')
    except G113EvidenceError:
        raise
    except Exception as exc:
        raise G113EvidenceError('G113_PDF_EXTRACAO_INDISPONIVEL') from exc
    if type(page_text) is not str or not page_text:
        _stop('PAGINA_SEM_TEXTO_EXTRAIVEL')
    if not hmac.compare_digest(_hash(page_text), anchor['pagina_texto_sha256']):
        _stop('PAGINA_TEXTO_DIVERGENTE')
    if page_text.count(quote) != 1 or page_text.find(quote) != start:
        _stop('EXCERTO_NAO_UNICO_OU_OFFSET_DIVERGENTE')
    params = getattr(rule_version, 'structured_content', None)
    extraction_params = getattr(extraction_result, 'structured_content', None)
    if (type(params) is not dict or type(extraction_params) is not dict
        or type(params.get('g113_v1')) is not dict
        or extraction_params.get('g113_v1') != params['g113_v1']):
        _stop('PARAMETROS_REGRA_EXTRACAO_DIVERGENTES')
    rule = params['g113_v1']
    if set(rule) != _RULE_FIELDS:
        _stop('PARAMETROS_INCOMPLETOS')
    dimensions = {
        'uf':'uf_operacao','ncm':'ncm','cest':'cest_observado',
        'cfop':'cfop','cst':'cst_observado','regime':'regime_empresa',
    }
    if any(rule.get(k) != g14_item.get(v) for k,v in dimensions.items()):
        _stop('DIMENSOES_ITEM_REGRA_DIVERGENTES')
    if (rule.get('operacao') != 'saida_interna' or rule.get('metodo_base') != 'iva_st'
        or type(rule.get('ncm')) is not str or not _NCM.fullmatch(rule['ncm'])
        or type(rule.get('cest')) is not str or not _CEST.fullmatch(rule['cest'])
        or type(rule.get('cfop')) is not str or not _CFOP.fullmatch(rule['cfop'])
        or type(rule.get('cst')) is not str or not _CST.fullmatch(rule['cst'])):
        _stop('OPERACAO_OU_CODIGOS_NAO_SUPORTADOS')
    try:
        op_date = date.fromisoformat(g16_result['data_operacao_observada'])
        start_validity = date.fromisoformat(rule['vigencia_inicio'])
        end_validity = (date.fromisoformat(rule['vigencia_fim'])
                        if type(rule.get('vigencia_fim')) is str else None)
        if (rule.get('vigencia_fim') is not None and end_validity is None
            or not start_validity <= op_date
            or end_validity is not None and (end_validity < start_validity or op_date > end_validity)
            or g14_item.get('competencia_declarada') != op_date.strftime('%Y-%m')):
            _stop('VIGENCIA_DECLARADA_NAO_COBRE_OPERACAO')
    except (KeyError, TypeError, ValueError) as exc:
        raise G113EvidenceError('G113_DATA_INVALIDA') from exc
    mva = _percent(rule['mva_percentual'])
    ali = _percent(rule['aliquota_percentual'])
    if not 0 < ali <= 100 or not 0 <= mva <= 999:
        _stop('PERCENTUAIS_SEM_VALOR')
    return {
        'schema_version': SCHEMA,
        'estado': 'EXCERTO_LOCALIZADO_REGRA_E_ITEM_COTEJADOS_SEM_AUTORIDADE',
        'documento_id': g18_result['documento_id'],
        'indice_item':indice_item,
        'xml_sha256':g18_result['xml_sha256'],
        'pdf_sha256':pdf_sha256,
        'extraction_result_id':extraction_result.extraction_result_id,
        'normative_artifact_id':extraction_result.normative_artifact_id,
        'rule_id':rule_version.rule_id,'rule_version':rule_version.rule_version,
        'rule_hash':rule_version.rule_hash,
        'pagina_1_based':page,'inicio_caracter':start,
        'pagina_texto_sha256':anchor['pagina_texto_sha256'],
        'excerto_sha256':anchor['excerto_sha256'],
        'dispositivo_declarado':anchor['dispositivo_declarado'],
        'mva_percentual_declarada':str(mva),
        'aliquota_percentual_declarada':str(ali),
        'formula_candidata':'(vProd*(1+MVA))*aliquota-vICMS_XML',
        'excerto_presente_nos_bytes_pdf_extraidos':True,
        'prova_de_relacao_semantica_entre_excerto_e_parametros':False,
        'hash_pdf_distinto_hash_excerto':True,
        'reconciliacao_com_calculo_g12':False,
        'consultas_db_neste_servico':0,
        **{name: False for name in _UNTRUSTED},
    }

__all__ = ['SCHEMA','G113EvidenceError','cotejar_excerto_normativo_g113']
