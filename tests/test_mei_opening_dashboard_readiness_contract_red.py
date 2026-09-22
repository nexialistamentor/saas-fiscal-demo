from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_mei_em_abertura_nao_pode_ser_apresentado_como_pronto_para_das():
    # A reconstrução do perfil após reload precisa preservar o estado canônico
    # devolvido por /empresas/.
    profile_block_start = APP.index("const perfil = {")
    profile_block = APP[profile_block_start:profile_block_start + 700]

    assert "status_empresa" in profile_block

    # A disponibilidade do DAS não pode depender apenas de tipo=mei + id positivo.
    das_start = APP.index('<h3>Emitir DAS oficial</h3>')
    das_block = APP[das_start - 900:das_start + 1800]

    assert "status_empresa" in das_block
    assert '"ativa"' in das_block or "'ativa'" in das_block
