from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")

TERMS = APP.split("  if (precisaAceitarTermos) {", 1)[1].split(
    "  if (erroConsentimento) {", 1
)[0]
PRIVACY = APP.split("  if (precisaConsentir) {", 1)[1].split(
    "  if (verificandoSessao) {", 1
)[0]


def test_mei_consent_journey_explains_two_separate_steps():
    assert "quando pendente" in TERMS
    assert "separada da" in PRIVACY
    assert "dos Termos de Uso." in PRIVACY
    assert "Termos de Uso" in TERMS
    assert "Política de Privacidade" in PRIVACY

    assert "onClick={handleAceitarTermos}" in TERMS
    assert "onClick={handleConsentirPrivacidade}" in PRIVACY
    assert "/auth/accept-terms" in APP
    assert "/auth/consent" in APP


def test_mei_consent_screens_share_institutional_visual_structure():
    for screen in (TERMS, PRIVACY):
        assert "solveris-consent-page" in screen
        assert "solveris-consent-card" in screen
        assert "solveris-consent-primary" in screen

    for selector in (
        ".solveris-consent-page",
        ".solveris-consent-card",
        ".solveris-consent-primary",
    ):
        assert selector in CSS
