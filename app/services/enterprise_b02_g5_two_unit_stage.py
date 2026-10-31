"""R5 G5 real two-unit staging, a bounded source-side transaction helper.

CANDIDATE ONLY. This never provides signatures, creates authority/identity,
changes schema, reserves one-shot approval, commits, or suppresses failed gates.
Caller owns transaction and MUST ROLLBACK on any exception.

Only use after independent review, currently approved G4/G5 authority and
a trusted stage_authenticity callback per document. 0062 installed triggers
are named z_b02_complete_unit on five tables, DEFERRABLE INITIALLY DEFERRED.
stage_completion forces ALL IMMEDIATE per complete unit, so the next unit
MUST explicitly re-defer only those five triggers before its first insert.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from sqlalchemy import text

from app.services.enterprise_b02_noncredential_acquisition import stage_completion

C3_DOCUMENTS = {
    "101201900571":(
        "af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d",
        1944929,
    ),
    "101202501245":(
        "e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832",
        258302,
    ),
}
_NAMED_DEFER = text("SET CONSTRAINTS public.z_b02_complete_unit DEFERRED")
_REQUIRED = frozenset({
    "document_id","binding","start","read_cas","build_evidence","stage_authenticity"
})

def _stop(code):
    raise ValueError(code)

def _validate_units(units):
    if type(units) not in (list,tuple) or len(units)!=2:
        _stop("EXACT_TWO_C3_DOCUMENTS_REQUIRED")
    ids = []
    executions = []
    for unit in units:
        if not isinstance(unit, Mapping) or set(unit)!=_REQUIRED:
            _stop("EXACT_REAL_UNIT_FIELDS_REQUIRED")
        document_id=unit["document_id"]
        ids.append(document_id)
        binding=unit["binding"]
        if not isinstance(binding,Mapping) or binding.get("mode")!="LOCAL_CAS_INCORPORATION":
            _stop("REAL_C3_UNIT_REQUIRED")
        provenance=binding.get("provenance")
        if (not isinstance(provenance,Mapping) or
                provenance.get("synthetic_only") is not False):
            _stop("REAL_C3_UNIT_REQUIRED")
        execution_id=binding.get("acquisition_execution_id")
        if not isinstance(execution_id,str) or not execution_id:
            _stop("EXACT_REAL_EXECUTION_ID_REQUIRED")
        executions.append(execution_id)
        for callback in ("read_cas","build_evidence","stage_authenticity"):
            if not callable(unit[callback]):
                _stop("EXACT_REAL_CALLBACK_REQUIRED")
        if not isinstance(unit["start"],Mapping):
            _stop("EXACT_REAL_START_REQUIRED")
    if set(ids)!=set(C3_DOCUMENTS):
        _stop("EXACT_TWO_C3_DOCUMENTS_REQUIRED")
    if len(set(executions))!=2:
        _stop("TWO_DISTINCT_REAL_EXECUTIONS_REQUIRED")

def stage_two_real_c3_units(connection, *, units):
    """Stage only two authentic C3 units, no COMMIT or one-shot reservation.

    The approved authenticity callback must insert the exact G4 verified row
    inside the same caller-owned transaction, after each artifact insert and
    before stage_completion's immediate trigger check. No callback can grant
    authority by itself. Exceptions propagate; the caller MUST roll back.
    """
    _validate_units(units)  # fail before any SQL, without synthesizing a G4
    if not connection.in_transaction():
        _stop("OUTER_TRANSACTION_REQUIRED")
    results=[]
    for unit in units:
        document_id=unit["document_id"]
        expected_hash,expected_size=C3_DOCUMENTS[document_id]
        reader=unit["read_cas"]

        def pinned_read(reader=reader, expected_hash=expected_hash,
                        expected_size=expected_size):
            raw=reader()
            if (type(raw) is not bytes or len(raw)!=expected_size or
                    hashlib.sha256(raw).hexdigest()!=expected_hash):
                _stop("EXACT_C3_BYTES_REQUIRED")
            return raw

        # This changes the timing only of the ORIGINAL five 0062 constraint
        # triggers, not all FKs, approvals, or a future one-shot reservation.
        # It is required even for unit 1 if the caller's session inherited
        # a prior immediate mode in this same transaction.
        connection.execute(_NAMED_DEFER)
        result=stage_completion(
            connection,
            binding=unit["binding"],start=unit["start"],read_cas=pinned_read,
            build_evidence=unit["build_evidence"],
            stage_authenticity=unit["stage_authenticity"]
        )
        if not isinstance(result,Mapping) or result.get("artifact_hash")!=expected_hash:
            _stop("STAGED_C3_HASH_DIVERGENCE")
        results.append(dict(result))
    # NOT permitted: reserve one-shot here. Caller must bind signed decision
    # and approved native capability only after both units are complete.
    return results
