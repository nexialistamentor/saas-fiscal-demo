from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
APP_CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")
SOLVERIS_LOGO = ROOT / "frontend-dashboard/public/solveris-logo.jpg"


def test_solveris_mei_public_user_journey_contract() -> None:
    # SOLVERIS é a marca pública soberana.
    assert "SOLVERIS" in APP
    assert "Plataforma Tributária L2" not in APP
    assert "Plataforma de Inteligência Tributária em Tempo Real" not in APP

    # /mei deve separar claramente as duas intenções do usuário.
    assert "Quero abrir meu MEI" in APP
    assert "Já tenho MEI" in APP

    # O fluxo de quem quer abrir MEI não pode exigir CNPJ.
    assert "Não precisa de CNPJ para começar" in APP

    # A simulação MEI deve nascer coerente com o próprio MEI.
    assert (
        'const [formAberturaPorte, setFormAberturaPorte] = useState("mei")'
        in APP
    )

    # O paywall só pode aparecer quando existir diagnóstico comprável.
    assert "relatorio_id" in APP
    assert "request_fingerprint" in APP
    assert "taxReportPurchasable" in APP
    assert "Diagnóstico completo bloqueado" in APP

def test_solveris_terms_are_readable_before_acceptance() -> None:
    assert "Ler Termos de Uso" in APP
    assert "Política de Privacidade" in APP
    assert '/auth/privacy' in APP
    assert "Usoe" not in APP


def test_solveris_mei_public_visual_identity_contract() -> None:
    assert SOLVERIS_LOGO.is_file()
    assert "solveris-mei-theme" in APP
    assert "import.meta.env.BASE_URL" in APP
    assert "solveris-logo.jpg" in APP
    assert 'src="/solveris-logo.jpg"' not in APP

    for class_name in (
        "solveris-public-entry",
        "solveris-brand-lockup",
        "solveris-logo",
        "solveris-entry-card",
        "solveris-primary-action",
        "solveris-secondary-action",
        "solveris-login-card",
        "solveris-login-title",
        "solveris-login-form",
        "solveris-login-field",
        "solveris-password-field",
        "solveris-password-toggle",
        "solveris-login-submit",
        "solveris-account-callout",
        "solveris-account-link",
    ):
        assert class_name in APP

    for canonical_color in (
        "#06101c",
        "#0a1727",
        "#07111f",
        "#071320",
        "#091827",
        "#0b2034",
        "#7cf7c2",
        "#79a8ff",
        "#6ee7f2",
        "#f5d48c",
        "#f4f7fb",
        "#a8b7c8",
        "rgba(12,28,46,.72)",
        "rgba(177,205,230,.14)",
    ):
        assert canonical_color in APP_CSS.lower()

    for canonical_selector in (
        ".solveris-mei-theme",
        ".solveris-mei-theme .card",
        ".solveris-mei-theme .hero-card",
        ".solveris-mei-theme .profile-toggle",
        ".solveris-mei-theme .bloqueio-relatorio",
        ".solveris-public-entry",
        ".solveris-entry-card",
        ".solveris-primary-action",
        ".solveris-secondary-action",
        ".solveris-brand-lockup",
        ".solveris-logo",
        ".solveris-public-entry .solveris-login-card",
        ".solveris-public-entry .solveris-login-form",
        ".solveris-public-entry .solveris-login-field",
        ".solveris-public-entry .solveris-password-field",
        ".solveris-public-entry .solveris-password-toggle",
        ".solveris-public-entry .solveris-login-submit",
        ".solveris-public-entry .solveris-account-callout",
        ".solveris-public-entry .solveris-account-link",
    ):
        assert canonical_selector in APP_CSS

    assert "SOLVERIS" in APP
    assert ".solveris-brand-lockup" in APP_CSS
    assert any(
        top_right_declaration in APP_CSS
        for top_right_declaration in (
            "margin-left: auto",
            "justify-self: end",
            "align-self: flex-end",
            "right: 0",
        )
    )
