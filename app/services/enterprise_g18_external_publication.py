"""SOLVERIS Enterprise G1.8: external PDF bytes ↔ ADR-020 reference, read-only.

This is a *hash and relational identity* bridge to G1.7, NOT an official
publisher authenticator. It does not accept audit logs as cryptographic proof,
verify a PDF CMS signature, build an ICP-Brasil trust path, establish past
revocation/issuance time, prove legal effect or enable financial/commercial use.

Bytes may be supplied by the caller from a separately protected immutable
storage location. That storage/custody must be independently revalidated.
No implicit network, filesystem, DB writes, payments or deployments.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from urllib.parse import urlsplit

SCHEMA = 'SOLVERIS_ENTERPRISE_G18_EXTERNAL_PUBLICATION_HASH_LINK_V1'
_G17_SCHEMA = 'SOLVERIS_ENTERPRISE_G17_BOUNDED_COVERAGE_V1'
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_IDENT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,63}\Z')
MAX_PDF = 16 * 1024 * 1024
MAX_EVIDENCES = 32
_EVIDENCE_FIELDS = frozenset({
    'indice_item', 'normative_artifact_id', 'artifact_reference_record_id',
    'url_publicacao', 'sha256_publicacao', 'pdf_bytes',
})
_DENIED = (
    'fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente',
)


class EnterpriseG18GateError(ValueError):
    """A broken identity/evidence contract cannot produce reusable evidence."""


def _stop(reason: str) -> None:
    raise EnterpriseG18GateError('G18_' + reason)


def _id(x: object) -> bool:
    return type(x) is int and x > 0


def _ident(x: object) -> bool:
    return type(x) is str and _IDENT.fullmatch(x) is not None


def _sha(x: object) -> bool:
    return type(x) is str and _SHA.fullmatch(x) is not None


def _url(x: object) -> bool:
    if type(x) is not str or not (1 <= len(x) <= 2048):
        return False
    try:
        p = urlsplit(x)
        return (p.scheme == 'https' and bool(p.hostname) and p.port in (None, 443)
                and p.username is None and p.password is None
                and not p.query and not p.fragment and p.path.startswith('/')
                and p.geturl() == x and not any(ord(c) < 32 for c in x)
                and p.hostname == p.hostname.lower())
    except (ValueError, TypeError):
        return False


def _pdf(e: dict) -> tuple[str, int]:
    raw = e['pdf_bytes']
    if type(raw) is not bytes or not (1024 <= len(raw) <= MAX_PDF):
        _stop('PDF_BYTES_INVALIDOS_OU_EXCESSIVOS')
    if raw[:5] != b'%PDF-':
        _stop('PDF_HEADER_INVALIDO')
    digest = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(digest, e['sha256_publicacao']):
        _stop('PDF_HASH_DIVERGENTE')
    return digest, len(raw)


def _evidence(e: object) -> bool:
    return (type(e) is dict and set(e) == _EVIDENCE_FIELDS
            and _id(e.get('indice_item'))
            and _ident(e.get('normative_artifact_id'))
            and _ident(e.get('artifact_reference_record_id'))
            and _url(e.get('url_publicacao'))
            and _sha(e.get('sha256_publicacao')))


def observar_pdf_publicacao_g18(*, pdf_bytes: bytes, url_publicacao: str,
                                 sha256_publicacao: str) -> dict:
    """Verify a provided PDF's actual bytes; never elevate to official trust.

    Useful for the >2 MiB IOEPA pilot even before ADR-020 storage linkage.
    Caller-controlled URL and expected digest do not authenticate origin.
    """
    entry = dict(indice_item=1, normative_artifact_id='observation',
                 artifact_reference_record_id='observation',
                 url_publicacao=url_publicacao,
                 sha256_publicacao=sha256_publicacao, pdf_bytes=pdf_bytes)
    if not _evidence(entry):
        _stop('OBSERVACAO_CONTRATO_INVALIDO')
    digest, size = _pdf(entry)
    return {'schema_version': SCHEMA, 'tipo': 'OBSERVACAO_PDF_ISOLADA',
            'url_publicacao_observada': url_publicacao,
            'sha256_publicacao_observado': digest, 'tamanho_bytes': size,
            'pdf_bytes_recalculados': True, 'vinculo_adr020': False,
            'assinatura_cms_verificada_neste_servico': False,
            'cadeia_icp_brasil_verificada_neste_servico': False,
            'revogacao_historica_comprovada': False,
            'tempo_assinatura_confiavel': False,
            **{key: False for key in _DENIED}}


def cotejar_evidencia_externa_publicacao_g18(*, db, authenticated_user_id: int,
        empresa_id: int, relatorio_id: int, xml_bytes: bytes,
        candidatos_normativos: list[dict] | None = None,
        referencias_adr020: list[dict] | None = None,
        referencias_temporais: list[dict] | None = None,
        referencias_cobertura: list[dict] | None = None,
        evidencias_externas: list[dict] | None = None,
        cas_root=None) -> dict:
    """Recompute real bytes then link to the exact G1.7 ADR-020 artefact.

    No trust upgrade is possible. In particular, this does not resolve the
    G1.5 storage-location restriction or establish official PDF authenticity.
    """
    if db is None or not all(_id(v) for v in
                              (authenticated_user_id, empresa_id, relatorio_id)):
        _stop('IDENTIDADE_INVALIDA')
    if type(xml_bytes) is not bytes or not (0 < len(xml_bytes) <= 2*1024*1024):
        _stop('XML_INVALIDO')
    entries = [] if evidencias_externas is None else evidencias_externas
    if type(entries) is not list or len(entries) > MAX_EVIDENCES:
        _stop('EVIDENCIAS_INVALIDAS')
    by_idx = {}
    digest_by_idx = {}
    for entry in entries:
        if not _evidence(entry) or entry['indice_item'] in by_idx:
            _stop('EVIDENCIA_INVALIDA_OU_DUPLICADA')
        digest_by_idx[entry['indice_item']] = _pdf(entry)
        by_idx[entry['indice_item']] = entry

    try:
        from app.services.enterprise_g17_publication_coverage_checkpoint import (
            cotejar_cobertura_publicacao_g17,
        )
        g17 = cotejar_cobertura_publicacao_g17(
            db=db, authenticated_user_id=authenticated_user_id,
            empresa_id=empresa_id, relatorio_id=relatorio_id,
            xml_bytes=xml_bytes, candidatos_normativos=candidatos_normativos,
            referencias_adr020=referencias_adr020,
            referencias_temporais=referencias_temporais,
            referencias_cobertura=referencias_cobertura,
            **({'cas_root':cas_root} if cas_root is not None else {}),
        )
    except Exception as exc:
        raise EnterpriseG18GateError('G18_G17_GATE_FALHOU') from exc
    items = g17.get('itens') if type(g17) is dict else None
    if (type(g17) is not dict or g17.get('schema_version') != _G17_SCHEMA
        or g17.get('empresa_id') != empresa_id
        or g17.get('relatorio_id') != relatorio_id
        or not _id(g17.get('documento_id'))
        or not _sha(g17.get('xml_sha256'))
        or not hmac.compare_digest(g17['xml_sha256'], hashlib.sha256(xml_bytes).hexdigest())
        or g17.get('posse_documental_interna_g16') is not True
        or any(g17.get(k) is not False for k in _DENIED)
        or type(items) is not list or not (0 < len(items) <= 500)
        or type(g17.get('itens_total')) is not int
        or g17['itens_total'] != len(items)):
        _stop('G17_CONTRATO_INCOMPATIVEL')
    if any(idx > len(items) for idx in by_idx):
        _stop('ITEM_FORA_DO_DOCUMENTO')

    covers = {}  # G17 requires exact records; recheck matching IDs here.
    for r in ([] if referencias_cobertura is None else referencias_cobertura):
        if type(r) is dict and _id(r.get('indice_item')):
            covers[r['indice_item']] = r

    result = []
    matched = 0
    for index, upstream in enumerate(items, 1):
        if (type(upstream) is not dict or upstream.get('indice_item') != index
            or type(upstream.get('indice_item')) is not int
            or upstream.get('fonte_primaria_autenticada') is not False
            or upstream.get('edicao_oficial_assinatura_validada') is not False
            or upstream.get('vigencia_juridica_comprovada') is not False):
            _stop('ITEM_G17_INCONSISTENTE')
        item = {'indice_item': index, 'estado': 'SEM_EVIDENCIA_EXTERNA_VINCULADA',
                'motivo': 'SEM_PDF_EXTERNO_EXPLICITO',
                'sha256_publicacao_observado': None, 'tamanho_bytes': 0,
                'pdf_bytes_recalculados': False, 'vinculo_hash_adr020': False,
                'custodia_externa_revalidada': False,
                'assinatura_cms_verificada_neste_servico': False,
                'cadeia_icp_brasil_verificada_neste_servico': False,
                'revogacao_historica_comprovada': False,
                'tempo_assinatura_confiavel': False,
                'fonte_primaria_autenticada': False,
                'edicao_oficial_assinatura_validada': False,
                'vigencia_juridica_comprovada': False}
        entry = by_idx.get(index)
        if entry is not None:
            digest, size = digest_by_idx[index]
            item['sha256_publicacao_observado'] = digest
            item['tamanho_bytes'] = size
            item['pdf_bytes_recalculados'] = True
            cover = covers.get(index)
            if upstream.get('janela_administrativa_cotejada') is not True:
                item['motivo'] = 'G17_JANELA_NAO_COTEJADA'
            elif (type(cover) is not dict or
                  cover.get('normative_artifact_id') != entry['normative_artifact_id'] or
                  cover.get('artifact_reference_record_id') != entry['artifact_reference_record_id']):
                item['motivo'] = 'REFERENCIA_G17_DIVERGENTE'
            else:
                from app.models import NormativeArtifact, ArtifactReference
                try:
                    art = db.get(NormativeArtifact, entry['normative_artifact_id'])
                    ref = db.get(ArtifactReference, entry['artifact_reference_record_id'])
                except Exception:
                    art, ref = None, None
                if art is None or ref is None:
                    item['motivo'] = 'REGISTO_ADR020_AUSENTE'
                elif (getattr(art, 'normative_artifact_id', None) != entry['normative_artifact_id']
                      or getattr(ref, 'artifact_reference_record_id', None) != entry['artifact_reference_record_id']
                      or getattr(ref, 'reference_event', None) != 'resolvida'
                      or getattr(art, 'artifact_reference_id', None) != getattr(ref, 'artifact_reference_id', None)
                      or getattr(ref, 'exact_locator', None) != entry['url_publicacao']
                      or getattr(art, 'artifact_hash', None) != digest
                      or type(getattr(art, 'byte_size', None)) is not int
                      or art.byte_size != size or not _sha(getattr(art, 'record_hash', None))
                      or not _sha(getattr(ref, 'record_hash', None))):
                    item['motivo'] = 'REGISTO_ADR020_OU_DIGEST_DIVERGENTE'
                else:
                    stored = getattr(art, 'immutable_bytes', None)
                    location = getattr(art, 'immutable_location', None)
                    if stored is not None and (type(stored) is not bytes or
                                               not hmac.compare_digest(stored, entry['pdf_bytes'])):
                        item['motivo'] = 'BYTES_ADR020_DIVERGENTES'
                    elif ((stored is None) == (location is None)):
                        item['motivo'] = 'ARMAZENAMENTO_ADR020_INVALIDO'
                    else:
                        item['vinculo_hash_adr020'] = True
                        item['custodia_externa_revalidada'] = False
                        item['estado'] = 'HASH_PDF_ADR020_COTEJADO_SEM_AUTORIDADE'
                        item['motivo'] = 'HASH_E_REFERENCIA_COTEJADOS_TRUST_EXTERNO_PENDENTE'
                        matched += 1
        result.append(item)
    return {'schema_version': SCHEMA,
            'estado': ('HASHES_ADR020_COTEJADOS_SEM_AUTORIDADE' if matched == len(items)
                       else 'COBERTURA_EXTERNA_PARCIAL_SEM_AUTORIDADE' if matched
                       else 'SEM_LIGACAO_EXTERNA_ADR020'),
            'empresa_id': empresa_id, 'relatorio_id': relatorio_id,
            'documento_id': g17['documento_id'],
            'xml_sha256': g17['xml_sha256'],
            'itens_total': len(items), 'itens_hash_externo_cotejado': matched,
            'itens': result, 'posse_documental_interna_g17': True,
            **{key: False for key in _DENIED}}


__all__ = ['SCHEMA', 'MAX_PDF', 'EnterpriseG18GateError',
           'observar_pdf_publicacao_g18', 'cotejar_evidencia_externa_publicacao_g18']
