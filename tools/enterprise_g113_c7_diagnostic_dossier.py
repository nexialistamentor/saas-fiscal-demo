"""SOLVERIS Enterprise C7 - read-only investigatory item dossier from C3-C6.

No DB/network, tax recomputation, SEFAZ authentication or tax-credit claim.
Upstream snapshots are declarations of caller; require execution by trusted
orchestrator. Existing G1 numerical comparison is NOT independent legal tax.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C7_INTERNAL_ITEM_DOSSIER_V1'
SCHEMAS = {
    'c3':'SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1',
    'c4':'SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1',
    'c5':'SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1',
    'c6':'SOLVERIS_ENTERPRISE_G113_C6_L2_RECORD_PROVENANCE_V1',
}
DENIED = ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente')
SHA = re.compile(r'[0-9a-f]{64}\Z')
DEC = re.compile(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z')
MONEY = re.compile(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?\Z')

class G113C7GateError(ValueError):
    pass

def _stop(reason):
    raise G113C7GateError('G113_C7_' + reason)

def _number(raw, regex):
    if type(raw) is not str or regex.fullmatch(raw) is None:
        _stop('NUMERO_NAO_CANONICO')
    try:
        value = Decimal(raw)
    except InvalidOperation:
        _stop('NUMERO_INVALIDO')
    if not value.is_finite():
        _stop('NUMERO_NAO_FINITO')
    return value

def _sha(s):
    return type(s) is str and SHA.fullmatch(s) is not None

def _proof_false(result):
    return type(result) is dict and all(result.get(k) is False for k in DENIED)

def preparar_dossie_investigativo_g113_c7(*, c3_result:dict, c4_result:dict,
        c5_result:dict, c6_result:dict, indice_item:int, c1_result:dict|None=None) -> dict:
    """Reconcile *previously verified* upstream results; no tax decision.

    The only monetary figures are the two existing G1 numeric comparisons.
    No amount here represents payment, overpayment, recoverable credit or loss.
    An optionally supplied C1 result must match exact C3 PDF/excerpt hashes,
    but still cannot establish TabelaMVA FK or juridical applicability.
    """
    if type(indice_item) is not int or not 1 <= indice_item <= 500:
        _stop('ITEM_INVALIDO')
    data = {'c3':c3_result,'c4':c4_result,'c5':c5_result,'c6':c6_result}
    for key,result in data.items():
        if (not _proof_false(result) or result.get('schema_version') != SCHEMAS[key]
                or result.get('indice_item') != indice_item):
            _stop(key.upper()+'_CONTRATO_OU_AUTORIDADE')
    if (c3_result.get('estado') != 'CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE'
            or c3_result.get('verificacao_pdf_pagina_excerto') is not True
            or c5_result.get('parametros_motor_cotejados') is not True
            or c4_result.get('estado') != 'CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL'
            or c5_result.get('estado') not in (
                'MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE',
                'DIVERGENCIA_MVA_USADA_VS_CANDIDATA_SEM_DECISAO_FISCAL')
            or c6_result.get('estado') != 'REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020'):
        _stop('SEM_PONTE_UPSTREAM_COMPLETA')
    for name in ('pdf_sha256','excerto_sha256'):
        if not _sha(c3_result.get(name)) or c4_result.get(name) != c3_result[name]:
            _stop('PDF_OU_EXCERTO_DIVERGENTE')
    if (c4_result.get('versao_c3') != c3_result.get('versao_selecionada')
            or c4_result.get('mva_observada_c3') != c3_result.get('mva_original_percentual_observada')
            or c5_result.get('versao_documental_c3') != c3_result.get('versao_selecionada')
            or c5_result.get('mva_c3_percentual_observada') != c3_result.get('mva_original_percentual_observada')):
        _stop('VERSAO_C3_DIVERGENTE')
    if c4_result.get('data_operacao') != c3_result.get('data_operacao_declarada'):
        _stop('DATA_OPERACAO_DIVERGENTE')
    for k in ('uf','ncm','cest'):
        if c3_result.get(k) != c4_result.get(k) or c6_result.get(k) != c4_result.get(k):
            _stop('CLASSIFICACAO_DIVERGENTE')
    if (c4_result.get('xml_sha256') != c5_result.get('xml_sha256')
            or c4_result.get('xml_sha256') != c6_result.get('xml_sha256')
            or not _sha(c4_result.get('xml_sha256'))
            or c4_result.get('documento_id') != c5_result.get('documento_id')
            or c4_result.get('documento_id') != c6_result.get('documento_id')
            or c4_result.get('chave_nfe') != c5_result.get('chave_nfe')):
        _stop('DOCUMENTO_DIVERGENTE')
    if (not type(c6_result.get('identificador_registo_l2_observado')) is int
            or c6_result['identificador_registo_l2_observado'] < 1
            or c6_result.get('vinculo_adr020_comprovado') is not False
            or c6_result.get('unicidade_registos_vigentes_comprovada') is not False
            or c6_result.get('correspondencia_cest_l2_comprovada') is not False):
        _stop('L2_REGISTO_OU_TRUST_INVALIDO')
    candidate = _number(c3_result['mva_original_percentual_observada'], DEC)
    used = _number(c5_result.get('mva_motor_percentual'), DEC)
    if (used != _number(c6_result.get('mva_motor_percentual'), DEC)
            or used - candidate != _number(c5_result.get('diferencial_mva_pontos_percentuais'), re.compile(r'-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,8})?\Z'))
            or (used == candidate) != (c5_result['estado'] == 'MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE')):
        _stop('MVA_EXECUTADA_DIVERGENTE')
    if (_number(c5_result.get('aliquota_motor_percentual'), DEC)
            != _number(c6_result.get('aliquota_motor_percentual'), DEC)):
        _stop('ALIQUOTA_DIVERGENTE')
    pairs = c4_result.get('comparacao_g1')
    if type(pairs) is not dict or set(pairs) != {'BASE_ST','ICMS_ST'}:
        _stop('PARES_G1_AUSENTES')
    # C5 also witnesses the G12 motor amounts; do not trust C4 alone.
    if (_number(c5_result.get('base_st_motor'), MONEY) != _number(pairs['BASE_ST'].get('valor_motor_g12'), MONEY)
            or _number(c5_result.get('icms_st_motor'), MONEY) != _number(pairs['ICMS_ST'].get('valor_motor_g12'), MONEY)):
        _stop('C5_MONTANTES_MOTOR_DIVERGENTES')
    comparison = {}
    for key in ('BASE_ST','ICMS_ST'):
        pair = pairs[key]
        if type(pair) is not dict or pair.get('prova_normativa') is not False:
            _stop('PAR_G1_INVALIDO')
        x = _number(pair.get('valor_xml'), MONEY)
        y = _number(pair.get('valor_motor_g12'), MONEY)
        rawdiff = pair.get('diferenca_motor_menos_xml')
        expected = (y-x).quantize(Decimal('.01'))
        try:
            displayed = Decimal(rawdiff) if type(rawdiff) is str else None
        except InvalidOperation:
            displayed = None
        if (displayed != expected or type(pair.get('divergencia_numerica')) is not bool
                or pair['divergencia_numerica'] != (abs(y-x)>Decimal('.01'))):
            _stop('PAR_G1_INCONSISTENTE')
        comparison[key] = {
            'valor_xml':str(x.quantize(Decimal('.01'))),
            'valor_motor_condicional':str(y.quantize(Decimal('.01'))),
            'diferenca_motor_menos_xml':str(expected),
            'divergencia_numerica':pair['divergencia_numerica'],
            'credito_comprovado':False,
        }
    adr020 = None
    if c1_result is not None:
        if (not _proof_false(c1_result)
                or c1_result.get('schema_version') != 'SOLVERIS_ENTERPRISE_G113_EXACT_PAGE_RULE_ITEM_V1'
                or c1_result.get('estado') != 'EXCERTO_LOCALIZADO_REGRA_E_ITEM_COTEJADOS_SEM_AUTORIDADE'
                or c1_result.get('indice_item') != indice_item
                or c1_result.get('documento_id') != c4_result['documento_id']
                or c1_result.get('xml_sha256') != c4_result['xml_sha256']
                or c1_result.get('pdf_sha256') != c3_result['pdf_sha256']
                or c1_result.get('excerto_sha256') != c3_result['excerto_sha256']
                or c1_result.get('mva_percentual_declarada') is None
                or _number(c1_result['mva_percentual_declarada'], DEC) != candidate
                or _number(c1_result.get('aliquota_percentual_declarada'), DEC)
                    != _number(c5_result.get('aliquota_motor_percentual'), DEC)
                or type(c1_result.get('rule_id')) is not str
                or type(c1_result.get('rule_version')) is not int
                or not _sha(c1_result.get('rule_hash'))
                or c1_result.get('prova_de_relacao_semantica_entre_excerto_e_parametros') is not False):
            _stop('C1_EXCERTO_REGRA_NAO_CONCILIADOS')
        adr020={'rule_id_declarado':c1_result['rule_id'],
                'rule_version_declarada':c1_result['rule_version'],
                'rule_hash_observado':c1_result['rule_hash'],
                'vinculo_entre_registo_l2_e_adr020_comprovado':False}
    blockers = [
        'L2_SEM_CEST_COMO_CHAVE_DE_CONSULTA',
        'L2_UNICIDADE_NAO_COMPROVADA',
        'L2_SEM_FK_A_RULEVERSION_ADR020',
        'VIGENCIA_EXCECOES_BENEFICIOS_NAO_COMPROVADOS',
        'ALIQ_INTERNA_NAO_AUTENTICADA_POR_FONTE_INDEPENDENTE',
        'ICMS_PROPRIO_NAO_RECALCULADO_INDEPENDENTEMENTE',
        'AUTENTICIDADE_SEFAZ_E_POSSE_EXTERNA_NAO_COMPROVADAS',
        'EFD_E_RECOLHIMENTO_NAO_CONCILIADOS',
        'PERIODO_NORMATIVO_POSTERIOR_NAO_EXAUSTIVO',
        'REVISAO_TRIBUTARIA_ESPECIALIZADA_PENDENTE',
    ]
    if adr020 is None:
        blockers.append('C1_SEM_CADEIA_DE_EXCERTO_REGRA_EM_EXECUCAO')
    return {
        'schema_version':SCHEMA, 'estado':'DOSSIER_INTERNO_NAO_PUBLICAVEL',
        'indice_item':indice_item, 'documento_id':c4_result['documento_id'],
        'empresa_id':c4_result.get('empresa_id'), 'relatorio_id':c4_result.get('relatorio_id'),
        'chave_nfe_declarada':c4_result.get('chave_nfe'),
        'xml_sha256':c4_result['xml_sha256'],
        'data_operacao_declarada':c4_result['data_operacao'],
        'uf':c4_result['uf'],'ncm':c4_result['ncm'],'cest':c4_result['cest'],
        'fonte_pdf_sha256':c3_result['pdf_sha256'],
        'excerto_sha256':c3_result['excerto_sha256'],
        'versao_documental':c3_result['versao_selecionada'],
        'mva_documental_candidata_percentual':str(candidate),
        'mva_utilizada_motor_percentual':str(used),
        'mva_divergencia_pontos_percentuais':str(used-candidate),
        'aliquota_motor_percentual':c5_result['aliquota_motor_percentual'],
        'id_registo_l2_observado':c6_result['identificador_registo_l2_observado'],
        'adr020_c1':adr020,'comparacoes_monetarias_condicionais':comparison,
        'alerta_investigativo':'DIVERGENCIA_NUMERICA_A_REVER' if any(p['divergencia_numerica'] for p in comparison.values()) else 'COINCIDENCIA_NUMERICA_NAO_PROVA_CONFORMIDADE',
        'pendencias_para_decisao_fiscal':blockers,
        'resultado_nao_comprova_pagamento_indevido':True,
        'fonte_primaria_autenticada':False,'aplicabilidade_juridica_comprovada':False,
        'completude_normativa_comprovada':False,'recolhimento_verificado':False,
        'credito_recuperavel_demonstrado':False,
        **{k:False for k in DENIED},
    }

__all__ = ['SCHEMA','G113C7GateError','preparar_dossie_investigativo_g113_c7']
