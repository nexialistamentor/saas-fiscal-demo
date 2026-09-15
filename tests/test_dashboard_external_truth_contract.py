import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard" / "src" / "App.jsx"
EMPRESA_HOOK = ROOT / "frontend-dashboard" / "src" / "hooks" / "useEmpresaDashboard.js"
PDF_SERVICE = ROOT / "app" / "services" / "pdf_report_service.py"
MAPA_SERVICE = ROOT / "app" / "services" / "mapa_oportunidades_service.py"
INSIGHTS_ENGINE = ROOT / "app" / "services" / "insights_engine.py"


def test_dashboard_does_not_use_fictitious_evolution_series():
    app = APP.read_text(encoding="utf-8")
    fictitious_series = r"P1[\s\S]*?20[\s\S]*?P2[\s\S]*?35[\s\S]*?P3[\s\S]*?30[\s\S]*?P4[\s\S]*?48[\s\S]*?P5[\s\S]*?52"

    assert not re.search(fictitious_series, app)


def test_score_global_is_not_renamed_as_recuperacao():
    app = APP.read_text(encoding="utf-8")

    assert not re.search(r"\brecuperacao\s*:\s*item\.score_global\b", app)


def test_missing_risco_tributario_percentual_remains_unavailable():
    hook = EMPRESA_HOOK.read_text(encoding="utf-8")
    risco_assignment = re.search(
        r"\bconst\s+risco\s*=\s*(?P<value>.*?)(?=\bconst\s+pontuacao\b)",
        hook,
        flags=re.DOTALL,
    )

    assert risco_assignment is not None
    assert "?? 0" not in risco_assignment.group("value")
    assert "-1" in risco_assignment.group("value")


def test_pdf_does_not_present_score_global_as_tax_score():
    pdf_service = PDF_SERVICE.read_text(encoding="utf-8")

    assert not re.search(
        r"score\s*=\s*relatorio\.get\([\"']score_global[\"']\)[\s\S]{0,300}Score tribut.rio",
        pdf_service,
    )


def test_ncm_distribution_surface_is_not_backed_by_hardcoded_empty_data():
    app = APP.read_text(encoding="utf-8")
    hardcoded_empty_ncm = re.search(r"\bconst\s+dadosNCM\s*=\s*\[\s*\]", app)
    ncm_distribution_surface = re.search(
        r"Distribui..o por NCM[\s\S]{0,1500}data\s*=\s*\{dadosNCM\}",
        app,
    )

    assert not (hardcoded_empty_ncm and ncm_distribution_surface)


def test_empresa_mixed_impact_is_not_presented_as_recoverable_estimate():
    app = APP.read_text(encoding="utf-8")
    hook = EMPRESA_HOOK.read_text(encoding="utf-8")
    mapa_service = MAPA_SERVICE.read_text(encoding="utf-8")

    backend_aggregates_direct_and_estimated_impact = (
        "TIPOS_IMPACTO_DIRETO" in mapa_service
        and "TIPOS_IMPACTO_ESTIMADO" in mapa_service
        and re.search(
            r'mapa\[["\']impacto_financeiro_anual["\']\]\s*\+=\s*valor'
            r'[\s\S]{0,300}?tipo\s+in\s+TIPOS_IMPACTO_DIRETO'
            r'[\s\S]{0,300}?tipo\s+in\s+TIPOS_IMPACTO_ESTIMADO',
            mapa_service,
        )
        and '"valor_recuperavel_real"' in mapa_service
        and '"valor_estimado"' in mapa_service
    )
    mixed_total_reaches_impacto = re.search(
        r'\bconst\s+impacto\s*=\s*data\?\.impacto_financeiro_anual'
        r'\s*\?\?\s*\(data\?\.restituicao_st\s*\?\?\s*0\)\s*\*\s*12',
        hook,
    )
    profile_copy = re.search(
        r'tipoPerfil\s*===\s*["\']cpf["\']\s*'
        r'\?\s*["\']IRPF Estimado Anual["\']\s*'
        r':\s*["\']Impacto Financeiro Anual["\']'
        r'[\s\S]{0,300}?\bimpacto\b'
        r'[\s\S]{0,300}?tipoPerfil\s*===\s*["\']cpf["\']\s*'
        r'\?\s*["\']Imposto de renda estimado no ano["\']\s*'
        r':\s*["\']Valor recuper.vel estimado no ano["\']',
        app,
    )

    assert re.search(
        r'tipoPerfil\s*===\s*["\']cpf["\']\s*'
        r'\?\s*["\']IRPF Estimado Anual["\']',
        app,
    ), "O caminho CPF deve permanecer coberto como IRPF Estimado Anual"
    assert not (
        backend_aggregates_direct_and_estimated_impact
        and mixed_total_reaches_impacto
        and profile_copy
    ), (
        "EMPRESA não pode apresentar impacto_financeiro_anual misto como "
        "Valor recuperável estimado no ano"
    )


def test_unvalidated_global_score_is_not_surfaced_as_fiscal_score_out_of_100():
    app = APP.read_text(encoding="utf-8")
    hook = EMPRESA_HOOK.read_text(encoding="utf-8")
    mapa_service = MAPA_SERVICE.read_text(encoding="utf-8")

    legacy_score_derivation = re.search(
        r"score_data\s*=\s*calcular_score_global_tributario\([^)]*\)"
        r"[\s\S]{0,300}?score_raw\s*=\s*score_data\.get\([\"']score_global_tributario[\"']"
        r"[\s\S]{0,300}?mapa\[[\"']pontuacao_fiscal[\"']\]\s*=\s*normalizar_pontuacao\(score_raw\)",
        mapa_service,
    )
    backend_value_reaches_card = re.search(
        r"\bconst\s+pontuacao\s*=\s*[^\n]*data\.pontuacao_fiscal",
        hook,
    )
    commercial_score_card = re.search(
        r"id\s*:\s*[\"']pontuacao-fiscal[\"']"
        r"[\s\S]{0,300}?titulo\s*:\s*[\"']Pontua..o Fiscal[\"']"
        r"[\s\S]{0,300}?valor\s*:\s*[^\n]*pontuacao[^\n]*/100",
        app,
    )

    assert not (
        legacy_score_derivation
        and backend_value_reaches_card
        and commercial_score_card
    ), "Pontuação Fiscal /100 não pode derivar de score_global_tributario sem metodologia validada"


def test_estimated_st_restitution_is_not_presented_as_recovered_value():
    app = APP.read_text(encoding="utf-8")
    mapa_service = MAPA_SERVICE.read_text(encoding="utf-8")
    insights_engine = INSIGHTS_ENGINE.read_text(encoding="utf-8")

    estimated_sources = (
        re.search(
            r'["\']tipo["\']\s*:\s*["\']PRODUTO_COM_RESTITUICAO_RELEVANTE["\']'
            r'[\s\S]{0,300}?["\']valor_estimado["\']\s*:\s*item\[["\']restituicao_estimada["\']\]',
            insights_engine,
        )
        and re.search(
            r'["\']tipo["\']\s*:\s*["\']ST_RESTITUICAO["\']'
            r'[\s\S]{0,300}?["\']valor_estimado["\']\s*:\s*round\(restituicao_estimada\s*,\s*2\)'
            r'[\s\S]{0,300}?Poss.vel restitui..o de ST estimada',
            insights_engine,
        )
    )
    estimated_sources_feed_restituicao_st = re.search(
        r'if\s+tipo\s+in\s*\(\s*["\']PRODUTO_COM_RESTITUICAO_RELEVANTE["\']\s*,'
        r'\s*["\']ST_RESTITUICAO["\']\s*\)\s*:'
        r'[\s\S]{0,150}?mapa\[["\']restituicao_st["\']\]\s*\+=\s*valor',
        mapa_service,
    )
    simple_recovery_card = re.search(
        r'id\s*:\s*["\']restituicao-st["\']'
        r'[\s\S]{0,200}?titulo\s*:\s*["\']Recupera..o["\']'
        r'[\s\S]{0,200}?valor\s*:\s*[^\n]*data\?\.restituicao_st',
        app,
    )

    assert not (
        estimated_sources
        and estimated_sources_feed_restituicao_st
        and simple_recovery_card
    ), "Restituição ST estimada não pode ser apresentada externamente como Recuperação"
