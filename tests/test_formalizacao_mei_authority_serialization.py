from decimal import Decimal
from types import SimpleNamespace

from app.routers import formalizacao_router
from app.services import regime_engine


NAO_AVALIADO_MEI = {
    "mei": {
        "estado": "autoridade_indisponivel",
        "codigo": "AUTORIDADE_NORMATIVA_MEI_INDISPONIVEL",
        "motivo": "BINDING_MISSING",
    }
}


def _resultado_simples() -> regime_engine.ResultadoRegime:
    return regime_engine.ResultadoRegime(
        regime="simples",
        carga_anual=Decimal("1200.00"),
        carga_mensal=Decimal("100.00"),
        aliquota_efetiva_pct=10.0,
        anexo_simples="III",
        fator_r=None,
        alertas=[],
        detalhes={"stub": True},
    )


def _comparacao_com_mei_nao_avaliado() -> regime_engine.ResultadoComparacao:
    return regime_engine.ResultadoComparacao(
        regime_recomendado="simples",
        economia_anual_vs_pior=Decimal("0"),
        resultados={"simples": _resultado_simples()},
        justificativa=["Regime recomendado: SIMPLES"],
        regimes_inelegiveis={},
        regimes_nao_avaliados=NAO_AVALIADO_MEI,
    )


def test_comparar_regimes_endpoint_exposes_mei_non_evaluated_authority_state(monkeypatch):
    """RED: public comparison must distinguish authority denial from ineligibility."""
    monkeypatch.setattr(
        formalizacao_router,
        "_exigir_tempo_normativo",
        lambda *args, **kwargs: 2026,
    )
    monkeypatch.setattr(
        formalizacao_router,
        "comparar_regimes",
        lambda *args, **kwargs: _comparacao_com_mei_nao_avaliado(),
    )

    body = formalizacao_router.CompararRegimesRequest(
        faturamento_anual=Decimal("12000.00"),
        regimes_permitidos=["mei", "simples"],
        ano_referencia=2026,
    )

    resposta = formalizacao_router.comparar_regimes_endpoint(
        body=body,
        usuario=object(),
    )

    assert resposta["regimes_nao_avaliados"] == NAO_AVALIADO_MEI
    assert "mei" not in resposta["regimes_inelegiveis"]
    assert "mei" not in resposta["resultados"]


def test_simular_empresa_exposes_mei_non_evaluated_authority_state(monkeypatch):
    """RED: full public simulation must preserve the same authority-state semantics."""
    cnae_principal = SimpleNamespace(
        codigo_subclasse="6202-3/00",
        descricao="Desenvolvimento de software",
        codigo_classe="6202-3",
        codigo_grupo="620",
        codigo_divisao="62",
        secao="J",
        versao_cnae="2.3",
    )
    resultado_cnae = SimpleNamespace(
        cnae_principal_sugerido=cnae_principal,
        cnaes_secundarios_sugeridos=[],
        score_confianca=100.0,
        permite_mei=True,
        motivo_nao_mei=None,
        regimes_compativeis=["mei", "simples"],
        justificativa=["stub CNAE"],
        palavras_detectadas=["software"],
    )

    monkeypatch.setattr(
        formalizacao_router,
        "recomendar_cnaes",
        lambda *args, **kwargs: resultado_cnae,
    )
    monkeypatch.setattr(
        formalizacao_router,
        "_exigir_tempo_normativo",
        lambda *args, **kwargs: 2026,
    )
    monkeypatch.setattr(
        formalizacao_router,
        "comparar_regimes",
        lambda *args, **kwargs: _comparacao_com_mei_nao_avaliado(),
    )

    body = formalizacao_router.SimularEmpresaRequest(
        descricao_actividade="software",
        porte="mei",
        faturamento_anual=Decimal("12000.00"),
        ano_referencia=2026,
    )

    resposta = formalizacao_router.simular_empresa(
        body=body,
        usuario=object(),
    )

    assert resposta["regimes_nao_avaliados"] == NAO_AVALIADO_MEI
    assert "mei" not in resposta["regimes_inelegiveis"]
    assert "mei" not in resposta["resultados_regime"]
