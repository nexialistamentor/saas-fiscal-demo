"""02-R4G immutable RED: minimal relational and modality boundary contracts.

No database connections, data writes, network acquisition or policy activation.
These tests are not the later PostgreSQL T01-T28 acceptance suite.
"""
from __future__ import annotations
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / 'app/services/enterprise_b02_noncredential_acquisition.py'


def service():
    assert SERVICE.is_file(), 'B02_R4G_RED_SERVICE_ABSENT'
    spec = importlib.util.spec_from_file_location('b02_r4g_frozen_contract_target', SERVICE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def model(name):
    # The runner forces ALEMBIC_RUNNING=1 and an in-memory URL before collection.
    # Metadata inspection only: no create_all, engine.connect or session.
    from app import models
    assert hasattr(models, name), 'B02_R4G_RED_MODEL_ABSENT:' + name
    return getattr(models, name)


@pytest.mark.parametrize('name,table,parents', [
    ('AcquisitionModeBinding', 'acquisition_mode_bindings', {'acquisition_executions'}),
    ('NonCredentialAcquisitionReceipt', 'noncredential_acquisition_receipts',
     {'acquisition_mode_bindings', 'acquisition_executions'}),
    ('NonCredentialSanitizationVerification', 'noncredential_sanitization_verifications',
     {'noncredential_acquisition_receipts'}),
])
def test_new_modes_require_exact_physical_predecessors(name, table, parents):
    entity = model(name)
    assert entity.__tablename__ == table
    columns = entity.__table__.columns
    assert 'record_hash' in columns and not columns['record_hash'].nullable
    assert any(c.primary_key for c in columns)
    for parent in parents:
        constraints = [fk for fk in entity.__table__.foreign_key_constraints
                       if fk.referred_table.name == parent]
        assert constraints, 'missing FK to ' + parent
        assert any(len(fk.elements) >= 2 and
                   any('hash' in e.parent.name for e in fk.elements)
                   for fk in constraints), 'predecessor must bind identity and hash: ' + parent


def test_credentialled_mode_cannot_use_noncredential_receipt():
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(
            'EXTERNAL_CREDENTIALLED', credential_chain_present=True,
            transport={'dispatched': True, 'response_observed': True,
                       'credential_presentation_observed': True,
                       'components_complete': True},
            cas={}, receipt_kind='noncredential')
    assert exc.value.code == 'CREDENTIALLED_REQUIRES_ORIGINAL_CHAIN'


def test_cas_receipt_cannot_claim_external_dispatch():
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(
            'LOCAL_CAS_INCORPORATION', credential_chain_present=False,
            transport={'dispatched': True, 'response_observed': True},
            cas={'read_observed': True, 'components_complete': True},
            receipt_kind='noncredential')
    assert exc.value.code == 'CAS_EXTERNAL_TRANSPORT_FORBIDDEN'


@pytest.mark.parametrize('credential_source', [
    'authorization', 'proxy_authorization', 'cookie', 'query_token',
    'body_token', 'api_key', 'client_certificate', 'credentialled_redirect',
])
def test_public_mode_rejects_every_observed_credential_presentation(credential_source):
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(
            'EXTERNAL_PUBLIC_NO_CREDENTIALS', credential_chain_present=False,
            transport={'dispatched': True, 'response_observed': True,
                       'components_complete': True,
                       'credential_presentation_observed': True,
                       'credential_categories': [credential_source]},
            cas={}, receipt_kind='noncredential')
    assert exc.value.code == 'PUBLIC_CREDENTIAL_PRESENTATION_FORBIDDEN'


@pytest.mark.parametrize('mode', ['EXTERNAL_PUBLIC_NO_CREDENTIALS', 'LOCAL_CAS_INCORPORATION'])
def test_noncredential_mode_rejects_existing_credential_chain(mode):
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(mode, credential_chain_present=True,
                                 transport={}, cas={}, receipt_kind='noncredential')
    assert exc.value.code == 'NONCREDENTIAL_CHAIN_CONTRADICTION'


def test_public_absence_of_database_rows_does_not_prove_observation():
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(
            'EXTERNAL_PUBLIC_NO_CREDENTIALS', credential_chain_present=False,
            transport={'dispatched': True, 'response_observed': True,
                       'credential_presentation_observed': False,
                       'components_complete': False},
            cas={}, receipt_kind='noncredential')
    assert exc.value.code == 'MODE_EVIDENCE_INCONCLUSIVE'


@pytest.mark.parametrize('mode', [None, '', 'public', 'latest', 'UNKNOWN'])
def test_missing_or_inferred_mode_is_not_an_authority(mode):
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(mode, credential_chain_present=False,
                                 transport={}, cas={}, receipt_kind='noncredential')
    assert exc.value.code == 'MODE_NOT_EXPLICIT'


def test_cas_requires_observed_read():
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.validate_mode_evidence(
            'LOCAL_CAS_INCORPORATION', credential_chain_present=False,
            transport={}, cas={'read_observed': False, 'components_complete': True},
            receipt_kind='noncredential')
    assert exc.value.code == 'MODE_EVIDENCE_INCONCLUSIVE'


def test_canonical_record_hash_is_reproducible_without_self_reference():
    m = service()
    a = {'schema': 'B02_TEST_CANONICAL_V1', 'id': 'synthetic', 'value': 3}
    b = {'value': 3, 'id': 'synthetic', 'schema': 'B02_TEST_CANONICAL_V1'}
    expected = hashlib.sha256(
        b'{"id":"synthetic","schema":"B02_TEST_CANONICAL_V1","value":3}'
    ).hexdigest()
    assert m.record_hash(a) == m.record_hash(b) == expected
    assert m.record_hash({**a, 'record_hash': '0' * 64}) == expected
    assert m.record_hash({**a, 'value': 4}) != expected


@pytest.mark.parametrize('payload', [{'value': float('nan')}, {'value': float('inf')}])
def test_nonfinite_values_cannot_enter_canonical_evidence(payload):
    m = service()
    with pytest.raises(m.AcquisitionEvidenceError) as exc:
        m.record_hash(payload)
    assert exc.value.code == 'CANONICALIZATION_INVALID'


def test_public_mode_admissibility_is_only_a_boundary_check():
    m = service()
    result = m.validate_mode_evidence(
        'EXTERNAL_PUBLIC_NO_CREDENTIALS', credential_chain_present=False,
        transport={'dispatched': True, 'response_observed': True,
                   'credential_presentation_observed': False,
                   'components_complete': True},
        cas={}, receipt_kind='noncredential')
    assert result is None, 'Boundary check must not return authority or acquired content'


def test_cas_mode_admissibility_is_only_a_boundary_check():
    m = service()
    result = m.validate_mode_evidence(
        'LOCAL_CAS_INCORPORATION', credential_chain_present=False,
        transport={}, cas={'read_observed': True, 'components_complete': True},
        receipt_kind='noncredential')
    assert result is None, 'Boundary check must not return authority or acquired content'


def test_original_receipt_still_requires_credential_use():
    from app import models
    columns = models.SanitizedAcquisitionReceipt.__table__.columns
    for name in ('credential_use_record_id', 'credential_use_record_hash',
                 'credential_binding_id', 'credential_binding_version', 'credential_binding_hash'):
        assert not columns[name].nullable
    assert any(fk.referred_table.name == 'credential_use_records'
               for fk in models.SanitizedAcquisitionReceipt.__table__.foreign_key_constraints)
