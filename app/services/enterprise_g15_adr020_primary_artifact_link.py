"""G1.5: cotejo read-only dos artefactos ADR-020 com candidatos G1.4.

A G1.4 (e antes G1.3/I2/G1.2/G1) e OBRIGATORIA; IDs fornecidos pelo
chamador nao autenticam por si qualquer ato. Verifica somente o que a BD
ADR-020 contem, as ligacoes e os bytes imutaveis efectivamente presentes.
Nao valida a origem externa independente, texto normativo interpretado,
CEST juridico, excecoes, status actual de revogacao ou direito a credito.
Sem rede, escrita, ficheiros externos, pagamento ou decisao fiscal.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from app.models import (
    AcquisitionExecution, ArtifactReference, ArtifactVerificationRecord,
    NormativeArtifact,
)
from app.services.enterprise_g14_operational_normative_scope import (
    cotejar_enquadramento_normativo_operacao_g14,
)

SCHEMA = 'SOLVERIS_ENTERPRISE_G15_ADR020_ARTIFACT_LINK_V1'
_G14_SCHEMA = 'SOLVERIS_ENTERPRISE_G14_OPERATIONAL_NORMATIVE_SCOPE_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_FIELDS = frozenset({
    'indice_item', 'artifact_reference_record_id',
    'acquisition_execution_record_id', 'normative_artifact_id',
    'authenticity_verification_record_id',
    'integrity_verification_record_id',
    'preservation_verification_record_id',
})
_FLAGS = (
    'fonte_primaria_autenticada', 'enquadramento_legal_autorizado',
    'cest_aplicabilidade_juridica_comprovada', 'excecoes_e_beneficios_verificados',
    'icms_proprio_independente', 'documento_autenticado_sefaz',
    'efd_escrituracao_verificada', 'recolhimento_verificado',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente',
)


class EnterpriseG15GateError(ValueError):
    """Erro no sujeito/contrato/identidade: nenhuma conclusao reutilizavel."""


def _stop(code: str):
    raise EnterpriseG15GateError(code)


def _id(value: object) -> bool:
    return type(value) is int and value > 0


def _ident(value: object) -> bool:
    return type(value) is str and 0 < len(value) <= 64 and value == value.strip()


def _sha(value: object) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _row(db, model, ident):
    try:
        return db.get(model, ident)
    except Exception:
        return None


def _matched_verification(row, *, expected_id, vtype, artifact_id, digest):
    return bool(row is not None
                and getattr(row, 'artifact_verification_record_id', None) == expected_id
                and getattr(row, 'normative_artifact_id', None) == artifact_id
                and getattr(row, 'verified_artifact_hash', None) == digest
                and getattr(row, 'verification_type', None) == vtype
                and getattr(row, 'outcome', None) == 'conclusivo_favoravel'
                and getattr(row, 'incident_id', None) is None
                and _sha(getattr(row, 'record_hash', None)))


def _cotejar_artefacto(db, candidate: dict, link: dict) -> tuple[bool, str, str | None]:
    """Cotejo dos registos guardados, sem transformar estado BD em trust externo."""
    ref = _row(db, ArtifactReference, link['artifact_reference_record_id'])
    execution = _row(db, AcquisitionExecution, link['acquisition_execution_record_id'])
    artifact = _row(db, NormativeArtifact, link['normative_artifact_id'])
    if ref is None or execution is None or artifact is None:
        return False, 'REGISTO_ADR020_NAO_ENCONTRADO', None
    if (getattr(ref, 'artifact_reference_record_id', None) != link['artifact_reference_record_id']
            or getattr(ref, 'reference_event', None) != 'resolvida'
            or not _ident(getattr(ref, 'source_id', None))
            or getattr(ref, 'exact_locator', None) != candidate['url_fonte_candidata']
            or getattr(ref, 'official_identifier', None) != candidate['fonte_legal_candidata']
            or not _sha(getattr(ref, 'record_hash', None))):
        return False, 'REFERENCIA_FONTE_OU_LOCALIZADOR_DIVERGENTE', None
    if (getattr(execution, 'acquisition_execution_record_id', None) != link['acquisition_execution_record_id']
            or getattr(execution, 'artifact_reference_record_id', None) != ref.artifact_reference_record_id
            or getattr(execution, 'artifact_reference_id', None) != ref.artifact_reference_id
            or getattr(execution, 'execution_event', None) != 'conclusao'
            or getattr(execution, 'projected_state', None) != 'concluida'
            or not _sha(getattr(execution, 'record_hash', None))):
        return False, 'AQUISICAO_ADR020_NAO_CONCLUIDA_OU_DIVERGENTE', None
    if (getattr(artifact, 'normative_artifact_id', None) != link['normative_artifact_id']
            or getattr(artifact, 'artifact_reference_id', None) != ref.artifact_reference_id
            or getattr(artifact, 'acquisition_execution_record_id', None) != execution.acquisition_execution_record_id
            or getattr(artifact, 'acquisition_execution_id', None) != execution.acquisition_execution_id
            or getattr(artifact, 'acquisition_attempt_number', None) != execution.attempt_number
            or getattr(artifact, 'acquisition_event', None) != 'conclusao'
            or getattr(artifact, 'acquisition_state', None) != 'concluida'
            or not _sha(getattr(artifact, 'record_hash', None))):
        return False, 'ARTEFACTO_SEM_ORIGEM_EXACTA', None
    raw = getattr(artifact, 'immutable_bytes', None)
    if (type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024
            or getattr(artifact, 'immutable_location', None) is not None):
        # Sem leitura de CAS arbitrario: location exige gate proprio.
        return False, 'BYTES_IMUTAVEIS_NAO_DISPONIVEIS_OFFLINE', None
    digest = hashlib.sha256(raw).hexdigest()
    if (getattr(artifact, 'byte_size', None) != len(raw)
            or not _sha(getattr(artifact, 'artifact_hash', None))
            or not hmac.compare_digest(digest, artifact.artifact_hash)
            or not hmac.compare_digest(digest, candidate['sha256_texto_normativo_declarado'])):
        return False, 'HASH_BYTES_ADR020_DIVERGENTE', None
    auth = _row(db, ArtifactVerificationRecord, link['authenticity_verification_record_id'])
    integrity = _row(db, ArtifactVerificationRecord, link['integrity_verification_record_id'])
    preservation = _row(db, ArtifactVerificationRecord, link['preservation_verification_record_id'])
    if not all((_matched_verification(auth, expected_id=link['authenticity_verification_record_id'], vtype='authenticity', artifact_id=artifact.normative_artifact_id, digest=digest),
                _matched_verification(integrity, expected_id=link['integrity_verification_record_id'], vtype='integrity', artifact_id=artifact.normative_artifact_id, digest=digest),
                _matched_verification(preservation, expected_id=link['preservation_verification_record_id'], vtype='preservation', artifact_id=artifact.normative_artifact_id, digest=digest))):
        return False, 'VERIFICACOES_ADR020_SEM_CADEIA_FAVORAVEL', None
    if (getattr(integrity, 'authenticity_verification_record_id', None) != auth.artifact_verification_record_id
            or getattr(integrity, 'authenticity_predecessor_type', None) != 'authenticity'
            or getattr(integrity, 'authenticity_predecessor_outcome', None) != 'conclusivo_favoravel'
            or getattr(preservation, 'authenticity_verification_record_id', None) != auth.artifact_verification_record_id
            or getattr(preservation, 'integrity_verification_record_id', None) != integrity.artifact_verification_record_id
            or getattr(preservation, 'authenticity_predecessor_type', None) != 'authenticity'
            or getattr(preservation, 'integrity_predecessor_type', None) != 'integrity'
            or getattr(preservation, 'authenticity_predecessor_outcome', None) != 'conclusivo_favoravel'
            or getattr(preservation, 'integrity_predecessor_outcome', None) != 'conclusivo_favoravel'):
        return False, 'PREDECESSORES_ADR020_NAO_CONCILIADOS', None
    return True, 'CADEIA_INTERNA_ADR020_COTEJADA_SEM_TRUST_EXTERNO', digest


def cotejar_artefacto_primario_g15(*, db, authenticated_user_id: int,
        empresa_id: int, relatorio_id: int, xml_bytes: bytes,
        candidatos_normativos: list[dict] | None = None,
        referencias_adr020: list[dict] | None = None) -> dict:
    """G14 primeiro; ADR-020 por item depois. Nunca concede autoridade fiscal.

    Links ADR-020 sao identificadores *nao confiaveis*; sempre sao resolvidos
    a registos via db.get. A BD usada deve ser a mesma base de leitura da G14.
    """
    if (db is None or not all(_id(v) for v in (authenticated_user_id, empresa_id, relatorio_id))
            or type(xml_bytes) is not bytes or not 0 < len(xml_bytes) <= 2 * 1024 * 1024):
        _stop('G15_ENTRADA_INVALIDA')
    links = [] if referencias_adr020 is None else referencias_adr020
    if type(links) is not list or len(links) > 500:
        _stop('G15_REFERENCIAS_MALFORMADAS')
    by_index = {}
    for link in links:
        if (type(link) is not dict or set(link) != _FIELDS
                or not _id(link.get('indice_item'))
                or any(not _ident(link.get(key)) for key in _FIELDS - {'indice_item'})
                or link['indice_item'] in by_index):
            _stop('G15_REFERENCIA_DUPLICADA_OU_INVALIDA')
        by_index[link['indice_item']] = link
    try:
        g14 = cotejar_enquadramento_normativo_operacao_g14(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes, candidatos_normativos=candidatos_normativos)
    except Exception as exc:
        raise EnterpriseG15GateError('G15_G14_NAO_COMPROVOU_SUJEITO_E_OPERACAO') from exc
    digest_xml = hashlib.sha256(xml_bytes).hexdigest()
    if (type(g14) is not dict or g14.get('schema_version') != _G14_SCHEMA
            or g14.get('empresa_id') != empresa_id or g14.get('relatorio_id') != relatorio_id
            or not _sha(g14.get('xml_sha256'))
            or not hmac.compare_digest(g14['xml_sha256'], digest_xml)
            or type(g14.get('documento_id')) is not int or g14['documento_id'] <= 0
            or g14.get('posse_e_proveniencia_interna_g13') is not True
            or any(g14.get(flag) is not False for flag in _FLAGS)
            or type(g14.get('itens')) is not list
            or not 0 < len(g14['itens']) <= 500
            or type(g14.get('itens_total')) is not int
            or g14['itens_total'] != len(g14['itens'])):
        _stop('G15_G14_CONTRATO_INCOMPATIVEL')
    if any(index > len(g14['itens']) for index in by_index):
        _stop('G15_REFERENCIA_ITEM_FORA_DA_NOTA')
    reports=[]
    matched=0
    for index, item in enumerate(g14['itens'], 1):
        if (type(item) is not dict or type(item.get('indice_item')) is not int
                or item['indice_item'] != index):
            _stop('G15_ITEM_G14_INCONSISTENTE')
        rec={'indice_item':index,'ncm':item.get('ncm'),'cest_observado':item.get('cest_observado'),
             'estado':'NAO_COTEJADO','motivo':None,'normative_artifact_id':None,
             'artefacto_sha256':None,'cadeia_interna_adr020_verificada':False,
             'fonte_primaria_autenticada':False,'versao_ato_verificada':False,
             'aplicabilidade_juridica_comprovada':False}
        link=by_index.get(index)
        if item.get('estado') != 'COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST':
            rec['motivo']='G14_SEM_CANDIDATO_ESTRUTURAL_COTEJADO'
        elif link is None:
            rec['motivo']='SEM_EVIDENCIA_ADR020_EXPLICITA'
        elif (not _sha(item.get('sha256_texto_normativo_declarado'))
              or type(item.get('url_fonte_candidata')) is not str
              or type(item.get('fonte_legal_candidata')) is not str):
            _stop('G15_CANDIDATO_G14_MALFORMADO')
        else:
            good, reason, artifact_digest = _cotejar_artefacto(db, item, link)
            rec['motivo']=reason
            if good:
                matched+=1
                rec['estado']='ARTEFACTO_INTERNO_COTEJADO_SEM_AUTORIDADE'
                rec['normative_artifact_id']=link['normative_artifact_id']
                rec['artefacto_sha256']=artifact_digest
                rec['cadeia_interna_adr020_verificada']=True
        reports.append(rec)
    return {'schema_version':SCHEMA,
            'estado':('ARTEFACTOS_ADR020_COTEJADOS_SEM_AUTORIDADE' if matched == len(reports)
                     else 'COBERTURA_ADR020_PARCIAL_SEM_AUTORIDADE' if matched
                     else 'SEM_ARTEFACTOS_ADR020_COTEJADOS'),
            'empresa_id':empresa_id,'relatorio_id':relatorio_id,
            'documento_id':g14['documento_id'], 'xml_sha256':digest_xml,
            'itens_total':len(reports), 'itens_com_cadeia_interna':matched,
            'itens':reports,'posse_e_proveniencia_interna_g14':True,
            'adr020_snapshot_referenciado_nao_frescura_verificada':True,
            'texto_normativo_interpretado_e_aplicado':False,
            'versao_oficial_verificada':False,
            **{flag:False for flag in _FLAGS}}


__all__ = ['SCHEMA','EnterpriseG15GateError','cotejar_artefacto_primario_g15']
