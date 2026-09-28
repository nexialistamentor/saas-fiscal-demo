from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")


def test_legacy_registration_fallback_is_explicit_and_public_styles_remain_scoped():
    assert 'isMeiPublicJourney ? "solveris-mei-theme solveris-public-entry" : "solveris-legacy-entry"' in APP
    for rule in (
        '.solveris-legacy-entry .solveris-register-password-wrap',
        '.solveris-legacy-entry .solveris-register-password-toggle',
        '.solveris-legacy-entry .solveris-register-hint',
        '.solveris-legacy-entry .solveris-register-login-link',
    ):
        assert rule in CSS
    assert 'isMeiPublicJourney ? "Criar conta" : "Registar"' in APP


def test_public_forms_have_labels_and_contrast():
    for field in ('login-email', 'login-password', 'register-name', 'register-email', 'register-password'):
        assert f'htmlFor="solveris-{field}"' in APP
        assert f'id="solveris-{field}"' in APP
    assert 'htmlFor="solveris-register-document"' in APP
    assert 'required={isMeiPublicJourney && meiPublicIntent === "existing"}' in APP
    assert 'Nome de referência do negócio' in APP
    assert 'solveris-register-error' in APP and '.solveris-public-entry .solveris-register-error' in CSS
    assert 'aria-label={mostrarSenhaLogin ? "Ocultar senha" : "Mostrar senha"}' in APP


def test_consent_actions_remain_distinct_and_fail_closed():
    assert 'Aceitar Termos de Uso e continuar' in APP
    assert 'Confirmar consentimento e continuar' in APP
    assert 'onClick={handleAceitarTermos}' in APP
    assert 'onClick={handleConsentirPrivacidade}' in APP
    assert '/auth/accept-terms' in APP and '/auth/consent' in APP
    assert APP.index('/auth/has-accepted-terms') < APP.index('/auth/has-consented') < APP.index('setUsuario(usuarioJson)')


def test_opening_state_never_exposes_das_action_and_no_empty_metrics():
    assert 'perfilAtual.status_empresa === "em_abertura"' in APP
    assert 'perfilAtual.status_empresa !== "em_abertura" && (' in APP
    assert 'A emissão de DAS oficial só ficará disponível' in APP
    assert 'status_empresa === "em_abertura" && data == null' in APP
    assert '<h3>Emitir DAS oficial</h3>' in APP
