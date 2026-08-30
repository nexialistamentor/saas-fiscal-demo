"""Contrato RED offline do futuro orquestrador de webhook Mercado Pago."""

from importlib import import_module

import pytest


class _Espia:
    def __init__(self, metodo, resultado=None, erro=None, ordem=None):
        self._metodo = metodo
        self.resultado = resultado
        self.erro = erro
        self.ordem = ordem if ordem is not None else []
        self.chamadas = []

    def __getattr__(self, nome):
        if nome != self._metodo:
            raise AttributeError(nome)

        def chamar(*args, **kwargs):
            self.chamadas.append((args, kwargs))
            self.ordem.append((self._metodo, args, kwargs))
            if self.erro is not None:
                raise self.erro
            return self.resultado

        return chamar


def _dependencias(*, assinatura=True, resolucao=None, resultado_core=None):
    ordem = []
    verificador = _Espia("verificar", assinatura, ordem=ordem)
    resolvedor = _Espia("resolver_pagamento", resolucao, ordem=ordem)
    core = _Espia(
        "confirmar_pagamento_autorizado", resultado_core, ordem=ordem
    )
    return verificador, resolvedor, core, ordem


def _orquestrador(modulo, **substituicoes):
    verificador, resolvedor, core, ordem = _dependencias(**substituicoes)
    instancia = modulo.MercadoPagoWebhookOrchestrator(
        verificador_assinatura=verificador,
        resolvedor_pagamento=resolvedor,
        checkout_core=core,
    )
    return instancia, verificador, resolvedor, core, ordem


def _assert_sanitizado(erro, *dados_proibidos):
    assert type(erro).__name__ == "MercadoPagoWebhookOrchestrationError"
    for representacao in (str(erro), repr(erro)):
        texto = representacao.lower()
        for marcador in ("token", "payload", "segredo", "credencial", "interno"):
            assert marcador not in texto
        for dado in dados_proibidos:
            assert str(dado).lower() not in texto


def test_mercado_pago_webhook_orchestration_contract_red():
    modulo = import_module(
        "app.services.mercado_pago_webhook_orchestration"
    )
    erro_publico = modulo.MercadoPagoWebhookOrchestrationError
    evento = {"event_id": "4719", "request_id": "request-8128"}
    assinatura = "assinatura-opaca-9931"

    dependencias_validas = _dependencias()[:3]
    invalidas = (None, object(), lambda: None, _Espia("metodo_errado"))
    for indice in range(3):
        for invalida in invalidas:
            dependencias = list(dependencias_validas)
            dependencias[indice] = invalida
            with pytest.raises(erro_publico) as capturada:
                modulo.MercadoPagoWebhookOrchestrator(*dependencias)
            _assert_sanitizado(capturada.value)
    assert all(dependencia.chamadas == [] for dependencia in dependencias_validas)

    class _DictDerivado(dict):
        pass

    eventos_invalidos = (
        None,
        [],
        _DictDerivado(evento),
        {},
        {"event_id": "4719"},
        {"request_id": "request-8128"},
        {"event_id": "4719", "request_id": "request-8128", "status": "paid"},
        {"event_id": None, "request_id": "request-8128"},
        {"event_id": 4719, "request_id": "request-8128"},
        {"event_id": "", "request_id": "request-8128"},
        {"event_id": " ", "request_id": "request-8128"},
        {"event_id": "47 19", "request_id": "request-8128"},
        {"event_id": "4719\r", "request_id": "request-8128"},
        {"event_id": "4719\n", "request_id": "request-8128"},
        {"event_id": "4719", "request_id": None},
        {"event_id": "4719", "request_id": 8128},
        {"event_id": "4719", "request_id": ""},
        {"event_id": "4719", "request_id": " "},
        {"event_id": "4719", "request_id": "request 8128"},
        {"event_id": "4719", "request_id": "request\r8128"},
        {"event_id": "4719", "request_id": "request\n8128"},
    )
    for evento_invalido in eventos_invalidos:
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
        with pytest.raises(erro_publico):
            orquestrador.processar(evento_invalido, assinatura)
        assert verificador.chamadas == resolvedor.chamadas == core.chamadas == []
        assert ordem == []

    evento_extra = {
        **evento,
        "status": "approved",
        "preco": "0.01",
        "moeda": "USD",
        "empresa_id": 314,
        "user_id": 42,
        "payload": {"token": "nao-confiavel"},
    }
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
    with pytest.raises(erro_publico):
        orquestrador.processar(evento_extra, assinatura)
    assert verificador.chamadas == resolvedor.chamadas == core.chamadas == []
    assert ordem == []

    segredo = "segredo-ultrassecreto-4719"
    detalhe = "detalhe-interno-8128"
    for retorno_assinatura in (False, None, 0, 1, "true", object()):
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
            modulo, assinatura=retorno_assinatura
        )
        with pytest.raises(erro_publico) as capturada:
            orquestrador.processar(evento, assinatura)
        assert ordem == [("verificar", (evento, assinatura), {})]
        assert len(verificador.chamadas) == 1
        assert resolvedor.chamadas == core.chamadas == []
        _assert_sanitizado(capturada.value, assinatura)

    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
    verificador.erro = RuntimeError(
        f"token payload credencial {segredo} {detalhe}"
    )
    with pytest.raises(erro_publico) as capturada:
        orquestrador.processar(evento, assinatura)
    assert ordem == [("verificar", (evento, assinatura), {})]
    assert resolvedor.chamadas == core.chamadas == []
    _assert_sanitizado(capturada.value, segredo, detalhe, assinatura)

    resultado_core = object()
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
        modulo, resolucao=None, resultado_core=resultado_core
    )
    assert orquestrador.processar(evento, assinatura) is None
    assert ordem == [
        ("verificar", (evento, assinatura), {}),
        ("resolver_pagamento", ("4719", "request-8128"), {}),
    ]
    assert core.chamadas == []

    resolucao = {"ordem_id": 91, "event_id": "request-8128"}
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
        modulo, resolucao=resolucao, resultado_core=resultado_core
    )
    assert orquestrador.processar(evento, assinatura) is resultado_core
    assert ordem == [
        ("verificar", (evento, assinatura), {}),
        ("resolver_pagamento", ("4719", "request-8128"), {}),
        ("confirmar_pagamento_autorizado", (91, "request-8128"), {}),
    ]

    resolucoes_invalidas = (
        {},
        [],
        {"ordem_id": True, "event_id": "request-8128"},
        {"ordem_id": 0, "event_id": "request-8128"},
        {"ordem_id": -1, "event_id": "request-8128"},
        {"ordem_id": 91},
        {"ordem_id": 91, "event_id": "request-divergente"},
        {"ordem_id": 91, "event_id": "request-8128", "status": "approved"},
    )
    for resolucao_invalida in resolucoes_invalidas:
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
            modulo, resolucao=resolucao_invalida
        )
        with pytest.raises(erro_publico) as capturada:
            orquestrador.processar(evento, assinatura)
        assert len(verificador.chamadas) == len(resolvedor.chamadas) == 1
        assert core.chamadas == []
        _assert_sanitizado(capturada.value, segredo, detalhe, resolucao_invalida)

    for dependencia, metodo in (
        ("resolvedor", "resolver_pagamento"),
        ("core", "confirmar_pagamento_autorizado"),
    ):
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
            modulo, resolucao=resolucao
        )
        alvo = resolvedor if dependencia == "resolvedor" else core
        alvo.erro = RuntimeError(f"token payload {segredo} {detalhe}")
        with pytest.raises(erro_publico) as capturada:
            orquestrador.processar(evento, assinatura)
        assert len(verificador.chamadas) == 1
        assert len(resolvedor.chamadas) == 1
        assert len(core.chamadas) == (1 if dependencia == "core" else 0)
        assert ordem[-1][0] == metodo
        _assert_sanitizado(capturada.value, segredo, detalhe, assinatura)
