from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_mei_public_registration_sends_selected_intent():
    register_start = APP.index('fetch(`${API_BASE}/auth/register`')
    register_block = APP[register_start:register_start + 900]

    assert "mei_intent:" in register_block
    assert "meiPublicIntent" in register_block


def test_generic_create_account_does_not_force_opening_intent():
    callout_start = APP.index('className="solveris-account-callout"')
    callout_block = APP[callout_start:callout_start + 900]

    assert 'setMeiPublicIntent("opening")' not in callout_block
