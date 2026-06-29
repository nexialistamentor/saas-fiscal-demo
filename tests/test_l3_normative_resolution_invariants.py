"""
B13-OPS-08 — Invariantes L3 de Resolução Normativa.

Prova estática que:
1. resolver_aliquota_e_mva() existe e expõe calculo_autorizado.
2. buscar_mva() directo não garante calculo_autorizado.
3. decidir_acao_st() é puro — não resolve fonte por si próprio.
4. Os caminhos limpos usam o resolvedor soberano.
5. Os bypasses conhecidos estão documentados como risco formal.

IMPORTANTE: estes testes não alteram comportamento.
São invariantes de regressão L3 — detectam se o bypass for removido
ou se novos bypasses forem introduzidos.
"""
import ast
import inspect
from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Helpers de análise estática
# ---------------------------------------------------------------------------

def _ler_source(caminho_relativo: str) -> str:
    p = Path(caminho_relativo)
    assert p.exists(), f"Ficheiro não encontrado: {p}"
    return p.read_text(encoding="utf-8")


def _chamadas_em_source(source: str, nome_funcao: str) -> list[int]:
    """Devolve linhas onde nome_funcao() é chamada."""
    tree = ast.parse(source)
    linhas = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == nome_funcao:
                linhas.append(node.lineno)
            elif isinstance(node.func, ast.Attribute) and node.func.attr == nome_funcao:
                linhas.append(node.lineno)
    return linhas


# ---------------------------------------------------------------------------
# 1. Resolvedor soberano existe e expõe contrato correcto
# ---------------------------------------------------------------------------

def test_resolvedor_soberano_existe():
    from app.services.fiscal_utils import resolver_aliquota_e_mva
    assert callable(resolver_aliquota_e_mva)


def test_resolvedor_soberano_expoe_calculo_autorizado():
    """resolver_aliquota_e_mva devolve dict com calculo_autorizado."""
    source = _ler_source("app/services/fiscal_utils.py")
    assert "calculo_autorizado" in source, \
        "fiscal_utils.py não contém calculo_autorizado — contrato violado"


def test_resolvedor_soberano_expoe_calculo_parcial():
    source = _ler_source("app/services/fiscal_utils.py")
    assert "calculo_parcial" in source, \
        "fiscal_utils.py não contém calculo_parcial — contrato violado"


# ---------------------------------------------------------------------------
# 2. Motor de decisão fiscal é puro
# ---------------------------------------------------------------------------

def test_motor_decisao_nao_chama_buscar_mva():
    """motor_decisao_tributaria.py não deve chamar buscar_mva() directamente."""
    source = _ler_source("app/services/motor_decisao_tributaria.py")
    assert "buscar_mva" not in source, \
        "INVARIANTE-NR-01 violado: motor_decisao_tributaria chama buscar_mva() directamente"


def test_motor_decisao_nao_importa_tabela_normativa():
    """motor_decisao_tributaria.py não deve importar tabela_normativa_service."""
    source = _ler_source("app/services/motor_decisao_tributaria.py")
    assert "tabela_normativa_service" not in source, \
        "motor_decisao_tributaria não deve aceder directamente à camada normativa"


def test_motor_decisao_nao_chama_resolver():
    """motor_decisao_tributaria.py deve ser puro — não resolve, só decide."""
    source = _ler_source("app/services/motor_decisao_tributaria.py")
    assert "resolver_aliquota_e_mva" not in source, \
        "motor_decisao_tributaria não deve resolver — recebe valores já resolvidos"


# ---------------------------------------------------------------------------
# 3. Caminhos limpos usam resolvedor soberano
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("caminho", [
    "app/services/detector_creditos_service.py",
    "app/services/motor_preditivo_service.py",
    "app/services/ranking_restituicao_service.py",
    "app/services/analisador_distorcao_service.py",
])
def test_servico_usa_resolvedor_soberano(caminho):
    source = _ler_source(caminho)
    assert "resolver_aliquota_e_mva" in source, \
        f"{caminho} não usa resolver_aliquota_e_mva() — caminho não autorizado"


@pytest.mark.parametrize("caminho", [
    "app/services/detector_creditos_service.py",
    "app/services/motor_preditivo_service.py",
    "app/services/ranking_restituicao_service.py",
])
def test_servico_verifica_calculo_autorizado(caminho):
    source = _ler_source(caminho)
    assert "calculo_autorizado" in source, \
        f"{caminho} não verifica calculo_autorizado — bypass potencial"


# ---------------------------------------------------------------------------
# 4. Bypass BYPASS-01 documentado (insights_engine linha ~840)
# ---------------------------------------------------------------------------

def test_bypass_01_eliminado_insights_engine():
    """
    B13-OPS-09: _analisar_decisao_st não chama buscar_mva() directamente.
    BYPASS-01 foi eliminado.
    """
    source = _ler_source("app/services/insights_engine.py")
    # Verificar que _analisar_decisao_st não contém chamada directa a buscar_mva
    # O método termina antes de decidir_acao_st se não houver calculo_autorizado
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_analisar_decisao_st":
            func_source = ast.get_source_segment(source, node)
            assert "buscar_mva" not in func_source, \
                "BYPASS-01 reintroduzido: _analisar_decisao_st chama buscar_mva() directamente"
            assert "resolver_aliquota_e_mva" in func_source, \
                "BYPASS-01 não eliminado: _analisar_decisao_st não usa resolver_aliquota_e_mva()"
            assert "calculo_autorizado" in func_source, \
                "_analisar_decisao_st não verifica calculo_autorizado"
            assert "calculo_parcial" in func_source, \
                "_analisar_decisao_st não verifica calculo_parcial"
            return
    pytest.fail("Método _analisar_decisao_st não encontrado em insights_engine.py")


def test_bypass_01_resolvedor_soberano_em_insights():
    """
    B13-OPS-09: insights_engine usa resolver_aliquota_e_mva em _analisar_decisao_st.
    """
    source = _ler_source("app/services/insights_engine.py")
    assert "resolver_aliquota_e_mva" in source, \
        "insights_engine não importa resolver_aliquota_e_mva"


# ---------------------------------------------------------------------------
# 5. Bypass BYPASS-02 documentado (motor_fiscal legacy)
# ---------------------------------------------------------------------------

def test_bypass_02_documentado_motor_fiscal():
    """
    BYPASS-02: motor_fiscal.carregar_mva() chama buscar_mva() directamente.
    Legacy — P2. Não alimenta decidir_acao_st() directamente.
    """
    source = _ler_source("app/motor_fiscal.py")
    assert "buscar_mva" in source, \
        "BYPASS-02 legacy foi eliminado — verificar se carregar_mva() foi refactorizado"


# ---------------------------------------------------------------------------
# 6. decidir_acao_st() só tem 1 caller (insights_engine)
# ---------------------------------------------------------------------------

def test_decidir_acao_st_caller_unico():
    """
    decidir_acao_st() deve ser chamado apenas por insights_engine.
    Se aparecer noutro ficheiro, é novo ponto de risco.
    """
    callers = []
    for py in Path("app").rglob("*.py"):
        source = py.read_text(encoding="utf-8")
        if "decidir_acao_st" in source and "def decidir_acao_st" not in source:
            callers.append(str(py))

    assert callers == ["app\\services\\insights_engine.py"] or \
           callers == ["app/services/insights_engine.py"], \
        f"decidir_acao_st() tem callers inesperados: {callers} — novo bypass potencial"
