from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")

TERMS_ERROR = APP.split("  if (erroTermos) {", 1)[1].split(
    "  if (precisaAceitarTermos) {", 1
)[0]

PRIVACY_ERROR = APP.split("  if (erroConsentimento) {", 1)[1].split(
    "  if (precisaConsentir) {", 1
)[0]


def test_mei_consent_errors_share_visual_structure():
    for screen in (TERMS_ERROR, PRIVACY_ERROR):
        assert "isMeiPublicJourney" in screen
        assert "solveris-consent-page" in screen
        assert "solveris-consent-card" in screen
        assert "solveris-consent-error" in screen
        assert "solveris-consent-primary" in screen
        assert "solveris-consent-exit" in screen


def test_mei_consent_errors_preserve_recovery_and_access_gate():
    for screen in (TERMS_ERROR, PRIVACY_ERROR):
        assert "window.location.reload()" in screen
        assert "handleLogout" in screen
        assert "Tentar novamente" in screen
        assert "Sair" in screen

    assert ".solveris-consent-error" in CSS
