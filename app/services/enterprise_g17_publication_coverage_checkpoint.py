"""SOLVERIS Enterprise G1.7: ADR-020 bounded publication-coverage checkpoint.

Read-only continuation of G1.6. Uses *actual stored* CoverageContract,
CoverageCheckpointRecord and CoverageLedgerEntry rows; never treats a caller's
list of IDs as proof of an exhaustive current publisher archive.

Only validates a finite, explicitly enumerated contiguous observation window.
No independent PDF/PAdES/ICP-Brasil verification, publication authority,
complete revocation timeline, external anchor, tax entitlement or checkout.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import date, datetime, time, timedelta, timezone

from app.models import (
    ArtifactReference, NormativeArtifact, ExtractionResult, RuleVersion,
    CoverageContract, CoverageCheckpointRecord, CoverageLedgerEntry,
)
from app.services.enterprise_g16_temporal_rule_chain import cotejar_ciclo_normativo_g16

SCHEMA = 'SOLVERIS_ENTERPRISE_G17_BOUNDED_COVERAGE_V1'
_G16_SCHEMA = 'SOLVERIS_ENTERPRISE_G16_TEMPORAL_RULE_CHECKPOINT_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_IDENT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,63}\Z')
_FIELDS = frozenset({
    'indice_item', 'rule_version_record_id', 'extraction_result_id',
    'normative_artifact_id', 'artifact_reference_record_id',
    'coverage_contract_record_id', 'coverage_checkpoint_record_id',
    'coverage_ledger_entry_ids',
})
_FORBIDDEN = (
    'fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente',
)


class EnterpriseG17GateError(ValueError):
    """Invalid caller trust boundary: no evaluable result."""


def _id(x):
    return type(x) is int and x > 0


def _ident(x):
    return type(x) is str and _IDENT.fullmatch(x) is not None


def _sha(x):
    return type(x) is str and _SHA.fullmatch(x) is not None


def _utc_aware(dt):
    return type(dt) is datetime and dt.tzinfo is not None and dt.utcoffset() is not None


def _required_brazil_day_utc(operation_date):
    """Fail-closed UTC bounds for a Brazilian civil date, without guessing NF-e TZ.

    The G16 output currently exposes only YYYY-MM-DD. Until exact timestamp
    and authoritative geographic timezone are bound, cover 00:00Z on that
    date through 06:00Z the following date. This intentionally overcovers
    Brazilian UTC offsets 00 through -06 and cannot promote legal trust.
    """
    lower = datetime.combine(operation_date, time.min, tzinfo=timezone.utc)
    return lower, lower + timedelta(days=1, hours=6)


def _get(db, cls, key):
    try:
        return db.get(cls, key)
    except Exception:
        return None


def _link_valid(x):
    if type(x) is not dict or set(x) != _FIELDS or not _id(x.get('indice_item')):
        return False
    if any(not _ident(x.get(k)) for k in _FIELDS - {'indice_item', 'coverage_ledger_entry_ids'}):
        return False
    seq = x.get('coverage_ledger_entry_ids')
    return (type(seq) is list and 0 < len(seq) <= 128 and
            all(_ident(y) for y in seq) and len(set(seq)) == len(seq))


def _checkpoint(db, link, g16_item, operation_date):
    """Cotejo bounded only; no complete/external coverage claim."""
    rule = _get(db, RuleVersion, link['rule_version_record_id'])
    extraction = _get(db, ExtractionResult, link['extraction_result_id'])
    artifact = _get(db, NormativeArtifact, link['normative_artifact_id'])
    reference = _get(db, ArtifactReference, link['artifact_reference_record_id'])
    contract = _get(db, CoverageContract, link['coverage_contract_record_id'])
    checkpoint = _get(db, CoverageCheckpointRecord, link['coverage_checkpoint_record_id'])
    if any(x is None for x in (rule, extraction, artifact, reference, contract, checkpoint)):
        return False, 'G17_REGISTO_ADR020_OU_COBERTURA_AUSENTE', None
    if (getattr(rule,'rule_version_record_id',None) != link['rule_version_record_id']
        or rule.rule_id != g16_item['rule_id']
        or rule.rule_version != g16_item['rule_version']
        or rule.rule_hash != g16_item['rule_hash']
        or not _sha(getattr(rule,'record_hash',None))
        or getattr(rule,'extraction_result_id',None) != link['extraction_result_id']
        or getattr(extraction,'extraction_result_id',None) != link['extraction_result_id']
        or getattr(extraction,'normative_artifact_id',None) != link['normative_artifact_id']
        or getattr(rule,'extraction_result_record_hash',None) != getattr(extraction,'record_hash',None)
        or getattr(artifact,'normative_artifact_id',None) != link['normative_artifact_id']
        or getattr(artifact,'artifact_hash',None) != getattr(extraction,'artifact_hash',None)
        or getattr(artifact,'artifact_reference_id',None) != getattr(reference,'artifact_reference_id',None)
        or getattr(reference,'artifact_reference_record_id',None) != link['artifact_reference_record_id']
        or getattr(reference,'reference_event',None) != 'resolvida'):
        return False, 'G17_REGRA_ARTEFACTO_FONTE_NAO_VINCULADOS', None
    if (getattr(contract,'coverage_contract_record_id',None) != link['coverage_contract_record_id']
        or getattr(contract,'contract_state',None) != 'ratificada'
        or getattr(contract,'source_id',None) != getattr(reference,'source_id',None)
        or not _ident(getattr(contract,'coverage_contract_id',None))
        or not _id(getattr(contract,'contract_version',None))
        or not _sha(getattr(contract,'contract_hash',None))
        or not _sha(getattr(contract,'record_hash',None))):
        return False, 'G17_CONTRATO_COBERTURA_SEM_ORIGEM_RATIFICADA', None
    start, end = getattr(contract,'effective_from',None), getattr(contract,'effective_to',None)
    if not _utc_aware(start) or (end is not None and not _utc_aware(end)):
        return False, 'G17_VIGENCIA_CONTRATO_SEM_TEMPO_CONFIAVEL', None
    # Check exact UTC bounds, not .date(): a noon start is only a partial day.
    required_start, required_end = _required_brazil_day_utc(operation_date)
    if start > required_start or (end is not None and end < required_end):
        return False, 'G17_CONTRATO_FORA_DATA_OPERACAO', None
    if (getattr(checkpoint,'coverage_checkpoint_record_id',None) != link['coverage_checkpoint_record_id']
        or checkpoint.coverage_contract_id != contract.coverage_contract_id
        or checkpoint.contract_version != contract.contract_version
        or checkpoint.contract_hash != contract.contract_hash
        or not _sha(getattr(checkpoint,'record_hash',None))
        or not _id(getattr(checkpoint,'checkpoint_sequence',None))
        or getattr(checkpoint,'cycle_fully_evaluated',None) is not True
        or getattr(checkpoint,'pending_gap_from',object()) is not None):
        return False, 'G17_CHECKPOINT_INCOMPLETO_OU_COM_LACUNA', None
    covered = getattr(checkpoint,'covered_through',None)
    if (not _id(covered) or covered != checkpoint.completed_through
        or covered != checkpoint.observed_through
        or covered != len(link['coverage_ledger_entry_ids'])):
        return False, 'G17_FRONTEIRA_DE_COBERTURA_NAO_CONCILIADA', None
    ws, we = getattr(checkpoint,'window_start',None), getattr(checkpoint,'window_end',None)
    if (not _utc_aware(ws) or not _utc_aware(we) or we <= ws
        or ws > required_start or we < required_end):
        return False, 'G17_JANELA_PUBLICACAO_NAO_COBRE_DIA', None
    if (ws < start or (end is not None and we > end)):
        return False, 'G17_JANELA_EXCEDE_CONTRATO', None
    ids = link['coverage_ledger_entry_ids']
    ledgers=[]
    for i, ident in enumerate(ids,1):
        row = _get(db,CoverageLedgerEntry,ident)
        if (row is None or getattr(row,'coverage_ledger_entry_id',None) != ident
            or getattr(row,'coverage_contract_id',None) != contract.coverage_contract_id
            or getattr(row,'contract_version',None) != contract.contract_version
            or getattr(row,'contract_hash',None) != contract.contract_hash
            or getattr(row,'window_start',None) != ws
            or getattr(row,'window_end',None) != we
            or getattr(row,'unit_order',None) != i
            or getattr(row,'coverage_outcome',None) != 'covered'
            or getattr(row,'observation_outcome',None) != 'observed'
            or getattr(row,'processing_outcome',None) != 'succeeded'
            or getattr(row,'response_kind',None) != 'non_empty'
            or getattr(row,'cycle_fully_evaluated',None) is not True
            or not _sha(getattr(row,'record_hash',None))):
            return False, 'G17_LEDGER_UNIDADE_NAO_COBERTA_OU_MAL_LIGADA', None
        ledgers.append(row)
    if getattr(checkpoint,'last_ledger_entry_id',None) != ledgers[-1].coverage_ledger_entry_id:
        return False, 'G17_ULTIMA_UNIDADE_NAO_CONCILIADA', None
    return True, 'G17_JANELA_ADR020_ENUMERADA_SEM_AUTORIDADE_EXTERNA', {
        'coverage_contract_id':contract.coverage_contract_id,
        'contract_version':contract.contract_version,
        'coverage_checkpoint_record_id':checkpoint.coverage_checkpoint_record_id,
        'unidades_observadas':len(ledgers),
    }


def cotejar_cobertura_publicacao_g17(*, db, authenticated_user_id:int,
        empresa_id:int, relatorio_id:int, xml_bytes:bytes,
        candidatos_normativos:list[dict]|None=None,
        referencias_adr020:list[dict]|None=None,
        referencias_temporais:list[dict]|None=None,
        referencias_cobertura:list[dict]|None=None,
        cas_root=None) -> dict:
    """G16 first; only then read ADR-020 bounded checkpoint/ledger rows.

    Does NOT claim fresh/exhaustive coverage of all amendments or official
    source validity. Caller IDs cannot prove that there is no later checkpoint.
    """
    if db is None or not all(_id(x) for x in (authenticated_user_id,empresa_id,relatorio_id)):
        raise EnterpriseG17GateError('G17_IDENTIDADE_INVALIDA')
    if type(xml_bytes) is not bytes or not (0 < len(xml_bytes) <= 2*1024*1024):
        raise EnterpriseG17GateError('G17_XML_INVALIDO')
    refs = [] if referencias_cobertura is None else referencias_cobertura
    if type(refs) is not list or len(refs)>500:
        raise EnterpriseG17GateError('G17_REFERENCIAS_INVALIDAS')
    by_idx={}
    for link in refs:
        if not _link_valid(link) or link['indice_item'] in by_idx:
            raise EnterpriseG17GateError('G17_REFERENCIA_INVALIDA_OU_DUPLICADA')
        by_idx[link['indice_item']]=link
    try:
        g16=cotejar_ciclo_normativo_g16(db=db,authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id,relatorio_id=relatorio_id,xml_bytes=xml_bytes,
            candidatos_normativos=candidatos_normativos,referencias_adr020=referencias_adr020,
            referencias_temporais=referencias_temporais,
            **({'cas_root':cas_root} if cas_root is not None else {}))
    except Exception as exc:
        raise EnterpriseG17GateError('G17_G16_GATE_FALHOU') from exc
    digest=hashlib.sha256(xml_bytes).hexdigest()
    items=g16.get('itens') if type(g16) is dict else None
    if (type(g16) is not dict or g16.get('schema_version') != _G16_SCHEMA
        or g16.get('empresa_id') != empresa_id or g16.get('relatorio_id') != relatorio_id
        or type(g16.get('documento_id')) is not int or g16['documento_id'] <= 0
        or not _sha(g16.get('xml_sha256')) or not hmac.compare_digest(g16['xml_sha256'], digest)
        or g16.get('posse_documental_interna_g15') is not True
        or any(g16.get(k) is not False for k in _FORBIDDEN)
        or type(items) is not list or not (0<len(items)<=500)
        or type(g16.get('itens_total')) is not int or g16['itens_total'] != len(items)):
        raise EnterpriseG17GateError('G17_G16_CONTRATO_INCOMPATIVEL')
    if any(idx>len(items) for idx in by_idx):
        raise EnterpriseG17GateError('G17_ITEM_FORA_DO_DOCUMENTO')
    try:
        opdate=date.fromisoformat(g16['data_operacao_observada'])
        if opdate.isoformat()!=g16['data_operacao_observada']:
            raise ValueError()
    except (TypeError,ValueError,KeyError) as exc:
        raise EnterpriseG17GateError('G17_DATA_OPERACAO_INVALIDA') from exc
    result=[]
    linked=0
    for idx,item in enumerate(items,1):
        if (type(item) is not dict or type(item.get('indice_item')) is not int
            or item['indice_item'] != idx or item.get('fonte_oficial_autenticada') is not False
            or item.get('cobertura_publicacoes_completa') is not False
            or item.get('vigencia_juridica_comprovada') is not False
            or item.get('ausencia_revogacao_comprovada') is not False):
            raise EnterpriseG17GateError('G17_ITEM_G16_INCONSISTENTE')
        rec={'indice_item':idx,'estado':'SEM_COBERTURA_COTEJADA','motivo':None,
             'coverage_contract_id':None,'contract_version':None,
             'coverage_checkpoint_record_id':None,'unidades_observadas':0,
             'janela_administrativa_cotejada':False,
             'edicao_oficial_assinatura_validada':False,
             'fonte_primaria_autenticada':False,
             'cobertura_publicacoes_exaustiva':False,
             'ausencia_revogacao_comprovada':False,
             'vigencia_juridica_comprovada':False}
        ref=by_idx.get(idx)
        if item.get('regra_interna_cotejada') is not True:
            rec['motivo']='G16_SEM_CADEIA_INTERNA'
        elif item.get('estado') == 'ALERTA_RELACAO_NORMATIVA_SEM_DECISAO':
            rec['motivo']='G16_RELACAO_RISCO_NORMATIVO'
        elif ref is None:
            rec['motivo']='SEM_CHECKPOINT_COBERTURA_EXPLICITO'
        elif not (_ident(item.get('rule_id')) and _id(item.get('rule_version')) and _sha(item.get('rule_hash'))):
            raise EnterpriseG17GateError('G17_IDENTIDADE_REGRA_INCONSISTENTE')
        else:
            ok,motivo,detail=_checkpoint(db,ref,item,opdate)
            rec['motivo']=motivo
            if ok:
                linked+=1
                rec.update(detail)
                rec['estado']='JANELA_ADR020_COTEJADA_NAO_EXAUSTIVA'
                rec['janela_administrativa_cotejada']=True
        result.append(rec)
    return {'schema_version':SCHEMA,
            'estado':('JANELAS_ADR020_COTEJADAS_NAO_EXAUSTIVAS' if linked==len(result)
                else 'COBERTURA_PARCIAL_NAO_EXAUSTIVA' if linked else 'SEM_COBERTURA_ADR020'),
            'empresa_id':empresa_id,'relatorio_id':relatorio_id,'documento_id':g16['documento_id'],
            'xml_sha256':digest,'data_operacao_observada':opdate.isoformat(),
            'itens_total':len(result),'itens_janela_interna_cotejada':linked,
            'itens':result,'posse_documental_interna_g16':True,
            'fonte_primaria_autenticada':False,'versao_oficial_verificada':False,
            'atualizacao_e_revogacao_exaustivas':False,'vigencia_juridica_comprovada':False,
            'autoridade_fiscal':False,'credito_confirmado':False,
            'checkout_autorizado':False,'usavel_comercialmente':False}

__all__=['SCHEMA','EnterpriseG17GateError','cotejar_cobertura_publicacao_g17']
