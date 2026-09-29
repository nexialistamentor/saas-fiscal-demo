from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CPF = (ROOT / "frontend-dashboard/src/hooks/useCpfDashboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")

def test_opening_is_separate_ui_not_gov_redirect():
    start = APP.index('  if (isOpeningMei) {\n    return (')
    end = APP.index('  return (\n    <div className={`app${isMeiPublicJourney', start)
    section = APP[start:end]
    assert 'Seu negócio começa aqui.' in section
    assert 'O MEI é só o início.' in section
    assert 'gov.br' not in section.lower()
    assert 'type="file"' not in section
    assert 'profile-toggle' not in section
    assert 'Emitir DAS oficial' not in section
    assert 'onSubmit={simularAbertura}' not in section
    assert 'solveris-opening-steps' in section
    assert '.solveris-opening-main' in CSS

def test_cpf_request_disabled_outside_cpf_and_checkout_skips_opening():
    assert 'enabled: tipoPerfil === "cpf" && !isOpeningMei' in APP
    assert 'if (!enabled || !isAuthenticated())' in CPF
    assert 'if (!isOpeningMei) void recuperarTaxReportCheckoutDoServidor(idPerfil)' in APP

def test_existing_capabilities_preserved():
    assert 'onSubmit={simularAbertura}' in APP
    assert 'emitirDasOficial' in APP
    assert '/auth/has-accepted-terms' in APP and '/auth/has-consented' in APP
