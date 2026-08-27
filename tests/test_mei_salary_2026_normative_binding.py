from __future__ import annotations

import json
from pathlib import Path

from app.schemas.source_authority_schema import NormativeBindingStatus
from app.services.source_authority_guard import validar_bindings_normativos
from tests.canonical_source_hash import canonical_opaque_bytes_sha256


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/mei/decreto_12797_2025_snapshot_2026-08-27.html"
MANIFEST = ROOT / "data/fontes_tributarias_manifest.json"
BINDING = ROOT / "data/mei/salario_minimo_2026_binding_v1.json"
EXPECTED_SHA256 = "9C3FC6738634B9E1FCDDA94307CFD90FE028FFEDF34FF7391A99A0359AE6A52C"


def _source():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    matches = [item for item in manifest["fontes"] if item["id"] == "SALARIO-MINIMO-001"]
    assert len(matches) == 1
    return matches[0]


def _payload():
    return json.loads(BINDING.read_text(encoding="utf-8"))


def test_salary_2026_snapshot_matches_manifest_hash_and_exact_bytes():
    raw = SNAPSHOT.read_bytes()
    assert len(raw) == 10327
    assert canonical_opaque_bytes_sha256(SNAPSHOT) == EXPECTED_SHA256
    assert _source()["hash_referencia"] == EXPECTED_SHA256
    assert b"12.797" in raw
    assert b"1.621,00" in raw


def test_salary_2026_source_has_narrow_temporal_dataset_authority():
    source = _source()
    assert source["pode_fundamentar_decisao"] is True
    assert source["status"] == "activa"
    assert source["vigencia_inicio"] == "2026-01-01"
    assert source["alvos_normativos_autorizados"] == [
        {"tipo": "dataset", "id": "SALARIO_MINIMO_POR_ANO"}
    ]
    assert "nao autoriza valores de outros anos" in source["observacoes"]


def test_salary_2026_real_binding_is_authorized_for_estimate_in_2026():
    result = validar_bindings_normativos(_payload())
    assert result.status == NormativeBindingStatus.valido_com_autoridade_decisoria
    assert result.autorizado_fundamentar_decisao is True
    assert result.bindings_validados == 1
    assert result.reasons == ()


def test_salary_2026_binding_fails_closed_outside_its_year():
    payload = _payload()
    payload["contexto"]["data_referencia"] = "2025-12-31"
    result = validar_bindings_normativos(payload)
    assert result.autorizado_fundamentar_decisao is False
    assert [reason.code.value for reason in result.reasons] == ["FORA_DA_VIGENCIA"]


def test_salary_2026_binding_is_discovered_as_canonical_batch():
    from app.scripts.mei_normative_census import _load_local_normative_evidence

    evidence = _load_local_normative_evidence()
    matches = [
        item for item in evidence.bindings
        if item.get("dataset_id") == "SALARIO_MINIMO_POR_ANO"
    ]
    assert len(matches) == 1
    assert matches[0]["fonte_id"] == "SALARIO-MINIMO-001"
    assert evidence.findings == ()
