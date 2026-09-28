from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")


def test_mei_public_create_account_link_is_actionable():
    start = APP.index('className="solveris-account-link"')
    end = APP.index("</button>", start)
    link = APP[start:end]

    assert "setMostrarRegisto(true)" in link
    assert 'setMeiPublicIntent("opening")' in link
    assert 'setTipoRegisto("mei")' in link
    assert 'setDocumentoRegisto("")' in link
    assert "if (isMeiPublicJourney) {\n                    return" not in link


def test_mei_registration_has_mobile_first_visual_structure():
    for class_name in (
        "solveris-register-card",
        "solveris-register-form",
        "solveris-register-field",
        "solveris-register-submit",
    ):
        assert f'className="{class_name}"' in APP
        assert f".solveris-public-entry .{class_name}" in CSS

    assert APP.count('className="solveris-register-field"') >= 3
