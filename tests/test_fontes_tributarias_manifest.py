"""
Testes B13-OPS-01 — Manifesto soberano de fontes tributárias.
14 invariantes L3.
"""
import json
import pytest
from pathlib import Path

MANIFEST_PATH = Path("data/fontes_tributarias_manifest.json")

TIPOS_VALIDOS = {
    "normativa_oficial", "operacional_oficial", "informativa_oficial",
    "auxiliar_nao_normativa", "proibida_para_decisao"
}
STATUS_VALIDOS = {"activa", "descontinuada", "substituida", "em_revisao"}
JURISDICAO_VALIDA = {"federal", "estadual", "municipal", "nacional", "federativa"}
CONFIANCA_VALIDA = {"absoluta", "alta", "media", "baixa", "nula"}
RISCO_VALIDO = {"baixo", "medio", "alto", "critico"}
INTERNALIZACAO_VALIDA = {"manual_curada", "ingestao_controlada", "tabela_versionada", "proibida"}
CAMPOS_OBRIGATORIOS = {
    "id", "nome", "tipo", "autoridade", "url_base", "escopo", "jurisdicao",
    "confianca", "pode_fundamentar_decisao", "pode_validar_fato_operacional",
    "pode_ser_usada_por_llm", "status", "vigencia_inicio", "vigencia_fim",
    "forma_internalizacao", "risco_se_desatualizada", "hash_referencia",
    "ultima_verificacao", "observacoes"
}


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.exists(), f"Manifest não encontrado: {MANIFEST_PATH}"
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def fontes(manifest):
    return manifest["fontes"]


def test_manifest_json_valido(manifest):
    assert "fontes" in manifest
    assert isinstance(manifest["fontes"], list)
    assert len(manifest["fontes"]) > 0


def test_campos_obrigatorios_presentes(fontes):
    for fonte in fontes:
        ausentes = CAMPOS_OBRIGATORIOS - set(fonte.keys())
        assert not ausentes, f"[{fonte.get('id')}] campos ausentes: {ausentes}"


def test_ids_unicos(fontes):
    ids = [f["id"] for f in fontes]
    assert len(ids) == len(set(ids)), "IDs duplicados no manifest"


def test_tipos_validos(fontes):
    for fonte in fontes:
        assert fonte["tipo"] in TIPOS_VALIDOS, f"[{fonte['id']}] tipo inválido: {fonte['tipo']}"


def test_status_validos(fontes):
    for fonte in fontes:
        assert fonte["status"] in STATUS_VALIDOS, f"[{fonte['id']}] status inválido"


def test_jurisdicao_valida(fontes):
    for fonte in fontes:
        assert fonte["jurisdicao"] in JURISDICAO_VALIDA, f"[{fonte['id']}] jurisdição inválida"


def test_risco_valido(fontes):
    for fonte in fontes:
        assert fonte["risco_se_desatualizada"] in RISCO_VALIDO, f"[{fonte['id']}] risco inválido"


def test_internalizacao_valida(fontes):
    for fonte in fontes:
        assert fonte["forma_internalizacao"] in INTERNALIZACAO_VALIDA, f"[{fonte['id']}] internalização inválida"


def test_proibida_nao_fundamenta_decisao(fontes):
    for fonte in fontes:
        if fonte["tipo"] == "proibida_para_decisao":
            assert fonte["pode_fundamentar_decisao"] is False, \
                f"[{fonte['id']}] proibida não pode fundamentar decisão"


def test_nao_normativa_nao_fundamenta_decisao(fontes):
    tipos_nao_normativa = {"operacional_oficial", "informativa_oficial", "auxiliar_nao_normativa", "proibida_para_decisao"}
    for fonte in fontes:
        if fonte["tipo"] in tipos_nao_normativa:
            assert fonte["pode_fundamentar_decisao"] is False, \
                f"[{fonte['id']}] tipo {fonte['tipo']} não pode fundamentar decisão"


def test_fundamenta_decisao_exige_hash(fontes):
    for fonte in fontes:
        if fonte["pode_fundamentar_decisao"] is True:
            assert fonte["hash_referencia"] is not None, \
                f"[{fonte['id']}] pode_fundamentar_decisao=true exige hash_referencia"


def test_fundamenta_decisao_exige_status_activa(fontes):
    for fonte in fontes:
        if fonte["pode_fundamentar_decisao"] is True:
            assert fonte["status"] == "activa", \
                f"[{fonte['id']}] pode_fundamentar_decisao=true exige status=activa"


def test_fundamenta_decisao_exige_internalizacao_valida(fontes):
    internalizacao_aceite = {"manual_curada", "ingestao_controlada", "tabela_versionada"}
    for fonte in fontes:
        if fonte["pode_fundamentar_decisao"] is True:
            assert fonte["forma_internalizacao"] in internalizacao_aceite, \
                f"[{fonte['id']}] pode_fundamentar_decisao=true exige internalização válida"


def test_operacional_nao_fundamenta_decisao_mas_pode_validar_fato(fontes):
    for fonte in fontes:
        if fonte["tipo"] == "operacional_oficial":
            assert fonte["pode_fundamentar_decisao"] is False, \
                f"[{fonte['id']}] operacional_oficial nunca fundamenta decisão fiscal"


def test_vedacao_llm_campos_correctos(fontes):
    vedacao = next((f for f in fontes if f["id"] == "VEDACAO-LLM-001"), None)
    assert vedacao is not None, "VEDACAO-LLM-001 não encontrada"
    assert vedacao["tipo"] == "proibida_para_decisao"
    assert vedacao["pode_fundamentar_decisao"] is False
    assert vedacao["pode_ser_usada_por_llm"] is False
    assert vedacao["forma_internalizacao"] == "proibida"
    assert vedacao["confianca"] == "nula"


# --- B13-OPS-12B — fontes ausentes adicionadas ---


def test_salario_minimo_001_existe(fontes):
    ids = [f["id"] for f in fontes]
    assert "SALARIO-MINIMO-001" in ids


def test_salario_minimo_001_aponta_para_decreto_nao_lei(fontes):
    fonte = next(f for f in fontes if f["id"] == "SALARIO-MINIMO-001")
    assert "l14663" not in fonte["url_base"].lower()
    assert "decreto" in fonte["url_base"].lower()


def test_irpf_progressivo_001_existe(fontes):
    ids = [f["id"] for f in fontes]
    assert "IRPF-PROGRESSIVO-001" in ids


@pytest.mark.parametrize("fonte_id", ["SALARIO-MINIMO-001", "IRPF-PROGRESSIVO-001"])
def test_fontes_12b_em_revisao(fontes, fonte_id):
    fonte = next(f for f in fontes if f["id"] == fonte_id)
    assert fonte["status"] == "em_revisao", f"{fonte_id} deve estar em_revisao"


@pytest.mark.parametrize("fonte_id", ["SALARIO-MINIMO-001", "IRPF-PROGRESSIVO-001"])
def test_fontes_12b_nao_fundamentam_decisao(fontes, fonte_id):
    fonte = next(f for f in fontes if f["id"] == fonte_id)
    assert fonte["pode_fundamentar_decisao"] is False


@pytest.mark.parametrize("fonte_id", ["SALARIO-MINIMO-001", "IRPF-PROGRESSIVO-001"])
def test_fontes_12b_sem_hash(fontes, fonte_id):
    fonte = next(f for f in fontes if f["id"] == fonte_id)
    assert fonte["hash_referencia"] is None


def test_source_authority_guard_bloqueia_salario_minimo_fundamentar():
    from app.schemas.source_authority_schema import SourceAuthorityRequest
    from app.services.source_authority_guard import verificar
    r = verificar(SourceAuthorityRequest(
        fonte_id="SALARIO-MINIMO-001",
        uso_pretendido="fundamentar_decisao",
    ))
    assert not r.permitido


def test_source_authority_guard_bloqueia_irpf_fundamentar():
    from app.schemas.source_authority_schema import SourceAuthorityRequest
    from app.services.source_authority_guard import verificar
    r = verificar(SourceAuthorityRequest(
        fonte_id="IRPF-PROGRESSIVO-001",
        uso_pretendido="fundamentar_decisao",
    ))
    assert not r.permitido



def test_decision_source_manifest_contract_rejects_missing_sovereign_fields():
    from app.services.source_authority_guard import (
        validar_fonte_decisoria_manifest,
    )

    fonte = {
        "id": "CGSN-ANEXO-XI-001",
        "tipo": "normativa_oficial",
        "nome": "Anexo XI da Resolucao CGSN 140/2018",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": "CGSN140-ANEXOXI-R182",
        "vigencia_inicio": "2025-10-01",
        "vigencia_fim": None,
        "jurisdicao": "federal",
        "risco_se_desatualizada": "critico",
        "hash_referencia": "a" * 64,
    }

    result = validar_fonte_decisoria_manifest(fonte)

    assert result == (
        False,
        (
            "alvos_normativos_autorizados",
            "jurisdicao_codigo",
        ),
    )



def test_decision_source_manifest_contract_rejects_invalid_sovereign_fields():
    from app.services.source_authority_guard import (
        validar_fonte_decisoria_manifest,
    )

    fonte = {
        "id": "CGSN-ANEXO-XI-001",
        "tipo": "normativa_oficial",
        "nome": "Anexo XI da Resolucao CGSN 140/2018",
        "pode_fundamentar_decisao": True,
        "pode_validar_fato_operacional": False,
        "pode_ser_usada_por_llm": False,
        "versao": "CGSN140-ANEXOXI-R182",
        "vigencia_inicio": "2025-10-01",
        "vigencia_fim": None,
        "jurisdicao": "federal",
        "jurisdicao_codigo": "br",
        "risco_se_desatualizada": "critico",
        "hash_referencia": "a" * 64,
        "alvos_normativos_autorizados": [],
    }

    result = validar_fonte_decisoria_manifest(fonte)

    assert result == (
        False,
        (
            "alvos_normativos_autorizados",
            "jurisdicao_codigo",
        ),
    )



def test_fontes_decisorias_cumprem_contrato_soberano(fontes):
    from app.services.source_authority_guard import (
        validar_fonte_decisoria_manifest,
    )

    for fonte in fontes:
        valido, campos_invalidos = validar_fonte_decisoria_manifest(fonte)

        assert valido, (
            f"[{fonte['id']}] fonte decisoria viola contrato soberano: "
            f"{campos_invalidos}"
        )
