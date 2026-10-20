"""SOLVERIS Enterprise G1.13-C6: observational L2 MVA row provenance.

Reconcile the TabelaMVA row identity already selected by buscar_mva() with
G1.2's executed parameters and C5's bounded numeric audit. No queries,
writes, legal eligibility, ADR-020 assertion, or payment decisions.
Caller-supplied snapshots are not proof of authenticated DB execution.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C6_L2_RECORD_PROVENANCE_V1'
C5_SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C5_PARAMETER_TRACE_V1'
C4_SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1'
G12_SCHEMA = 'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1'
_TRACE_KEYS = frozenset({
    'versao', 'registro_mva_id', 'uf', 'ncm', 'data_referencia',
    'vigencia_inicio', 'vigencia_fim', 'fonte_legal', 'url_fonte',
    'importado_por_declarado', 'mva_fracao_registo', 'aliquota_fracao_registo',
    'unicidade_registos_vigentes_comprovada', 'vinculo_adr020_comprovado',
    'autenticidade_fonte_externa_comprovada', 'autoridade_fiscal',
})
_DEC = re.compile(r'(?:0|[1-9][0-9]{0,2})(?:\.[0-9]{1,12})?\Z')
_DENIED = ('autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado', 'usavel_comercialmente')

class G113C6EvidenceError(ValueError):
    pass


def _stop(reason):
    raise G113C6EvidenceError('G113_C6_' + reason)


def _decimal(value):
    if type(value) is not str or _DEC.fullmatch(value) is None:
        _stop('NUMERO_INVALIDO')
    try:
        return Decimal(value)
    except InvalidOperation:
        _stop('NUMERO_INVALIDO')


def _day(value):
    if type(value) is not str:
        _stop('DATA_INVALIDA')
    try:
        d = date.fromisoformat(value)
    except ValueError:
        _stop('DATA_INVALIDA')
    if d.isoformat() != value:
        _stop('DATA_NAO_CANONICA')
    return d


def _blocked(result):
    return type(result) is dict and all(result.get(key) is False for key in _DENIED)


def cotejar_registo_l2_g113_c6(*, c4_result:dict, c5_result:dict,
                                 g13_result:dict, indice_item:int) -> dict:
    """Verify row identifier and fields from the same G12 result observed by C5.

    The row ID is an *internal selected row*, not documentary/legal authority.
    CEST, operation nature, benefits, and regime are not keys of TabelaMVA.
    """
    if type(indice_item) is not int or not 1 <= indice_item <= 500:
        _stop('INDICE_ITEM_INVALIDO')
    if (not _blocked(c4_result) or c4_result.get('schema_version') != C4_SCHEMA
            or c4_result.get('indice_item') != indice_item
            or c4_result.get('estado') != 'CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL'):
        _stop('C4_INVALIDO')
    if (not _blocked(c5_result) or c5_result.get('schema_version') != C5_SCHEMA
            or c5_result.get('indice_item') != indice_item
            or c5_result.get('xml_sha256') != c4_result.get('xml_sha256')
            or c5_result.get('documento_id') != c4_result.get('documento_id')
            or c5_result.get('chave_nfe') != c4_result.get('chave_nfe')
            or c5_result.get('parametros_motor_cotejados') is not True
            or c5_result.get('estado') not in (
                'MVA_USADA_COINCIDE_COM_CANDIDATO_DOCUMENTAL_SEM_AUTORIDADE',
                'DIVERGENCIA_MVA_USADA_VS_CANDIDATA_SEM_DECISAO_FISCAL')
            or c5_result.get('regra_normativa_persistida_vinculada') is not False):
        _stop('C5_INVALIDO')
    if (not _blocked(g13_result) or g13_result.get('xml_sha256') != c4_result['xml_sha256']
            or any(g13_result.get(k) != c4_result.get(k)
                   for k in ('empresa_id','relatorio_id','documento_id'))):
        _stop('G13_INVALIDO')
    g12 = g13_result.get('confronto_condicional_g12')
    if (not _blocked(g12) or g12.get('schema_version') != G12_SCHEMA
            or g12.get('xml_sha256') != c4_result['xml_sha256']
            or type(g12.get('itens')) is not list
            or g12.get('itens_total') != len(g12['itens'])
            or not 1 <= indice_item <= len(g12['itens'])):
        _stop('G12_INVALIDO')
    item = g12['itens'][indice_item-1]
    if (type(item) is not dict or item.get('indice_item') != indice_item
            or item.get('ncm') != c4_result.get('ncm')
            or item.get('estado') != 'SIMULACAO_CONDICIONAL_MVA'):
        _stop('G12_ITEM_INVALIDO')
    trace = item.get('rastro_parametros_g12_v1')
    if (type(trace) is not dict or trace.get('identidade_registo_normativo_comprovada') is not False
            or trace.get('regra_adr020_comprovada') is not False
            or trace.get('autoridade_fiscal') is not False
            or trace.get('credito_confirmado') is not False):
        _stop('C5_RASTRO_INVALIDO')
    common = dict(
        schema_version=SCHEMA, indice_item=indice_item,
        documento_id=c4_result['documento_id'], xml_sha256=c4_result['xml_sha256'],
        uf=c4_result.get('uf'), ncm=c4_result.get('ncm'), cest=c4_result.get('cest'),
        identificador_registo_l2_observado=None,
        unicidade_registos_vigentes_comprovada=False,
        correspondencia_cest_l2_comprovada=False,
        vinculo_adr020_comprovado=False,
        aplicabilidade_juridica_comprovada=False,
        fonte_primaria_autenticada=False,
        credito_recuperavel_demonstrado=False,
        **{k:False for k in _DENIED},
    )
    row = item.get('proveniencia_l2_g12_v1')
    if row is None:
        return dict(common, estado='ABSTENCAO_SEM_IDENTIDADE_REGISTO_L2',
                    motivo='BUSCAR_MVA_NAO_FORNECEU_ID_OBSERVAVEL')
    if type(row) is not dict or set(row) != _TRACE_KEYS:
        _stop('PROVENIENCIA_FORMA_INVALIDA')
    if (row['versao'] != 1
            or type(row['registro_mva_id']) is not int or row['registro_mva_id'] <= 0
            or any(row[k] is not False for k in (
                'unicidade_registos_vigentes_comprovada','vinculo_adr020_comprovado',
                'autenticidade_fonte_externa_comprovada','autoridade_fiscal'))):
        _stop('PROVENIENCIA_ID_OU_TRUST_INVALIDO')
    if (row['uf'] != c4_result.get('uf') or row['ncm'] != c4_result.get('ncm')
            or row['fonte_legal'] != trace.get('fonte_legal_consultada')
            or row['url_fonte'] != trace.get('url_fonte_consultada')
            or row['importado_por_declarado'] is not None and
            type(row['importado_por_declarado']) is not str):
        _stop('REGISTO_IDENTIDADE_OU_FONTE_DIVERGENTE')
    operation = _day(c4_result.get('data_operacao'))
    reference = _day(row['data_referencia'])
    start = _day(row['vigencia_inicio'])
    end = _day(row['vigencia_fim']) if row['vigencia_fim'] is not None else None
    if reference != operation or start > operation or (end is not None and end < operation):
        _stop('VIGENCIA_REGISTO_DIVERGENTE')
    mva = _decimal(row['mva_fracao_registo'])
    ali = _decimal(row['aliquota_fracao_registo'])
    if (mva != _decimal(trace.get('mva_fracao_utilizada'))
            or ali != _decimal(trace.get('aliquota_fracao_utilizada'))
            or mva*100 != _decimal(c5_result.get('mva_motor_percentual'))
            or ali*100 != _decimal(c5_result.get('aliquota_motor_percentual'))):
        _stop('PARAMETROS_L2_EXECUCAO_DIVERGENTES')
    return dict(common,
        estado='REGISTO_L2_IDENTIFICADO_SEM_UNICIDADE_OU_ADR020',
        motivo='IDENTIDADE_INTERNA_SEM_PROVA_DE_REGRA_JURIDICA_APLICAVEL',
        identificador_registo_l2_observado=row['registro_mva_id'],
        fonte_legal_declarada=row['fonte_legal'],
        url_fonte_declarada=row['url_fonte'],
        mva_motor_percentual=str(mva*100),
        aliquota_motor_percentual=str(ali*100),
        vigencia_inicio_registo=row['vigencia_inicio'],
        vigencia_fim_registo=row['vigencia_fim'],
    )

__all__ = ['SCHEMA','G113C6EvidenceError','cotejar_registo_l2_g113_c6']
