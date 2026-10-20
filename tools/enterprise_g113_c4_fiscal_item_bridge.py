"""G1.13-C4: read-only join of I2/G13/G14, G1.2/G1 and bounded G1.13-C3.

C4 reads upstream *results* and real XML bytes, never reruns an engine or grants
external authority. A claimed G12 calculation is not proven to have used the
MVA in C3: that missing causal parameter is the next engineering gate.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

SCHEMA = 'SOLVERIS_ENTERPRISE_G113_C4_FISCAL_ITEM_BRIDGE_V1'
G13 = 'SOLVERIS_ENTERPRISE_G13_SUBJECT_ST_ITEM_BRIDGE_V1'
G14 = 'SOLVERIS_ENTERPRISE_G14_OPERATIONAL_NORMATIVE_SCOPE_V1'
G12 = 'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1'
C3 = 'SOLVERIS_ENTERPRISE_G113_C3_TEMPORAL_MVA_EVIDENCE_V1'
URI = '{http://www.portalfiscal.inf.br/nfe}'
NS = {'n': 'http://www.portalfiscal.inf.br/nfe'}
SHA = re.compile(r'[0-9a-f]{64}\Z')
MONEY = re.compile(r'(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z')
KEY = re.compile(r'[0-9]{44}\Z')
DENIED = ('autoridade_fiscal','credito_confirmado','checkout_autorizado','usavel_comercialmente')


class G113C4EvidenceError(ValueError):
    pass


def _stop(code):
    raise G113C4EvidenceError('G113_C4_' + code)


def _id(v):
    return type(v) is int and v > 0


def _sha(v):
    return type(v) is str and SHA.fullmatch(v) is not None


def _money(v):
    if type(v) is not str or MONEY.fullmatch(v) is None:
        _stop('VALOR_MONETARIO_INVALIDO')
    try:
        x = Decimal(v)
    except InvalidOperation:
        _stop('VALOR_MONETARIO_INVALIDO')
    if not x.is_finite() or x < 0:
        _stop('VALOR_MONETARIO_INVALIDO')
    return x.quantize(Decimal('.01'))


def _one(parent, path):
    matches = parent.findall(path, NS) if parent is not None else []
    return matches[0] if len(matches) == 1 else None


def _text(parent, path):
    el = _one(parent, path)
    return el.text if el is not None else None


def _xml_item(raw, index):
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        _stop('XML_BYTES_INVALIDOS')
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError) as exc:
        raise G113C4EvidenceError('G113_C4_XML_NAO_SEGURO_OU_INVALIDO') from exc
    if root.tag == URI + 'NFe':
        nfe = root
    elif root.tag == URI + 'nfeProc':
        nfe = _one(root, 'n:NFe')
    else:
        nfe = None
    inf = _one(nfe, 'n:infNFe')
    ide = _one(inf, 'n:ide')
    if inf is None or ide is None:
        _stop('NFE_IDENTIDADE_AUSENTE')
    key = inf.get('Id', '')
    if not key.startswith('NFe') or KEY.fullmatch(key[3:]) is None:
        _stop('CHAVE_NFE_INVALIDA')
    if root.tag == URI + 'nfeProc':
        prot = _one(root, 'n:protNFe/n:infProt')
        if prot is not None and _text(prot,'n:chNFe') != key[3:]:
            _stop('PROTOCOLO_NFE_DIVERGENTE')
    if any((_text(ide,'n:mod') != '55', _text(ide,'n:tpNF') != '1',
            _text(ide,'n:finNFe') != '1', _text(ide,'n:idDest') != '1')):
        _stop('OPERACAO_NAO_SUPORTADA')
    try:
        issued = datetime.fromisoformat(_text(ide, 'n:dhEmi'))
        if issued.utcoffset() is None:
            raise ValueError('timezone')
    except (ValueError, TypeError) as exc:
        raise G113C4EvidenceError('G113_C4_DATA_EMISSAO_INVALIDA') from exc
    uf = _text(inf, 'n:emit/n:enderEmit/n:UF')
    if uf is None or _text(inf, 'n:dest/n:enderDest/n:UF') != uf:
        _stop('UF_OPERACAO_DIVERGENTE')
    dets = inf.findall('n:det', NS)
    if not 1 <= len(dets) <= 500 or not 1 <= index <= len(dets):
        _stop('INDICE_ITEM_FORA_DE_ESCOPO')
    det = dets[index-1]
    prod = _one(det,'n:prod')
    tax = _one(det,'n:imposto/n:ICMS')
    if det.get('nItem') != str(index) or prod is None or tax is None or len(tax) != 1:
        _stop('ITEM_XML_INCONSISTENTE')
    group = tax[0]
    if (group.tag != URI+'ICMS10' or _text(group,'n:CST') != '10'
        or _text(group,'n:modBCST') != '4'):
        _stop('ICMS10_IVA_ST_NAO_OBSERVADO')
    ident = dict(ncm=_text(prod,'n:NCM'), cest=_text(prod,'n:CEST'),
                 cfop=_text(prod,'n:CFOP'), cst='10', uf=uf,
                 data=issued.date().isoformat(), chave_nfe=key[3:],
                 itens_total=len(dets))
    if (type(ident['ncm']) is not str or not re.fullmatch(r'\d{8}',ident['ncm'])
        or type(ident['cest']) is not str or not re.fullmatch(r'\d{7}',ident['cest'])
        or type(ident['cfop']) is not str or not re.fullmatch(r'5\d{3}',ident['cfop'])):
        _stop('CLASSIFICACAO_XML_INVALIDA')
    ident['st_base_xml'] = _money(_text(group,'n:vBCST'))
    ident['st_value_xml'] = _money(_text(group,'n:vICMSST'))
    return ident


def _snapshot_item(s, schema, index, count):
    if (type(s) is not dict or s.get('schema_version') != schema
        or type(s.get('itens')) is not list or len(s['itens']) != count
        or s.get('itens_total') != count or type(s['itens'][index-1]) is not dict
        or s['itens'][index-1].get('indice_item') != index):
        _stop('CONTRATO_ITEM_UPSTREAM_INVALIDO')
    return s['itens'][index-1]


def _g1_pair(g1, index, xml_values):
    if (type(g1) is not dict or g1.get('estado') not in
        ('COMPARACAO_NUMERICA_SEM_AUTORIDADE', 'PARCIAL_SEM_AUTORIDADE')
        or g1.get('consistente') is not None or any(g1.get(k) is not False for k in DENIED)
        or type(g1.get('comparacoes')) is not list):
        return None
    found = [v for v in g1['comparacoes'] if type(v) is dict and v.get('indice_item') == index]
    if len(found) != 2 or {v.get('tipo') for v in found} != {'ICMS_ST','BASE_ST'}:
        return None
    out = {}
    for v in found:
        tipo = v['tipo']
        xml_amount = _money(v.get('valor_xml'))
        computed = _money(v.get('valor_motor'))
        if (xml_amount != xml_values['st_value_xml' if tipo=='ICMS_ST' else 'st_base_xml']
            or type(v.get('divergencia_numerica')) is not bool
            or v['divergencia_numerica'] != (abs(computed-xml_amount)>Decimal('.01'))
            or v.get('prova_normativa') is not False):
            _stop('CONFRONTO_G1_NAO_RECONCILIADO_COM_XML')
        out[tipo] = dict(valor_xml=str(xml_amount),valor_motor_g12=str(computed),
                         diferenca_motor_menos_xml=str((computed-xml_amount).quantize(Decimal('.01'))),
                         divergencia_numerica=v['divergencia_numerica'])
    return out


def cotejar_item_evidencia_calculo_g113_c4(*, xml_bytes: bytes, authenticated_user_id: int,
        empresa_id: int, relatorio_id: int, indice_item: int,
        g13_result: dict, g14_result: dict, c3_result: dict) -> dict:
    """Join results obtained by original callers; not a substitute for original gates.

    Explicitly does NOT prove that G1.2 used the MVA observed by C3.
    No new tax computation; numerical differences originate in G1 comparator.
    """
    if not all(_id(v) for v in (authenticated_user_id, empresa_id, relatorio_id, indice_item)):
        _stop('SUJEITO_OU_ITEM_INVALIDO')
    observed = _xml_item(xml_bytes, indice_item)
    digest = hashlib.sha256(xml_bytes).hexdigest()
    if (type(g13_result) is not dict or g13_result.get('schema_version') != G13
        or g13_result.get('posse_e_proveniencia_interna_i2') is not True
        or g13_result.get('chave_nfe') != observed['chave_nfe']
        or any(g13_result.get(x) != v for x,v in
               (('empresa_id',empresa_id),('relatorio_id',relatorio_id)))
        or not _id(g13_result.get('documento_id'))
        or not _sha(g13_result.get('xml_sha256'))
        or not hmac.compare_digest(g13_result['xml_sha256'],digest)
        or g13_result.get('competencia_declarada') != observed['data'][:7]
        or any(g13_result.get(k) is not False for k in DENIED)):
        _stop('G13_SUJEITO_DOCUMENTO_INCOMPATIVEL')
    # The user ID must be confirmed by the mandatory real G13 call: the
    # returned snapshot does not itself include user ID, by existing contract.
    g12 = g13_result.get('confronto_condicional_g12')
    if (type(g12) is not dict or g12.get('schema_version') != G12
        or not _sha(g12.get('xml_sha256')) or g12['xml_sha256'] != digest
        or g12.get('itens_total') != observed['itens_total']
        or any(g12.get(k) is not False for k in DENIED)
        or g12.get('icms_proprio_recalculado_por_fonte_independente') is not False):
        _stop('G12_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    calc = _snapshot_item(g12, G12, indice_item, observed['itens_total'])
    if (calc.get('ncm') != observed['ncm'] or calc.get('cfop') != observed['cfop']
        or calc.get('competencia') != observed['data'][:7]):
        _stop('G12_ITEM_INCOMPATIVEL')
    if (type(g14_result) is not dict or g14_result.get('schema_version') != G14
        or g14_result.get('empresa_id') != empresa_id or g14_result.get('relatorio_id') != relatorio_id
        or g14_result.get('documento_id') != g13_result['documento_id']
        or g14_result.get('xml_sha256') != digest
        or g14_result.get('posse_e_proveniencia_interna_g13') is not True
        or any(g14_result.get(k) is not False for k in DENIED)):
        _stop('G14_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    scope = _snapshot_item(g14_result, G14, indice_item, observed['itens_total'])
    if (scope.get('estado') != 'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST'
        or scope.get('uf_operacao') != observed['uf']
        or scope.get('ncm') != observed['ncm'] or scope.get('cest_observado') != observed['cest']
        or scope.get('cfop') != observed['cfop'] or scope.get('cst_observado') != observed['cst']
        or scope.get('competencia_declarada') != observed['data'][:7]):
        _stop('G14_CLASSIFICACAO_DIVERGENTE')
    if (type(c3_result) is not dict or c3_result.get('schema_version') != C3
        or c3_result.get('indice_item') != indice_item
        or c3_result.get('data_operacao_declarada') != observed['data']
        or c3_result.get('uf') != observed['uf']
        or c3_result.get('ncm') != observed['ncm'] or c3_result.get('cest') != observed['cest']
        or c3_result.get('verificacao_pdf_pagina_excerto') is not True
        or any(c3_result.get(k) is not False for k in DENIED)
        or c3_result.get('prova_nf_e_real') is not False
        or c3_result.get('prova_adr020_regra_persistida') is not False):
        _stop('C3_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    common = dict(schema_version=SCHEMA, documento_id=g13_result['documento_id'],
                  empresa_id=empresa_id, relatorio_id=relatorio_id, indice_item=indice_item,
                  chave_nfe=observed['chave_nfe'],xml_sha256=digest,
                  data_operacao=observed['data'],uf=observed['uf'],ncm=observed['ncm'],cest=observed['cest'],
                  fonte_mva_motor_g12_demonstrada=False,
                  prova_semantica_regra_st=False,
                  comprovacao_temporal_exaustiva=False,
                  icms_proprio_independente=False,
                  credito_recuperavel_demonstrado=False,
                  **{k:False for k in DENIED})
    if c3_result.get('estado') == 'ABSTENCAO_TEMPORAL':
        if (c3_result.get('versao_selecionada') is not None or
            c3_result.get('mva_original_percentual_observada') is not None):
            _stop('C3_ABSTENCAO_INCOERENTE')
        return dict(common,estado='ABSTENCAO_NORMATIVA_TEMPORAL',motivo=c3_result.get('motivo'),
                    comparacao_g1=None,mva_observada_c3=None)
    if (c3_result.get('estado') != 'CANDIDATO_TEMPORAL_OBSERVADO_SEM_AUTORIDADE'
        or not _sha(c3_result.get('pdf_sha256')) or not _sha(c3_result.get('excerto_sha256'))
        or c3_result.get('pdf_sha256') != scope.get('sha256_texto_normativo_declarado')
        or type(c3_result.get('versao_selecionada')) is not str
        or not c3_result['versao_selecionada'].strip()):
        _stop('C3_CANDIDATO_OU_PDF_DIVERGENTE')
    candidate_mva = c3_result.get('mva_original_percentual_observada')
    if type(candidate_mva) is not str or not re.fullmatch(r'\d{1,3}\.\d{2}',candidate_mva):
        _stop('C3_MVA_INVALIDA')
    if not 0 <= Decimal(candidate_mva) <= 999:
        _stop('C3_MVA_FORA_LIMITES')
    if (calc.get('comparacao_condicional') is not True
        or calc.get('estado') != 'SIMULACAO_CONDICIONAL_MVA'
        or calc.get('metodo_base') != 'iva_st'
        or calc.get('fonte_original_autenticada') is not False):
        return dict(common,estado='ABSTENCAO_G12_SEM_SIMULACAO_ITEM',motivo='G12_NAO_CALCULOU_ITEM',
                    comparacao_g1=None,mva_observada_c3=candidate_mva)
    pairs = _g1_pair(g12.get('confronto_g1'),indice_item,observed)
    if pairs is None:
        return dict(common,estado='ABSTENCAO_G1_SEM_PARES_NUMERICOS',motivo='G1_SEM_BASE_E_ICMS_ST_COTEJADOS',
                    comparacao_g1=None,mva_observada_c3=candidate_mva)
    return dict(common,estado='CONFRONTO_NUMERICO_E_MVA_CANDIDATA_SEM_PONTE_CAUSAL',
                motivo='G12_NAO_PUBLICA_MVA_EFETIVAMENTE_USADA_POR_ITEM',
                mva_observada_c3=candidate_mva,versao_c3=c3_result['versao_selecionada'],
                pdf_sha256=c3_result['pdf_sha256'],excerto_sha256=c3_result['excerto_sha256'],
                comparacao_g1=pairs)


__all__ = ['SCHEMA','G113C4EvidenceError','cotejar_item_evidencia_calculo_g113_c4']
