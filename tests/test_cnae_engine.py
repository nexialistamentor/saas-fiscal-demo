"""
Testes do motor de enquadramento CNAE soberano V1.
"""

from app.services.cnae_engine import recomendar_cnaes, ResultadoCNAE


def test_retorna_resultado_cnae():
    r = recomendar_cnaes("desenvolvimento de software")
    assert isinstance(r, ResultadoCNAE)


def test_software_detecta_secao_j():
    r = recomendar_cnaes("desenvolvimento de software")
    assert r.cnae_principal_sugerido is not None
    assert r.cnae_principal_sugerido.secao == "J"


def test_score_entre_0_e_100():
    r = recomendar_cnaes("consultoria em tecnologia")
    assert 0.0 <= r.score_confianca <= 100.0


def test_palavras_detectadas_preenchidas():
    r = recomendar_cnaes("plataforma de dados e software")
    assert len(r.palavras_detectadas) > 0


def test_justificativa_preenchida():
    r = recomendar_cnaes("desenvolvimento de software")
    assert len(r.justificativa) > 0


def test_mei_permitido_para_ti():
    r = recomendar_cnaes("desenvolvimento de software", porte="mei")
    assert r.permite_mei is True
    assert r.motivo_nao_mei is None


def test_mei_nao_permitido_para_financeiro():
    r = recomendar_cnaes("banco financeiro crédito investimento", porte="mei")
    assert r.permite_mei is False
    assert r.motivo_nao_mei is not None


def test_regimes_compativeis_nao_vazio():
    r = recomendar_cnaes("consultoria empresarial")
    assert len(r.regimes_compativeis) > 0


def test_mei_aparece_em_regimes_quando_permitido():
    r = recomendar_cnaes("desenvolvimento de software", porte="mei")
    assert "mei" in r.regimes_compativeis
    assert r.regimes_compativeis[0] == "mei"


def test_mei_ausente_em_regimes_quando_nao_permitido():
    r = recomendar_cnaes("banco financeiro crédito", porte="mei")
    assert "mei" not in r.regimes_compativeis


def test_cnaes_secundarios_lista():
    r = recomendar_cnaes("desenvolvimento de software e consultoria")
    assert isinstance(r.cnaes_secundarios_sugeridos, list)


def test_descricao_vazia_nao_quebra():
    r = recomendar_cnaes("")
    assert isinstance(r, ResultadoCNAE)


def test_porte_grande_sem_mei():
    r = recomendar_cnaes("software", porte="grande")
    assert "mei" not in r.regimes_compativeis


def test_restaurante_detecta_alimentacao():
    r = recomendar_cnaes("restaurante delivery comida")
    assert r.cnae_principal_sugerido is not None
    assert r.cnae_principal_sugerido.secao == "I"


def test_comercio_detecta_secao_g():
    r = recomendar_cnaes("venda de produtos varejo loja")
    assert r.cnae_principal_sugerido is not None
    assert r.cnae_principal_sugerido.secao == "G"
