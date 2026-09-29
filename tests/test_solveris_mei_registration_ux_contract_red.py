from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")


def test_mei_public_create_account_link_is_actionable():
    start = APP.index('className="solveris-account-link"')
    end = APP.index("</button>", start)
    link = APP[start:end]

    assert "setMostrarRegisto(true)" in link
    assert 'setMeiPublicIntent("existing")' in link
    assert 'setTipoRegisto("mei")' in link
    assert 'setDocumentoRegisto("")' in link
    assert "if (isMeiPublicJourney) {\n                    return" not in link



def test_public_release_only_offers_existing_mei():
    start = APP.index('className="solveris-entry-card"')
    end = APP.index("</section>", start)
    entry = APP[start:end]

    assert "tenho MEI" in entry
    assert 'setMeiPublicIntent("existing")' in entry
    assert "Quero abrir meu MEI" not in entry
    assert 'setMeiPublicIntent("opening")' not in entry

    # Contas em abertura anteriores continuam preservadas.
    assert 'if (isOpeningMei) {' in APP

    # Cadastro p?blico n?o aceita uma inten??o indeterminada.
    assert 'if (isMeiPublicJourney && meiPublicIntent !== "existing")' in APP


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
