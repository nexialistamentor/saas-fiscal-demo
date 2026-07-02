"""
B13-OPS-13D Fase 1 — Sentinelas estáticas L3 de tempo normativo.

Prova estática e comportamental que:
1. Engines fiscais do registry não têm ano_vigencia hardcoded.
2. date.today()/datetime.now() não aparecem em módulos de cálculo fiscal normativo.
3. buscar_mva(), buscar_pmpf(), resolver_base_calculo_st() não usam fallback temporal.
4. calcular_imposto_simples() e calcular_imposto_simples_nacional() exigem ano_referencia.
5. analysis_orchestrator.py não engole TempoNormativoAusenteError no except Exception.
6. Endpoints temporais expõem ano_referencia/data_referencia no schema ou tratamento equivalente.
7. Fontes com pode_fundamentar_decisao=false não aparecem como cálculo definitivo.
8. Parsers normativos não inventam vigência normativa com date.today().

IMPORTANTE: estes testes não alteram comportamento.
São invariantes de regressão L3 — detectam reintrodução de bypass temporal.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.services.engine_registry import ENGINES
from app.services.tax_engines.base_tax_engine import (
    BaseTaxEngine,
    TempoNormativoAusenteError,
)

MANIFEST_PATH = Path("data/fontes_tributarias_manifest.json")

# Módulos sujeitos à proibição de date.today()/datetime.now() em cálculo normativo.
MODULOS_CALCULO_NORMATIVO = [
    "app/services/imposto_service.py",
    "app/services/fiscal_utils.py",
    "app/services/st_service.py",
    "app/services/regime_engine.py",
    "app/services/tabela_normativa_service.py",
    "app/motor_fiscal.py",
]

TAX_ENGINES_DIR = Path("app/services/tax_engines")

# Allowlist explícita — uso operacional permitido (não é cálculo normativo).
ALLOWLIST_TEMPORAL_OPERACIONAL = (
    "app/services/parsers/",
    "app/services/normative_update_service.py",
    "app/services/atualizacao_normativa_service.py",
    "app/agents/normative_watchdog_agent.py",
    "app/agents/normative_validation_agent.py",
    "app/services/assistente_service.py",
)

PADROES_TEMPO_PROIBIDO = (
    re.compile(r"\bdate\.today\s*\("),
    re.compile(r"\bdatetime\.now\s*\("),
)

PADROES_ANO_VIGENCIA_HARDCODED = (
    re.compile(r"\bano_vigencia\s*=\s*\d{4}\b"),
    re.compile(r"\bano_vigencia\s*:\s*\d{4}\b"),
)

PADROES_FALLBACK_TEMPORAL = (
    re.compile(r"data_referencia\s*=\s*date\.today\s*\("),
    re.compile(r"data_referencia\s*=\s*datetime\.now\s*\("),
    re.compile(r"if\s+data_referencia\s+is\s+None\s*:\s*\n\s*data_referencia\s*=\s*date\.today"),
    re.compile(r"if\s+data_referencia\s+is\s+None\s*:\s*\n\s*data_referencia\s*=\s*datetime"),
    re.compile(r"or\s+date\.today\s*\(\)"),
    re.compile(r"or\s+datetime\.now\s*\(\)"),
)

FONTES_REFORMA_BLOQUEADAS = (
    "EC132-001",
    "LC214-001",
    "CBS-IBS-2026-001",
    "IMP-SELETIVO-001",
)

ENDPOINTS_TEMPORAIS = (
    ("app/routes/imposto_router.py", "/imposto/simples-nacional", "SimplesNacionalRequest"),
    ("app/routes/imposto_router.py", "/imposto/calcular", "DadosImposto"),
    ("app/routes/cpf_router.py", "/cpf/dashboard", "CPFRequest"),
)


def _ler_source(caminho: str | Path) -> str:
    p = Path(caminho)
    assert p.exists(), f"Ficheiro não encontrado: {p}"
    return p.read_text(encoding="utf-8")


def _ficheiros_tax_engines_registry() -> list[Path]:
    """Ficheiros .py das engines registadas em engine_registry.ENGINES."""
    caminhos: set[Path] = set()
    for engine in ENGINES.values():
        mod = inspect.getmodule(engine.__class__)
        if mod and mod.__file__:
            caminhos.add(Path(mod.__file__))
    return sorted(caminhos)


def _ficheiros_calculo_normativo() -> list[Path]:
    ficheiros: list[Path] = []
    for rel in MODULOS_CALCULO_NORMATIVO:
        p = Path(rel)
        if p.is_file():
            ficheiros.append(p)
    if TAX_ENGINES_DIR.is_dir():
        ficheiros.extend(sorted(TAX_ENGINES_DIR.glob("*.py")))
    return ficheiros


def _esta_na_allowlist_operacional(caminho: Path) -> bool:
    normalizado = caminho.as_posix()
    return any(normalizado.startswith(prefix) or normalizado == prefix.rstrip("/")
               for prefix in ALLOWLIST_TEMPORAL_OPERACIONAL)


def _carregar_manifest() -> list[dict]:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return json.load(f)["fontes"]


# ---------------------------------------------------------------------------
# 1. Engines fiscais do registry — sem ano_vigencia hardcoded
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("caminho", _ficheiros_tax_engines_registry(), ids=lambda p: p.name)
def test_sentinela_01_engine_registry_sem_ano_vigencia_hardcoded(caminho: Path):
    source = caminho.read_text(encoding="utf-8")
    for padrao in PADROES_ANO_VIGENCIA_HARDCODED:
        match = padrao.search(source)
        assert match is None, (
            f"SENTINELA-01 violada em {caminho}: ano_vigencia hardcoded ({match.group()})"
        )


def test_sentinela_01_base_tax_engine_sem_ano_vigencia_fixo():
    source = _ler_source("app/services/tax_engines/base_tax_engine.py")
    assert "ano_vigencia" not in source, (
        "SENTINELA-01: base_tax_engine ainda expõe ano_vigencia fixo"
    )


@pytest.mark.parametrize("caminho", _ficheiros_tax_engines_registry(), ids=lambda p: p.name)
def test_sentinela_01_engine_registry_usa_resolver_ano_referencia(caminho: Path):
    source = caminho.read_text(encoding="utf-8")
    if "def execute" not in source:
        pytest.skip(f"{caminho.name} não implementa execute()")
    assert "resolver_ano_referencia" in source, (
        f"SENTINELA-01: {caminho} não usa resolver_ano_referencia() em execute()"
    )


@pytest.mark.parametrize("nome, engine", list(ENGINES.items()))
def test_sentinela_01_execute_bloqueia_sem_contexto_temporal(nome, engine):
    with pytest.raises(TempoNormativoAusenteError):
        engine.execute({})


# ---------------------------------------------------------------------------
# 2. date.today()/datetime.now() proibidos em cálculo fiscal normativo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("caminho", _ficheiros_calculo_normativo(), ids=lambda p: p.name)
def test_sentinela_02_sem_date_today_em_calculo_normativo(caminho: Path):
    if _esta_na_allowlist_operacional(caminho):
        pytest.skip("allowlist operacional")
    source = caminho.read_text(encoding="utf-8")
    for padrao in PADROES_TEMPO_PROIBIDO:
        for match in padrao.finditer(source):
            linha = source[: match.start()].count("\n") + 1
            pytest.fail(
                f"SENTINELA-02 violada em {caminho}:{linha}: "
                f"{match.group()} proibido em cálculo fiscal normativo"
            )


# ---------------------------------------------------------------------------
# 3. buscar_mva / buscar_pmpf / resolver_base_calculo_st — sem fallback temporal
# ---------------------------------------------------------------------------

def test_sentinela_03_buscar_mva_exige_data_referencia():
    from app.database import SessionLocal
    from app.services.tabela_normativa_service import buscar_mva

    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            buscar_mva(db, "SP", "12345678", data_referencia=None)
    finally:
        db.close()


def test_sentinela_03_buscar_pmpf_exige_data_referencia():
    from app.database import SessionLocal
    from app.services.tabela_normativa_service import buscar_pmpf

    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            buscar_pmpf(db, "SP", "12345678", data_referencia=None)
    finally:
        db.close()


def test_sentinela_03_resolver_base_calculo_st_exige_data_referencia():
    from app.database import SessionLocal
    from app.services.tabela_normativa_service import resolver_base_calculo_st

    db = SessionLocal()
    try:
        with pytest.raises(TempoNormativoAusenteError):
            resolver_base_calculo_st(
                db, "SP", "12345678", valor_produto=100.0, data_referencia=None
            )
    finally:
        db.close()


def test_sentinela_03_tabela_normativa_sem_fallback_temporal_estatico():
    source = _ler_source("app/services/tabela_normativa_service.py")
    for padrao in PADROES_FALLBACK_TEMPORAL:
        assert not padrao.search(source), (
            "SENTINELA-03: tabela_normativa_service contém fallback temporal "
            f"({padrao.pattern})"
        )
    assert "_exigir_data_referencia_normativa" in source
    for func in ("buscar_mva", "buscar_pmpf", "resolver_base_calculo_st"):
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == func:
                func_source = ast.get_source_segment(source, node) or ""
                assert "_exigir_data_referencia_normativa" in func_source, (
                    f"SENTINELA-03: {func}() não chama _exigir_data_referencia_normativa"
                )


# ---------------------------------------------------------------------------
# 4. calcular_imposto_simples / calcular_imposto_simples_nacional — ano_referencia
# ---------------------------------------------------------------------------

def test_sentinela_04_calcular_imposto_simples_mei_exige_ano_referencia():
    from app.services.imposto_service import calcular_imposto_simples

    with pytest.raises(TempoNormativoAusenteError):
        calcular_imposto_simples(faturamento=5000.0, tipo="MEI")


def test_sentinela_04_calcular_imposto_simples_nacional_exige_ano_referencia():
    from app.services.imposto_service import calcular_imposto_simples_nacional

    with pytest.raises(TempoNormativoAusenteError):
        calcular_imposto_simples_nacional(rbt12=360_000.0, anexo="I")


def test_sentinela_04_assinaturas_exigem_ano_referencia():
    from app.services import imposto_service

    sig_simples = inspect.signature(imposto_service.calcular_imposto_simples)
    sig_sn = inspect.signature(imposto_service.calcular_imposto_simples_nacional)
    assert "ano_referencia" in sig_simples.parameters
    assert "ano_referencia" in sig_sn.parameters


def test_sentinela_04_guards_tempo_normativo_no_codigo():
    source = _ler_source("app/services/imposto_service.py")
    assert "TempoNormativoAusenteError" in source
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "calcular_imposto_simples_nacional":
            func_source = ast.get_source_segment(source, node) or ""
            assert "if ano_referencia is None" in func_source
            assert "TempoNormativoAusenteError" in func_source
            return
    pytest.fail("calcular_imposto_simples_nacional não encontrada")


# ---------------------------------------------------------------------------
# 5. analysis_orchestrator — TempoNormativoAusenteError não engolido
# ---------------------------------------------------------------------------

def _handler_tipo(handler: ast.ExceptHandler) -> str | None:
    if handler.type is None:
        return "bare"
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Attribute):
        return handler.type.attr
    return None


def _handler_faz_raise(handler: ast.ExceptHandler) -> bool:
    for stmt in handler.body:
        if isinstance(stmt, ast.Raise):
            return True
    return False


def test_sentinela_05_orchestrator_nao_engole_tempo_normativo_ausente():
    source = _ler_source("app/services/analysis_orchestrator.py")
    tree = ast.parse(source)
    violacoes: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        handlers = node.handlers
        tipos = [_handler_tipo(h) for h in handlers]
        if "Exception" not in tipos:
            continue
        idx_tempo = tipos.index("TempoNormativoAusenteError") if "TempoNormativoAusenteError" in tipos else -1
        idx_exc = tipos.index("Exception")
        if idx_tempo < 0:
            violacoes.append(
                f"linha {node.lineno}: except Exception sem handler TempoNormativoAusenteError"
            )
            continue
        if idx_tempo > idx_exc:
            violacoes.append(
                f"linha {node.lineno}: TempoNormativoAusenteError deve preceder except Exception"
            )
            continue
        handler_tempo = handlers[idx_tempo]
        if not _handler_faz_raise(handler_tempo):
            violacoes.append(
                f"linha {handler_tempo.lineno}: handler TempoNormativoAusenteError não faz raise"
            )

    assert not violacoes, "SENTINELA-05 violada:\n" + "\n".join(violacoes)


# ---------------------------------------------------------------------------
# 6. Endpoints temporais — schema ou tratamento equivalente
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ficheiro, rota, schema", ENDPOINTS_TEMPORAIS)
def test_sentinela_06_endpoint_expoe_campo_temporal(ficheiro, rota, schema):
    source = _ler_source(ficheiro)
    assert schema in source, f"SENTINELA-06: schema {schema} ausente em {ficheiro}"
    idx = source.find(f"class {schema}")
    trecho = source[idx : idx + 1200]
    assert "ano_referencia" in trecho or "data_referencia" in trecho, (
        f"SENTINELA-06: {schema} em {ficheiro} não expõe ano_referencia/data_referencia"
    )
    assert "TempoNormativoAusenteError" in source, (
        f"SENTINELA-06: {ficheiro} não trata TempoNormativoAusenteError"
    )
    assert "TEMPO_NORMATIVO_AUSENTE" in source, (
        f"SENTINELA-06: {ficheiro} não devolve tipo_bloqueio TEMPO_NORMATIVO_AUSENTE"
    )


# ---------------------------------------------------------------------------
# 7. Manifesto pode_fundamentar_decisao=false — não cálculo definitivo
# ---------------------------------------------------------------------------

def test_sentinela_07_fontes_reforma_nao_referenciadas_em_calculo():
    app_py = list(Path("app").rglob("*.py"))
    violacoes: list[str] = []
    for caminho in app_py:
        source = caminho.read_text(encoding="utf-8")
        for fonte_id in FONTES_REFORMA_BLOQUEADAS:
            if fonte_id in source:
                violacoes.append(f"{caminho}: referencia {fonte_id}")
    assert not violacoes, (
        "SENTINELA-07: fontes em_revisao/reforma não podem aparecer em código de cálculo:\n"
        + "\n".join(violacoes)
    )


def test_sentinela_07_simples_nacional_nao_apresenta_calculo_definitivo():
    from app.services.imposto_service import calcular_imposto_simples_nacional

    resultado = calcular_imposto_simples_nacional(
        rbt12=360_000.0, anexo="I", ano_referencia=2026
    )
    alertas = resultado.get("alertas") or []
    texto_alertas = " ".join(alertas).lower()
    assert alertas, "SENTINELA-07: Simples Nacional deve expor alertas (não é cálculo definitivo)"
    assert any(
        termo in texto_alertas
        for termo in ("estimado", "pendente", "validação", "validacao")
    ), "SENTINELA-07: alertas devem indicar carácter não-definitivo"


def test_sentinela_07_fontes_nao_fundamentaveis_marcadas_no_manifesto():
    fontes = _carregar_manifest()
    for fonte_id in FONTES_REFORMA_BLOQUEADAS:
        fonte = next((f for f in fontes if f["id"] == fonte_id), None)
        assert fonte is not None, f"SENTINELA-07: {fonte_id} ausente do manifesto"
        assert fonte["pode_fundamentar_decisao"] is False, (
            f"SENTINELA-07: {fonte_id} não pode fundamentar decisão"
        )
        assert fonte["status"] in ("em_revisao", "descontinuada", "substituida"), (
            f"SENTINELA-07: {fonte_id} deve estar bloqueada no manifesto"
        )


def test_sentinela_07_resposta_sem_calculo_autorizado_definitivo_com_fonte_bloqueada():
    """Respostas de imposto não devem expor calculo_autorizado=True sem resolvedor soberano."""
    from app.services.imposto_service import calcular_imposto_simples_nacional

    resultado = calcular_imposto_simples_nacional(
        rbt12=360_000.0, anexo="I", ano_referencia=2026
    )
    assert resultado.get("calculo_autorizado") is not True, (
        "SENTINELA-07: Simples Nacional não pode expor calculo_autorizado=True "
        "com fontes pode_fundamentar_decisao=false"
    )
    assert "calculo_definitivo" not in resultado, (
        "SENTINELA-07: campo calculo_definitivo proibido sem fonte autorizada"
    )


def test_sentinela_07_resolver_ano_referencia_com_data():
    eng = BaseTaxEngine()
    assert eng.resolver_ano_referencia({"data_referencia": date(2026, 6, 15)}) == 2026


# ---------------------------------------------------------------------------
# 8. Parsers normativos — vigência não inventada por date.today()
# ---------------------------------------------------------------------------

def test_sentinela_08_parsers_nao_inventam_vigencia_com_data_de_hoje():
    """
    B13-OPS-13E.3: parsers normativos podem usar date.today() para data_consulta
    (metadado operacional), mas nunca para preencher vigencia_inicio/vigencia_fim/
    data_referencia normativa.
    """
    parsers = [
        "app/services/parsers/sefaz_mg_parser.py",
        "app/services/parsers/sefaz_mg_pdf_parser.py",
        "app/services/parsers/sefaz_sp_parser.py",
        "app/services/parsers/dou_dados_abertos_parser.py",
        "app/services/parsers/dou_parser.py",
    ]
    padroes_proibidos = [
        re.compile(r"vigencia_inicio\s*=\s*date\.today\(\)"),
        re.compile(r"vigencia_fim\s*=\s*date\.today\(\)"),
        re.compile(r"vigencia_inicio\s*or\s*date\.today\(\)"),
        re.compile(r"vigencia_fim\s*or\s*date\.today\(\)"),
        re.compile(r"data_referencia\s*=\s*date\.today\(\)"),
    ]
    for caminho in parsers:
        src = Path(caminho).read_text(encoding="utf-8")
        for padrao in padroes_proibidos:
            assert not padrao.search(src), (
                f"{caminho} contém padrão proibido: {padrao.pattern} "
                f"— vigência normativa não pode ser inventada por date.today()"
            )
