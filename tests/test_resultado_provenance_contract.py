from inspect import signature
from types import SimpleNamespace

import pytest


NON_MEI_PRODUCER = "app.services.analysis_orchestrator.executar_analise_xml"


def _service():
    from app.services import resultado_provenance_service as service
    return service


def test_none_authority_roundtrip_strips_internal_provenance():
    service = _service()
    sealed = service.selar_resultado_nao_mei(
        {"dados_fiscais": {"ok": True}},
        producer_id=NON_MEI_PRODUCER,
    )
    fingerprint = service.fingerprint_resultado_json(sealed)
    rel = SimpleNamespace(resultado_json=sealed, fingerprint=fingerprint)

    assert service.verificar_resultado_persistido(rel) == {
        "dados_fiscais": {"ok": True}
    }


def test_legacy_result_without_provenance_fails_closed():
    service = _service()
    raw = {"tipo": "MEI", "imposto": 81.05}
    fingerprint = service.fingerprint_resultado_json(raw)
    rel = SimpleNamespace(resultado_json=raw, fingerprint=fingerprint)

    with pytest.raises(service.ResultadoProvenanceError):
        service.verificar_resultado_persistido(rel)


def test_fingerprint_mismatch_fails_closed():
    service = _service()
    sealed = service.selar_resultado_nao_mei(
        {"tipo": "CPF", "imposto": 10.0},
        producer_id="app.services.imposto_service.calcular_imposto_simples",
    )
    rel = SimpleNamespace(
        resultado_json=sealed,
        fingerprint="0" * 64,
    )

    with pytest.raises(service.ResultadoProvenanceError):
        service.verificar_resultado_persistido(rel)


def test_v1_sealer_has_no_authority_parameter():
    service = _service()
    params = signature(service.selar_resultado_nao_mei).parameters

    assert list(params) == ["resultado", "producer_id"]
    assert params["producer_id"].kind.name == "KEYWORD_ONLY"


def test_reserved_provenance_key_cannot_be_supplied_by_caller():
    service = _service()

    with pytest.raises(service.ResultadoProvenanceError):
        service.selar_resultado_nao_mei(
            {
                service.PROVENANCE_KEY: {
                    "schema_version": "forged",
                }
            },
            producer_id=NON_MEI_PRODUCER,
        )


def test_empty_producer_id_fails_closed():
    service = _service()

    with pytest.raises(service.ResultadoProvenanceError):
        service.selar_resultado_nao_mei(
            {"x": 1},
            producer_id="",
        )


def test_forged_canonical_authority_fails_closed_even_with_valid_fingerprint():
    service = _service()
    forged = {
        "regime": "mei",
        service.PROVENANCE_KEY: {
            "schema_version": service.SCHEMA_VERSION,
            "producer_id": (
                "app.services.tax_engines.mei_constants.calcular_das_mei"
            ),
            "mei_authority": "CANONICAL",
        },
    }
    fingerprint = service.fingerprint_resultado_json(forged)
    rel = SimpleNamespace(
        resultado_json=forged,
        fingerprint=fingerprint,
    )

    with pytest.raises(service.ResultadoProvenanceError):
        service.verificar_resultado_persistido(rel)


def test_unknown_authority_fails_closed():
    service = _service()
    forged = {
        "x": 1,
        service.PROVENANCE_KEY: {
            "schema_version": service.SCHEMA_VERSION,
            "producer_id": NON_MEI_PRODUCER,
            "mei_authority": "UNKNOWN",
        },
    }
    fingerprint = service.fingerprint_resultado_json(forged)
    rel = SimpleNamespace(
        resultado_json=forged,
        fingerprint=fingerprint,
    )

    with pytest.raises(service.ResultadoProvenanceError):
        service.verificar_resultado_persistido(rel)


def test_mei_analysis_type_with_none_authority_fails_closed_even_with_valid_fingerprint():
    service = _service()

    sealed = service.selar_resultado_nao_mei(
        {"tipo": "MEI", "imposto": 82.05},
        producer_id="app.services.imposto_service.calcular_imposto_simples",
    )
    fingerprint = service.fingerprint_resultado_json(sealed)
    rel = SimpleNamespace(
        analysis_type="mei_tax",
        resultado_json=sealed,
        fingerprint=fingerprint,
    )

    with pytest.raises(service.ResultadoProvenanceError):
        service.verificar_resultado_persistido(rel)
