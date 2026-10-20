"""G1.13-C5: verify parameters actually returned by G1.2 against C3/C4.

Read-only, pure bridge. Does not call calculation engines or grant legal trust.
The source instrumentation patch is separately pinned and tested.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1'
C4 = 'SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1'
C3 = 'SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1'
G12 = 'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1'
HEX = re.compile(r'[0-9a-f]{64}\Z')
CURRENCY = re.compile(r'(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z')
DECIMAL = re.compile(r'(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,12})?\Z')
TRACE_KEYS = frozenset({
    'versao','mva_fracao_utilizada','aliquota_fracao_utilizada',
    'fonte_legal_consultada','url_fonte_consultada','nivel_confianca_registro',
    'vprod_xml','icms_proprio_xml','base_st_motor','icms_st_motor',
    'metodo_base','identidade_registo_normativo_comprovada',
    'regra_adr020_comprovada','autoridade_fiscal','credito_confirmado',
})
DENIED = ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente')

class G113C5EvidenceError(ValueError):
    pass

def _stop(code):
    raise G113C5EvidenceError('G113_C5_' + code)

def _dec(s, expression):
    if type(s) is not str or expression.fullmatch(s) is None:
        _stop('NUMERO_NAO_CANONICO')
    try:
        value = Decimal(s)
    except (InvalidOperation, ValueError):
        _stop('NUMERO_INVALIDO')
    if not value.is_finite():
        _stop('NUMERO_NAO_FINITO')
    return value

def _money(s):
    return _dec(s, CURRENCY)

def _sha(s):
    return type(s) is str and HEX.fullmatch(s) is not None

def _trusted_false(d):
    return type(d) is dict and all(d.get(name) is False for name in DENIED)

def cotejar_rastro_parametros_g113_c5(*, c4_result:dict, c3_result:dict,
        g13_result:dict, g14_item:dict, indice_item:int) -> dict:
    """Reconcile G12 actual used parameters; NOT normative applicability.

    Requires caller's authentic upstream G13/G14/C3/C4 calls; this method cannot
    independently prove DB persistence or real-NFe/SEFAZ authenticity.
    """
    if type(indice_item) is not int or not 1 <= indice_item <= 500:
        _stop('ITEM_INVALIDO')
    if (type(c4_result) is not dict or c4_result.get('schema_version') != C4
        or c4_result.get('indice_item') != indice_item
        or not _sha(c4_result.get('xml_sha256'))
        or not _trusted_false(c4_result)
        or c4_result.get('fonte_mva_motor_g12_demonstrada') is not False):
        _stop('C4_INVALIDO_OU_AUTORIDADE_FORJADA')
    if (type(g13_result) is not dict or not _trusted_false(g13_result)
        or g13_result.get('xml_sha256') != c4_result['xml_sha256']
        or any(g13_result.get(k) != c4_result.get(k) for k in
               ('empresa_id','relatorio_id','documento_id'))):
        _stop('G13_IDENTIDADE_DIVERGENTE')
    if (type(c3_result) is not dict or c3_result.get('schema_version') != C3
        or c3_result.get('estado') != 'CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE'
        or not _trusted_false(c3_result)
        or c3_result.get('indice_item') != indice_item
        or c3_result.get('verificacao_pdf_pagina_excerto') is not True
        or not _sha(c3_result.get('pdf_sha256'))
        or not _sha(c3_result.get('excerto_sha256'))
        or c3_result.get('pdf_sha256') != c4_result.get('pdf_sha256')
        or c3_result.get('excerto_sha256') != c4_result.get('excerto_sha256')
        or c3_result.get('mva_original_percentual_observada') != c4_result.get('mva_observada_c3')
        or c3_result.get('versao_selecionada') != c4_result.get('versao_c3')
        or any(c3_result.get(k) != c4_result.get(v) for k,v in
               (('uf','uf'),('ncm','ncm'),('cest','cest'),('data_operacao_declarada','data_operacao')))):
        _stop('C3_CANDIDATO_DIVERGENTE')
    if (type(g14_item) is not dict or g14_item.get('indice_item') != indice_item
        or g14_item.get('estado') != 'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST'
        or g14_item.get('sha256_texto_normativo_declarado') != c3_result['pdf_sha256']
        or any(g14_item.get(k) != c4_result.get(v) for k,v in
               (('uf_operacao','uf'),('ncm','ncm'),('cest_observado','cest')))):
        _stop('G14_IDENTIDADE_DIVERGENTE')
    if c4_result.get('estado') != 'CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL':
        _stop('C4_SEM_COMPARACAO_NUMERICA')
    pairs = c4_result.get('comparacao_g1')
    if (type(pairs) is not dict or set(pairs) != {'ICMS_ST','BASE_ST'}):
        _stop('C4_PARES_NUMERICOS_INVALIDOS')
    for pair in pairs.values():
        if type(pair) is not dict:
            _stop('C4_PAR_INVALIDO')
        _money(pair.get('valor_motor_g12'))
    g12 = g13_result.get('confronto_condicional_g12')
    if (type(g12) is not dict or g12.get('schema_version') != G12
        or g12.get('xml_sha256') != c4_result['xml_sha256'] or not _trusted_false(g12)
        or type(g12.get('itens')) is not list
        or g12.get('itens_total') != len(g12['itens'])
        or not 1 <= indice_item <= len(g12['itens'])):
        _stop('G12_IDENTIDADE_INVALIDA')
    item = g12['itens'][indice_item-1]
    if (type(item) is not dict or item.get('indice_item') != indice_item
        or item.get('estado') != 'SIMULACAO_CONDICIONAL_MVA'
        or item.get('metodo_base') != 'iva_st'
        or item.get('comparacao_condicional') is not True
        or item.get('fonte_original_autenticada') is not False
        or item.get('ncm') != c4_result['ncm']):
        _stop('G12_ITEM_INCONSISTENTE')
    common = {
        'schema_version':SCHEMA, 'indice_item':indice_item,
        'xml_sha256':c4_result['xml_sha256'], 'documento_id':c4_result.get('documento_id'),
        'chave_nfe':c4_result.get('chave_nfe'),
        'mva_c3_percentual_observada':c3_result['mva_original_percentual_observada'],
        'versao_documental_c3':c3_result['versao_selecionada'],
        'fonte_primaria_autenticada':False,
        'prova_aplicabilidade_juridica':False,
        'regra_normativa_persistida_vinculada':False,
        'icms_proprio_recalculado_independentemente':False,
        'credito_recuperavel_demonstrado':False,
        **{k:False for k in DENIED},
    }
    trace = item.get('rastro_parametros_g12_v1')
    if trace is None:
        return dict(common,estado='ABSTENCAO_G12_SEM_RASTRO_DE_EXECUCAO',
                    motivo='EXECUCAO_G12_NAO_PUBLICOU_PARAMETROS',
                    mva_motor_percentual=None, diferencial_mva_pontos_percentuais=None,
                    parametros_motor_cotejados=False)
    if type(trace) is not dict or set(trace) != TRACE_KEYS:
        _stop('RASTRO_FORMA_INVALIDA')
    if (trace['versao'] != 1 or trace['metodo_base'] != 'iva_st'
        or trace['nivel_confianca_registro'] != 'oficial'
        or any(trace.get(k) is not False for k in
               ('identidade_registo_normativo_comprovada','regra_adr020_comprovada',
                'autoridade_fiscal','credito_confirmado'))):
        _stop('RASTRO_AUTORIDADE_OU_METODO_INCOMPATIVEL')
    if (type(trace['fonte_legal_consultada']) is not str
        or not trace['fonte_legal_consultada'].strip()
        or trace['fonte_legal_consultada'] != g14_item.get('fonte_legal_candidata')):
        _stop('RASTRO_FONTE_DIVERGENTE')
    if (trace['url_fonte_consultada'] is not None
        and (type(trace['url_fonte_consultada']) is not str
             or not trace['url_fonte_consultada'].startswith('https://'))):
        _stop('RASTRO_URL_INVALIDA')
    mva = _dec(trace['mva_fracao_utilizada'], DECIMAL)
    aliquota = _dec(trace['aliquota_fracao_utilizada'], DECIMAL)
    if not 0 < aliquota <= 1 or not 0 < mva <= Decimal('9.99'):
        _stop('RASTRO_PARAMETROS_FORA_DE_ESCOPO')
    base = _money(trace['base_st_motor'])
    st = _money(trace['icms_st_motor'])
    product = _money(trace['vprod_xml'])
    own = _money(trace['icms_proprio_xml'])
    if (product <= 0 or own > product
        or base != _money(pairs['BASE_ST']['valor_motor_g12'])
        or st != _money(pairs['ICMS_ST']['valor_motor_g12'])):
        _stop('RASTRO_MONTANTES_G1_DIVERGENTES')
    # Only numerical reconstruction of the *same* observed trace, not an
    # independent legal assessment. The legacy motor uses float + round.
    if (abs(base - product*(1+mva)) > Decimal('.011')
        or abs(st - max(Decimal('0'), base*aliquota-own)) > Decimal('.011')):
        _stop('RASTRO_ARITMETICA_INTERNA_DIVERGENTE')
    candidate = _dec(c3_result['mva_original_percentual_observada'], DECIMAL)
    used = mva*100
    delta = used-candidate
    return dict(common,
        estado=('MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE'
                if delta == 0 else 'DIVERGENCIA_MVA_USADA_VS_CANDIDATA_SEM_DECISAO_FISCAL'),
        motivo='FONTE_E_PARAMETROS_OBSERVADOS_NAO_PROVAM_APLICABILIDADE_DA_NORMA',
        mva_motor_percentual=str(used),
        diferencial_mva_pontos_percentuais=str(delta),
        aliquota_motor_percentual=str(aliquota*100),
        parametros_motor_cotejados=True,
        mva_motor_igual_candidata_documental=delta==0,
        base_st_motor=str(base),icms_st_motor=str(st))

__all__ = ['SCHEMA','G113C5EvidenceError','cotejar_rastro_parametros_g113_c5']
