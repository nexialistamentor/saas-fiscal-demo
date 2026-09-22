from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_sessao_exige_consentimento_antes_de_ativar_dashboard():
    start = APP.index("async function validarSessao()")
    end = APP.index("\n    validarSessao()", start)
    block = APP[start:end]

    assert "/auth/has-accepted-terms" in block
    assert "/auth/has-consented" in block

    pos_consent = block.index("/auth/has-consented")
    pos_user = block.index("setUsuario(usuarioJson)")
    pos_empresas = block.index('fetch(`${API_BASE}/empresas/`')

    assert pos_consent < pos_user
    assert pos_consent < pos_empresas


def test_frontend_possui_acao_explicita_para_registrar_consentimento():
    assert "/auth/consent" in APP
    assert "precisaConsentir" in APP
