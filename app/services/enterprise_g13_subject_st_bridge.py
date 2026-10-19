"""G1.3: I2 documentary custody -> G1.2 conditional ST item reconciliation.

Read-only internal bridge; reuse real I2 ownership/provenance and G12 calculation.
No SEFAZ/authenticated certificate, normative act authenticity, CEST, EFD,
recolhimento, credit, legal entitlement, or checkout asserted here.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from app.services.enterprise_i2_documentary_bridge import projetar_diagnostico_integral_i2
from app.services.enterprise_g12_st_item_reconciliation import confrontar_st_por_item_g12

SCHEMA = 'SOLVERIS_ENTERPRISE_G13_SUBJECT_ST_ITEM_BRIDGE_V1'
_I2_SCHEMA = 'ENTERPRISE_I2_DOCUMENTARY_BRIDGE_V1'
_G12_SCHEMA = 'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_KEY = re.compile(r'[0-9]{44}\Z')
_COMP = re.compile(r'20\d\d-(?:0[1-9]|1[0-2])\Z')
_ALLOWED_ST = frozenset({
    'G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE',
    'G12_SIMULACAO_PARCIAL_SEM_AUTORIDADE',
    'G12_SEM_SIMULACAO',
})


class EnterpriseG13GateError(ValueError):
    """Explicit fail-closed STOP; no partially authoritative result."""


def _stop(code):
    raise EnterpriseG13GateError(code)


def _id(v):
    return type(v) is int and v > 0


def _sha(v):
    return type(v) is str and _HEX.fullmatch(v) is not None


def _nfe_key(v):
    return type(v) is str and _KEY.fullmatch(v) is not None


def projetar_confronto_st_sujeito_g13(*, db, authenticated_user_id: int,
                                      empresa_id: int, relatorio_id: int,
                                      xml_bytes: bytes) -> dict:
    """Evaluate I2 (mandatory) then G12 on the *same exact bytes and db*.

    The bridge itself is internal and isolated: it does not persist, authorize
    marketing, or promote a G12 mathematical match to proof of a lawful tax.
    """
    if (db is None or not all(map(_id, (authenticated_user_id, empresa_id, relatorio_id)))
            or type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 2*1024*1024):
        _stop('G13_ENTRADA_INVALIDA')
    fingerprint = hashlib.sha256(xml_bytes).hexdigest()
    # I2 checks ownership, persisted report fingerprint, byte hash, emitter,
    # document and row identities; do not try to reconstruct a second authority.
    try:
        i2 = projetar_diagnostico_integral_i2(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes)
    except Exception as exc:
        raise EnterpriseG13GateError('G13_I2_DOCUMENTO_OU_POSSE_NAO_COMPROVADOS') from exc
    if (type(i2) is not dict or i2.get('schema_version') != _I2_SCHEMA
            or i2.get('uso') != 'INTERNO_NAO_PUBLICAVEL'
            or i2.get('checkout_autorizado') is not False
            or i2.get('diagnostico_empresarial_completo') is not False
            or i2.get('comprovacao_normativa') is not False):
        _stop('G13_I2_CONTRATO_INCOMPATIVEL')
    documentary = i2.get('documental_i2')
    if (type(documentary) is not dict
            or documentary.get('estado') != 'DOCUMENTO_INTERNO_RECONCILIADO'
            or documentary.get('documento_id') is None
            or not _id(documentary.get('documento_id'))
            or documentary.get('relatorio_id') != relatorio_id
            or not _sha(documentary.get('xml_sha256'))
            or not hmac.compare_digest(documentary['xml_sha256'], fingerprint)
            or not _nfe_key(documentary.get('chave_nfe'))
            or type(documentary.get('competencia_observada')) is not str
            or _COMP.fullmatch(documentary['competencia_observada']) is None
            or documentary.get('autenticidade_sefaz_verificada') is not False
            or documentary.get('escrituracao_efd_verificada') is not False
            or documentary.get('norma_vigente_verificada') is not False
            or documentary.get('recolhimento_verificado') is not False
            or documentary.get('credibilidade_credito_fiscal') is not False):
        _stop('G13_I2_IDENTIDADE_OU_AUTORIDADE_INCONSISTENTE')
    observed = documentary.get('itens_xml_observados')
    if (type(observed) is not list or not 0 < len(observed) <= 500):
        _stop('G13_I2_ITENS_INVALIDOS')
    for idx, item in enumerate(observed, 1):
        if (type(item) is not dict or item.get('nItem') != idx
                or type(item.get('ncm')) is not str or not re.fullmatch(r'\d{8}',item['ncm'])
                or type(item.get('cfop')) is not str or not re.fullmatch(r'[56]\d{3}',item['cfop'])):
            _stop('G13_I2_ITEM_OBSERVADO_INCONSISTENTE')
    try:
        g12 = confrontar_st_por_item_g12(db=db, xml_bytes=xml_bytes)
    except Exception as exc:
        raise EnterpriseG13GateError('G13_G12_MOTOR_INDISPONIVEL') from exc
    if (type(g12) is not dict or g12.get('schema_version') != _G12_SCHEMA
            or g12.get('estado') not in _ALLOWED_ST
            or not _sha(g12.get('xml_sha256'))
            or not hmac.compare_digest(g12['xml_sha256'],fingerprint)
            or type(g12.get('itens_total')) is not int
            or g12['itens_total'] != len(observed)
            or type(g12.get('itens_simulados')) is not int
            or not 0 <= g12['itens_simulados'] <= len(observed)
            or any(g12.get(f) is not False for f in (
                'autoridade_fiscal','norma_juridicamente_ratificada',
                'icms_proprio_recalculado_por_fonte_independente',
                'documento_autenticado_sefaz','credito_confirmado',
                'checkout_autorizado','usavel_comercialmente'))):
        _stop('G13_G12_PROVA_OU_IDENTIDADE_INCOMPATIVEL')
    g12items = g12.get('itens')
    if type(g12items) is not list or len(g12items) != len(observed):
        _stop('G13_G12_CARDINALIDADE_INCOMPATIVEL')
    conditional = 0
    for idx, (original, calc) in enumerate(zip(observed, g12items), 1):
        if (type(calc) is not dict or calc.get('indice_item') != idx
                or calc.get('ncm') != original['ncm']
                or calc.get('cfop') != original['cfop']
                or calc.get('competencia') != documentary['competencia_observada']
                or calc.get('fonte_original_autenticada') is not False
                or type(calc.get('comparacao_condicional')) is not bool):
            _stop('G13_G12_ITEM_OU_COMPETENCIA_DIVERGENTE')
        simulated = calc['comparacao_condicional']
        if simulated:
            conditional += 1
            if (calc.get('estado') != 'SIMULACAO_CONDICIONAL_MVA'
                    or calc.get('metodo_base') != 'iva_st'
                    or type(calc.get('fonte_legal_informada')) is not str
                    or not calc['fonte_legal_informada'].strip()):
                _stop('G13_G12_SIMULACAO_SEM_RASTRO_NORMATIVO')
        elif calc.get('estado') == 'SIMULACAO_CONDICIONAL_MVA':
            _stop('G13_G12_SIMULACAO_NAO_CONTABILIZADA')
    if conditional != g12['itens_simulados']:
        _stop('G13_G12_CONTAGEM_SIMULACAO_DIVERGENTE')
    state = ('SIMULACAO_CONDICIONAL_VINCULADA_NAO_AUTORIZADA'
             if conditional == len(observed) else
             'COBERTURA_PARCIAL_VINCULADA_NAO_AUTORIZADA'
             if conditional else 'SEM_SIMULACAO_VINCULADA')
    expected_g12 = ('G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE' if conditional == len(observed)
                    else 'G12_SIMULACAO_PARCIAL_SEM_AUTORIDADE' if conditional else 'G12_SEM_SIMULACAO')
    if g12['estado'] != expected_g12:
        _stop('G13_G12_ESTADO_INCONSISTENTE')
    comparison = g12.get('confronto_g1')
    if (type(comparison) is not dict or comparison.get('consistente') is not None
            or comparison.get('autoridade_fiscal') is not False
            or comparison.get('credito_confirmado') is not False
            or comparison.get('checkout_autorizado') is not False):
        _stop('G13_G1_CONFRONTO_NAO_FALHA_FECHADO')
    # Keep G12 per-item numeric observations, but not I2 aggregate tax planning
    # projections; this result is exclusively for ST conditional analysis.
    return {
        'schema_version':SCHEMA, 'estado':state,
        'empresa_id':empresa_id, 'relatorio_id':relatorio_id,
        'documento_id':documentary['documento_id'],
        'xml_sha256':fingerprint, 'competencia_declarada':documentary['competencia_observada'],
        'chave_nfe':documentary['chave_nfe'],
        'itens_total':len(observed), 'itens_simulados':conditional,
        'confronto_condicional_g12':g12,
        'posse_e_proveniencia_interna_i2':True,
        'assinatura_certificado_icp_brasil_comprovados':False,
        'autenticidade_sefaz_verificada':False,
        'norma_legal_verificada_por_fonte_primaria':False,
        'cest_e_enquadramento_por_operacao_verificados':False,
        'icms_proprio_independente':False,
        'efd_escrituracao_verificada':False,
        'recolhimento_verificado':False,
        'credito_confirmado':False,
        'autoridade_fiscal':False,
        'checkout_autorizado':False,
        'usavel_comercialmente':False,
    }


__all__=['SCHEMA','EnterpriseG13GateError','projetar_confronto_st_sujeito_g13']
