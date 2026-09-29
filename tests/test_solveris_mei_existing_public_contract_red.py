from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend-dashboard/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend-dashboard/src/App.css').read_text(encoding='utf-8')


def test_public_existing_mei_uses_persisted_profile_and_no_simulator():
    assert 'const isOpeningMei = isMeiPublicJourney && tipoPerfil === "mei" && perfilAtual.status_empresa === "em_abertura"' in APP
    assert 'const isExistingMei = isMeiPublicJourney && tipoPerfil === "mei" &&' in APP
    assert 'Number.isInteger(idPerfil) && idPerfil > 0' in APP
    assert '!isMeiPublicJourney && (\n        <div' in APP
    assert 'onSubmit={simularAbertura}' in APP  # preserved on legacy non-MEI route
    assert 'if (isMeiPublicJourney && !isExistingMei)' in APP
    assert 'Meu MEI' in APP
    assert 'Não encontramos um perfil de MEI existente válido nesta sessão' in APP


def test_existing_mei_navigation_preserves_official_service_gates():
    assert 'id={isExistingMei ? "mei-das-oficial" : undefined}' in APP
    assert 'id={isExistingMei ? "mei-documentos" : undefined}' in APP
    assert 'id={isExistingMei ? "mei-diagnostico" : undefined}' in APP
    assert 'perfilAtual.status_empresa !== "em_abertura" && (' in APP
    assert 'perfilAtual.status_empresa !== "ativa" ||' in APP
    assert 'handleEmitirDasOficial' in APP
    assert 'taxReportPurchasable' in APP
    assert '!isMeiPublicJourney && (\n        <div className="profile-toggle">' in APP
    assert '!(tipoPerfil === "mei" && data == null)' in APP


def test_public_registration_contrast_and_existing_dashboard_mobile():
    assert '.solveris-public-entry .solveris-register-card h2' in CSS
    assert '.solveris-public-entry .solveris-register-login-link' in CSS
    assert '.app.solveris-existing-app .solveris-existing-actions' in CSS
    assert 'color:#f4f7fb' in CSS
    assert 'width:min(100% - 32px, 900px)' in CSS
