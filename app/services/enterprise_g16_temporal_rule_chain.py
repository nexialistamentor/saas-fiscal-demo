"""Enterprise G1.6 — ADR-020 structured rule and lifecycle checkpoint.

Read-only G1.5 -> ExtractionResult/Run -> RuleVersion -> review -> activation.
A nominated relation list can reveal amendments/revocation; it cannot prove
completeness, publication freshness, current legal validity or official origin.
No external authority is promoted. Never authorizes credit/checkout.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException

from app.models import (ExtractionResult, ExtractionRun, RuleVersion,
                        RuleReviewRecord, NormativeActivation,
                        NormativeRelationVersion)
from app.services.enterprise_g15_adr020_primary_artifact_link import (
    cotejar_artefacto_primario_g15,
)

SCHEMA = 'SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1'
_G15_SCHEMA = 'SOLVERIS_ENTERPRISE_G15_ADR020_ARTIFACT_LINK_V1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_IDENT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,63}\Z')
_FIELDS = frozenset({'indice_item','extraction_result_id','rule_version_record_id',
                     'rule_review_record_id','normative_activation_id',
                     'relation_version_record_ids'})
_NEGATIVE = (
    'fonte_primaria_autenticada','enquadramento_legal_autorizado',
    'cest_aplicabilidade_juridica_comprovada','excecoes_e_beneficios_verificados',
    'icms_proprio_independente','documento_autenticado_sefaz',
    'efd_escrituracao_verificada','recolhimento_verificado',
    'autoridade_fiscal','credito_confirmado','checkout_autorizado',
    'usavel_comercialmente',
)
_RISK_RELATIONS = frozenset({'rectifica','republica','altera','substitui','revoga','sucede'})
_NS = {'n':'http://www.portalfiscal.inf.br/nfe'}
_URI = '{http://www.portalfiscal.inf.br/nfe}'

class EnterpriseG16GateError(ValueError):
    """Invalid trust boundary: abort whole projection."""


def _id(x):
    return type(x) is int and x > 0


def _ident(x):
    return type(x) is str and _IDENT.fullmatch(x) is not None


def _sha(x):
    return type(x) is str and _HEX.fullmatch(x) is not None


def _get(db, cls, key):
    try:
        return db.get(cls, key)
    except Exception:
        return None


def _emissao(raw):
    """Date observed in exact document bytes (not publication timestamp)."""
    try:
        root = ET.fromstring(raw, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        if root.tag == _URI+'NFe':
            nfe = root
        elif root.tag == _URI+'nfeProc':
            nodes = root.findall('n:NFe',_NS)
            nfe = nodes[0] if len(nodes)==1 else None
        else:
            return None
        infs = nfe.findall('n:infNFe',_NS) if nfe is not None else []
        if len(infs)!=1:
            return None
        stamps = infs[0].findall('n:ide/n:dhEmi',_NS)
        if len(stamps)!=1 or type(stamps[0].text) is not str:
            return None
        issued = datetime.fromisoformat(stamps[0].text)
        if issued.tzinfo is None or issued.utcoffset() is None:
            return None
        return issued.date().isoformat()
    except (ET.ParseError,DefusedXmlException,ValueError,TypeError,OverflowError):
        return None


def _temporal(db, row, item):
    """Only exact internal links; never assert absence of later changes."""
    extraction = _get(db, ExtractionResult, row['extraction_result_id'])
    rule = _get(db, RuleVersion, row['rule_version_record_id'])
    review = _get(db, RuleReviewRecord, row['rule_review_record_id'])
    activation = _get(db, NormativeActivation, row['normative_activation_id'])
    if any(x is None for x in (extraction,rule,review,activation)):
        return 'REGISTOS_TEMPORAIS_INCOMPLETOS',None,[]
    ah = item['artefacto_sha256']
    if (getattr(extraction,'extraction_result_id',None)!=row['extraction_result_id']
        or getattr(extraction,'normative_artifact_id',None)!=item['normative_artifact_id']
        or getattr(extraction,'artifact_hash',None)!=ah
        or getattr(extraction,'outcome',None)!='conclusivo'
        or getattr(extraction,'run_event',None)!='conclusao'
        or getattr(extraction,'run_state',None)!='concluida'
        or not _sha(getattr(extraction,'record_hash',None))
        or not _ident(getattr(extraction,'extraction_run_record_id',None))):
        return 'EXTRACAO_NAO_VINCULADA_AO_ARTEFACTO',None,[]
    run = _get(db, ExtractionRun, extraction.extraction_run_record_id)
    if (run is None
        or getattr(run,'extraction_run_record_id',None)!=extraction.extraction_run_record_id
        or getattr(run,'normative_artifact_id',None)!=item['normative_artifact_id']
        or getattr(run,'artifact_hash',None)!=ah
        or getattr(run,'run_event',None)!='conclusao'
        or getattr(run,'projected_state',None)!='concluida'
        or not _sha(getattr(run,'record_hash',None))):
        return 'EXECUCAO_EXTRACAO_NAO_VINCULADA',None,[]
    rid = getattr(rule,'rule_id',None)
    rv = getattr(rule,'rule_version',None)
    rh = getattr(rule,'rule_hash',None)
    if (getattr(rule,'rule_version_record_id',None)!=row['rule_version_record_id']
        or not _ident(rid) or not _id(rv) or not _sha(rh)
        or getattr(rule,'extraction_result_id',None)!=extraction.extraction_result_id
        or getattr(rule,'extraction_result_record_hash',None)!=extraction.record_hash
        or not _sha(getattr(rule,'record_hash',None))):
        return 'VERSAO_REGRA_SEM_ORIGEM_EXACTA',None,[]
    if (getattr(review,'rule_review_record_id',None)!=row['rule_review_record_id']
        or getattr(review,'subject_id',None)!=rid
        or getattr(review,'subject_version',None)!=rv
        or getattr(review,'subject_hash',None)!=rh
        or getattr(review,'review_event',None)!='revisao_concluida'
        or getattr(review,'outcome',None)!='validada'
        or not _sha(getattr(review,'record_hash',None))):
        return 'REVISAO_REGRA_NAO_FAVORAVEL',None,[]
    if (getattr(activation,'normative_activation_id',None)!=row['normative_activation_id']
        or getattr(activation,'subject_type',None)!='rule_version'
        or getattr(activation,'subject_id',None)!=rid
        or getattr(activation,'subject_version',None)!=rv
        or getattr(activation,'subject_hash',None)!=rh
        or getattr(activation,'review_record_id',None)!=review.rule_review_record_id
        or getattr(activation,'review_record_hash',None)!=review.record_hash
        or not _sha(getattr(activation,'record_hash',None))):
        return 'ATIVACAO_SEM_VINCULO_EXACTO',None,[]
    if activation.state!='active':
        return 'ATIVACAO_INTERNA_NAO_ATIVA',None,[]
    # Caller-specified relation IDs are an incomplete sample by construction.
    observed=[]
    for refid in row['relation_version_record_ids']:
        relation=_get(db,NormativeRelationVersion,refid)
        if (relation is None or getattr(relation,'normative_relation_version_record_id',None)!=refid
            or getattr(relation,'relation_type',None) not in
                (_RISK_RELATIONS | frozenset({'complementa','referencia'}))
            or not _sha(getattr(relation,'record_hash',None))
            or not _sha(getattr(relation,'normative_relation_hash',None))):
            return 'RELACAO_ADR020_NAO_COMPROVADA',None,[]
        matched = any((getattr(relation,p+'subject_type',None)=='rule_version'
                       and getattr(relation,p+'subject_id',None)==rid
                       and getattr(relation,p+'subject_version',None)==rv
                       and getattr(relation,p+'subject_hash',None)==rh)
                      for p in ('source_','target_'))
        if not matched:
            return 'RELACAO_NAO_LIGADA_A_REGRA',None,[]
        observed.append(relation.relation_type)
    identity={'rule_id':rid,'rule_version':rv,'rule_hash':rh}
    if any(t in _RISK_RELATIONS for t in observed):
        return 'ALTERACAO_OU_REVOGACAO_DECLARADA_REQUER_REAVALIACAO',identity,observed
    return 'CADEIA_INTERNA_REGRA_COTEJADA_SEM_PROVA_DE_VIGENCIA',identity,observed


def cotejar_ciclo_normativo_g16(*,db,authenticated_user_id:int,empresa_id:int,
    relatorio_id:int,xml_bytes:bytes,candidatos_normativos:list[dict]|None=None,
    referencias_adr020:list[dict]|None=None,referencias_temporais:list[dict]|None=None)->dict:
    """Never authorize legal efficacy from internal data, including active rows."""
    if (db is None or not all(_id(x) for x in (authenticated_user_id,empresa_id,relatorio_id))
        or type(xml_bytes) is not bytes or not 0<len(xml_bytes)<=2*1024*1024):
        raise EnterpriseG16GateError('G16_ENTRADA_INVALIDA')
    requested=[] if referencias_temporais is None else referencias_temporais
    if type(requested) is not list or len(requested)>500:
        raise EnterpriseG16GateError('G16_REFERENCIAS_TEMPORAIS_INVALIDAS')
    by_idx={}
    for x in requested:
        if (type(x) is not dict or set(x)!=_FIELDS or not _id(x.get('indice_item'))
            or x['indice_item'] in by_idx or any(not _ident(x.get(k)) for k in
                _FIELDS-{'indice_item','relation_version_record_ids'})
            or type(x.get('relation_version_record_ids')) is not list
            or len(x['relation_version_record_ids'])>30
            or any(not _ident(v) for v in x['relation_version_record_ids'])
            or len(set(x['relation_version_record_ids']))!=len(x['relation_version_record_ids'])):
            raise EnterpriseG16GateError('G16_REFERENCIA_DUPLICADA_OU_INVALIDA')
        by_idx[x['indice_item']]=x
    try:
        g15=cotejar_artefacto_primario_g15(db=db,authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id,relatorio_id=relatorio_id,xml_bytes=xml_bytes,
            candidatos_normativos=candidatos_normativos,referencias_adr020=referencias_adr020)
    except Exception as exc:
        raise EnterpriseG16GateError('G16_G15_DOCUMENTO_E_ARTEFACTO_NAO_COTEJADOS') from exc
    digest=hashlib.sha256(xml_bytes).hexdigest()
    items=g15.get('itens') if type(g15) is dict else None
    if (type(g15) is not dict or g15.get('schema_version')!=_G15_SCHEMA
        or g15.get('empresa_id')!=empresa_id or g15.get('relatorio_id')!=relatorio_id
        or not _sha(g15.get('xml_sha256'))
        or not hmac.compare_digest(g15['xml_sha256'],digest)
        or type(g15.get('documento_id')) is not int or g15['documento_id']<=0
        or g15.get('posse_e_proveniencia_interna_g14') is not True
        or any(g15.get(k) is not False for k in _NEGATIVE)
        or g15.get('versao_oficial_verificada') is not False
        or g15.get('texto_normativo_interpretado_e_aplicado') is not False
        or type(items) is not list or not 0<len(items)<=500
        or type(g15.get('itens_total')) is not int or len(items)!=g15['itens_total']
        or type(g15.get('itens_com_cadeia_interna')) is not int
        or not 0<=g15['itens_com_cadeia_interna']<=len(items)):
        raise EnterpriseG16GateError('G16_G15_CONTRATO_INCOMPATIVEL')
    if any(x>len(items) for x in by_idx):
        raise EnterpriseG16GateError('G16_REFERENCIA_FORA_DO_DOCUMENTO')
    operation_date=_emissao(xml_bytes)
    if operation_date is None:
        raise EnterpriseG16GateError('G16_DATA_EMISSAO_INCONSISTENTE')
    result=[]
    for idx,item in enumerate(items,1):
        if (type(item) is not dict or type(item.get('indice_item')) is not int
            or item['indice_item']!=idx
            or item.get('fonte_primaria_autenticada') is not False
            or item.get('versao_ato_verificada') is not False
            or item.get('aplicabilidade_juridica_comprovada') is not False):
            raise EnterpriseG16GateError('G16_ITEM_G15_INCONSISTENTE')
        record={'indice_item':idx,'estado':'LACUNA_CADEIA_TEMPORAL',
                'motivo':'SEM_ARTEFACTO_OU_REGRA_TEMPORAL','rule_id':None,
                'rule_version':None,'rule_hash':None,'relacoes_declaradas':[],
                'regra_interna_cotejada':False,'fonte_oficial_autenticada':False,
                'cobertura_publicacoes_completa':False,'vigencia_juridica_comprovada':False,
                'ausencia_revogacao_comprovada':False,'excecoes_aplicadas':False}
        x=by_idx.get(idx)
        if item.get('cadeia_interna_adr020_verificada') is not True:
            record['motivo']='G15_SEM_CADEIA_INTERNA_ADR020'
        elif x is None:
            record['motivo']='SEM_REFERENCIAS_EXTRACAO_REGRA_ATIVACAO'
        elif not _ident(item.get('normative_artifact_id')) or not _sha(item.get('artefacto_sha256')):
            raise EnterpriseG16GateError('G16_ITEM_ARTEFACTO_INCONSISTENTE')
        else:
            status,identity,relations=_temporal(db,x,item)
            record['motivo']=status
            if identity is not None:
                record.update(identity)
                record['relacoes_declaradas']=relations
                record['regra_interna_cotejada']=True
                record['estado']='CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE'
                if status.startswith('ALTERACAO_'):
                    record['estado']='ALERTA_RELACAO_NORMATIVA_SEM_DECISAO'
        result.append(record)
    linked=sum(1 for x in result if x['regra_interna_cotejada'])
    return {'schema_version':SCHEMA,'estado':('CADEIAS_TEMPORAIS_INTERNAS_SEM_AUTORIDADE'
             if linked==len(result) else 'COBERTURA_TEMPORAL_PARCIAL' if linked
             else 'SEM_COBERTURA_TEMPORAL'),
            'empresa_id':empresa_id,'relatorio_id':relatorio_id,
            'documento_id':g15['documento_id'],'xml_sha256':digest,
            'data_operacao_observada':operation_date,'itens_total':len(result),
            'itens_com_cadeia_temporal_interna':linked,'itens':result,
            'posse_documental_interna_g15':True,
            'fonte_primaria_autenticada':False,'versao_oficial_verificada':False,
            'atualizacao_e_revogacao_exaustivas':False,'vigencia_juridica_comprovada':False,
            'autoridade_fiscal':False,'credito_confirmado':False,
            'checkout_autorizado':False,'usavel_comercialmente':False}

__all__=['SCHEMA','EnterpriseG16GateError','cotejar_ciclo_normativo_g16']
