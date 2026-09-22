from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_perfil_mei_preserva_cnpj_canonico_da_empresa():
    profile_start = APP.index("const perfil = {")
    profile_block = APP[profile_start:profile_start + 800]

    assert "cnpj" in profile_block
    assert "e.cnpj" in profile_block


def test_mei_sem_cnpj_tem_acao_explicita_para_completar_identidade():
    assert "/empresas/${idPerfil}/cnpj" in APP
    assert 'method: "PATCH"' in APP or "method: 'PATCH'" in APP
    assert "Authorization" in APP
    assert "JSON.stringify" in APP
    assert "cnpj" in APP


def test_das_permanece_bloqueado_enquanto_cnpj_estiver_ausente():
    das_start = APP.index('<h3>Emitir DAS oficial</h3>')
    das_block = APP[das_start - 1200:das_start + 2200]

    assert "cnpj" in das_block
    assert (
        "!perfilAtual.cnpj" in das_block
        or "perfilAtual.cnpj == null" in das_block
        or "perfilAtual.cnpj === null" in das_block
    )
