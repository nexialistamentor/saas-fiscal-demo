"""I3N: planeamento e leitura de NFeConsultaProtocolo4 por autorizador de UF.

PURA, sem rede/certificado/BD, sem inferencia de CST/ICMS ou credito.
Fonte do catalogo: Portal Nacional NF-e, Relação de Serviços Web (16/10/2026).
"""
from __future__ import annotations

from datetime import datetime
import re
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

SCHEMA = 'ENTERPRISE_NFE_NACIONAL_I3N_V1'
NFE_NS = 'http://www.portalfiscal.inf.br/nfe'
WS_NS = 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeConsultaProtocolo4'
SOAP_NS = 'http://www.w3.org/2003/05/soap-envelope'
ACTION = WS_NS + '/nfeConsultaNF'
MAX_RESPONSE_BYTES = 256 * 1024

# UF emissora da chave, NAO UF destino, nem domicilio do cliente.
_CUF_UF = {
 '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP',
 '17': 'TO', '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB',
 '26': 'PE', '27': 'AL', '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES',
 '33': 'RJ', '35': 'SP', '41': 'PR', '42': 'SC', '43': 'RS', '50': 'MS',
 '51': 'MT', '52': 'GO', '53': 'DF',
}
_SVRS = frozenset('AC AL AP CE DF ES PA PB PI RJ RN RO RR SC SE TO'.split())
_SVAN = frozenset({'MA'})
_AUTORIZADORES_DIRETOS = frozenset('AM BA GO MG MS MT PE PR RS SP'.split())
assert set(_CUF_UF.values()) == _SVRS | _SVAN | _AUTORIZADORES_DIRETOS
assert len(_CUF_UF) == 27

# Apenas autorizadores NORMAIS, versao 4.00, ambiente producao;
# contingencia SVC nao e fallback automatico (depende do tpEmis/operacao).
_ENDPOINTS = {
 'SVRS': 'https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx',
 'SVAN': 'https://www.sefazvirtual.fazenda.gov.br/NFeConsultaProtocolo4/NFeConsultaProtocolo4.asmx',
 'AM': 'https://nfe.sefaz.am.gov.br/services2/services/NfeConsulta4',
 'BA': 'https://nfe.sefaz.ba.gov.br/webservices/NFeConsultaProtocolo4/NFeConsultaProtocolo4.asmx',
 'GO': 'https://nfe.sefaz.go.gov.br/nfe/services/NFeConsultaProtocolo4',
 'MG': 'https://nfe.fazenda.mg.gov.br/nfe2/services/NFeConsultaProtocolo4',
 'MS': 'https://nfe.sefaz.ms.gov.br/ws/NFeConsultaProtocolo4',
 'MT': 'https://nfe.sefaz.mt.gov.br/nfews/v2/services/NfeConsulta4',
 'PE': 'https://nfe.sefaz.pe.gov.br/nfe-service/services/NFeConsultaProtocolo4',
 'PR': 'https://nfe.sefa.pr.gov.br/nfe/NFeConsultaProtocolo4',
 'RS': 'https://nfe.sefazrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx',
 'SP': 'https://nfe.fazenda.sp.gov.br/ws/nfeconsultaprotocolo4.asmx',
}


class NfeConsultaNacionalError(ValueError):
    """STOP de input, routing ou resposta inconclusiva."""


def _stop(code: str):
    raise NfeConsultaNacionalError(code)


def _key(key: object) -> tuple[str, str]:
    if type(key) is not str or re.fullmatch(r'[0-9]{44}', key) is None:
        _stop('I3N_CHAVE_INVALIDA')
    uf = _CUF_UF.get(key[:2])
    if uf is None:
        _stop('I3N_CUF_NAO_RECONHECIDO')
    if key[20:22] != '55':
        _stop('I3N_MODELO_NFE_55_OBRIGATORIO')
    # Digito verificador NFC-e/NF-e, modulo 11 sobre primeiros 43 digitos.
    soma = sum(int(digito) * (2 + (indice % 8)) for indice, digito in
               enumerate(reversed(key[:43])))
    resto = soma % 11
    dv = 0 if resto < 2 else 11 - resto
    if dv != int(key[43]):
        _stop('I3N_CHAVE_DV_INCORRETO')
    return key, uf


def _autorizador(uf: str) -> str:
    return 'SVRS' if uf in _SVRS else 'SVAN' if uf in _SVAN else uf


def preparar_consulta_nfe_nacional(chave_nfe: str) -> dict:
    """Plano offline: nunca executa POST, nao autentica TLS/autoriza uso."""
    chave, uf = _key(chave_nfe)
    autorizador = _autorizador(uf)
    endpoint = _ENDPOINTS.get(autorizador)
    if endpoint is None:
        _stop('I3N_AUTORIZADOR_NAO_CONFIGURADO')
    soap = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}"><soap:Body>'
        f'<nfeDadosMsg xmlns="{WS_NS}">'
        f'<consSitNFe xmlns="{NFE_NS}" versao="4.00">'
        '<tpAmb>1</tpAmb><xServ>CONSULTAR</xServ>'
        f'<chNFe>{chave}</chNFe>'
        '</consSitNFe></nfeDadosMsg></soap:Body></soap:Envelope>'
    ).encode('utf-8')
    return {
        'schema_version': SCHEMA, 'ambiente': 'producao',
        'uf_emissora_chave': uf, 'autorizador': autorizador,
        'endpoint_oficial_catalogado': endpoint, 'acao_soap': ACTION,
        'chave_nfe': chave, 'soap_bytes': soap,
        'consulta_real_executada': False,
        'autenticidade_sefaz_verificada': False,
        'autoridade_fiscal': False,
        'checkout_autorizado': False,
    }


def _text(el, name):
    got = el.find(f'{{{NFE_NS}}}{name}') if el is not None else None
    return got.text.strip() if got is not None and type(got.text) is str and got.text.strip() else None


def _time(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        dt = datetime.fromisoformat(value)
        return dt.tzinfo is not None and dt.utcoffset() is not None
    except (ValueError, TypeError):
        return False


def interpretar_consulta_nfe_nacional(*, resposta_soap: bytes, chave_esperada: str) -> dict:
    """Valida corpo SOAP; sem testemunho autenticado de transporte, sem prova oficial."""
    chave, uf = _key(chave_esperada)
    route = _autorizador(uf)
    if type(resposta_soap) is not bytes or not 0 < len(resposta_soap) <= MAX_RESPONSE_BYTES:
        _stop('I3N_RESPONSE_SIZE_INVALID')
    try:
        root = ET.fromstring(resposta_soap, forbid_dtd=True,
                             forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, TypeError, ValueError):
        _stop('I3N_SOAP_MALFORMED')
    soap = f'{{{SOAP_NS}}}'
    nfe = f'{{{NFE_NS}}}'
    if root.tag != soap+'Envelope':
        _stop('I3N_NOT_SOAP12')
    bodies = root.findall(soap+'Body')
    if len(bodies) != 1 or bodies[0].find(soap+'Fault') is not None:
        _stop('I3N_SOAP_FAULT_OR_CARDINALITY')
    results = list(bodies[0].iter(nfe+'retConsSitNFe'))
    if len(results) != 1:
        _stop('I3N_RESPONSE_CARDINALITY')
    ret = results[0]
    if ret.get('versao') != '4.00':
        _stop('I3N_VERSION_INVALID')
    if _text(ret, 'tpAmb') != '1':
        _stop('I3N_AMBIENTE_INVALIDO')
    if _text(ret, 'chNFe') != chave:
        _stop('I3N_CHAVE_RESPOSTA_DIVERGENTE')
    cstat = _text(ret, 'cStat')
    if type(cstat) is not str or re.fullmatch(r'[0-9]{3}', cstat) is None:
        _stop('I3N_CSTAT_INVALID')
    state = 'NAO_CONCLUSIVO'
    proto = None
    if cstat == '100':
        ps = ret.findall(nfe+'protNFe')
        if len(ps) != 1:
            _stop('I3N_PROTOCOL_REQUIRED')
        inf = ps[0].findall(nfe+'infProt')
        if len(inf) != 1 or _text(inf[0], 'chNFe') != chave or _text(inf[0], 'cStat') != '100':
            _stop('I3N_PROTOCOL_IDENTITY_INVALID')
        proto = _text(inf[0], 'nProt')
        if proto is None or re.fullmatch('[0-9]{10,20}',proto) is None or not _time(_text(inf[0], 'dhRecbto')):
            _stop('I3N_PROTOCOL_INCOMPLETE')
        state = 'AUTORIZADA_CONFORME_RETORNO'
    elif cstat == '101':
        state = 'CANCELADA_CONFORME_RETORNO'
    elif cstat in {'110', '301', '302'}:
        state = 'DENEGADA_CONFORME_RETORNO'
    elif cstat == '217':
        state = 'NAO_CONSTA_CONFORME_RETORNO'
    elif cstat == '656':
        state = 'CONSUMO_INDEVIDO_BLOQUEADO'
    # Evento cancelamento não pode ser mascarado por cStat principal 100.
    for ev in ret.findall('.//'+nfe+'retEvento'):
        info=ev.find(nfe+'infEvento')
        if info is None or _text(info, 'chNFe') not in (None, chave):
            _stop('I3N_EVENT_MISMATCH')
        typ, stat = _text(info, 'tpEvento'), _text(info, 'cStat')
        if typ == '110111' and stat in {'135', '136', '155'}:
            state = 'CANCELADA_CONFORME_RETORNO'
        elif typ == '110111' or stat is None:
            _stop('I3N_EVENT_NOT_EVALUABLE')
    return {
        'schema_version': SCHEMA, 'uf_emissora_chave': uf,
        'autorizador': route, 'chave_nfe': chave, 'cstat': cstat,
        'situacao_declarada_pela_resposta': state,
        'protocolo_declarado': proto,
        'canal_mtls_verificado_por_este_modulo': False,
        'situacao_oficial_confirmada': False,
        'autenticidade_sefaz_verificada': False,
        'assinatura_xml_verificada': False,
        'credito_fiscal_comprovado': False,
        'apuracao_mensal_completa': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
    }


__all__ = ['SCHEMA', 'ACTION', 'NfeConsultaNacionalError',
           'preparar_consulta_nfe_nacional', 'interpretar_consulta_nfe_nacional']
