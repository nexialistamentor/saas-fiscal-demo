def test_api_publica_binding_normativo_existe():
    from app.schemas.source_authority_schema import (
        NormativeBindingUsage,
        NormativeBindingStatus,
        NormativeBindingReasonCode,
        NormativeBindingItem,
        NormativeBindingContext,
        NormativeBindingBatchRequest,
        NormativeBindingReason,
        NormativeBindingResult,
    )
    from app.services.source_authority_guard import validar_bindings_normativos

    assert NormativeBindingUsage
    assert NormativeBindingStatus
    assert NormativeBindingReasonCode
    assert NormativeBindingItem
    assert NormativeBindingContext
    assert NormativeBindingBatchRequest
    assert NormativeBindingReason
    assert NormativeBindingResult
    assert callable(validar_bindings_normativos)

from copy import deepcopy
import json

import pytest

from app.schemas.source_authority_schema import (
    NormativeBindingReasonCode,
    NormativeBindingStatus,
)
from app.services import source_authority_guard
from app.services.source_authority_guard import validar_bindings_normativos


P0 = {
    "contexto": {
        "data_referencia": "2026-01-01",
        "jurisdicao_codigo": "BR",
        "uso_solicitado": "diagnostico",
    },
    "bindings": [
        {
            "constante_id": "CONST_001",
            "fonte_id": "SYNTH-001",
            "versao_fonte": "1.0.0",
            "vigencia_inicio": "2025-01-01",
            "vigencia_fim": "2026-12-31",
            "jurisdicao_codigo": "BR",
            "risco": "alto",
            "invariantes": ["INV_001"],
        }
    ],
}


def test_unknown_field_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["extra"] = 1

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"validar_bindings_normativos continua no skeleton: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (NormativeBindingReasonCode.CAMPO_DESCONHECIDO, 0, "extra")
    ]
    assert result.bindings_validados == 0

def test_missing_required_field_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0].pop("vigencia_fim")

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"campo obrigatório ausente ainda não implementado: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.CAMPO_OBRIGATORIO_AUSENTE,
            0,
            "vigencia_fim",
        )
    ]
    assert result.bindings_validados == 0

def test_invalid_identifiers_are_rejected():
    payload = deepcopy(P0)
    payload["bindings"][0]["constante_id"] = "ＣONST_001"
    payload["bindings"][0]["fonte_id"] = " synth-001"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"validação de identificadores ainda não implementada: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
            0,
            "constante_id",
        ),
        (
            NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
            0,
            "fonte_id",
        ),
    ]
    assert result.bindings_validados == 0

def test_invalid_version_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["versao_fonte"] = " 1.0.0"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"validação de versão ainda não implementada: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.VERSAO_INVALIDA,
            0,
            "versao_fonte",
        )
    ]
    assert result.bindings_validados == 0

S_AUTH = {
    "id": "SYNTH-001",
    "tipo": "normativa_oficial",
    "nome": "Fonte sint?tica autorizada",
    "pode_fundamentar_decisao": True,
    "pode_validar_fato_operacional": False,
    "pode_ser_usada_por_llm": False,
    "versao": "1.0.0",
    "vigencia_inicio": "2025-01-01",
    "vigencia_fim": "2026-12-31",
    "jurisdicao": "BR",
    "jurisdicao_codigo": "BR",
    "risco_se_desatualizada": "alto",
    "hash_referencia": "a" * 64,
    "alvos_normativos_autorizados": [
        {
            "tipo": "constante",
            "id": "CONST_001",
        }
    ],
}


S_AUTH_2 = {
    **S_AUTH,
    "id": "SYNTH-002",
    "vigencia_inicio": "2026-12-31",
    "vigencia_fim": "2027-12-31",
}


S_INCOMPLETE = {
    key: value
    for key, value in S_AUTH.items()
    if key != "hash_referencia"
}


@pytest.fixture
def synthetic_manifest(monkeypatch, tmp_path):
    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [S_AUTH]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )
        yield

    source_authority_guard._carregar_manifest.cache_clear()


@pytest.fixture
def synthetic_manifest_two_sources(monkeypatch, tmp_path):
    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [S_AUTH, S_AUTH_2]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )
        yield

    source_authority_guard._carregar_manifest.cache_clear()


@pytest.fixture
def synthetic_manifest_incomplete(monkeypatch, tmp_path):
    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [S_INCOMPLETE]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )
        yield

    source_authority_guard._carregar_manifest.cache_clear()


def test_source_mismatched_version_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["versao_fonte"] = "2.0.0"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"compatibilidade de vers?o ainda n?o implementada: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.VERSAO_FONTE_INCOMPATIVEL,
            0,
            "versao_fonte",
        )
    ]
    assert result.bindings_validados == 0

def test_invalid_interval_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["vigencia_inicio"] = "2027-01-01"
    payload["bindings"][0]["vigencia_fim"] = "2026-12-31"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"valida??o temporal ainda n?o implementada: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.VIGENCIA_INVALIDA,
            0,
            "vigencia_fim",
        )
    ]
    assert result.bindings_validados == 0

S_FALSE = {
    **S_AUTH,
    "pode_fundamentar_decisao": False,
}


@pytest.fixture
def synthetic_manifest_false(monkeypatch, tmp_path):
    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [S_FALSE]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )
        yield

    source_authority_guard._carregar_manifest.cache_clear()


def test_inclusive_start_boundary_is_valid(synthetic_manifest_false):
    payload = deepcopy(P0)
    payload["contexto"]["data_referencia"] = "2025-01-01"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"limite inicial inclusivo ainda n?o implementado: {exc}"

    assert result.status == NormativeBindingStatus.valido_sem_autoridade_decisoria
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 1

def test_inclusive_end_boundary_is_valid(synthetic_manifest_false):
    payload = deepcopy(P0)
    payload["contexto"]["data_referencia"] = "2026-12-31"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"inclusive end boundary not implemented: {exc}"

    assert result.status == NormativeBindingStatus.valido_sem_autoridade_decisoria
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 1

@pytest.fixture
def synthetic_manifest_false_open_ended(monkeypatch, tmp_path):
    source = deepcopy(S_FALSE)
    source["vigencia_fim"] = None

    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [source]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )
        yield

    source_authority_guard._carregar_manifest.cache_clear()


def test_open_ended_end_is_valid(
    synthetic_manifest_false_open_ended,
):
    payload = deepcopy(P0)
    payload["bindings"][0]["vigencia_fim"] = None

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"open-ended validity not implemented: {exc}"

    assert result.status == NormativeBindingStatus.valido_sem_autoridade_decisoria
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 1

def test_outside_validity_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["contexto"]["data_referencia"] = "2027-01-01"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"outside validity not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FORA_DA_VIGENCIA,
            0,
            "data_referencia",
        )
    ]
    assert result.bindings_validados == 0

def test_invalid_jurisdiction_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["contexto"]["jurisdicao_codigo"] = "br"
    payload["bindings"][0]["jurisdicao_codigo"] = "br"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"jurisdiction validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.JURISDICAO_INVALIDA,
            None,
            "jurisdicao_codigo",
        ),
        (
            NormativeBindingReasonCode.JURISDICAO_INVALIDA,
            0,
            "jurisdicao_codigo",
        ),
    ]
    assert result.bindings_validados == 0

def test_incompatible_jurisdiction_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["contexto"]["jurisdicao_codigo"] = "BR-SP"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"jurisdiction compatibility not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.JURISDICAO_INCOMPATIVEL,
            0,
            "jurisdicao_codigo",
        )
    ]
    assert result.bindings_validados == 0

def test_invalid_risk_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["risco"] = "severo"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"risk validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.RISCO_INVALIDO,
            0,
            "risco",
        )
    ]
    assert result.bindings_validados == 0

def test_source_mismatched_risk_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["risco"] = "baixo"

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"source risk compatibility not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.RISCO_FONTE_INCOMPATIVEL,
            0,
            "risco",
        )
    ]
    assert result.bindings_validados == 0

def test_invalid_invariants_are_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["invariantes"] = ["x"]

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"invariant validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
            0,
            "invariantes",
        )
    ]
    assert result.bindings_validados == 0

def test_duplicated_invariants_are_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["invariantes"] = [
        "INV_001",
        "INV_001",
    ]

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"duplicate invariant validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
            0,
            "invariantes",
        )
    ]
    assert result.bindings_validados == 0

def test_unsorted_invariants_are_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["invariantes"] = [
        "INV_002",
        "INV_001",
    ]

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"unsorted invariant validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
            0,
            "invariantes",
        )
    ]
    assert result.bindings_validados == 0

def test_duplicate_binding_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"].append(
        deepcopy(payload["bindings"][0])
    )

    try:
        result = validar_bindings_normativos(payload)
    except NotImplementedError as exc:
        assert False, f"duplicate binding validation not implemented: {exc}"

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.BINDING_DUPLICADO,
            1,
            "bindings",
        )
    ]
    assert result.bindings_validados == 0

def test_conflicting_overlapping_binding_is_rejected(
    synthetic_manifest_two_sources,
):
    payload = deepcopy(P0)
    second_binding = deepcopy(payload["bindings"][0])
    second_binding["fonte_id"] = "SYNTH-002"
    second_binding["vigencia_inicio"] = "2026-12-31"
    second_binding["vigencia_fim"] = "2027-12-31"
    payload["bindings"].append(second_binding)

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.BINDINGS_CONFLITANTES,
            1,
            "bindings",
        )
    ]
    assert result.bindings_validados == 0

def test_missing_source_is_rejected(synthetic_manifest):
    payload = deepcopy(P0)
    payload["bindings"][0]["fonte_id"] = "MISSING-001"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_INEXISTENTE,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 0

def test_incomplete_source_is_rejected(
    synthetic_manifest_incomplete,
):
    payload = deepcopy(P0)

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_INCOMPLETA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 0

P0E = deepcopy(P0)
P0E["contexto"]["uso_solicitado"] = "estimativa"


def test_existing_false_source_is_not_promoted(
    synthetic_manifest_false,
):
    payload = deepcopy(P0E)

    result = validar_bindings_normativos(payload)

    assert (
        result.status
        == NormativeBindingStatus.valido_sem_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 1

P0D = deepcopy(P0)
P0D["contexto"]["uso_solicitado"] = "decisao_definitiva"

def test_definitive_use_without_authority_is_blocked(
    synthetic_manifest_false,
):
    payload = deepcopy(P0D)

    result = validar_bindings_normativos(payload)

    assert (
        result.status
        == NormativeBindingStatus.valido_sem_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        ),
        (
            NormativeBindingReasonCode.DECISAO_DEFINITIVA_BLOQUEADA,
            None,
            "uso_solicitado",
        ),
    ]
    assert result.bindings_validados == 1

def test_structurally_valid_binding_without_decision_authority(
    synthetic_manifest_false,
):
    payload = deepcopy(P0)

    result = validar_bindings_normativos(payload)

    assert (
        result.status
        == NormativeBindingStatus.valido_sem_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 1

def test_synthetic_authorized_source_allows_definitive_use(
    synthetic_manifest,
):
    payload = deepcopy(P0D)

    result = validar_bindings_normativos(payload)

    assert (
        result.status
        == NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is True
    assert result.reasons == ()
    assert result.bindings_validados == 1

def test_deterministic_reason_ordering(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    binding = payload["bindings"][0]

    binding.pop("vigencia_fim")
    binding["extra"] = 1
    binding["constante_id"] = "x"
    binding["versao_fonte"] = " 1"
    binding["jurisdicao_codigo"] = "br"
    binding["risco"] = "severo"
    binding["invariantes"] = []
    binding["fonte_id"] = "MISSING-001"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.CAMPO_OBRIGATORIO_AUSENTE,
            0,
            "vigencia_fim",
        ),
        (
            NormativeBindingReasonCode.CAMPO_DESCONHECIDO,
            0,
            "extra",
        ),
        (
            NormativeBindingReasonCode.IDENTIFICADOR_INVALIDO,
            0,
            "constante_id",
        ),
        (
            NormativeBindingReasonCode.VERSAO_INVALIDA,
            0,
            "versao_fonte",
        ),
        (
            NormativeBindingReasonCode.JURISDICAO_INVALIDA,
            0,
            "jurisdicao_codigo",
        ),
        (
            NormativeBindingReasonCode.RISCO_INVALIDO,
            0,
            "risco",
        ),
        (
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
            0,
            "invariantes",
        ),
        (
            NormativeBindingReasonCode.FONTE_INEXISTENTE,
            0,
            "fonte_id",
        ),
    ]
    assert result.bindings_validados == 0

def test_canonical_json_is_stable(
    synthetic_manifest,
):
    first = validar_bindings_normativos(deepcopy(P0D))
    second = validar_bindings_normativos(deepcopy(P0D))

    expected = (
        b'{"autorizado_fundamentar_decisao":true,'
        b'"bindings_validados":1,'
        b'"reasons":[],'
        b'"status":"valido_com_autoridade_decisoria"}'
    )

    first_text = first.canonical_json()
    second_text = second.canonical_json()

    assert isinstance(first_text, str)
    assert isinstance(second_text, str)

    first_bytes = first_text.encode("utf-8")
    second_bytes = second_text.encode("utf-8")

    assert (
        first.status
        == NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert first.autorizado_fundamentar_decisao is True
    assert first.reasons == ()
    assert first.bindings_validados == 1

    assert second == first
    assert first_bytes == expected
    assert second_bytes == expected
    assert first_bytes == second_bytes

def test_real_manifest_bytes_are_unchanged(
    synthetic_manifest,
):
    from hashlib import sha256
    from pathlib import Path

    real_manifest = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "fontes_tributarias_manifest.json"
    )

    before_bytes = real_manifest.read_bytes()
    before_hash = sha256(before_bytes).hexdigest()

    result = validar_bindings_normativos(deepcopy(P0))

    after_bytes = real_manifest.read_bytes()
    after_hash = sha256(after_bytes).hexdigest()

    assert (
        result.status
        == NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is True
    assert result.reasons == ()
    assert result.bindings_validados == 1

    assert after_bytes == before_bytes
    assert after_hash == before_hash

def test_existing_verificar_behavior_is_preserved():
    from app.schemas.source_authority_schema import (
        SourceAuthorityRequest,
        SourceAuthorityResult,
    )

    result = source_authority_guard.verificar(
        SourceAuthorityRequest(
            fonte_id="INEXISTENTE-999",
            uso_pretendido="fundamentar_decisao",
        )
    )

    assert type(result) is SourceAuthorityResult
    assert result.permitido is False
    assert result.fonte_id == "INEXISTENTE-999"
    assert result.uso_pretendido == "fundamentar_decisao"
    assert (
        result.motivo
        == "Fonte 'INEXISTENTE-999' não existe no manifesto soberano."
    )
    assert (
        result.acao
        == (
            "Verificar o id da fonte em "
            "data/fontes_tributarias_manifest.json."
        )
    )

    dump = result.model_dump(mode="json")

    expected_non_null = {
        "permitido": False,
        "fonte_id": "INEXISTENTE-999",
        "uso_pretendido": "fundamentar_decisao",
        "motivo": (
            "Fonte 'INEXISTENTE-999' "
            "não existe no manifesto soberano."
        ),
        "acao": (
            "Verificar o id da fonte em "
            "data/fontes_tributarias_manifest.json."
        ),
    }

    assert {
        key: value
        for key, value in dump.items()
        if value is not None
    } == expected_non_null

    assert all(
        value is None
        for key, value in dump.items()
        if key not in expected_non_null
    )

def test_existing_source_authority_models_are_preserved():
    from hashlib import sha256

    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        SourceAuthorityRequest,
        SourceAuthorityResult,
    )

    def canonical(value):
        return json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def assert_baseline(value, expected_length, expected_hash):
        raw = canonical(value)

        assert len(raw) == expected_length
        assert sha256(raw).hexdigest().upper() == expected_hash

    assert_baseline(
        SourceAuthorityRequest.model_json_schema(),
        310,
        (
            "C5003C4E23024A399FC1B577115020E17"
            "B590021A0CBF045CBE7DA66CAB7AFCF"
        ),
    )
    assert_baseline(
        SourceAuthorityResult.model_json_schema(),
        956,
        (
            "971F9F4D2E62052FA1D8A2D9B5F65D74"
            "726CAAF4A491A170EE823378F718FDA2"
        ),
    )

    request = SourceAuthorityRequest(
        fonte_id="INEXISTENTE-999",
        uso_pretendido="fundamentar_decisao",
    )

    assert_baseline(
        request.model_dump(mode="json"),
        69,
        (
            "71225B25A5FC8C443CB7C974152885C3"
            "B2BDBA881FB7786A75B6590AEAF71854"
        ),
    )

    result = source_authority_guard.verificar(request)

    assert type(result) is SourceAuthorityResult
    assert_baseline(
        result.model_dump(mode="json"),
        359,
        (
            "592FB81382900BD77BF1DF9483F191AD"
            "642DD311036846AD7D18FF618BFFBD07"
        ),
    )

    def rejection(model):
        try:
            model()
        except ValidationError as exc:
            return exc.errors(include_url=False)

        raise AssertionError(
            model.__name__ + " deveria rejeitar payload vazio"
        )

    assert_baseline(
        rejection(SourceAuthorityRequest),
        151,
        (
            "5FB504A5DB0AD87D50B01166D6F9DEC8"
            "0D8A9293BBE81EDC1CB553AA8FF07D17"
        ),
    )
    assert_baseline(
        rejection(SourceAuthorityResult),
        294,
        (
            "F60708F892B2CE51F3933B8EA19D3E19"
            "105F74C4393DFCB3266ACD2E8D8807A4"
        ),
    )

def test_validator_does_not_import_or_call_engine(
    synthetic_manifest,
    monkeypatch,
):
    import builtins
    import importlib
    import sys
    import types

    targets = {
        "app.motor_fiscal",
        "app.services.regime_engine",
        "app.services.tax_engines",
    }
    imported_targets = []
    called_targets = []

    real_import = builtins.__import__
    real_import_module = importlib.import_module

    def tracked_import(
        name,
        globals=None,
        locals=None,
        fromlist=(),
        level=0,
    ):
        if any(
            name == target
            or name.startswith(target + ".")
            for target in targets
        ):
            imported_targets.append(name)

        return real_import(
            name,
            globals,
            locals,
            fromlist,
            level,
        )

    def tracked_import_module(name, package=None):
        if any(
            name == target
            or name.startswith(target + ".")
            for target in targets
        ):
            imported_targets.append(name)

        return real_import_module(name, package)

    class CallSentinel:
        def __init__(self, qualified_name):
            self.qualified_name = qualified_name

        def __getattr__(self, attribute):
            return CallSentinel(
                self.qualified_name + "." + attribute
            )

        def __call__(self, *args, **kwargs):
            called_targets.append(self.qualified_name)
            raise AssertionError(
                "engine call detected: "
                + self.qualified_name
            )

    class SentinelModule(types.ModuleType):
        def __getattr__(self, attribute):
            return CallSentinel(
                self.__name__ + "." + attribute
            )

    monkeypatch.setattr(
        builtins,
        "__import__",
        tracked_import,
    )
    monkeypatch.setattr(
        importlib,
        "import_module",
        tracked_import_module,
    )

    app_package = sys.modules["app"]
    services_package = sys.modules["app.services"]

    for target in sorted(targets):
        sentinel = SentinelModule(target)
        monkeypatch.setitem(sys.modules, target, sentinel)

        if target == "app.motor_fiscal":
            monkeypatch.setattr(
                app_package,
                "motor_fiscal",
                sentinel,
                raising=False,
            )
        elif target == "app.services.regime_engine":
            monkeypatch.setattr(
                services_package,
                "regime_engine",
                sentinel,
                raising=False,
            )
        elif target == "app.services.tax_engines":
            monkeypatch.setattr(
                services_package,
                "tax_engines",
                sentinel,
                raising=False,
            )

    result = validar_bindings_normativos(deepcopy(P0D))

    assert (
        result.status
        == NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is True
    assert result.reasons == ()
    assert result.bindings_validados == 1
    assert imported_targets == []
    assert called_targets == []

def test_validator_creates_no_fiscal_value_fallback_or_presumption(
    synthetic_manifest,
):
    import inspect

    payload = deepcopy(P0D)
    payload_before = deepcopy(payload)

    validator_source = inspect.getsource(
        validar_bindings_normativos
    ).lower()

    assert "fallback" not in validator_source
    assert "presum" not in validator_source

    result = validar_bindings_normativos(payload)

    assert (
        result.status
        == NormativeBindingStatus.valido_com_autoridade_decisoria
    )
    assert result.autorizado_fundamentar_decisao is True
    assert result.reasons == ()
    assert result.bindings_validados == 1

    dump = result.model_dump(mode="json")

    assert dump == {
        "status": "valido_com_autoridade_decisoria",
        "autorizado_fundamentar_decisao": True,
        "reasons": [],
        "bindings_validados": 1,
    }

    assert set(dump) == {
        "status",
        "autorizado_fundamentar_decisao",
        "reasons",
        "bindings_validados",
    }

    forbidden_result_terms = (
        "valor",
        "aliquota",
        "percentual",
        "imposto",
        "tributo",
        "base_calculo",
        "faturamento",
        "receita",
        "presuncao",
        "fallback",
        "binding",
    )

    assert not any(
        term in key.lower()
        for key in dump
        for term in forbidden_result_terms
        if key != "bindings_validados"
    )

    assert payload == payload_before
    assert len(payload["bindings"]) == 1

def test_binding_starts_before_source_validity_is_rejected(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    payload["bindings"][0]["vigencia_inicio"] = "2024-12-31"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.VIGENCIA_FONTE_INCOMPATIVEL,
            0,
            "vigencia_inicio",
        )
    ]
    assert result.bindings_validados == 0

def test_open_binding_exceeds_finite_source_validity_is_rejected(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    payload["bindings"][0]["vigencia_fim"] = None

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.VIGENCIA_FONTE_INCOMPATIVEL,
            0,
            "vigencia_fim",
        )
    ]
    assert result.bindings_validados == 0

def test_pairwise_checks_skip_structurally_invalid_binding(
    synthetic_manifest,
):
    payload = deepcopy(P0)

    second = deepcopy(payload["bindings"][0])
    second["invariantes"] = ["x"]
    payload["bindings"].append(second)

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.INVARIANTES_INVALIDOS,
            1,
            "invariantes",
        )
    ]
    assert result.bindings_validados == 0

    emitted = {reason.code for reason in result.reasons}

    assert NormativeBindingReasonCode.BINDING_DUPLICADO not in emitted
    assert NormativeBindingReasonCode.BINDINGS_CONFLITANTES not in emitted
    assert NormativeBindingReasonCode.FONTE_INEXISTENTE not in emitted
    assert NormativeBindingReasonCode.FONTE_INCOMPLETA not in emitted
    assert NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA not in emitted
    assert (
        NormativeBindingReasonCode.VERSAO_FONTE_INCOMPATIVEL
        not in emitted
    )
    assert (
        NormativeBindingReasonCode.VIGENCIA_FONTE_INCOMPATIVEL
        not in emitted
    )
    assert (
        NormativeBindingReasonCode.RISCO_FONTE_INCOMPATIVEL
        not in emitted
    )

def test_invalid_context_reference_date_is_rejected(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    payload["contexto"]["data_referencia"] = "2026-02-30"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.CONTEXTO_INVALIDO,
            None,
            "data_referencia",
        )
    ]
    assert result.bindings_validados == 0

    emitted = {reason.code for reason in result.reasons}
    assert NormativeBindingReasonCode.FORA_DA_VIGENCIA not in emitted

def test_invalid_context_usage_is_rejected(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    payload["contexto"]["uso_solicitado"] = "definitiva"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.CONTEXTO_INVALIDO,
            None,
            "uso_solicitado",
        )
    ]
    assert result.bindings_validados == 0

    emitted = {reason.code for reason in result.reasons}

    assert NormativeBindingReasonCode.FONTE_NAO_AUTORIZADA not in emitted
    assert (
        NormativeBindingReasonCode.DECISAO_DEFINITIVA_BLOQUEADA
        not in emitted
    )

def test_invalid_context_reasons_have_deterministic_order(
    synthetic_manifest,
):
    payload = deepcopy(P0)
    payload["contexto"]["data_referencia"] = "2026-02-30"
    payload["contexto"]["uso_solicitado"] = "definitiva"

    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.CONTEXTO_INVALIDO,
            None,
            "data_referencia",
        ),
        (
            NormativeBindingReasonCode.CONTEXTO_INVALIDO,
            None,
            "uso_solicitado",
        ),
    ]
    assert result.bindings_validados == 0



def test_new_normative_models_forbid_unknown_fields():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingBatchRequest,
        NormativeBindingContext,
        NormativeBindingItem,
        NormativeBindingReason,
        NormativeBindingResult,
    )

    item_kwargs = dict(
        constante_id="CONST_001",
        fonte_id="SYNTH-001",
        versao_fonte="1.0.0",
        vigencia_inicio="2025-01-01",
        vigencia_fim="2026-12-31",
        jurisdicao_codigo="BR",
        risco="alto",
        invariantes=("INV_001",),
    )

    context_kwargs = dict(
        data_referencia="2025-06-01",
        jurisdicao_codigo="BR",
        uso_solicitado="diagnostico",
    )

    reason_kwargs = dict(
        code=NormativeBindingReasonCode.CONTEXTO_INVALIDO,
        binding_index=None,
        field="data_referencia",
    )

    result_kwargs = dict(
        status=NormativeBindingStatus.invalido,
        autorizado_fundamentar_decisao=False,
        reasons=(),
        bindings_validados=0,
    )

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            **item_kwargs,
            campo_extra="x",
        )

    with pytest.raises(ValidationError):
        NormativeBindingContext(
            **context_kwargs,
            campo_extra="x",
        )

    context = NormativeBindingContext(**context_kwargs)
    item = NormativeBindingItem(**item_kwargs)

    with pytest.raises(ValidationError):
        NormativeBindingBatchRequest(
            contexto=context,
            bindings=(item,),
            campo_extra="x",
        )

    with pytest.raises(ValidationError):
        NormativeBindingReason(
            **reason_kwargs,
            campo_extra="x",
        )

    with pytest.raises(ValidationError):
        NormativeBindingResult(
            **result_kwargs,
            campo_extra="x",
        )


def test_normative_binding_item_rejects_risk_outside_closed_set():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="severo",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_empty_invariants():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=(),
        )


def test_normative_binding_batch_rejects_empty_bindings():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingBatchRequest,
        NormativeBindingContext,
    )

    contexto = NormativeBindingContext(
        data_referencia="2025-06-01",
        jurisdicao_codigo="BR",
        uso_solicitado="diagnostico",
    )

    with pytest.raises(ValidationError):
        NormativeBindingBatchRequest(
            contexto=contexto,
            bindings=(),
        )


def test_normative_binding_result_rejects_negative_bindings_validados():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingResult,
        NormativeBindingStatus,
    )

    with pytest.raises(ValidationError):
        NormativeBindingResult(
            status=NormativeBindingStatus.invalido,
            autorizado_fundamentar_decisao=False,
            reasons=(),
            bindings_validados=-1,
        )


def test_normative_binding_item_rejects_constante_id_external_whitespace():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id=" CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_fonte_id_control_character():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-\n001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_constante_id_nfkc_drift():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="\uFF23ONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_datetime_string_in_vigencia_inicio():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01T00:00:00",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_datetime_object_in_vigencia_inicio():
    from datetime import datetime

    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio=datetime(2025, 1, 1, 0, 0, 0),
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_context_rejects_datetime_string_in_data_referencia():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingContext

    with pytest.raises(ValidationError):
        NormativeBindingContext(
            data_referencia="2025-06-01T00:00:00",
            jurisdicao_codigo="BR",
            uso_solicitado="diagnostico",
        )


def test_normative_binding_context_rejects_datetime_object_in_data_referencia():
    from datetime import datetime

    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingContext

    with pytest.raises(ValidationError):
        NormativeBindingContext(
            data_referencia=datetime(2025, 6, 1, 0, 0, 0),
            jurisdicao_codigo="BR",
            uso_solicitado="diagnostico",
        )


def test_normative_binding_item_rejects_datetime_string_in_vigencia_fim():
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31T00:00:00",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


def test_normative_binding_item_rejects_datetime_object_in_vigencia_fim():
    from datetime import datetime

    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim=datetime(2026, 12, 31, 0, 0, 0),
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=("INV_001",),
        )


@pytest.mark.parametrize(
    ("target", "field", "invalid_value"),
    (
        ("item", "constante_id", "CONST_\n001"),
        ("item", "fonte_id", " SYNTH-001"),
        ("item", "fonte_id", "\uFF33YNTH-001"),
        ("item", "versao_fonte", " 1.0.0"),
        ("item", "versao_fonte", "1.0.\n0"),
        ("item", "versao_fonte", "\uFF11.0.0"),
        ("item", "jurisdicao_codigo", " BR"),
        ("item", "jurisdicao_codigo", "B\nR"),
        ("item", "jurisdicao_codigo", "\uFF22R"),
        ("item", "invariantes", (" INV_001",)),
        ("item", "invariantes", ("INV_\n001",)),
        ("item", "invariantes", ("\uFF29NV_001",)),
        ("context", "jurisdicao_codigo", " BR"),
        ("context", "jurisdicao_codigo", "B\nR"),
        ("context", "jurisdicao_codigo", "\uFF22R"),
    ),
)
def test_normative_text_representation_is_rejected_transversally(
    target,
    field,
    invalid_value,
):
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingContext,
        NormativeBindingItem,
    )

    if target == "item":
        payload = {
            "constante_id": "CONST_001",
            "fonte_id": "SYNTH-001",
            "versao_fonte": "1.0.0",
            "vigencia_inicio": "2025-01-01",
            "vigencia_fim": "2026-12-31",
            "jurisdicao_codigo": "BR",
            "risco": "alto",
            "invariantes": ("INV_001",),
        }
        payload[field] = invalid_value

        with pytest.raises(ValidationError):
            NormativeBindingItem(**payload)
        return

    payload = {
        "data_referencia": "2025-06-01",
        "jurisdicao_codigo": "BR",
        "uso_solicitado": "diagnostico",
    }
    payload[field] = invalid_value

    with pytest.raises(ValidationError):
        NormativeBindingContext(**payload)


@pytest.mark.parametrize(
    ("target", "field", "invalid_value"),
    (
        ("item", "constante_id", "AB"),
        ("item", "fonte_id", "AB"),
        ("item", "versao_fonte", "1/0"),
        ("item", "jurisdicao_codigo", "US"),
        ("item", "invariantes", ("inv_001",)),
        ("context", "jurisdicao_codigo", "US"),
    ),
)
def test_normative_identifier_grammar_is_rejected_transversally(
    target,
    field,
    invalid_value,
):
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingContext,
        NormativeBindingItem,
    )

    if target == "item":
        payload = {
            "constante_id": "CONST_001",
            "fonte_id": "SYNTH-001",
            "versao_fonte": "1.0.0",
            "vigencia_inicio": "2025-01-01",
            "vigencia_fim": "2026-12-31",
            "jurisdicao_codigo": "BR",
            "risco": "alto",
            "invariantes": ("INV_001",),
        }
        payload[field] = invalid_value

        with pytest.raises(ValidationError):
            NormativeBindingItem(**payload)
        return

    payload = {
        "data_referencia": "2025-06-01",
        "jurisdicao_codigo": "BR",
        "uso_solicitado": "diagnostico",
    }
    payload[field] = invalid_value

    with pytest.raises(ValidationError):
        NormativeBindingContext(**payload)


@pytest.mark.parametrize(
    "invariantes",
    (
        ("INV_AAA", "INV_AAA"),
        ("INV_BBB", "INV_AAA"),
    ),
)
def test_normative_invariants_require_unique_sorted_order(
    invariantes,
):
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import NormativeBindingItem

    with pytest.raises(ValidationError):
        NormativeBindingItem(
            constante_id="CONST_001",
            fonte_id="SYNTH-001",
            versao_fonte="1.0.0",
            vigencia_inicio="2025-01-01",
            vigencia_fim="2026-12-31",
            jurisdicao_codigo="BR",
            risco="alto",
            invariantes=invariantes,
        )


@pytest.mark.parametrize(
    "field",
    (
        " campo",
        "cam\npo",
        "\uff46ield",
    ),
)
def test_normative_reason_field_rejects_invalid_text_representation(
    field,
):
    from pydantic import ValidationError

    from app.schemas.source_authority_schema import (
        NormativeBindingReason,
        NormativeBindingReasonCode,
    )

    with pytest.raises(ValidationError):
        NormativeBindingReason(
            code=NormativeBindingReasonCode.CAMPO_OBRIGATORIO_AUSENTE,
            binding_index=0,
            field=field,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        {"vigencia_inicio": "2025-99-99"},
        {"vigencia_fim": "2026-99-99"},
        {
            "vigencia_inicio": "2026-12-31",
            "vigencia_fim": "2025-01-01",
        },
    ),
)
def test_invalid_source_temporal_contract_is_incomplete(
    mutation,
    monkeypatch,
    tmp_path,
):
    source = deepcopy(S_AUTH)
    source.update(mutation)

    manifest_path = tmp_path / "fontes_tributarias_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"fontes": [source]},
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    source_authority_guard._carregar_manifest.cache_clear()

    with monkeypatch.context() as patch:
        patch.setattr(
            source_authority_guard,
            "MANIFEST_PATH",
            manifest_path,
        )

        result = validar_bindings_normativos(deepcopy(P0))

    source_authority_guard._carregar_manifest.cache_clear()

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_INCOMPLETA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 0



def test_source_jurisdiction_code_mismatch_is_rejected(monkeypatch):
    import app.services.source_authority_guard as guard

    source = deepcopy(S_AUTH)
    source["jurisdicao_codigo"] = "BR-SP"

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = deepcopy(P0)
    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.JURISDICAO_INCOMPATIVEL,
            0,
            "jurisdicao_codigo",
        )
    ]
    assert result.bindings_validados == 0



def test_decision_source_without_jurisdiction_code_is_incomplete(monkeypatch):
    import app.services.source_authority_guard as guard

    source = deepcopy(S_AUTH)
    source.pop("jurisdicao_codigo")

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = deepcopy(P0)
    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_INCOMPLETA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 0



def test_decision_source_with_invalid_jurisdiction_code_is_incomplete(
    monkeypatch,
):
    import app.services.source_authority_guard as guard

    source = deepcopy(S_AUTH)
    source["jurisdicao_codigo"] = "br"

    monkeypatch.setattr(
        guard,
        "_carregar_manifest",
        lambda: {source["id"]: source},
    )

    payload = deepcopy(P0)
    result = validar_bindings_normativos(payload)

    assert result.status == NormativeBindingStatus.invalido
    assert result.autorizado_fundamentar_decisao is False
    assert [
        (reason.code, reason.binding_index, reason.field)
        for reason in result.reasons
    ] == [
        (
            NormativeBindingReasonCode.FONTE_INCOMPLETA,
            0,
            "fonte_id",
        )
    ]
    assert result.bindings_validados == 0
