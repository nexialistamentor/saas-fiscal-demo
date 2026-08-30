"""Contrato RED offline do autenticador de assinatura Mercado Pago."""

from importlib import import_module

import pytest


SECRET = "segredo-de-teste-nao-real-4719"


class _ValidadorOficialFalso:
    def __init__(self, resultado=True, erro=None):
        self.resultado = resultado
        self.erro = erro
        self.chamadas = []

    def __call__(self, **dados):
        self.chamadas.append(dados)
        if self.erro is not None:
            raise self.erro
        return self.resultado


def _assert_publico_sanitizado(valor, *dados_proibidos):
    representacoes = (str(valor), repr(valor))
    for representacao in representacoes:
        texto = representacao.lower()
        assert "token" not in texto
        assert "credencial" not in texto
        assert "payload" not in texto
        for dado in dados_proibidos:
            assert str(dado).lower() not in texto


def test_mercado_pago_webhook_signature_contract_red():
    mercado_pago = import_module("app.services.mercado_pago_webhook")

    validador = _ValidadorOficialFalso()
    configuracoes_invalidas = (
        {"validador": None, "secret": SECRET},
        {"validador": object(), "secret": SECRET},
        {"validador": validador, "secret": None},
        {"validador": validador, "secret": 123},
        {"validador": validador, "secret": ""},
        {"validador": validador, "secret": "   "},
    )
    for configuracao in configuracoes_invalidas:
        chamadas_antes = list(validador.chamadas)
        with pytest.raises(mercado_pago.MercadoPagoWebhookError) as capturada:
            mercado_pago.MercadoPagoWebhookSignatureVerifier(**configuracao)
        assert validador.chamadas == chamadas_antes
        _assert_publico_sanitizado(capturada.value, SECRET)

    verificador = mercado_pago.MercadoPagoWebhookSignatureVerifier(
        validador=validador,
        secret=SECRET,
    )
    _assert_publico_sanitizado(verificador, SECRET)

    envelopes_invalidos = (
        None,
        [],
        "evento",
        {},
        {"notification_id": "8128", "payment_id": "4719"},
        {"request_id": "request-1"},
        {"notification_id": "8128", "request_id": "request-1"},
        {"payment_id": "4719", "request_id": "request-1"},
        {"notification_id": None, "payment_id": "4719", "request_id": "request-1"},
        {"notification_id": 8128, "payment_id": "4719", "request_id": "request-1"},
        {"notification_id": "", "payment_id": "4719", "request_id": "request-1"},
        {"notification_id": "0", "payment_id": "4719", "request_id": "request-1"},
        {"notification_id": "08128", "payment_id": "4719", "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": None, "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": 4719, "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": "", "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": "0", "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": "04719", "request_id": "request-1"},
        {"notification_id": "8128", "payment_id": "4719", "request_id": None},
        {"notification_id": "8128", "payment_id": "4719", "request_id": 1},
        {"notification_id": "8128", "payment_id": "4719", "request_id": ""},
        {"notification_id": "8128", "payment_id": "4719", "request_id": "request 1"},
        {"notification_id": "8128", "payment_id": "4719", "request_id": "request\r1"},
        {"notification_id": "8128", "payment_id": "4719", "request_id": "request\n1"},
        {"notification_id": "8128", "payment_id": "4719", "request_id": "request-1", "event_id": "8128"},
        {"notification_id": "4719", "payment_id": "8128", "request_id": "request-1", "extra": True},
    )
    assinaturas_invalidas = (None, 123, "", "   ", "assinatura\rforjada", "x\ny")
    for envelope in envelopes_invalidos:
        chamadas_antes = list(validador.chamadas)
        assert verificador.verificar(envelope, "assinatura-valida") is False
        assert validador.chamadas == chamadas_antes
    envelope_minimo = {
        "notification_id": "8128",
        "payment_id": "4719",
        "request_id": "request-1",
    }
    for assinatura in assinaturas_invalidas:
        chamadas_antes = list(validador.chamadas)
        assert verificador.verificar(envelope_minimo, assinatura) is False
        assert validador.chamadas == chamadas_antes

    envelope = {
        "notification_id": "8128",
        "payment_id": "4719",
        "request_id": "request-8128",
    }
    assinatura = "ts=1700000000,v1=assinatura-falsa"
    assert verificador.verificar(envelope, assinatura) is True
    assert validador.chamadas == [
        {
            "x_signature": assinatura,
            "x_request_id": "request-8128",
            "data_id": "4719",
            "secret": SECRET,
        }
    ]
    assert envelope == {
        "notification_id": "8128",
        "payment_id": "4719",
        "request_id": "request-8128",
    }

    for retorno in (False, None, 0, 1, "true", object()):
        validador_falso = _ValidadorOficialFalso(resultado=retorno)
        verificador_falso = mercado_pago.MercadoPagoWebhookSignatureVerifier(
            validador=validador_falso,
            secret=SECRET,
        )
        assert verificador_falso.verificar(envelope_minimo, assinatura) is False
        assert len(validador_falso.chamadas) == 1

    detalhe_interno = "falha-interna-privada-9931"
    validador_em_falha = _ValidadorOficialFalso(
        erro=RuntimeError(
            f"token credencial payload {SECRET} {detalhe_interno}"
        )
    )
    verificador_em_falha = mercado_pago.MercadoPagoWebhookSignatureVerifier(
        validador=validador_em_falha,
        secret=SECRET,
    )
    assert verificador_em_falha.verificar(envelope_minimo, assinatura) is False
    assert len(validador_em_falha.chamadas) == 1
    _assert_publico_sanitizado(verificador_em_falha, SECRET, detalhe_interno)
