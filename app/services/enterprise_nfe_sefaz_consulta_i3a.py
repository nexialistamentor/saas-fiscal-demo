"""Enterprise I3A: consulta NF-e 4.00 SVRS-PA, contrato PURO e fail-closed.

Nao consulta rede, nao opera certificado, nao confere assinatura XML local,
nao demonstra credito, regime, EFD ou apuracao mensal. O invocador de transporte
precisa ser independente, autenticado, autorizado e limitado a uma consulta.
"""
from __future__ import annotations

from datetime import datetime
import re
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

SCHEMA = "ENTERPRISE_NFE_SEFAZ_CONSULTA_I3A_V1"
ENDPOINT_PA_PRODUCAO = "https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx"
NFE_NS = "http://www.portalfiscal.inf.br/nfe"
WS_NS = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeConsultaProtocolo4"
SOAP_NS = "http://www.w3.org/2003/05/soap-envelope"
ACTION = WS_NS + "/nfeConsultaNF"
CHAVE = re.compile(r"15[0-9]{42}\Z")  # UF PA = cUF 15, 44 algarismos
PROTOCOLO = re.compile(r"[0-9]{10,20}\Z")
MAX_RESPONSE_BYTES = 256 * 1024


class NfeSefazConsultaError(ValueError):
    """Consulta/retorno externo invalido; nunca converter em autorizacao."""


def _recusa(codigo: str):
    raise NfeSefazConsultaError(codigo)


def _key(chave: object) -> str:
    if type(chave) is not str or CHAVE.fullmatch(chave) is None:
        _recusa("I3A_CHAVE_NFE_PA_INVALIDA")
    if chave[20:22] != "55":
        _recusa("I3A_MODELO_NFE_INVALIDO")
    return chave


def construir_envelope_consulta_pa(chave_nfe: str) -> bytes:
    """SOAP 1.2 com consSitNFe 4.00; NAO envia ou assina XML."""
    chave = _key(chave_nfe)
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap:Envelope xmlns:soap="{SOAP_NS}">'
        '<soap:Body>'
        f'<nfeDadosMsg xmlns="{WS_NS}">'
        f'<consSitNFe xmlns="{NFE_NS}" versao="4.00">'
        '<tpAmb>1</tpAmb><xServ>CONSULTAR</xServ>'
        f'<chNFe>{chave}</chNFe></consSitNFe>'
        '</nfeDadosMsg></soap:Body></soap:Envelope>'
    ).encode("utf-8")


def _get_text(element: object, path: str) -> str | None:
    e = element.find(path) if element is not None else None
    return e.text.strip() if e is not None and type(e.text) is str and e.text.strip() else None


def _date(value: str | None) -> bool:
    if type(value) is not str:
        return False
    try:
        obj = datetime.fromisoformat(value)
        return obj.tzinfo is not None and obj.utcoffset() is not None
    except (TypeError, ValueError):
        return False


def interpretar_resposta_consulta_pa(*, soap_bytes: bytes, chave_esperada: str) -> dict:
    """Interpreta XML recebido. Nao comprova que bytes vieram da SEFAZ.

    Fonte externa devera provar canal TLS/mTLS e endpoint no transportador.
    Nunca marcar fiscal/comercial autorizado so com resposta XML.
    """
    chave = _key(chave_esperada)
    if type(soap_bytes) is not bytes or not 0 < len(soap_bytes) <= MAX_RESPONSE_BYTES:
        _recusa("I3A_RESPONSE_SIZE_INVALID")
    try:
        root = ET.fromstring(soap_bytes, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError):
        _recusa("I3A_SOAP_MALFORMED")
    if root.tag != f'{{{SOAP_NS}}}Envelope':
        _recusa("I3A_NOT_SOAP12")
    bodies = root.findall(f'{{{SOAP_NS}}}Body')
    if len(bodies) != 1 or bodies[0].find(f'{{{SOAP_NS}}}Fault') is not None:
        _recusa("I3A_SOAP_FAULT_OR_CARDINALITY")
    # Nao aceitar documento solto ou segundo retorno aninhado.
    returns = list(bodies[0].iter(f'{{{NFE_NS}}}retConsSitNFe'))
    if len(returns) != 1:
        _recusa("I3A_RESPONSE_CARDINALITY")
    ret = returns[0]
    if ret.get("versao") != "4.00":
        _recusa("I3A_VERSION_INVALID")
    n = f'{{{NFE_NS}}}'
    if _get_text(ret, n+'tpAmb') != '1':
        _recusa("I3A_AMBIENTE_DIVERGENTE")
    if _get_text(ret, n+'chNFe') != chave:
        _recusa("I3A_RESPONSE_KEY_DIVERGENTE")
    cstat = _get_text(ret, n+'cStat')
    if type(cstat) is not str or not re.fullmatch('[0-9]{3}', cstat):
        _recusa("I3A_CSTAT_INVALID")
    situacao = 'NAO_CONCLUSIVO'
    protocolo = None
    if cstat == '100':
        prot = ret.findall(n+'protNFe')
        if len(prot) != 1:
            _recusa("I3A_PROTOCOL_REQUIRED")
        infs = prot[0].findall(n+'infProt')
        if len(infs) != 1 or _get_text(infs[0], n+'chNFe') != chave:
            _recusa("I3A_PROTOCOL_IDENTITY_MISMATCH")
        if _get_text(infs[0], n+'cStat') != '100':
            _recusa("I3A_PROTOCOL_STATUS_MISMATCH")
        protocolo = _get_text(infs[0], n+'nProt')
        if protocolo is None or PROTOCOLO.fullmatch(protocolo) is None or not _date(_get_text(infs[0], n+'dhRecbto')):
            _recusa("I3A_PROTOCOL_PROOF_INCOMPLETE")
        situacao = 'AUTORIZADA_CONFORME_RETORNO'
    elif cstat == '101':
        situacao = 'CANCELADA_CONFORME_RETORNO'
    elif cstat in ('110', '301', '302'):
        situacao = 'DENEGADA_CONFORME_RETORNO'
    elif cstat == '217':
        situacao = 'NAO_CONSTA_CONFORME_RETORNO'
    elif cstat == '656':
        situacao = 'CONSUMO_INDEVIDO_BLOQUEADO'
    # Se a resposta registrar evento de cancelamento, ele nunca pode ser ignorado.
    eventos = ret.findall('.//'+n+'retEvento')
    for e in eventos:
        inf = e.find(n+'infEvento')
        if inf is None:
            _recusa("I3A_EVENT_INCOMPLETE")
        if _get_text(inf,n+'chNFe') not in (None,chave):
            _recusa("I3A_EVENT_KEY_MISMATCH")
        typ=_get_text(inf,n+'tpEvento')
        stat=_get_text(inf,n+'cStat')
        if typ == '110111' and stat in ('135','136','155'):
            situacao='CANCELADA_CONFORME_RETORNO'
        elif typ == '110111' or stat is None:
            _recusa('I3A_EVENT_NOT_EVALUABLE')
    return {
        'schema_version': SCHEMA, 'servico': 'SVRS_NFE_CONSULTA_PROTOCOLO_4',
        'ambiente': 'producao', 'chave_nfe': chave, 'cstat': cstat,
        'situacao_declarada_pela_resposta': situacao, 'protocolo_declarado': protocolo,
        'canal_mtls_verificado_por_este_modulo': False,
        'assinatura_xml_verificada': False, 'titularidade_consulta_verificada': False,
        'situacao_oficial_confirmada': False, 'apuracao_mensal_completa': False,
        'credito_fiscal_comprovado': False, 'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
    }


__all__ = ['SCHEMA', 'ACTION', 'ENDPOINT_PA_PRODUCAO', 'NfeSefazConsultaError',
           'construir_envelope_consulta_pa', 'interpretar_resposta_consulta_pa']
