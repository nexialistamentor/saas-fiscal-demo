"""
B13-OPS-13A — Testes do motor temporal normativo.
"""

import ast
from pathlib import Path

import pytest

from app.services.tax_engines.base_tax_engine import (
    BaseTaxEngine,
    TempoNormativoAusenteError,
)

ENGINES_EM_ESCOPO = [
    "app/services/tax_engines/cpf_tax_engine.py",
    "app/services/tax_engines/csll_engine.py",
    "app/services/tax_engines/irpj_engine.py",
    "app/services/tax_engines/lucro_presumido_engine.py",
    "app/services/tax_engines/lucro_real_engine.py",
    "app/services/tax_engines/pis_cofins_engine.py",
    "app/services/tax_engines/tax_planning_engine.py",
    "app/services/tax_engines/tax_recovery_engine.py",
]


def _metodo_da_classe(caminho, classe, metodo):
    arvore = ast.parse(Path(caminho).read_text(encoding="utf-8"))
    classe_ast = next(
        node
        for node in arvore.body
        if isinstance(node, ast.ClassDef) and node.name == classe
    )
    return next(
        node
        for node in classe_ast.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == metodo
    )


def _nome_chamada(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def test_base_tax_engine_sem_ano_vigencia_fixo():
    src = Path("app/services/tax_engines/base_tax_engine.py").read_text(encoding="utf-8")
    assert "ano_vigencia = 2024" not in src
    assert "ano_vigencia = 2026" not in src


def test_resolver_usa_ano_referencia():
    eng = BaseTaxEngine()
    assert eng.resolver_ano_referencia({"ano_referencia": 2026}) == 2026


def test_resolver_usa_data_referencia():
    from datetime import date

    eng = BaseTaxEngine()
    assert eng.resolver_ano_referencia({"data_referencia": date(2026, 3, 1)}) == 2026


def test_resolver_bloqueia_sem_dado_temporal():
    eng = BaseTaxEngine()
    with pytest.raises(TempoNormativoAusenteError):
        eng.resolver_ano_referencia({})


@pytest.mark.parametrize("caminho", ENGINES_EM_ESCOPO)
def test_engine_usa_resolver_ano_referencia(caminho):
    src = Path(caminho).read_text(encoding="utf-8")
    assert "resolver_ano_referencia" in src, f"{caminho} não chama resolver_ano_referencia"


def test_mei_engine_delega_contexto_integral_ao_motor_canonico():
    execute = _metodo_da_classe(
        "app/services/tax_engines/mei_engine.py", "MEIEngine", "execute"
    )
    chamadas = [node for node in ast.walk(execute) if isinstance(node, ast.Call)]

    delegacoes = [
        node
        for node in chamadas
        if isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
        and isinstance(node.func.value, ast.Call)
        and isinstance(node.func.value.func, ast.Name)
        and node.func.value.func.id == "MEITaxEngine"
        and not node.func.value.args
        and not node.func.value.keywords
    ]

    assert len(delegacoes) == 1
    delegacao = delegacoes[0]
    assert len(delegacao.args) == 1
    assert isinstance(delegacao.args[0], ast.Name)
    assert delegacao.args[0].id == "context"
    assert not delegacao.keywords
    assert not {
        "obter_salario_minimo",
        "calcular_das_mei",
    }.intersection(_nome_chamada(node) for node in chamadas)


def test_mei_tax_engine_resolve_tempo_antes_da_autoridade_e_do_calculo():
    execute = _metodo_da_classe(
        "app/services/tax_engines/mei_tax_engine.py", "MEITaxEngine", "execute"
    )
    chamadas = [node for node in ast.walk(execute) if isinstance(node, ast.Call)]
    por_nome = {
        nome: [node for node in chamadas if _nome_chamada(node) == nome]
        for nome in (
            "resolver_data_referencia_mei",
            "_exigir_autoridade_normativa_mei",
            "obter_salario_minimo",
            "calcular_das_mei",
        )
    }

    assert all(len(nodes) == 1 for nodes in por_nome.values())
    resolver = por_nome["resolver_data_referencia_mei"][0]
    posicao_resolver = (resolver.lineno, resolver.col_offset)
    for nome in (
        "_exigir_autoridade_normativa_mei",
        "obter_salario_minimo",
        "calcular_das_mei",
    ):
        chamada = por_nome[nome][0]
        assert posicao_resolver < (chamada.lineno, chamada.col_offset)


def test_cpf_engine_fora_do_escopo_nao_herda_base():
    src = Path("app/services/tax_engines/cpf_engine.py").read_text(encoding="utf-8")
    assert "BaseTaxEngine" not in src


def test_insights_engine_converte_erro_temporal_em_bloqueio_l3():
    src = Path("app/services/insights_engine.py").read_text(encoding="utf-8")
    assert "TempoNormativoAusenteError" in src
    assert "TEMPO_NORMATIVO_AUSENTE" in src
    assert '"estado_l3": "bloqueado"' in src or "'estado_l3': 'bloqueado'" in src
