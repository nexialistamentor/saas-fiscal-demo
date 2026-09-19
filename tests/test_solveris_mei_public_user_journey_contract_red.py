from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend-dashboard/src/App.jsx").read_text(encoding="utf-8")


def test_solveris_mei_public_user_journey_contract() -> None:
    # SOLVERIS é a marca pública soberana.
    assert "SOLVERIS" in APP
    assert "Plataforma Tributária L2" not in APP
    assert "Plataforma de Inteligência Tributária em Tempo Real" not in APP

    # /mei deve separar claramente as duas intenções do usuário.
    assert "Quero abrir meu MEI" in APP
    assert "Já tenho MEI" in APP

    # O fluxo de quem quer abrir MEI não pode exigir CNPJ.
    assert "Não precisa de CNPJ para começar" in APP

    # A simulação MEI deve nascer coerente com o próprio MEI.
    assert (
        'const [formAberturaPorte, setFormAberturaPorte] = useState("mei")'
        in APP
    )

    # O paywall só pode aparecer quando existir diagnóstico comprável.
    assert "relatorio_id" in APP
    assert "request_fingerprint" in APP
    assert "taxReportPurchasable" in APP
    assert "Diagnóstico completo bloqueado" in APP

def test_solveris_terms_are_readable_before_acceptance() -> None:
    assert "Ler Termos de Uso" in APP
    assert "Pol?tica de Privacidade" in APP
    assert '/auth/privacy' in APP
    assert "Usoe" not in APP
