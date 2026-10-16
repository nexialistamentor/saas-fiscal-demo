"""SOLVERIS I1: fronteira Enterprise PIS/Cofins, conservadora e nao comercial.

Nao corrige a engine legada nem declara credito, indébito, recolhimento ou
conformidade. Um registo declarado, embora estruturalmente coerente, NAO prova
norma, autenticidade da NF-e ou escrituracao. Autorizacao comercial sempre False.

O adaptador envolve a projecao integral I0 e elimina, apenas na sua propria
saida I1, valores PIS/Cofins legados potencialmente calculados de ST.
NENHUM caminho MEI/legado o chama automaticamente.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from app.services.enterprise_integral_projection import (
    EnterpriseIntegralProjectionError,
    projetar_diagnostico_integral_i0,
)

SCHEMA_VERSION = 'ENTERPRISE_INTEGRAL_I1_PIS_COFINS_V1'
_COMPONENTES = ('pis', 'cofins', 'credito_pis', 'credito_cofins')
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_COMPETENCIA = re.compile(r'(20[0-9]{2})-(0[1-9]|1[0-2])\Z')
_MONEY = re.compile(r'(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?\Z')


def _quantia(valor: object) -> Decimal | None:
    if type(valor) is not str or _MONEY.fullmatch(valor) is None:
        return None
    try:
        n = Decimal(valor)
    except (InvalidOperation, ValueError):
        return None
    return n if n.is_finite() and n >= 0 else None


def _verificar_documentos(empresa_id: int, evidencia: object):
    """Inspeciona alegacoes DOCUMENTAIS; nunca autentica sua origem externa."""
    if type(evidencia) is not dict:
        return None, 'I1_EVIDENCIA_DOCUMENTAL_AUSENTE'
    if type(evidencia.get('empresa_id')) is not int or evidencia['empresa_id'] != empresa_id:
        return None, 'I1_EMPRESA_EVIDENCIA_DIVERGENTE'
    regime = evidencia.get('regime')
    if regime not in ('real', 'presumido'):
        return None, 'I1_REGIME_NAO_COMPROVADO'
    competencia = evidencia.get('competencia')
    if type(competencia) is not str or _COMPETENCIA.fullmatch(competencia) is None:
        return None, 'I1_COMPETENCIA_INVALIDA'
    documentos = evidencia.get('documentos')
    if type(documentos) is not list or not documentos:
        return None, 'I1_NFES_DE_SAIDA_NAO_VINCULADAS'
    total_receita = Decimal('0.00')
    icms_proprio = Decimal('0.00')
    ids = set()
    hashes = set()
    for doc in documentos:
        if type(doc) is not dict:
            return None, 'I1_DOCUMENTO_ESTRUTURA_INVALIDA'
        documento_id = doc.get('documento_id')
        if type(documento_id) is not int or documento_id <= 0 or documento_id in ids:
            return None, 'I1_DOCUMENTO_ID_AUSENTE_OU_DUPLICADO'
        doc_hash = doc.get('sha256')
        if type(doc_hash) is not str or _SHA.fullmatch(doc_hash) is None or doc_hash in hashes:
            return None, 'I1_HASH_AUSENTE_OU_DUPLICADO'
        ids.add(documento_id)
        hashes.add(doc_hash)
        if (doc.get('empresa_id') != empresa_id or doc.get('competencia') != competencia
            or doc.get('tipo_operacao') != 'saida' or doc.get('papel_empresa') != 'emitente'):
            return None, 'I1_IDENTIDADE_OPERACAO_INCOERENTE'
        if doc.get('modalidade_icms') != 'ICMS_PROPRIO':
            return None, 'I1_ST_NAO_E_ICMS_PROPRIO'
        receita = _quantia(doc.get('receita_documental'))
        icms = _quantia(doc.get('icms_proprio_documental'))
        if receita is None or icms is None:
            return None, 'I1_BASE_OU_ICMS_PROPRIO_NAO_IDENTIFICADO'
        if icms > receita:
            return None, 'I1_ICMS_MAIOR_QUE_RECEITA_DOCUMENTAL'
        total_receita += receita
        icms_proprio += icms
    if total_receita <= 0:
        return None, 'I1_RECEITA_DOCUMENTAL_INSUFICIENTE'
    ano, mes = map(int, competencia.split('-'))
    return {
        'regime': regime,
        'data_referencia': date(ano, mes, 1),
        'faturamento': float(total_receita),
        'icms': float(icms_proprio),
        'documento_ids': sorted(ids),
        'competencia': competencia,
    }, None


def projetar_diagnostico_integral_i1(*, resultado: dict, empresa_id: int,
                                     evidencia_documental: dict | None = None) -> dict:
    """Projeta I0 e quarentena PIS/Cofins a partir de prova declarada.

    A evidencia chega do chamador, nunca de dados HTTP; verificar autenticidade,
    ownership e hashes dos bytes/documentos ANTES de qualquer confianca fiscal.
    Saida sempre INTERNA, sem valor financeiro comprovado, creditos ou checkout.
    """
    base = projetar_diagnostico_integral_i0(resultado=resultado, empresa_id=empresa_id)
    saida = deepcopy(base)
    saida['schema_version'] = SCHEMA_VERSION
    saida['uso'] = 'INTERNO_NAO_PUBLICAVEL'
    saida['checkout_autorizado'] = False
    saida['diagnostico_empresarial_completo'] = False
    saida['comprovacao_normativa'] = False

    # Sobretudo, nunca reutilizar os numericos legados marcados com ICMS de ST.
    itens = {e['id']: e for e in saida['cobertura']}
    for nome in _COMPONENTES:
        registro = itens[nome]
        registro['resultado_bruto_nao_validado'] = None
        registro['autoridade_fiscal'] = False
        registro['estado'] = 'nao_apurado'
        registro['causa'] = 'I1_ICMS_PROPRIO_NAO_VINCULADO_ST_NAO_E_ICMS_PROPRIO'
        registro['simulacao_condicional'] = None

    engines = resultado.get('resultados_engines') if type(resultado) is dict else None
    legado = engines.get('pis_cofins') if type(engines) is dict else None
    if type(legado) is dict and (legado.get('erro') is not None or legado.get('estado_l3') == 'bloqueado'):
        causa = str(legado.get('codigo') or 'I1_MOTOR_LEGADO_BLOQUEADO')
        for nome in _COMPONENTES:
            itens[nome]['estado'] = 'falha_motor'
            itens[nome]['causa'] = causa
        saida['pis_cofins_i1'] = {'estado': 'falha_motor', 'causa': causa, 'documentos': [],
                                 'simulacao_nao_comercial': None}
        return saida

    contexto, causa = _verificar_documentos(empresa_id, evidencia_documental)
    if causa is not None:
        for nome in _COMPONENTES:
            itens[nome]['causa'] = causa
        saida['pis_cofins_i1'] = {'estado': 'nao_apurado', 'causa': causa, 'documentos': [],
                                 'simulacao_nao_comercial': None}
        return saida

    # INTEGRACAO REAL COM MOTOR EXISTENTE: apenas para simular condicionalmente.
    # Nunca transmitir icms_pago, icms_devido, ST, credito manual ou insumos brutos.
    try:
        from app.services.tax_engines.pis_cofins_engine import calcular_pis_cofins
        calculo = calcular_pis_cofins(
            {'faturamento': contexto['faturamento'], 'icms': contexto['icms'],
             'data_referencia': contexto['data_referencia']},
            regime=contexto['regime'],
        )
        if type(calculo) is not dict or type(calculo.get('tributos')) is not dict:
            raise ValueError('I1_CALCULO_FORMATO_INVALIDO')
        n_pis = calculo['tributos'].get('pis')
        n_cofins = calculo['tributos'].get('cofins')
        if any(type(n) not in (int, float) or not (0 <= n < 1e15) for n in (n_pis, n_cofins)):
            raise ValueError('I1_CALCULO_TRIBUTOS_INVALIDOS')
    except Exception:
        for nome in _COMPONENTES:
            itens[nome]['estado'] = 'falha_motor'
            itens[nome]['causa'] = 'I1_EXECUCAO_MOTOR_INDISPONIVEL'
        saida['pis_cofins_i1'] = {'estado': 'falha_motor',
                                 'causa': 'I1_EXECUCAO_MOTOR_INDISPONIVEL',
                                 'documentos': contexto['documento_ids'],
                                 'simulacao_nao_comercial': None}
        return saida

    valores = {'pis': n_pis, 'cofins': n_cofins}
    for nome in ('pis', 'cofins'):
        itens[nome]['estado'] = 'informativo_sem_prova'
        itens[nome]['causa'] = 'I1_SIMULACAO_SEM_AUTENTICIDADE_ESCRITURACAO_E_NORMA'
        itens[nome]['simulacao_condicional'] = valores[nome]
    # Os zeros produzidos pelo motor para creditos ausentes NAO sao prova de credito zero.
    for nome in ('credito_pis', 'credito_cofins'):
        itens[nome]['estado'] = 'nao_apurado'
        itens[nome]['causa'] = 'I1_INSUMOS_ESCRITURACAO_E_ELEGIBILIDADE_NAO_PROVADOS'
    saida['pis_cofins_i1'] = {
        'estado': 'simulacao_sem_prova',
        'causa': 'I1_DOCUMENTOS_DECLARADOS_NAO_AUTENTICADOS',
        'documentos': contexto['documento_ids'],
        'competencia': contexto['competencia'],
        'regime_declarado': contexto['regime'],
        'simulacao_nao_comercial': deepcopy(valores),
    }
    return saida


__all__ = ['SCHEMA_VERSION', 'projetar_diagnostico_integral_i1']
