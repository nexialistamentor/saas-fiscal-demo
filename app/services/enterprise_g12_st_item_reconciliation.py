"""G1.2 Enterprise: read-only, non-authoritative ST/MVA per-item bridge.

Joins the real XML parser, normative MVA/base resolver, existing MotorFiscal
and G1 comparator. Never interprets this as tax compliance, SEFAZ proof,
paid credits or entitlement. No writes, external calls or checkout.

Only a narrow intrastate ICMS10 + MVA (modBCST=4) case can be simulated;
PMPF, other tax groups, accessory bases and unknown rules remain blocked.
The ICMS-proprio deduction originates in the XML, so the resulting ST
simulation is not a fully independent tax assessment.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import re

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.motor_fiscal import MotorFiscal
from app.services.fiscal_utils import resolver_aliquota_e_mva
from app.services.tabela_normativa_service import buscar_mva, resolver_base_calculo_st
from app.services.tax_consistency.tax_consistency_engine import TaxConsistencyEngine
from app.xml_service import ler_xml_unico

SCHEMA = 'SOLVERIS_ENTERPRISE_G12_ST_ITEM_READONLY_V1'
_N = {'n': 'http://www.portalfiscal.inf.br/nfe'}
_URI = '{http://www.portalfiscal.inf.br/nfe}'
_MONEY = re.compile(r'(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{1,2})?\Z')
_NCM = re.compile(r'[0-9]{8}\Z')
_KEY = re.compile(r'[0-9]{44}\Z')


def _money(x):
    if type(x) is not str or not _MONEY.fullmatch(x):
        return None
    try:
        d = Decimal(x)
        return d if d.is_finite() and d >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def _frac(x):
    if type(x) not in (str, int, float, Decimal):
        return None
    try:
        n = Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None
    return n if n.is_finite() and 0 < n <= 1 else None


def _mva_frac(x):
    if type(x) not in (str, int, float, Decimal):
        return None
    try:
        n = Decimal(str(x))
    except (InvalidOperation, ValueError):
        return None
    if not n.is_finite() or n <= 0:
        return None
    return n / Decimal('100') if n > 1 else n


def _result(code, xml_hash=None, *, details=None, comparison=None):
    return {
        'schema_version': SCHEMA,
        'estado': code,
        'xml_sha256': xml_hash,
        'itens': details or [],
        'confronto_g1': comparison,
        'autoridade_fiscal': False,
        'norma_juridicamente_ratificada': False,
        'icms_proprio_recalculado_por_fonte_independente': False,
        'documento_autenticado_sefaz': False,
        'credito_confirmado': False,
        'checkout_autorizado': False,
        'usavel_comercialmente': False,
    }


def _single(root, path):
    matches = root.findall(path, _N)
    return matches[0] if len(matches) == 1 else None


def _text(el, path):
    return el.findtext(path, namespaces=_N) if el is not None else None


def confrontar_st_por_item_g12(*, db, xml_bytes: bytes) -> dict:
    """Observe real engines conditionally; never persist or elevate authority.

    The caller must perform subject/ownership verification and independent
    external document authentication separately. This method DOES NOT do so.
    """
    if db is None or type(xml_bytes) is not bytes or not (0 < len(xml_bytes) <= 2*1024*1024):
        return _result('G12_ENTRADA_INVALIDA')
    digest = hashlib.sha256(xml_bytes).hexdigest()
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError):
        return _result('G12_XML_NAO_PARSEAVEL', digest)
    if root.tag == _URI + 'NFe':
        nfe = root
    elif root.tag == _URI + 'nfeProc':
        nfe = _single(root, 'n:NFe')
    else:
        return _result('G12_NAO_NFE', digest)
    if nfe is None:
        return _result('G12_NFE_CARDINALIDADE', digest)
    inf = _single(nfe, 'n:infNFe')
    if inf is None:
        return _result('G12_INF_CARDINALIDADE', digest)
    key_id = inf.get('Id', '')
    chave = key_id[3:] if key_id.startswith('NFe') else ''
    if not _KEY.fullmatch(chave):
        return _result('G12_CHAVE_INVALIDA', digest)
    if (root.tag == _URI + 'nfeProc'):
        protocol = _single(root, 'n:protNFe/n:infProt')
        if protocol is not None and _text(protocol, 'n:chNFe') != chave:
            return _result('G12_PROTOCOLO_DIVERGENTE', digest)
    ide = _single(inf, 'n:ide')
    if (ide is None or _text(ide, 'n:mod') != '55'
            or _text(ide, 'n:tpNF') != '1'
            or _text(ide, 'n:finNFe') != '1'
            or _text(ide, 'n:idDest') != '1'):
        return _result('G12_OPERACAO_NAO_SUPORTADA', digest)
    stamp = _text(ide, 'n:dhEmi')
    try:
        issued = datetime.fromisoformat(stamp)
        if issued.tzinfo is None or issued.utcoffset() is None:
            raise ValueError('timezone ausente')
        reference_date = issued.date()
    except (ValueError, TypeError):
        return _result('G12_DATA_NAO_COMPROVADA', digest)
    issuer = _text(inf, 'n:emit/n:enderEmit/n:UF')
    dest = _text(inf, 'n:dest/n:enderDest/n:UF')
    if not issuer or not dest or issuer != dest or len(issuer) != 2:
        return _result('G12_UF_INTERESTADUAL_NAO_SUPORTADA', digest)
    details = inf.findall('n:det', _N)
    if not details or len(details) > 500:
        return _result('G12_CARDINALIDADE_ITENS_INVALIDA', digest)
    try:
        parsed = ler_xml_unico(xml_bytes=xml_bytes)
    except Exception:
        return _result('G12_PARSER_LEGADO_INDISPONIVEL', digest)
    if (type(parsed) is not dict or parsed.get('chave_nfe') != chave
            or len(parsed.get('itens') or []) != len(details)
            or parsed.get('uf_emit') != issuer or parsed.get('uf_dest') != dest):
        return _result('G12_PARSER_IDENTIDADE_DIVERGENTE', digest)

    computed = []
    detail_report = []
    for idx, det in enumerate(details, 1):
        item = parsed['itens'][idx-1]
        prod = _single(det, 'n:prod')
        taxes = _single(det, 'n:imposto/n:ICMS')
        ncm, cfop = item.get('ncm'), item.get('cfop')
        if (det.get('nItem') != str(idx) or prod is None or taxes is None
                or not isinstance(ncm, str) or not _NCM.fullmatch(ncm)
                or not isinstance(cfop, str) or not re.fullmatch(r'5[0-9]{3}', cfop)
                or _text(prod, 'n:NCM') != ncm or _text(prod, 'n:CFOP') != cfop):
            return _result('G12_IDENTIDADE_ITEM_NAO_CONCILIADA', digest)
        info = {'indice_item':idx, 'ncm':ncm, 'cfop':cfop,
                'competencia':reference_date.strftime('%Y-%m'),
                'estado':'NAO_AVALIADO', 'motivo':None,
                'fonte_legal_informada':None, 'fonte_original_autenticada':False,
                'metodo_base':None, 'formula':'(vProd*(1+MVA))*aliquota-vICMS_XML',
                'comparacao_condicional':False}
        calc = {'indice_item':idx, 'ncm':ncm, 'cfop':cfop,
                'base_st_calculada':None, 'valor_st_calculado':None}
        computed.append(calc)
        detail_report.append(info)
        if len(taxes) != 1 or taxes[0].tag != _URI + 'ICMS10':
            info['motivo'] = 'G12_MODALIDADE_ICMS_PMPF_OU_OUTRA_NAO_RESOLVIDA'
            continue
        group = taxes[0]
        if _text(group, 'n:modBCST') != '4':
            info['motivo'] = 'G12_BASE_PMPF_PAUTA_OU_OUTRA_NAO_SUPORTADA'
            continue
        if any((_text(prod,'n:'+field) is not None and
                _money(_text(prod,'n:'+field)) != Decimal('0')) for field in
               ('vFrete', 'vSeg', 'vOutro', 'vDesc')):
            info['motivo'] = 'G12_COMPONENTES_BASE_NAO_RECONCILIADOS'
            continue
        if any((_text(group,'n:'+field) is not None and
                _money(_text(group,'n:'+field)) != Decimal('0')) for field in
               ('pRedBC', 'pRedBCST')):
            info['motivo'] = 'G12_REDUCAO_BASE_NAO_RECONCILIADA'
            continue
        product_value = _money(_text(prod,'n:vProd'))
        own_icms = _money(_text(group,'n:vICMS'))
        own_bc = _money(_text(group,'n:vBC'))
        own_percent = _money(_text(group,'n:pICMS'))
        if (product_value is None or product_value <= 0 or own_icms is None
                or own_bc is None or own_percent is None
                or own_icms > own_bc or own_bc > product_value):
            info['motivo']='G12_COMPONENTE_ICMS_PROPRIO_NAO_OBSERVADO'
            continue
        # Internal arithmetic coherence, not external rule validation.
        expected_own = (own_bc * own_percent/Decimal('100')).quantize(Decimal('0.01'))
        if abs(expected_own - own_icms) > Decimal('0.01'):
            info['motivo'] = 'G12_ICMS_PROPRIO_XML_INCOERENTE'
            continue
        if (item.get('st_observado_xml') is not True
                or _money(str(item.get('base_st'))) is None
                or _money(str(item.get('valor_st'))) is None):
            info['motivo'] = 'G12_ST_NAO_OBSERVADO_XML'
            continue
        try:
            rule = resolver_aliquota_e_mva(db, issuer, ncm, data_referencia=reference_date)
            if (type(rule) is not dict or rule.get('calculo_autorizado') is not True
                    or rule.get('calculo_parcial') is not False
                    or rule.get('mva_autorizada') is not True
                    or rule.get('aliquota_autorizada') is not True
                    or rule.get('confianca') != 'oficial'):
                info['motivo'] = 'G12_REGRA_NAO_AUTORIZADA_PELO_RESOLVEDOR'
                continue
            norm = buscar_mva(db, issuer, ncm, data_referencia=reference_date)
            if type(norm) is not dict or norm.get('nivel_confianca_fonte') != 'oficial':
                info['motivo'] = 'G12_FONTE_NORMATIVA_NAO_COTEJADA'
                continue
            vstart, vend = norm.get('vigencia_inicio'), norm.get('vigencia_fim')
            from datetime import date
            if (type(vstart) is not date or vstart > reference_date
                    or (vend is not None and (type(vend) is not date or vend < reference_date))):
                info['motivo'] = 'G12_VIGENCIA_NORMATIVA_INVALIDA'
                continue
            source = norm.get('fonte_legal')
            ali, mva = _frac(rule.get('aliquota')), _mva_frac(rule.get('mva'))
            if (not isinstance(source, str) or not source.strip()
                    or ali is None or mva is None
                    or ali != _frac(norm.get('aliquota_interna'))
                    or mva != _mva_frac(norm.get('mva'))):
                info['motivo'] = 'G12_FONTE_NORMATIVA_DIVERGENTE'
                continue
            base_rule = resolver_base_calculo_st(db,issuer,ncm,float(product_value),data_referencia=reference_date)
            if (type(base_rule) is not dict or base_rule.get('metodo') != 'iva_st'
                    or base_rule.get('confianca') != 'oficial'
                    or base_rule.get('fonte_legal') != source):
                info['motivo'] = 'G12_PMPF_OU_BASE_COM_PRIORIDADE_NAO_COTEJADA'
                continue
            base_norm = _money(str(base_rule.get('base_calculo')))
            base_motor = Decimal(str(MotorFiscal.calcular_base_st(float(product_value),float(mva*100))))
            if (base_norm is None or base_norm != base_motor
                    or _frac(base_rule.get('aliquota_interna')) != ali):
                info['motivo'] = 'G12_DIVERGENCIA_ENTRE_MOTORES_EXISTENTES'
                continue
            st_motor = Decimal(str(MotorFiscal.calcular_icms_st(float(base_motor),float(ali*100),float(own_icms))))
            if st_motor < 0 or not st_motor.is_finite() or st_motor > Decimal('9999999999.99'):
                info['motivo'] = 'G12_RESULTADO_MOTOR_INVALIDO'
                continue
            calc['base_st_calculada'] = str(base_motor)
            calc['valor_st_calculado'] = str(st_motor)
            info['rastro_parametros_g12_v1'] = {
                'versao': 1,
                'mva_fracao_utilizada': str(mva),
                'aliquota_fracao_utilizada': str(ali),
                'fonte_legal_consultada': source,
                'url_fonte_consultada': norm.get('url_fonte'),
                'nivel_confianca_registro': norm.get('nivel_confianca_fonte'),
                'vprod_xml': str(product_value),
                'icms_proprio_xml': str(own_icms),
                'base_st_motor': str(base_motor),
                'icms_st_motor': str(st_motor),
                'metodo_base': 'iva_st',
                'identidade_registo_normativo_comprovada': False,
                'regra_adr020_comprovada': False,
                'autoridade_fiscal': False,
                'credito_confirmado': False,
            }
            registro_mva_id = norm.get('registro_mva_id')
            if type(registro_mva_id) is int and registro_mva_id > 0:
                info['proveniencia_l2_g12_v1'] = {
                    'versao': 1,
                    'registro_mva_id': registro_mva_id,
                    'uf': issuer, 'ncm': ncm,
                    'data_referencia': reference_date.isoformat(),
                    'vigencia_inicio': vstart.isoformat(),
                    'vigencia_fim': vend.isoformat() if vend is not None else None,
                    'fonte_legal': source,
                    'url_fonte': norm.get('url_fonte'),
                    'importado_por_declarado': norm.get('importado_por'),
                    'mva_fracao_registo': str(mva),
                    'aliquota_fracao_registo': str(ali),
                    'unicidade_registos_vigentes_comprovada': False,
                    'vinculo_adr020_comprovado': False,
                    'autenticidade_fonte_externa_comprovada': False,
                    'autoridade_fiscal': False,
                }
            info['estado'] = 'SIMULACAO_CONDICIONAL_MVA'
            info['motivo'] = 'G12_NORMA_DECLARADA_SEM_PROVA_ORIGINAL_E_ICMS_PROPRIO_XML'
            info['fonte_legal_informada'] = source
            info['metodo_base'] = 'iva_st'
            info['comparacao_condicional'] = True
        except Exception:
            info['motivo'] = 'G12_RESOLVEDOR_OU_MOTOR_INDISPONIVEL'
            continue
    confronto = TaxConsistencyEngine().verificar_consistencia(
        parsed, {'chave_nfe':chave, 'itens_calculados':computed})
    simulated = sum(1 for i in detail_report if i['comparacao_condicional'])
    state = 'G12_SIMULACAO_CONDICIONAL_SEM_AUTORIDADE' if simulated else 'G12_SEM_SIMULACAO'
    if simulated < len(details) and simulated:
        state = 'G12_SIMULACAO_PARCIAL_SEM_AUTORIDADE'
    out = _result(state, digest, details=detail_report, comparison=confronto)
    out['itens_simulados'] = simulated
    out['itens_total'] = len(details)
    return out


__all__ = ['SCHEMA','confrontar_st_por_item_g12']
