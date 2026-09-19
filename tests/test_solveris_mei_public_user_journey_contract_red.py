from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_solveris_mei_public_user_journey_contract() -> None:
    # Marca soberana pública
    assert "SOLVERIS" in APP
    assert "Plataforma Tributária L2" not in APP
    assert "Plataforma de Inteligência Tributária em Tempo Real" not in APP

    # Entrada MEI deve distinguir intenção do usuário
    assert "Quero abrir meu MEI" in APP
    assert "Já tenho MEI" in APP

    # Fluxo de abertura não pode exigir CNPJ
    assert "Não precisa de CNPJ para começar" in APP

    # Perfil MEI deve nascer coerente com MEI, nunca ME
    assert 'useState("mei")' in APP

    # DAS oficial não deve ser apresentado como operacional
    # antes da autoridade SERPRO estar disponível.
    assert "DAS oficial temporariamente indisponível" in APP

    # Paywall público não deve ser apresentado sem relatório comprável.
    assert "relatorio_id" in APP
    assert "request_fingerprint" in APP
    assert "Diagnóstico completo bloqueado" in APP
