from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

from app.schemas.source_authority_schema import NormativeBindingStatus
from app.services.source_authority_guard import validar_bindings_normativos


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/fontes_tributarias_manifest.json"
BINDING = ROOT / "data/mei/mei_das_2026_normative_binding_v1.json"
LC123 = ROOT / "data/mei/lc_123_consolidada_snapshot_2026-08-27.html"
LEI8212 = ROOT / "data/mei/lei_8212_consolidada_snapshot_2026-08-27.html"

LC123_SHA256 = "662D98EB6AE4F825809EABBAAA3B2BC6F98B524CF2278A97F79FC69AA7F60BE0"
LEI8212_SHA256 = "12DEDBB415B179A94ABDA2E9E743C04A44A9718499EB0597769E6E67F3C528DE"


def _sources():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {source["id"]: source for source in manifest["fontes"]}


def _payload():
    return json.loads(BINDING.read_text(encoding="utf-8"))


def _visible_text(raw: bytes) -> str:
    for encoding in ("utf-8", "windows-1252", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text).replace("\xa0", " ")).strip()


def test_mei_2026_normative_snapshots_match_exact_hashes_and_evidence():
    lc_raw = LC123.read_bytes()
    lei_raw = LEI8212.read_bytes()
    assert len(lc_raw) == 1622252
    assert len(lei_raw) == 320998
    assert hashlib.sha256(lc_raw).hexdigest().upper() == LC123_SHA256
    assert hashlib.sha256(lei_raw).hexdigest().upper() == LEI8212_SHA256
    assert "81.000,00" in _visible_text(lc_raw)
    assert "R$ 1,00" in _visible_text(lc_raw)
    assert "R$ 5,00" in _visible_text(lc_raw)
    lei_text = _visible_text(lei_raw)
    assert "5% (cinco por cento)" in lei_text
    assert "microempreendedor individual" in lei_text.lower()


def test_mei_2026_sources_have_disjoint_minimal_authority():
    sources = _sources()
    lc = sources["LC123-001"]
    lei = sources["LEI8212-MEI-001"]
    assert lc["alvos_normativos_autorizados"] == [
        {"tipo": "dataset", "id": "MEI_LIMITE_ANUAL_FATURAMENTO"},
        {"tipo": "dataset", "id": "PARCELA_FIXA_POR_ATIVIDADE"},
    ]
    assert lei["alvos_normativos_autorizados"] == [
        {"tipo": "dataset", "id": "MEI_DAS_FATOR_SALARIO_MINIMO"}
    ]
    assert lc["vigencia_fim"] == "2026-12-31"
    assert lei["vigencia_fim"] == "2026-12-31"


def test_mei_2026_binding_is_authorized_for_estimate():
    result = validar_bindings_normativos(_payload())
    assert result.status == NormativeBindingStatus.valido_com_autoridade_decisoria
    assert result.autorizado_fundamentar_decisao is True
    assert result.bindings_validados == 3
    assert result.reasons == ()


def test_mei_2026_binding_fails_closed_with_incompatible_source_risk():
    payload = _payload()
    payload["bindings"][0]["risco"] = "alto"
    result = validar_bindings_normativos(payload)
    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert len(result.reasons) == 1
    reason = result.reasons[0]
    assert reason.code.value == "RISCO_FONTE_INCOMPATIVEL"
    assert reason.binding_index == 0
    assert reason.field == "risco"


def test_mei_2026_binding_fails_closed_in_2027_transition():
    payload = _payload()
    payload["contexto"]["data_referencia"] = "2027-01-01"
    result = validar_bindings_normativos(payload)
    assert result.autorizado_fundamentar_decisao is False
    assert {reason.code.value for reason in result.reasons} == {"FORA_DA_VIGENCIA"}


def test_mei_2026_binding_excludes_policy_operational_and_alias_targets():
    serialized = json.dumps(_payload(), ensure_ascii=False)
    assert "MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE" not in serialized
    assert "ATIVIDADE_MEI_NORMALIZADA_POR_ALIAS" not in serialized
    assert "PGMEI-001" not in serialized


def test_mei_2026_binding_is_discovered_as_canonical_batch():
    from app.scripts.mei_normative_census import _load_local_normative_evidence

    evidence = _load_local_normative_evidence()
    expected = {
        "MEI_LIMITE_ANUAL_FATURAMENTO": "LC123-001",
        "MEI_DAS_FATOR_SALARIO_MINIMO": "LEI8212-MEI-001",
        "PARCELA_FIXA_POR_ATIVIDADE": "LC123-001",
    }
    for dataset_id, source_id in expected.items():
        matches = [
            item for item in evidence.bindings
            if item.get("dataset_id") == dataset_id
        ]
        assert len(matches) == 1
        assert matches[0]["fonte_id"] == source_id
    assert evidence.findings == ()
