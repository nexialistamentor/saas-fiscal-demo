"""Contrato RED offline do futuro orquestrador de webhook Mercado Pago."""

from decimal import Decimal
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


def _assert_sanitizado(erro, *dados_proibidos, tipo_esperado=None):
    if tipo_esperado is None:
        assert type(erro).__name__ == (
            "MercadoPagoWebhookOrchestrationError"
        )
    else:
        assert type(erro) is tipo_esperado
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
    erro_autenticacao = modulo.MercadoPagoWebhookAuthenticationError
    assert issubclass(erro_autenticacao, erro_publico)
    assert erro_autenticacao is not erro_publico
    envelope = {
        "notification_id": "8128",
        "payment_id": "4719",
        "request_id": "request-9931",
    }
    assinatura = "assinatura-opaca-9931"
    BRL = "BRL"

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
        _DictDerivado(envelope),
        {},
        {"notification_id": "8128", "payment_id": "4719"},
        {"notification_id": "8128", "request_id": "request-9931"},
        {"payment_id": "4719", "request_id": "request-9931"},
        {**envelope, "status": "paid"},
        {**envelope, "valor": "49.90"},
        {**envelope, "transaction_amount": "49.90"},
        {**envelope, "moeda": "BRL"},
        {**envelope, "currency_id": "BRL"},
        {**envelope, "notification_id": None},
        {**envelope, "notification_id": 8128},
        {**envelope, "notification_id": ""},
        {**envelope, "notification_id": "0"},
        {**envelope, "notification_id": "-1"},
        {**envelope, "notification_id": "08128"},
        {**envelope, "notification_id": "81 28"},
        {**envelope, "notification_id": "8128\r"},
        {**envelope, "notification_id": "8128\n"},
        {**envelope, "payment_id": None},
        {**envelope, "payment_id": 4719},
        {**envelope, "payment_id": ""},
        {**envelope, "payment_id": "0"},
        {**envelope, "payment_id": "-1"},
        {**envelope, "payment_id": "04719"},
        {**envelope, "payment_id": "47 19"},
        {**envelope, "payment_id": "4719\r"},
        {**envelope, "payment_id": "4719\n"},
        {**envelope, "request_id": None},
        {**envelope, "request_id": 9931},
        {**envelope, "request_id": ""},
        {**envelope, "request_id": "request 9931"},
        {**envelope, "request_id": "request\r9931"},
        {**envelope, "request_id": "request\n9931"},
    )
    for evento_invalido in eventos_invalidos:
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
        with pytest.raises(erro_publico):
            orquestrador.processar(evento_invalido, assinatura)
        assert verificador.chamadas == resolvedor.chamadas == core.chamadas == []
        assert ordem == []

    envelope_extra = {
        **envelope,
        "status": "approved",
        "preco": "0.01",
        "moeda": "USD",
        "empresa_id": 314,
        "user_id": 42,
        "payload": {"token": "nao-confiavel"},
    }
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
    with pytest.raises(erro_publico):
        orquestrador.processar(envelope_extra, assinatura)
    assert verificador.chamadas == resolvedor.chamadas == core.chamadas == []
    assert ordem == []

    segredo = "segredo-ultrassecreto-4719"
    detalhe = "detalhe-interno-8128"
    for retorno_assinatura in (False, None, 0, 1, "true", object()):
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
            modulo, assinatura=retorno_assinatura
        )
        with pytest.raises(erro_publico) as capturada:
            orquestrador.processar(envelope, assinatura)
        assert ordem == [("verificar", (envelope, assinatura), {})]
        assert len(verificador.chamadas) == 1
        assert resolvedor.chamadas == core.chamadas == []
        _assert_sanitizado(
            capturada.value,
            assinatura,
            tipo_esperado=erro_autenticacao,
        )

    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(modulo)
    verificador.erro = RuntimeError(
        f"token payload credencial {segredo} {detalhe}"
    )
    with pytest.raises(erro_publico) as capturada:
        orquestrador.processar(envelope, assinatura)
    assert ordem == [("verificar", (envelope, assinatura), {})]
    assert resolvedor.chamadas == core.chamadas == []
    _assert_sanitizado(capturada.value, segredo, detalhe, assinatura)

    resultado_core = object()
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
        modulo, resolucao=None, resultado_core=resultado_core
    )
    assert orquestrador.processar(envelope, assinatura) is None
    assert ordem == [
        ("verificar", (envelope, assinatura), {}),
        ("resolver_pagamento", ("4719", "8128"), {}),
    ]
    assert core.chamadas == []

    valor_autenticado = Decimal("49.90")
    resolucao = {
        "ordem_id": 91,
        "event_id": "8128",
        "valor": valor_autenticado,
        "moeda": BRL,
    }
    orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
        modulo, resolucao=resolucao, resultado_core=resultado_core
    )
    assert orquestrador.processar(envelope, assinatura) is resultado_core
    assert ordem == [
        ("verificar", (envelope, assinatura), {}),
        ("resolver_pagamento", ("4719", "8128"), {}),
        (
            "confirmar_pagamento_autorizado",
            (91, "8128", "4719", valor_autenticado, BRL),
            {},
        ),
    ]
    assert core.chamadas == [
        ((91, "8128", "4719", valor_autenticado, BRL), {})
    ]
    assert core.chamadas[0][0][3] is valor_autenticado

    resolucoes_invalidas = (
        {},
        [],
        {**resolucao, "ordem_id": True},
        {**resolucao, "ordem_id": 0},
        {**resolucao, "ordem_id": -1},
        {chave: valor for chave, valor in resolucao.items() if chave != "ordem_id"},
        {chave: valor for chave, valor in resolucao.items() if chave != "event_id"},
        {chave: valor for chave, valor in resolucao.items() if chave != "valor"},
        {chave: valor for chave, valor in resolucao.items() if chave != "moeda"},
        {**resolucao, "status": "approved"},
        {**resolucao, "event_id": 8128},
        {**resolucao, "event_id": 4719},
        {**resolucao, "event_id": "4719"},
        {**resolucao, "event_id": "request-9931"},
        {**resolucao, "event_id": 8129},
        {**resolucao, "event_id": "8129"},
        {**resolucao, "valor": True},
        {**resolucao, "valor": 49},
        {**resolucao, "valor": 49.90},
        {**resolucao, "valor": "49.90"},
        {**resolucao, "valor": Decimal("0.00")},
        {**resolucao, "valor": Decimal("-0.01")},
        {**resolucao, "valor": Decimal("NaN")},
        {**resolucao, "valor": Decimal("Infinity")},
        {**resolucao, "valor": Decimal("49.9")},
        {**resolucao, "valor": Decimal("49.900")},
        {**resolucao, "valor": Decimal("49.901")},
        {**resolucao, "moeda": "brl"},
        {**resolucao, "moeda": "USD"},
        {**resolucao, "moeda": ""},
        {**resolucao, "moeda": None},
        {**resolucao, "moeda": True},
        {**resolucao, "moeda": 986},
    )
    for resolucao_invalida in resolucoes_invalidas:
        orquestrador, verificador, resolvedor, core, ordem = _orquestrador(
            modulo, resolucao=resolucao_invalida
        )
        with pytest.raises(erro_publico) as capturada:
            orquestrador.processar(envelope, assinatura)
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
            orquestrador.processar(envelope, assinatura)
        assert len(verificador.chamadas) == 1
        assert len(resolvedor.chamadas) == 1
        assert len(core.chamadas) == (1 if dependencia == "core" else 0)
        assert ordem[-1][0] == metodo
        _assert_sanitizado(capturada.value, segredo, detalhe, assinatura)
