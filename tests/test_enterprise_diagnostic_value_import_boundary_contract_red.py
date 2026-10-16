"""SOLVERIS P1-02C RED: leitura sem BD + normalizacao monetaria efemera.

Teste contratual de preparacao comercial, SEM checkout, pagamento ou deploy.
Protege P1-02A/B. Nao usa SQLAlchemy, importacao de xml_service ou BD.
Este teste apenas observa a politica pura e exige uma fronteira nova.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib
from pathlib import Path

import pytest

from app.services.enterprise_paid_diagnostic_eligibility import (
    avaliar_elegibilidade_diagnostico_empresarial,
)

ROOT = Path(__file__).resolve().parents[1]
COVERAGE = ROOT / "app/services/enterprise_diagnostic_coverage.py"


def _payload(*, valor="1499.00", incomplete=False):
    return {
        "empresa_id": 21,
        "dados_fiscais": {
            "chave_nfe": "1" * 44,
            "valor_total_nota": valor,
            "uf_emit": "PA",
            "uf_dest": "PA",
            "icms_st": 0,
        },
        "insights": {"documental": [], "empresarial": None},
        "oportunidades": [],
        "creditos_detectados": [],
        "previsao_recuperacao": {"potencial_recuperacao_nota": None},
        "context_flags": {
            "documental": {"dados_incompletos": incomplete},
            "empresarial": {"dados_incompletos": incomplete},
        },
    }


def test_p102c_observacao_politica_p102a_rejeita_string_sem_mutar():
    original = _payload()
    copia = deepcopy(original)
    assert avaliar_elegibilidade_diagnostico_empresarial(
        original, empresa_id=21
    ) == {"eligible": False}
    assert original == copia
    numerico = _payload(valor=1499.0)
    assert avaliar_elegibilidade_diagnostico_empresarial(
        numerico, empresa_id=21
    ) == {"eligible": True}


def test_p102c_red_coverage_nao_importa_parser_com_efeitos_de_banco():
    # AST estatico: nao importa app.xml_service porque isso carrega models/database
    # e pode executar ensure_sqlite_schema_compat em importacao isolada.
    source = COVERAGE.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    importacoes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            importacoes.append(node.module or "")
        elif isinstance(node, ast.Import):
            importacoes.extend(alias.name for alias in node.names)
    assert not any(
        item == "app.xml_service" or item.startswith("app.xml_service.")
        for item in importacoes
    ), "P102C_DATABASE_IMPORT_BOUNDARY_RED"


def test_p102c_red_exige_normalizacao_efemera_pura_sem_dispensar_flags():
    # A verificacao de provenance/ownership acontece ANTES no futuro chamador.
    # A normalizacao serve apenas para o input efemero do gate informativo.
    # Nao persiste nem altera o valor monetario canonico original.
    try:
        module = importlib.import_module(
            "app.services.enterprise_diagnostic_amount_binding"
        )
    except ModuleNotFoundError as exc:
        if exc.name == "app.services.enterprise_diagnostic_amount_binding":
            pytest.fail("P102C_VALUE_BINDING_MISSING", pytrace=False)
        raise
    normalizar = getattr(module, "normalizar_valor_nfe_para_politica", None)
    assert callable(normalizar), "P102C_VALUE_BINDING_MISSING"

    original = _payload()
    backup = deepcopy(original)
    convertido = normalizar(original)
    assert type(convertido) is dict, "P102C_NORMALIZED_PAYLOAD_REQUIRED"
    assert convertido is not original
    assert original == backup, "P102C_PERSISTED_RESULT_MUTATED"
    assert type(convertido["dados_fiscais"]["valor_total_nota"]) is float
    assert avaliar_elegibilidade_diagnostico_empresarial(
        convertido, empresa_id=21
    ) == {"eligible": True}, "P102C_CANONICAL_DECISION_MUST_BE_REUSED"

    bloqueado = normalizar(_payload(incomplete=True))
    assert type(bloqueado) is dict
    assert avaliar_elegibilidade_diagnostico_empresarial(
        bloqueado, empresa_id=21
    ) == {"eligible": False}, "P102C_MUST_NOT_OVERRIDE_FLAGS"

    for valor in (True, None, "-1.00", "NaN", "Infinity", "1e3", "1,00", " 1.00 ",
                  "100.001", "999999999999999999999999.99"):
        assert normalizar(_payload(valor=valor)) is None, (
            "P102C_MALFORMED_MONETARY_VALUE_MUST_FAIL_CLOSED", valor
        )
