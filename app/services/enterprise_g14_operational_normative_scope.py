"""SOLVERIS Enterprise G1.4 — enquadramento estrutural por operação, read-only.

Executa obrigatoriamente G1.3 (I2 -> G1.2 -> G1), sobre os mesmos bytes.
Coteja NCM, CEST, CFOP, CST, UF, regime, metodo e intervalo temporal com
candidatos normativos declarados, sem conferir-lhes autenticidade.

CEST/NCM/CFOP nao bastam para provar sujeicao a ST, beneficios, regimes,
excecoes, fonte primaria, escritura ou credito. Nunca eleva autoridade fiscal.
"""
from __future__ import annotations

from datetime import datetime, date
import hashlib
import hmac
import re
from urllib.parse import urlsplit

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.models import Empresa
from app.services.enterprise_g13_subject_st_bridge import projetar_confronto_st_sujeito_g13

SCHEMA = 'SOLVERIS_ENTERPRISE_G14_OPERATIONAL_NORMATIVE_SCOPE_V1'
_N = {'n': 'http://www.portalfiscal.inf.br/nfe'}
_URI = '{http://www.portalfiscal.inf.br/nfe}'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_NCM = re.compile(r'[0-9]{8}\Z')
_CEST = re.compile(r'[0-9]{7}\Z')
_CFOP = re.compile(r'5[0-9]{3}\Z')
_CST = re.compile(r'[0-9]{2}\Z')
_UF = frozenset({'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'})
_CANDIDATE_FIELDS = frozenset({
    'indice_item','uf','ncm','cest','cfop','cst','regime','operacao',
    'metodo_base','vigencia_inicio','vigencia_fim','fonte_legal',
    'url_fonte','sha256_texto_normativo_declarado','versao_ato',
})


class EnterpriseG14GateError(ValueError):
    """Falta de identidade documental ou quebra do contrato interno."""


def _stop(code):
    raise EnterpriseG14GateError(code)


def _id(x):
    return type(x) is int and x > 0


def _one(el, path):
    nodes = el.findall(path, _N)
    return nodes[0] if len(nodes) == 1 else None


def _txt(el, path):
    return el.findtext(path, namespaces=_N) if el is not None else None


def _source_url(s):
    if type(s) is not str or len(s) > 2048 or '\\' in s:
        return False
    try:
        u = urlsplit(s)
        return (u.scheme == 'https' and bool(u.hostname) and u.username is None
                and u.password is None and u.port in (None, 443) and not u.fragment)
    except ValueError:
        return False


def _candidate(x):
    if type(x) is not dict or set(x) != _CANDIDATE_FIELDS:
        return False
    if (not _id(x.get('indice_item')) or type(x.get('uf')) is not str or x['uf'] not in _UF
        or type(x.get('ncm')) is not str or _NCM.fullmatch(x['ncm']) is None
        or type(x.get('cest')) is not str or _CEST.fullmatch(x['cest']) is None
        or type(x.get('cfop')) is not str or _CFOP.fullmatch(x['cfop']) is None
        or type(x.get('cst')) is not str or _CST.fullmatch(x['cst']) is None
        or x.get('regime') not in ('real','presumido')
        or x.get('operacao') != 'saida_interna'
        or x.get('metodo_base') != 'iva_st'):
        return False
    try:
        if type(x.get('vigencia_inicio')) is not str or (x.get('vigencia_fim') is not None and type(x['vigencia_fim']) is not str):
            return False
        start = date.fromisoformat(x['vigencia_inicio'])
        end = date.fromisoformat(x['vigencia_fim']) if type(x['vigencia_fim']) is str else None
        if start is None or (end is not None and end < start):
            return False
        if start.isoformat() != x['vigencia_inicio']:
            return False
        if end is not None and end.isoformat() != x['vigencia_fim']:
            return False
    except ValueError:
        return False
    if (type(x.get('fonte_legal')) is not str or not x['fonte_legal'].strip()
        or len(x['fonte_legal']) > 500 or not _source_url(x.get('url_fonte'))
        or type(x.get('sha256_texto_normativo_declarado')) is not str
        or _HEX.fullmatch(x['sha256_texto_normativo_declarado']) is None
        or type(x.get('versao_ato')) is not str or not x['versao_ato'].strip()
        or len(x['versao_ato']) > 100):
        return False
    return True


def _false_flags():
    return {
        'fonte_primaria_autenticada':False,
        'enquadramento_legal_autorizado':False,
        'cest_aplicabilidade_juridica_comprovada':False,
        'excecoes_e_beneficios_verificados':False,
        'icms_proprio_independente':False,
        'documento_autenticado_sefaz':False,
        'efd_escrituracao_verificada':False,
        'recolhimento_verificado':False,
        'autoridade_fiscal':False,
        'credito_confirmado':False,
        'checkout_autorizado':False,
        'usavel_comercialmente':False,
    }


def cotejar_enquadramento_normativo_operacao_g14(*, db, authenticated_user_id:int,
        empresa_id:int, relatorio_id:int, xml_bytes:bytes,
        candidatos_normativos:list[dict]|None=None) -> dict:
    """G13 comprova custodia interna ANTES de examinar candidatos nao confiaveis.

    A conclusao maxima e COERENCIA_ESTRUTURAL_CANDIDATA. Nenhum dado deste
    adaptador pode ser consumido como prova legal ou calculo definitivo.
    """
    if (db is None or not all(_id(v) for v in (authenticated_user_id,empresa_id,relatorio_id))
        or type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 2*1024*1024):
        _stop('G14_ENTRADA_INVALIDA')
    try:
        g13 = projetar_confronto_st_sujeito_g13(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id, xml_bytes=xml_bytes)
    except Exception as exc:
        raise EnterpriseG14GateError('G14_G13_SUJEITO_DOCUMENTO_NAO_VERIFICADOS') from exc
    digest = hashlib.sha256(xml_bytes).hexdigest()
    if (type(g13) is not dict
        or g13.get('schema_version') != 'SOLVERIS_ENTERPRISE_G13_SUBJECT_ST_ITEM_BRIDGE_V1'
        or g13.get('empresa_id') != empresa_id or g13.get('relatorio_id') != relatorio_id
        or type(g13.get('documento_id')) is not int or g13['documento_id'] <= 0
        or type(g13.get('xml_sha256')) is not str or not hmac.compare_digest(g13['xml_sha256'], digest)
        or g13.get('posse_e_proveniencia_interna_i2') is not True
        or any(g13.get(k) is not False for k in (
          'assinatura_certificado_icp_brasil_comprovados','autenticidade_sefaz_verificada',
          'norma_legal_verificada_por_fonte_primaria','cest_e_enquadramento_por_operacao_verificados',
          'icms_proprio_independente','efd_escrituracao_verificada','recolhimento_verificado',
          'credito_confirmado','autoridade_fiscal','checkout_autorizado','usavel_comercialmente'))):
        _stop('G14_G13_IDENTIDADE_OU_AUTORIDADE_INCOMPATIVEL')
    g12 = g13.get('confronto_condicional_g12')
    if (type(g12) is not dict or type(g12.get('itens')) is not list
        or g12.get('itens_total') != len(g12['itens'])
        or g13.get('itens_total') != len(g12['itens'])):
        _stop('G14_G12_ITENS_INCOMPATIVEIS')
    try:
        emp = db.get(Empresa,empresa_id)
    except Exception as exc:
        raise EnterpriseG14GateError('G14_EMPRESA_INDISPONIVEL') from exc
    if (emp is None or getattr(emp,'id',None) != empresa_id
        or getattr(emp,'user_id',None) != authenticated_user_id
        or getattr(emp,'optante_mei',False) is True
        or getattr(emp,'regime_tributario',None) not in ('real','presumido')):
        _stop('G14_REGIME_OU_SUJEITO_NAO_COMPROVADOS')
    regime = emp.regime_tributario
    try:
        root = ET.fromstring(xml_bytes, forbid_dtd=True,forbid_entities=True,forbid_external=True)
    except (ET.ParseError,DefusedXmlException,ValueError,TypeError) as exc:
        raise EnterpriseG14GateError('G14_XML_NAO_PARSEAVEL') from exc
    if root.tag == _URI+'NFe':
        nfe = root
    elif root.tag == _URI+'nfeProc':
        nfe = _one(root,'n:NFe')
    else:
        nfe = None
    inf = _one(nfe,'n:infNFe') if nfe is not None else None
    ide = _one(inf,'n:ide') if inf is not None else None
    if inf is None or ide is None:
        _stop('G14_NFE_IDENTIDADE_ESTRUTURAL_INVALIDA')
    issued_text = _txt(ide,'n:dhEmi')
    try:
        issued = datetime.fromisoformat(issued_text)
        if issued.utcoffset() is None:
            raise ValueError('timezone')
        issue_date = issued.date()
    except (TypeError,ValueError) as exc:
        raise EnterpriseG14GateError('G14_DATA_INVALIDA') from exc
    uf = _txt(inf,'n:emit/n:enderEmit/n:UF')
    dest = _txt(inf,'n:dest/n:enderDest/n:UF')
    if (uf not in _UF or dest != uf or _txt(ide,'n:mod')!='55'
        or _txt(ide,'n:tpNF')!='1' or _txt(ide,'n:finNFe')!='1'
        or _txt(ide,'n:idDest')!='1'
        or g13.get('competencia_declarada')!=issue_date.strftime('%Y-%m')):
        _stop('G14_OPERACAO_OU_COMPETENCIA_INCOMPATIVEL')
    dets = inf.findall('n:det',_N)
    if not 0<len(dets)<=500 or len(dets)!=g13['itens_total']:
        _stop('G14_CARDINALIDADE_DIVERGENTE')
    candidates = [] if candidatos_normativos is None else candidatos_normativos
    if type(candidates) is not list or len(candidates)>500:
        _stop('G14_CANDIDATOS_INVALIDOS')
    candidates_by_index = {}
    for c in candidates:
        if not _candidate(c) or c['indice_item']>len(dets) or c['indice_item'] in candidates_by_index:
            _stop('G14_CANDIDATO_MALFORMADO_OU_DUPLICADO')
        candidates_by_index[c['indice_item']]=c

    reports=[]
    matches=0
    for idx,(det,sim) in enumerate(zip(dets,g12['itens']),1):
        prod=_one(det,'n:prod')
        icms=_one(det,'n:imposto/n:ICMS')
        group=icms[0] if icms is not None and len(icms)==1 else None
        if (det.get('nItem') != str(idx) or prod is None or type(sim) is not dict
            or sim.get('indice_item')!=idx or sim.get('competencia')!=issue_date.strftime('%Y-%m')):
            _stop('G14_ITEM_IDENTIDADE_DIVERGENTE')
        if (len(prod.findall('n:NCM',_N))!=1 or len(prod.findall('n:CFOP',_N))!=1
            or len(prod.findall('n:CEST',_N))>1
            or (group is not None and (len(group.findall('n:CST',_N))>1
                                        or len(group.findall('n:modBCST',_N))>1))):
            _stop('G14_CLASSIFICACAO_XML_CARDINALIDADE_INVALIDA')
        ncm=_txt(prod,'n:NCM')
        cest=_txt(prod,'n:CEST')
        cfop=_txt(prod,'n:CFOP')
        cst=_txt(group,'n:CST')
        mod=_txt(group,'n:modBCST')
        if (type(ncm) is not str or _NCM.fullmatch(ncm) is None
            or type(cfop) is not str or _CFOP.fullmatch(cfop) is None
            or sim.get('ncm')!=ncm or sim.get('cfop')!=cfop):
            _stop('G14_NCM_CFOP_G13_DIVERGENTE')
        data = {'indice_item':idx,'ncm':ncm,'cest_observado':cest,'cfop':cfop,
                'cst_observado':cst,'uf_operacao':uf,
                'regime_empresa':regime,'competencia_declarada':issue_date.strftime('%Y-%m'),
                'estado':'LACUNA_CANDIDATO_NORMATIVO','motivo':None,
                'fonte_legal_candidata':None,'url_fonte_candidata':None,
                'versao_ato_declarada':None,'sha256_texto_normativo_declarado':None,
                'g12_simulacao_condicional':sim.get('comparacao_condicional') is True}
        candidate=candidates_by_index.get(idx)
        if cest is None:
            data['motivo']='CEST_AUSENTE_NAO_PROVA_NAO_INCIDENCIA'
        elif type(cest) is not str or _CEST.fullmatch(cest) is None:
            data['motivo']='CEST_XML_MALFORMADO'
        elif group is None or group.tag != _URI+'ICMS10' or cst != '10' or mod != '4':
            data['motivo']='CST_OU_MODALIDADE_ST_NAO_COBERTOS'
        elif candidate is None:
            data['motivo']='SEM_CANDIDATO_EXPLICITO_PARA_ITEM'
        elif not (candidate['uf']==uf and candidate['ncm']==ncm
                  and candidate['cest']==cest and candidate['cfop']==cfop
                  and candidate['cst']==cst and candidate['regime']==regime):
            data['motivo']='DIMENSOES_CANDIDATAS_DIVERGENTES'
        elif not (date.fromisoformat(candidate['vigencia_inicio'])<=issue_date
                  and (candidate['vigencia_fim'] is None or issue_date<=date.fromisoformat(candidate['vigencia_fim']))):
            data['motivo']='VIGENCIA_CANDIDATA_NAO_COBRE_EMISSAO'
        elif (sim.get('comparacao_condicional') is not True
              or sim.get('estado') != 'SIMULACAO_CONDICIONAL_MVA'
              or sim.get('metodo_base') != 'iva_st'):
            data['motivo']='G12_SEM_SIMULACAO_ITEM'
        elif (sim.get('fonte_legal_informada') != candidate['fonte_legal']):
            data['motivo']='FONTE_CANDIDATA_DIVERGE_MOTOR_L2'
        else:
            data['estado']='COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST'
            data['motivo']='SEM_AUTENTICACAO_FONTE_PRIMARIA_EXCECOES_OU_EFD'
            data['fonte_legal_candidata']=candidate['fonte_legal']
            data['url_fonte_candidata']=candidate['url_fonte']
            data['versao_ato_declarada']=candidate['versao_ato']
            data['sha256_texto_normativo_declarado']=candidate['sha256_texto_normativo_declarado']
            matches+=1
        reports.append(data)
    return {
        'schema_version':SCHEMA,
        'estado':('CANDIDATOS_ESTRUTURAIS_SEM_AUTORIDADE' if matches==len(reports)
                 else 'COBERTURA_CANDIDATA_PARCIAL' if matches else 'SEM_COBERTURA_NORMATIVA_CANDIDATA'),
        'empresa_id':empresa_id,'relatorio_id':relatorio_id,
        'documento_id':g13['documento_id'],'xml_sha256':digest,
        'competencia_declarada':issue_date.strftime('%Y-%m'),
        'itens_total':len(reports),'itens_cotejados_estruturalmente':matches,
        'candidatos_declarados_total':len(candidates),'itens':reports,
        'posse_e_proveniencia_interna_g13':True,
        **_false_flags(),
    }

__all__=['SCHEMA','EnterpriseG14GateError','cotejar_enquadramento_normativo_operacao_g14']
