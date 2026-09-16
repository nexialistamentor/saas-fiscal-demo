import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "frontend-dashboard" / "src" / "App.jsx"
EMPRESA_HOOK = ROOT / "frontend-dashboard" / "src" / "hooks" / "useEmpresaDashboard.js"
PDF_SERVICE = ROOT / "app" / "services" / "pdf_report_service.py"
MAPA_SERVICE = ROOT / "app" / "services" / "mapa_oportunidades_service.py"
INSIGHTS_ENGINE = ROOT / "app" / "services" / "insights_engine.py"
TENDENCIA_SERVICE = ROOT / "app" / "services" / "tendencia_inteligencia_service.py"


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


def test_missing_estimated_st_restitution_is_not_presented_as_monetary_zero():
    app = APP.read_text(encoding="utf-8")
    st_card = re.search(
        r'\{\s*id\s*:\s*["\']restituicao-st["\']'
        r'[\s\S]*?titulo\s*:\s*["\']Valor estimado de ST para an.lise["\']'
        r'(?P<body>[\s\S]*?)\n\s*\},',
        app,
    )

    assert st_card is not None
    st_card_body = st_card.group("body")
    st_value = r"data\?\.restituicao_st"

    assert re.search(st_value, st_card_body), (
        "O cartão ST deve continuar ligado ao valor externo de restituição estimada"
    )
    assert not re.search(
        rf'{st_value}[\s\S]{{0,100}}?(?:\?\?|\|\|)\s*0\b',
        st_card_body,
    ), "Ausência de restituição ST não pode ser convertida silenciosamente em zero monetário"
    assert not re.search(
        rf'(?:!\s*{st_value}|{st_value}\s*(?:\?(?!\?)|&&|\|\|))',
        st_card_body,
    ), "Zero legítimo de restituição ST não pode ser confundido com ausência por truthiness"

    nullish_comparison = re.search(
        rf'{st_value}\s*(?:==|!=)\s*null\b',
        st_card_body,
    )
    nullish_coalescing = re.search(rf'{st_value}\s*\?\?', st_card_body)
    strict_null = rf'{st_value}\s*===\s*null\b'
    strict_undefined = (
        rf'(?:{st_value}\s*===\s*undefined\b|'
        rf'typeof\s+{st_value}\s*===\s*["\']undefined["\'])'
    )
    strict_not_null = rf'{st_value}\s*!==\s*null\b'
    strict_not_undefined = (
        rf'(?:{st_value}\s*!==\s*undefined\b|'
        rf'typeof\s+{st_value}\s*!==\s*["\']undefined["\'])'
    )
    explicit_null_and_undefined = re.search(
        rf'(?:{strict_null}[\s\S]{{0,100}}?\|\|[\s\S]{{0,100}}?{strict_undefined}|'
        rf'{strict_undefined}[\s\S]{{0,100}}?\|\|[\s\S]{{0,100}}?{strict_null}|'
        rf'{strict_not_null}[\s\S]{{0,100}}?&&[\s\S]{{0,100}}?{strict_not_undefined}|'
        rf'{strict_not_undefined}[\s\S]{{0,100}}?&&[\s\S]{{0,100}}?{strict_not_null})',
        st_card_body,
    )

    assert nullish_comparison or nullish_coalescing or explicit_null_and_undefined, (
        "Indisponibilidade de restituição ST deve distinguir null/undefined do zero numérico"
    )


def test_empresa_missing_impact_is_not_presented_as_monetary_zero_in_hero():
    app = APP.read_text(encoding="utf-8")
    hook = EMPRESA_HOOK.read_text(encoding="utf-8")

    hook_fabricates_zero_for_missing_empresa_impact = re.search(
        r'\bconst\s+impacto\s*=\s*data\?\.impacto_financeiro_anual'
        r'\s*\?\?\s*\(data\?\.restituicao_st\s*\?\?\s*0\)\s*\*\s*12',
        hook,
    )
    empresa_hero = re.search(
        r'tipoPerfil\s*!==\s*["\']mei["\']\s*&&\s*'
        r'<section\s+className=["\']impacto-hero["\']>'
        r'(?P<body>[\s\S]{0,1500}?)</section>',
        app,
    )

    assert empresa_hero is not None
    hero_body = empresa_hero.group("body")
    hero_fabricates_money_zero = re.search(
        r'R\$\s*\{\s*\(\s*impacto\s*\?\?\s*0\s*\)'
        r'\.toLocaleString\(\s*["\']pt-BR["\']\s*\)',
        hero_body,
    )
    hero_distinguishes_missing_impact_from_zero = re.search(
        r'impacto\s*(?:==|!=)\s*null\b|impacto\s*\?\?',
        hero_body,
    ) and not re.search(
        r'(?:!\s*impacto\b|\bimpacto\s*(?:\?(?!\?)|&&|\|\|))',
        hero_body,
    )
    empresa_uses_canonical_missing_signals = (
        re.search(r'tipoPerfil\s*===\s*["\']empresa["\']', hero_body)
        and re.search(r'data\?\.context_flags\?\.dados_incompletos\s*===\s*true', hero_body)
        and re.search(r'data\?\.impacto_financeiro_anual\s*(?:==|!=)\s*null\b', hero_body)
        and re.search(r'data\?\.restituicao_st\s*(?:==|!=)\s*null\b', hero_body)
        and not re.search(
            r'(?:!\s*data\?\.(?:impacto_financeiro_anual|restituicao_st)\b|'
            r'data\?\.(?:impacto_financeiro_anual|restituicao_st)\s*'
            r'(?:\?(?!\?)|&&|\|\|))',
            hero_body,
        )
    )

    assert not hook_fabricates_zero_for_missing_empresa_impact or (
        empresa_uses_canonical_missing_signals
    ), (
        "A origem EMPRESA não pode fabricar zero quando impacto e restituição ST "
        "estão ausentes, salvo se o hero consultar diretamente os sinais canónicos"
    )
    assert (
        hero_distinguishes_missing_impact_from_zero
        and not hero_fabricates_money_zero
    ) or empresa_uses_canonical_missing_signals, (
        "O hero EMPRESA deve distinguir ausência/null de zero numérico real; "
        "corrigir somente o hook não torna a apresentação segura"
    )


def test_external_fiscal_intelligence_trend_is_not_derived_from_unvalidated_global_score():
    app = APP.read_text(encoding="utf-8")
    tendencia_service = TENDENCIA_SERVICE.read_text(encoding="utf-8")

    historical_global_score_delta = re.search(
        r'primeiro\s*=\s*historico\[0\]\[["\']score_global["\']\]'
        r'[\s\S]{0,200}?ultimo\s*=\s*historico\[-1\]\[["\']score_global["\']\]'
        r'[\s\S]{0,200}?variacao\s*=\s*ultimo\s*-\s*primeiro',
        tendencia_service,
    )
    current_threshold_classification = all(
        re.search(pattern, tendencia_service)
        for pattern in (
            r'variacao\s*>\s*30000[\s\S]{0,100}?["\']melhoria_forte["\']',
            r'variacao\s*>\s*5000[\s\S]{0,100}?["\']melhoria["\']',
            r'variacao\s*<\s*-30000[\s\S]{0,100}?["\']queda_forte["\']',
            r'variacao\s*<\s*-5000[\s\S]{0,100}?["\']queda["\']',
        )
    )
    external_trend_card = re.search(
        r'id\s*:\s*["\']tendencia-inteligencia["\']'
        r'[\s\S]{0,200}?titulo\s*:\s*["\']Tend.ncia da Intelig.ncia Fiscal["\']'
        r'[\s\S]{0,500}?tendencia\?\.tendencia\s*===\s*["\']melhoria_forte["\']'
        r'[\s\S]{0,500}?tendencia\?\.tendencia\s*===\s*["\']queda_forte["\']',
        app,
    )

    assert not (
        historical_global_score_delta
        and current_threshold_classification
        and external_trend_card
    ), (
        "Tendência da Inteligência Fiscal não pode ser exposta externamente quando "
        "derivada do histórico de score_global pelos limiares atuais"
    )


def test_raw_risk_with_arbitrary_normalization_is_not_exposed_as_percentage_or_severity():
    app = APP.read_text(encoding="utf-8")
    mapa_service = MAPA_SERVICE.read_text(encoding="utf-8")
    risco_service = (
        ROOT / "app" / "services" / "risco_tributario_service.py"
    ).read_text(encoding="utf-8")

    raw_risk_engine = (
        all(
            re.search(rf'sum\(item\[["\']{component}["\']\]\s+for\s+item\s+in', risco_service)
            for component in ("variacao_detectada", "distorcao", "credito_estimado")
        )
        and re.search(
            r"score_anomalias\s*\*\s*0\.4\s*\+"
            r"[\s\S]{0,100}?score_distorcoes\s*\*\s*0\.3\s*\+"
            r"[\s\S]{0,100}?score_creditos\s*\*\s*0\.3",
            risco_service,
        )
        and re.search(
            r"if\s+risco\s*>\s*100000\s*:[\s\S]{0,100}?nivel\s*=\s*[\"']alto[\"']"
            r"[\s\S]{0,100}?elif\s+risco\s*>\s*30000\s*:"
            r"[\s\S]{0,100}?nivel\s*=\s*[\"']medio[\"']"
            r"[\s\S]{0,100}?else\s*:[\s\S]{0,100}?nivel\s*=\s*[\"']baixo[\"']",
            risco_service,
        )
    )
    arbitrary_zero_to_one_hundred_normalization = (
        re.search(
            r"def\s+normalizar_risco\([^)]*\)[\s\S]{0,300}?"
            r"\(float\(score_risco_raw\)\s*/\s*1000(?:\.0)?\)\s*\*\s*100(?:\.0)?"
            r"[\s\S]{0,200}?max\(0(?:\.0)?,\s*min\([\s\S]{0,100}?,\s*100(?:\.0)?\)\)",
            mapa_service,
        )
        and re.search(
            r'mapa\[["\']risco_tributario_percentual["\']\]\s*=\s*'
            r"normalizar_risco\(risco_raw\)",
            mapa_service,
        )
    )
    external_percentage_and_severity = (
        re.search(
            r'titulo\s*:\s*["\']Risco Tribut.rio["\']'
            r"[\s\S]{0,150}?valor\s*:\s*risco\s*===\s*-1\s*\?"
            r'[\s\S]{0,100}?`\$\{risco\}%`',
            app,
        )
        and re.search(
            r"risco\s*>=\s*80\s*\?\s*[\"']cr.tico[\"']\s*:"
            r"[\s\S]{0,100}?risco\s*>=\s*60\s*\?\s*[\"']alto[\"']\s*:"
            r"[\s\S]{0,100}?risco\s*>=\s*40\s*\?\s*[\"']moderado[\"']\s*:"
            r"[\s\S]{0,100}?risco\s*>=\s*20\s*\?\s*[\"']baixo[\"']\s*:"
            r"[\s\S]{0,100}?[\"']controlado[\"']",
            app,
        )
        and re.search(
            r'titulo\s*:\s*["\']Severidade["\']'
            r"[\s\S]{0,100}?valor\s*:\s*severidadeRisco",
            app,
        )
    )

    assert not (
        raw_risk_engine
        and arbitrary_zero_to_one_hundred_normalization
        and external_percentage_and_severity
    ), (
        "Risco bruto normalizado arbitrariamente para 0-100 não pode ser exposto "
        "como percentual e severidade sem metodologia validada"
    )
