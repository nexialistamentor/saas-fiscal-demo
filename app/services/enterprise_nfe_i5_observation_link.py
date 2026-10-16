"""I5 Enterprise: vinculo read-only de observacao SOAP I4N a documento I2.

NAO atesta transporte, assinatura, SEFAZ, norma, EFD, apuracao, credito ou
pagamento. O input SOAP pode ser arbitrario: digest nao prova origem.
Nao guarda XML, SOAP, certificados ou registos na BD. Nao chama rede.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.services.enterprise_i2_documentary_bridge import projetar_diagnostico_integral_i2
from app.services.enterprise_nfe_sefaz_operador_i4n import interpretar_observacao_unica
from app.services.enterprise_nfe_sefaz_nacional_i3n import preparar_consulta_nfe_nacional

SCHEMA = 'ENTERPRISE_NFE_I5_DOCUMENTARY_OBSERVATION_V1'
_NFE = '{http://www.portalfiscal.inf.br/nfe}'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_MAX_XML = 2 * 1024 * 1024
_MAX_SOAP = 256 * 1024


class EnterpriseI5ObservationError(ValueError):
    """Recusa de vinculo ou de evidencia incompleta, sem valor comercial."""


def _stop(reason: str):
    raise EnterpriseI5ObservationError(reason)


def _positive_id(x: object) -> bool:
    return type(x) is int and x > 0


def _nf_key(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True, forbid_entities=True,
                             forbid_external=True)
    except (ET.ParseError, DefusedXmlException, ValueError, TypeError):
        _stop('I5_XML_PARSE_INVALID')
    if root.tag == _NFE + 'NFe':
        nfe = root
    elif root.tag == _NFE + 'nfeProc':
        nodes = root.findall(_NFE + 'NFe')
        if len(nodes) != 1:
            _stop('I5_NFE_CARDINALITY_INVALID')
        nfe = nodes[0]
    else:
        _stop('I5_XML_NOT_NFE')
    infs = nfe.findall(_NFE + 'infNFe')
    if len(infs) != 1:
        _stop('I5_INF_NFE_CARDINALITY_INVALID')
    identity = infs[0].get('Id')
    if type(identity) is not str or not re.fullmatch(r'NFe[0-9]{44}', identity):
        _stop('I5_NFE_KEY_INVALID')
    chave = identity[3:]
    # Nao existe fallback para modelo 65, DV incorreto ou autorizador desconhecido.
    try:
        preparar_consulta_nfe_nacional(chave)
    except ValueError:
        _stop('I5_NATIONAL_KEY_INVALID')
    return chave


def vincular_observacao_nfe_i5(
    *, db: object, authenticated_user_id: int, empresa_id: int,
    relatorio_id: int, xml_bytes: bytes, resposta_soap: bytes,
) -> dict:
    """Liga duas observacoes por IDENTIDADE e HASH, nao por autoridade externa.

    A I2 comprova vinculo interno de XML, relatorio, empresa e itens. A I4N
    interpreta SOAP estruturado. Nenhum argumento booleando de 'origem oficial'
    pode elevar a autoridade de uma resposta autodeclarada.
    """
    if (db is None or not all(_positive_id(x) for x in
        (authenticated_user_id, empresa_id, relatorio_id))
        or type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= _MAX_XML
        or type(resposta_soap) is not bytes or not 0 < len(resposta_soap) <= _MAX_SOAP):
        _stop('I5_INPUT_INVALID')

    chave = _nf_key(xml_bytes)
    try:
        observacao = interpretar_observacao_unica(
            chave_nfe=chave, resposta_soap=resposta_soap,
        )
    except (ValueError, TypeError, KeyError):
        _stop('I5_SOAP_RESPONSE_INVALID')
    try:
        projecao = projetar_diagnostico_integral_i2(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes,
        )
    except Exception:
        # Protege informacao de titularidade e erros internos na fronteira.
        _stop('I5_DOCUMENTARY_I2_NOT_VALIDATED')

    if type(projecao) is not dict or projecao.get('checkout_autorizado') is not False:
        _stop('I5_I2_CONTRACT_INVALID')
    documento = projecao.get('documental_i2')
    if type(documento) is not dict or documento.get('estado') != 'DOCUMENTO_INTERNO_RECONCILIADO':
        _stop('I5_I2_DOCUMENT_INVALID')
    sha_xml = hashlib.sha256(xml_bytes).hexdigest()
    chave_sha = hashlib.sha256(chave.encode('ascii')).hexdigest()
    sha_soap = hashlib.sha256(resposta_soap).hexdigest()
    if (documento.get('xml_sha256') != sha_xml
        or documento.get('chave_nfe') != chave
        or not _positive_id(documento.get('documento_id'))
        or documento.get('relatorio_id') != relatorio_id
        or observacao.get('schema_version') != 'ENTERPRISE_NFE_OPERADOR_I4N_V1'
        or observacao.get('chave_sha256') != chave_sha
        or observacao.get('resposta_sha256') != sha_soap
        or observacao.get('checkout_autorizado') is not False
        or observacao.get('canal_mtls_verificado_por_este_modulo') is not False):
        _stop('I5_PROOF_IDENTITY_MISMATCH')

    status = observacao.get('situacao_declarada')
    if type(status) is not str or status not in {
        'AUTORIZADA_CONFORME_RETORNO', 'CANCELADA_CONFORME_RETORNO',
        'DENEGADA_CONFORME_RETORNO', 'NAO_CONSTA_CONFORME_RETORNO',
        'CONSUMO_INDEVIDO_BLOQUEADO', 'NAO_CONCLUSIVO',
    }:
        _stop('I5_STATUS_INVALID')
    if type(observacao.get('cstat')) is not str or not re.fullmatch(r'[0-9]{3}', observacao['cstat']):
        _stop('I5_CSTAT_INVALID')

    # Receipt sem PII direta, valores fiscais ou SOAP: SHA256 nao e assinatura.
    base = {
        'schema_version': SCHEMA,
        'empresa_id': empresa_id, 'relatorio_id': relatorio_id,
        'documento_id': documento['documento_id'],
        'xml_sha256': sha_xml, 'chave_sha256': chave_sha,
        'resposta_soap_sha256': sha_soap,
        'autorizador_catalogado': observacao['autorizador'],
        'uf_emissora_chave': observacao['uf_emissora'],
        'endpoint_catalogado': observacao['endpoint_catalogado'],
        'cstat_observado': observacao['cstat'],
        'situacao_observada': status,
        'origem_resposta_atestada': False,
        'situacao_sefaz_confirmada': False,
        'assinatura_nfe_verificada': False,
        'norma_vigente_verificada': False,
        'efd_competencia_reconciliada': False,
        'apuracao_mensal_completa': False,
        'direito_creditorio_comprovado': False,
        'autorizado_para_calculo_comercial': False,
        'checkout_autorizado': False,
        'uso': 'INTERNO_NAO_PUBLICAVEL',
        'pendencia': 'I5_ORIGEM_TLS_MTLS_NAO_ATESTADA',
    }
    fingerprint = hashlib.sha256(json.dumps(
        base, ensure_ascii=True, sort_keys=True, separators=(',', ':'),
    ).encode('ascii')).hexdigest()
    return {**base, 'recibo_fingerprint_sha256': fingerprint}


__all__ = ['SCHEMA', 'EnterpriseI5ObservationError', 'vincular_observacao_nfe_i5']
