"""SOLVERIS Enterprise G1.9: bounded, local content-addressed custody.

G1.9 is deliberately a NEW, opt-in location scheme. ADR-020's historical
``immutable_location`` field has no implied preexisting CAS resolver. No DB
write, network, user-id authority or implicit filesystem I/O at import.

The explicit file writer is O_EXCL; the verifier recomputes actual bytes on
every read. A local file is not a proof of hardware-backed immutability,
third-party preservation, ICP-Brasil authenticity or publication coverage.

G1.5 *still rejects* location-backed NormativeArtifact; this independent
bridge does not bypass G1.5/G1.7/G1.8, tax or commercial gates.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
import re
import stat

SCHEMA = 'SOLVERIS_ENTERPRISE_G19_LOCAL_CAS_V1'
PREFIX = 'cas+sha256://sha256/'
MAX_PDF = 16 * 1024 * 1024
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_IDENT = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,63}\Z')
_DENIED = (
    'fonte_primaria_autenticada', 'versao_oficial_verificada',
    'atualizacao_e_revogacao_exaustivas', 'vigencia_juridica_comprovada',
    'autoridade_fiscal', 'credito_confirmado', 'checkout_autorizado',
    'usavel_comercialmente',
)


class EnterpriseG19GateError(ValueError):
    """Stop without promoting a claim of custody or source authority."""


def _stop(reason: str):
    raise EnterpriseG19GateError('G19_' + reason)


def _sha(x):
    return type(x) is str and _SHA.fullmatch(x) is not None


def _id(x):
    return type(x) is str and _IDENT.fullmatch(x) is not None


def _root(root, *, create=False):
    # Explicit fixed absolute caller-provided directory, never URL or repo path.
    if not isinstance(root, (str, Path)):
        _stop('CAS_ROOT_INVALIDA')
    p = Path(root)
    if not p.is_absolute() or '..' in p.parts:
        _stop('CAS_ROOT_NAO_ABSOLUTA')
    if create:
        _reject_reparse(p)
        p.mkdir(parents=True, exist_ok=True)
    if not p.is_dir():
        _stop('CAS_ROOT_INEXISTENTE')
    _reject_reparse(p)
    return p


def _reject_reparse(p: Path):
    # Includes Windows junctions; Windows reparse points require special care.
    for parent in (*reversed(p.parents), p):
        try:
            if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
                _stop('CAS_REPARSE_POINT_PROIBIDO')
            s = parent.lstat()
            if getattr(s, 'st_file_attributes', 0) & 0x400:
                _stop('CAS_REPARSE_POINT_PROIBIDO')
        except FileNotFoundError:
            continue


def _location(digest):
    if not _sha(digest):
        _stop('SHA256_INVALIDO')
    return PREFIX + digest


def _parse_location(location):
    if type(location) is not str or not location.startswith(PREFIX):
        _stop('LOCALIZACAO_CAS_NAO_CANONICA')
    digest = location[len(PREFIX):]
    if not _sha(digest) or location != _location(digest):
        _stop('LOCALIZACAO_CAS_NAO_CANONICA')
    return digest


def _path(root: Path, digest):
    return root / 'sha256' / digest[:2] / (digest + '.pdf')


def _check_bytes(raw, expected_digest, expected_size=None):
    if type(raw) is not bytes or not 1024 <= len(raw) <= MAX_PDF:
        _stop('PDF_TAMANHO_INVALIDO')
    if raw[:5] != b'%PDF-':
        _stop('PDF_CABECALHO_INVALIDO')
    if expected_size is not None and (type(expected_size) is not int or len(raw) != expected_size):
        _stop('PDF_TAMANHO_DIVERGENTE')
    if not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), expected_digest):
        _stop('PDF_SHA256_DIVERGENTE')


def _read(*, root, location, expected_sha256, expected_size):
    """Reopen twice and hash real bytes; compare identities via descriptor stats.

    Windows can report different metadata from ``os.fstat(fd)`` and
    ``Path.stat()`` after create/flush, yielding false-positive object swaps.
    Compare only descriptor-to-descriptor identity while both handles are
    open, and validate content independently through both handles.
    This is *not* external immutability or protection against privileged races.
    """
    digest = _parse_location(location)
    if not _sha(expected_sha256) or not hmac.compare_digest(digest, expected_sha256):
        _stop('CAS_HASH_LOCALIZACAO_DIVERGENTE')
    if type(expected_size) is not int or not 1024 <= expected_size <= MAX_PDF:
        _stop('CAS_TAMANHO_ESPERADO_INVALIDO')
    base = _root(root)
    target = _path(base, digest)
    _reject_reparse(target)
    if not target.is_file():
        _stop('CAS_OBJETO_AUSENTE')
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    attrs = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')

    def read_handle(fd):
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_size != expected_size
                or before.st_nlink > 1):
            _stop('CAS_OBJETO_TIPO_TAMANHO_OU_LINK_INVALIDO')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_PDF + 1)
        after = os.fstat(fd)
        if any(getattr(before, a) != getattr(after, a) for a in attrs):
            _stop('CAS_OBJETO_MODIFICADO_DURANTE_LEITURA')
        _check_bytes(raw, digest, expected_size)
        return raw, before

    try:
        first_fd = os.open(target, flags)
    except OSError as exc:
        raise EnterpriseG19GateError('G19_CAS_OPEN_FALHOU') from exc
    try:
        first_raw, first_stat = read_handle(first_fd)
        _reject_reparse(target)
        try:
            second_fd = os.open(target, flags)
        except OSError as exc:
            raise EnterpriseG19GateError('G19_CAS_REOPEN_FALHOU') from exc
        try:
            second_raw, second_stat = read_handle(second_fd)
            if ((first_stat.st_dev, first_stat.st_ino)
                    != (second_stat.st_dev, second_stat.st_ino)):
                _stop('CAS_OBJETO_TROCADO_DEPOIS_DA_LEITURA')
            if not hmac.compare_digest(first_raw, second_raw):
                _stop('CAS_BYTES_TROCADOS_ENTRE_LEITURAS')
            _reject_reparse(target)
            return second_raw
        finally:
            os.close(second_fd)
    finally:
        os.close(first_fd)


def guardar_pdf_cas_g19(*, root, pdf_bytes, sha256_esperado):
    """Explicit write-once local pilot only; never overwrites an existing file."""
    if not _sha(sha256_esperado):
        _stop('SHA256_INVALIDO')
    _check_bytes(pdf_bytes, sha256_esperado)
    base = _root(root, create=True)
    target = _path(base, sha256_esperado)
    _reject_reparse(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse(target)
    if target.exists():
        _stop('CAS_OBJETO_JA_EXISTE_SEM_SOBRESCRITA')
    flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
             getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0))
    try:
        fd = os.open(target, flags, 0o600)
    except FileExistsError as exc:
        raise EnterpriseG19GateError('G19_CAS_OBJETO_JA_EXISTE') from exc
    except OSError as exc:
        raise EnterpriseG19GateError('G19_CAS_CREATE_FALHOU') from exc
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(pdf_bytes)
            stream.flush()
            os.fsync(fd)
        # chmod is not an immutability guarantee; Windows may lack fchmod.
        if hasattr(os, 'fchmod'):
            os.fchmod(fd, 0o400)
    finally:
        os.close(fd)
    # Reopen + recalculate. File permission bits are NOT immutable custody.
    location = _location(sha256_esperado)
    _read(root=base, location=location, expected_sha256=sha256_esperado,
          expected_size=len(pdf_bytes))
    return _meta(location=location, digest=sha256_esperado, size=len(pdf_bytes),
                 status='CAS_CREATED_EXCLUSIVE_BYTES_REVERIFIED')


def _meta(*, location, digest, size, status):
    return {'schema_version': SCHEMA, 'estado': status,
            'immutable_location_proposta': location,
            'sha256_recalculado': digest, 'tamanho_bytes': size,
            'bytes_revalidados': True, 'vinculo_adr020': False,
            'custodia_externa_imutavel_comprovada': False,
            'cadeia_g15_location_integrada': False,
            'assinatura_pdf_validada_neste_servico': False,
            'tempo_assinatura_confiavel': False,
            'revogacao_historica_comprovada': False,
            **{key: False for key in _DENIED}}


def verificar_pdf_cas_g19(*, root, immutable_location, sha256_esperado, tamanho_esperado):
    """Read and rehash actual bytes; no legal/external authority claim."""
    raw = _read(root=root, location=immutable_location,
                expected_sha256=sha256_esperado, expected_size=tamanho_esperado)
    return _meta(location=immutable_location, digest=hashlib.sha256(raw).hexdigest(),
                 size=len(raw), status='CAS_BYTES_REVERIFIED_NO_EXTERNAL_TRUST')


def cotejar_localizacao_adr020_g19(*, db, root, normative_artifact_id,
        artifact_reference_record_id, acquisition_execution_record_id,
        url_publicacao, sha256_esperado, tamanho_esperado):
    """Compare stored *real* ADR-020 row identity with CAS bytes, read-only.

    This is intentionally NOT callable as a replacement for G1.5; its output
    never authorizes downstream normative, fiscal or commercial decisions.
    """
    from app.models import NormativeArtifact, ArtifactReference, AcquisitionExecution
    if db is None or not all(_id(v) for v in (normative_artifact_id,
            artifact_reference_record_id, acquisition_execution_record_id)):
        _stop('ADR020_IDENTIDADE_INVALIDA')
    if (type(url_publicacao) is not str or not url_publicacao.startswith('https://')
        or len(url_publicacao) > 2048):
        _stop('ADR020_URL_INVALIDA')
    try:
        art = db.get(NormativeArtifact, normative_artifact_id)
        ref = db.get(ArtifactReference, artifact_reference_record_id)
        exe = db.get(AcquisitionExecution, acquisition_execution_record_id)
    except Exception as exc:
        raise EnterpriseG19GateError('G19_ADR020_READ_FALHOU') from exc
    if any(obj is None for obj in (art, ref, exe)):
        _stop('ADR020_REGISTO_AUSENTE')
    location = getattr(art, 'immutable_location', None)
    if (getattr(art, 'normative_artifact_id', None) != normative_artifact_id
        or getattr(ref, 'artifact_reference_record_id', None) != artifact_reference_record_id
        or getattr(exe, 'acquisition_execution_record_id', None) != acquisition_execution_record_id
        or getattr(ref, 'reference_event', None) != 'resolvida'
        or getattr(ref, 'exact_locator', None) != url_publicacao
        or getattr(art, 'artifact_reference_id', None) != getattr(ref, 'artifact_reference_id', None)
        or getattr(exe, 'artifact_reference_id', None) != getattr(ref, 'artifact_reference_id', None)
        or getattr(exe, 'artifact_reference_record_id', None) != artifact_reference_record_id
        or getattr(exe, 'execution_event', None) != 'conclusao'
        or getattr(exe, 'projected_state', None) != 'concluida'
        or getattr(art, 'acquisition_execution_record_id', None) != acquisition_execution_record_id
        or getattr(art, 'acquisition_execution_id', None) != getattr(exe, 'acquisition_execution_id', None)
        or getattr(art, 'acquisition_attempt_number', None) != getattr(exe, 'attempt_number', None)
        or getattr(art, 'acquisition_event', None) != 'conclusao'
        or getattr(art, 'acquisition_state', None) != 'concluida'
        or getattr(art, 'immutable_bytes', None) is not None
        or getattr(art, 'artifact_hash', None) != sha256_esperado
        or getattr(art, 'byte_size', None) != tamanho_esperado
        or not all(_sha(getattr(obj, 'record_hash', None)) for obj in (art, ref, exe))):
        _stop('ADR020_ORIGEM_STORAGE_OU_HASH_DIVERGENTE')
    result = verificar_pdf_cas_g19(root=root, immutable_location=location,
                                  sha256_esperado=sha256_esperado,
                                  tamanho_esperado=tamanho_esperado)
    result['estado'] = 'CAS_ADR020_BYTES_COTEJADOS_G15_AINDA_BLOQUEADO'
    result['vinculo_adr020'] = True
    return result


__all__ = ['SCHEMA', 'PREFIX', 'MAX_PDF', 'EnterpriseG19GateError',
           'guardar_pdf_cas_g19', 'verificar_pdf_cas_g19',
           'cotejar_localizacao_adr020_g19']
