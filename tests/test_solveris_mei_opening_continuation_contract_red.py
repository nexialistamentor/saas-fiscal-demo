from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend-dashboard/src/App.css").read_text(encoding="utf-8")

def test_opening_isolated_from_generic_dashboard():
    assert 'if (isOpeningMei) {' in APP
    assert 'Seu negócio começa aqui.' in APP
    assert 'Continuar no Portal do Empreendedor (Gov.br)' not in APP
    assert 'onSubmit={simularAbertura}' in APP
    assert 'A emissão de DAS oficial só ficará disponível' in APP
    assert '.solveris-opening-main' in CSS

def test_existing_safety_guards_remain():
    assert 'perfilAtual.status_empresa !== "em_abertura" && (' in APP
    assert 'setUsuario(usuarioJson)' in APP
    assert '/auth/has-accepted-terms' in APP
    assert '/auth/has-consented' in APP
