"""I12 Enterprise: compare-and-swap transacional local para estados I11.

SQLite e checkpoint Ed25519 externo expresso: NAO prova autenticidade ITI,
proveniencia do checkpoint, antirollback contra restauro de ficheiro+checkpoint,
SEFAZ, ICP-Brasil, fiscalidade ou elegibilidade comercial.

Nao cria uma DB, nao abre paths, nao toca producao. Recebe conexao explicita;
so executa escritas quando um chamador chamar registrar_custodia_lcr_i12.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import re
import sqlite3
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.services.enterprise_nfe_i11_crl_provenance import conferir_proveniencia_lcr_i11

SCHEMA = 'ENTERPRISE_I12_LOCAL_CAS_LEDGER_V1'
CHECKPOINT_SCHEMA = 'ENTERPRISE_I12_EXTERNAL_SIGNED_CHECKPOINT_V1'
_CHECKPOINT_FIELDS = frozenset({
    'schema_version', 'ledger_id', 'sequence', 'state_sha256',
    'last_manifest_sha256', 'checkpoint_pub_sha256', 'issuer', 'scope',
})
_ALL_CHECKPOINT_FIELDS = _CHECKPOINT_FIELDS | {'signature_ed25519_b64'}
_ZERO = '0' * 64
_SHA = re.compile(r'[0-9a-f]{64}\Z')
_STATE = 'ENTERPRISE_I11_PRIOR_STATE_V1'
_TABLE = 'enterprise_i12_nfe_crl_ledger'


class EnterpriseI12LedgerError(ValueError):
    """Falha fechada sem publicar material de origem ou identificador fiscal."""


def _stop(reason: str):
    raise EnterpriseI12LedgerError('I12_' + reason)


def _sha(s: object) -> bool:
    return type(s) is str and _SHA.fullmatch(s) is not None


def _canonical(x: object) -> bytes:
    return json.dumps(x, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def _uuid(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _public_key(v: object) -> bool:
    return type(v) is bytes and len(v) == 32


def _validate_checkpoint(checkpoint: dict, *, ledger_id: str,
                         trusted_public_key: bytes) -> None:
    if type(checkpoint) is not dict or set(checkpoint) != _ALL_CHECKPOINT_FIELDS:
        _stop('CHECKPOINT_SCHEMA_INVALID')
    if (checkpoint['schema_version'] != CHECKPOINT_SCHEMA
        or checkpoint['ledger_id'] != ledger_id
        or checkpoint['issuer'] != 'CUSTODIANTE_CHECKPOINT_EXTERNO_CONTROLADO'
        or checkpoint['scope'] != 'SOLVERIS_ENTERPRISE_NFE_LCR_LEDGER'
        or type(checkpoint['sequence']) is not int
        or not 0 <= checkpoint['sequence'] < 2**63 - 1
        or not _sha(checkpoint['state_sha256'])
        or not _sha(checkpoint['last_manifest_sha256'])
        or not _sha(checkpoint['checkpoint_pub_sha256'])):
        _stop('CHECKPOINT_CLAIMS_INVALID')
    if not hmac.compare_digest(hashlib.sha256(trusted_public_key).hexdigest(),
                               checkpoint['checkpoint_pub_sha256']):
        _stop('CHECKPOINT_KEY_PIN_MISMATCH')
    if checkpoint['sequence'] == 0 and (checkpoint['state_sha256'] != _ZERO
                                       or checkpoint['last_manifest_sha256'] != _ZERO):
        _stop('CHECKPOINT_GENESIS_INVALID')
    signature = checkpoint['signature_ed25519_b64']
    if type(signature) is not str or len(signature) != 88:
        _stop('CHECKPOINT_SIGNATURE_FORMAT_INVALID')
    try:
        raw = base64.b64decode(signature, validate=True)
        if len(raw) != 64 or base64.b64encode(raw).decode('ascii') != signature:
            _stop('CHECKPOINT_SIGNATURE_FORMAT_INVALID')
        signed = _canonical({k: checkpoint[k] for k in sorted(_CHECKPOINT_FIELDS)})
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(raw, signed)
    except (InvalidSignature, ValueError, TypeError, binascii.Error):
        _stop('CHECKPOINT_SIGNATURE_INVALID')


def _conn(value: object) -> sqlite3.Connection:
    if type(value) is not sqlite3.Connection:
        _stop('SQLITE_CONNECTION_REQUIRED')
    if value.in_transaction:
        _stop('CONNECTION_ALREADY_IN_TRANSACTION')
    return value


def provisionar_schema_ledger_i12(*, sqlite_conn: sqlite3.Connection,
                                  autorizar_criacao_esquema: bool = False) -> None:
    """DDL explicito pelo host. Instalador nao invoca; testes usam :memory:."""
    conn = _conn(sqlite_conn)
    if autorizar_criacao_esquema is not True:
        _stop('SCHEMA_OPT_IN_REQUIRED')
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS enterprise_i12_nfe_crl_ledger (
            ledger_id TEXT NOT NULL PRIMARY KEY,
            sequence INTEGER NOT NULL CHECK(sequence >= 1),
            state_sha256 TEXT NOT NULL CHECK(length(state_sha256) = 64),
            last_manifest_sha256 TEXT NOT NULL CHECK(length(last_manifest_sha256) = 64),
            state_json TEXT NOT NULL
        )''')
        conn.commit()
    except sqlite3.Error:
        conn.rollback()
        _stop('SCHEMA_PROVISION_FAILED')


def _read_row(conn: sqlite3.Connection, ledger_id: str):
    try:
        return conn.execute(
            'SELECT sequence, state_sha256, last_manifest_sha256, state_json '
            'FROM enterprise_i12_nfe_crl_ledger WHERE ledger_id=?', (ledger_id,)
        ).fetchone()
    except sqlite3.Error:
        _stop('LEDGER_SCHEMA_OR_READ_FAILED')


def consultar_ponta_ledger_i12(*, sqlite_conn: sqlite3.Connection, ledger_id: str) -> dict:
    """Consulta local sem receber XML nem consultar rede."""
    conn = _conn(sqlite_conn)
    if not _uuid(ledger_id):
        _stop('LEDGER_ID_INVALID')
    row = _read_row(conn, ledger_id)
    if row is None:
        return {'schema_version': SCHEMA, 'ledger_id': ledger_id, 'sequence': 0,
                'state_sha256': _ZERO, 'last_manifest_sha256': _ZERO}
    seq, state_sha, last_sha, state_json = row
    if type(seq) is not int or seq < 1 or not _sha(state_sha) or not _sha(last_sha):
        _stop('LEDGER_ROW_INVALID')
    if not hmac.compare_digest(hashlib.sha256(state_json.encode('utf-8')).hexdigest(), state_sha):
        _stop('LEDGER_ROW_HASH_INVALID')
    return {'schema_version': SCHEMA, 'ledger_id': ledger_id, 'sequence': seq,
            'state_sha256': state_sha, 'last_manifest_sha256': last_sha}


def registrar_custodia_lcr_i12(*, sqlite_conn: sqlite3.Connection,
                                  ledger_id: str, parametros_i10: dict,
                                  manifesto_i11: dict,
                                  trusted_custodian_public_key: bytes,
                                  checkpoint_externo: dict,
                                  trusted_checkpoint_public_key: bytes,
                                  agora_utc: datetime) -> dict:
    """Reexecuta I11 e grava o estado proposto com BEGIN IMMEDIATE e CAS.

    Chave de checkpoint e custodiante devem vir de canais EXTERNOS distintos.
    O caller precisa obter novo checkpoint externo antes do proximo registo.
    O ledger local nao assina atestados nem gera chaves; backup/rollback do
    ficheiro SQLite mais checkpoint correspondente continua risco externo.
    """
    conn = _conn(sqlite_conn)
    if (not _uuid(ledger_id) or not _public_key(trusted_custodian_public_key)
        or not _public_key(trusted_checkpoint_public_key)
        or hmac.compare_digest(trusted_custodian_public_key, trusted_checkpoint_public_key)
        or type(agora_utc) is not datetime or agora_utc.tzinfo is None
        or agora_utc.utcoffset() != timedelta(0)):
        _stop('INPUT_OR_KEY_SEPARATION_INVALID')
    _validate_checkpoint(checkpoint_externo, ledger_id=ledger_id,
                         trusted_public_key=trusted_checkpoint_public_key)
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = _read_row(conn, ledger_id)
        if row is None:
            prev = None
            prior_seq, prior_digest, prior_manifest = 0, _ZERO, _ZERO
        else:
            seq, digest, manifest_digest, content = row
            if (type(seq) is not int or seq < 1 or not _sha(digest)
                or not _sha(manifest_digest)
                or type(content) is not str or
                not hmac.compare_digest(hashlib.sha256(content.encode('utf-8')).hexdigest(), digest)):
                _stop('LEDGER_ROW_HASH_INVALID')
            try:
                prev = json.loads(content)
            except (TypeError, ValueError):
                _stop('LEDGER_STATE_JSON_INVALID')
            if (type(prev) is not dict or prev.get('schema_version') != _STATE
                or prev.get('sequencia') != seq or prev.get('manifesto_sha256') != manifest_digest
                or _canonical(prev).decode('ascii') != content):
                _stop('LEDGER_PRIOR_STATE_INVALID')
            prior_seq, prior_digest, prior_manifest = seq, digest, manifest_digest
        if (checkpoint_externo['sequence'] != prior_seq
            or not hmac.compare_digest(checkpoint_externo['state_sha256'], prior_digest)
            or not hmac.compare_digest(checkpoint_externo['last_manifest_sha256'], prior_manifest)):
            _stop('CHECKPOINT_LEDGER_HEAD_MISMATCH')
        try:
            linked = conferir_proveniencia_lcr_i11(
                parametros_i10=parametros_i10,
                manifesto=manifesto_i11,
                trusted_public_key=trusted_custodian_public_key,
                estado_previo_aprovado=prev,
                agora_utc=agora_utc,
            )
        except (ValueError, TypeError, KeyError):
            _stop('I11_PROVENANCE_NOT_VERIFIED')
        state = linked.get('estado_proposto_para_custodia_externa')
        if (type(linked) is not dict or type(state) is not dict
            or linked.get('assinatura_custodiante_verificada') is not True
            or linked.get('antirollback_duravel_verificado') is not False
            or linked.get('checkout_autorizado') is not False
            or state.get('schema_version') != _STATE
            or state.get('sequencia') != prior_seq + 1
            or state.get('manifesto_sha256') != linked.get('manifesto_assinado_sha256')):
            _stop('I11_CONTRACT_INVALID')
        raw_state = _canonical(state).decode('ascii')
        next_digest = hashlib.sha256(raw_state.encode('ascii')).hexdigest()
        if row is None:
            conn.execute('INSERT INTO enterprise_i12_nfe_crl_ledger '
                         '(ledger_id,sequence,state_sha256,last_manifest_sha256,state_json) '
                         'VALUES(?,?,?,?,?)',
                         (ledger_id,prior_seq + 1,next_digest,linked['manifesto_assinado_sha256'],raw_state))
        else:
            cur = conn.execute('UPDATE enterprise_i12_nfe_crl_ledger '
                               'SET sequence=?,state_sha256=?,last_manifest_sha256=?,state_json=? '
                               'WHERE ledger_id=? AND sequence=? AND state_sha256=?',
                               (prior_seq+1,next_digest,linked['manifesto_assinado_sha256'],
                                raw_state,ledger_id,prior_seq,prior_digest))
            if cur.rowcount != 1:
                _stop('CAS_LOST_RACE')
        conn.commit()
        return {
            'schema_version':SCHEMA,
            'ledger_id':ledger_id,
            'sequencia_local_committed':prior_seq+1,
            'estado_local_sha256':next_digest,
            'manifesto_i11_sha256':linked['manifesto_assinado_sha256'],
            'checkpoint_externo_entrada_verificado':True,
            'comparacao_cas_sqlite_local_confirmada':True,
            'checkpoint_externo_de_saida_ainda_nao_assinado':True,
            'custodia_externa_duravel_verificada':False,
            'origem_iti_oficial_verificada':False,
            'cadeia_icp_brasil_verificada':False,
            'revogacao_oficial_global_verificada':False,
            'situacao_sefaz_confirmada':False,
            'efd_competencia_reconciliada':False,
            'apuracao_mensal_completa':False,
            'direito_creditorio_comprovado':False,
            'checkout_autorizado':False,
            'uso':'INTERNO_NAO_PUBLICAVEL',
        }
    except Exception as exc:
        if conn.in_transaction:
            conn.rollback()
        if isinstance(exc, EnterpriseI12LedgerError):
            raise
        if isinstance(exc, (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError)):
            _stop('TRANSACTION_FAILED')
        raise


__all__ = ['SCHEMA','CHECKPOINT_SCHEMA','EnterpriseI12LedgerError',
           'provisionar_schema_ledger_i12','consultar_ponta_ledger_i12',
           'registrar_custodia_lcr_i12']
