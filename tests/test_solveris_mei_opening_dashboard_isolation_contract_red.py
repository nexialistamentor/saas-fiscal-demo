from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CPF = (ROOT / "frontend-dashboard/src/hooks/useCpfDashboard.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")

def test_opening_profile_has_no_public_opening_offer():
    start = APP.index('  if (isOpeningMei) {\n    return (')
    end = APP.index('  return (\n    <div className={`app${isMeiPublicJourney', start)
    section = APP[start:end]
    assert 'Seu acesso MEI precisa de confirma\u00e7\u00e3o' in section
    assert 'Vamos abrir seu MEI juntos' not in section
    assert 'Come\u00e7ar minha abertura' not in section
    assert 'Seu neg\u00f3cio come\u00e7a aqui.' not in section
    assert 'solveris-opening-steps' not in section
    assert 'gov.br' not in section.lower()
    assert 'type="file"' not in section
    assert 'profile-toggle' not in section
    assert 'Emitir DAS oficial' not in section
    assert 'onSubmit={simularAbertura}' not in section
    assert 'onClick={handleLogout}' in section

def test_cpf_request_disabled_outside_cpf_and_checkout_skips_opening():
    assert 'enabled: tipoPerfil === "cpf" && !isOpeningMei' in APP
    assert 'if (!enabled || !isAuthenticated())' in CPF
    assert 'if (!isOpeningMei) void recuperarTaxReportCheckoutDoServidor(idPerfil)' in APP

def test_existing_capabilities_preserved():
    assert 'onSubmit={simularAbertura}' in APP
    assert 'emitirDasOficial' in APP
    assert '/auth/has-accepted-terms' in APP and '/auth/has-consented' in APP
