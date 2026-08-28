import json

import pytest

from app.services.serpro_pgmei_client import (
    PgmeiClientError,
    PgmeiResult,
    SerproPgmeiClient,
)


ENDPOINT = "https://trial.invalid/integra-contador/v1/consultar"
TOKEN = "trial-token-that-must-never-leak"
CONTRATANTE = "12ABC34501DE67"
CONTRIBUINTE = "98XYZ76501AB43"


class StubResponse:
    def __init__(self, status_code=200, payload=None, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._payload


class RecordingTransport:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def valid_envelope(service, data=None):
    return {
        "status": 200,
        "mensagens": [{"codigo": "SUCESSO", "texto": "Pedido processado"}],
        "dados": data if data is not None else "conteudo-nominal",
        "sistema": "PGMEI",
        "servico": service,
    }


def make_client(transport):
    return SerproPgmeiClient(
        endpoint=ENDPOINT,
        authentication={"Authorization": f"Bearer {TOKEN}"},
        timeout=7.5,
        transport=transport,
        contratante=CONTRATANTE,
    )


@pytest.mark.parametrize("service", ["GERARDASPDF21", "GERARDASCODBARRA22"])
def test_exact_request_and_nominal_raw_response_for_supported_services(service):
    envelope = valid_envelope(service)
    transport = RecordingTransport(StubResponse(payload=envelope))

    result = make_client(transport).request(
        service=service,
        contribuinte=CONTRIBUINTE,
        periodo_apuracao="202608",
    )

    assert transport.calls == [
        {
            "url": ENDPOINT,
            "json": {
                "contratante": {"numero": CONTRATANTE, "tipo": 2},
                "autorPedidoDados": {"numero": CONTRATANTE, "tipo": 2},
                "contribuinte": {"numero": CONTRIBUINTE, "tipo": 2},
                "pedidoDados": {
                    "idSistema": "PGMEI",
                    "idServico": service,
                    "versaoSistema": "1.0",
                    "dados": json.dumps(
                        {"periodoApuracao": "202608"}, separators=(",", ":")
                    ),
                },
            },
            "headers": {"Authorization": f"Bearer {TOKEN}"},
            "timeout": 7.5,
        }
    ]
    assert isinstance(result, PgmeiResult)
    assert result.status == 200
    assert result.messages == envelope["mensagens"]
    assert result.data == "conteudo-nominal"
    assert result.raw_envelope is envelope


@pytest.mark.parametrize(
    "period", ["202600", "202613", "20261", "2026-08", "", None, 202608]
)
def test_invalid_period_is_rejected_before_transport(period):
    transport = RecordingTransport(StubResponse(payload=valid_envelope("GERARDASPDF21")))
    with pytest.raises(PgmeiClientError, match="periodo_apuracao invalido"):
        make_client(transport).request("GERARDASPDF21", CONTRIBUINTE, period)
    assert transport.calls == []


def test_unexpected_service_is_rejected_before_transport():
    transport = RecordingTransport()
    with pytest.raises(PgmeiClientError, match="servico nao suportado"):
        make_client(transport).request("CONSULTA_INESPERADA", CONTRIBUINTE, "202608")
    assert transport.calls == []


def test_alphanumeric_cnpj_is_preserved_without_numeric_validation():
    transport = RecordingTransport(
        StubResponse(payload=valid_envelope("GERARDASCODBARRA22"))
    )
    make_client(transport).request("GERARDASCODBARRA22", "AB12CD34EF56GH", "202608")
    assert transport.calls[0]["json"]["contribuinte"]["numero"] == "AB12CD34EF56GH"


@pytest.mark.parametrize("error", [TimeoutError("late"), OSError("wire failed")])
def test_transport_failures_are_closed_and_sanitized(error):
    transport = RecordingTransport(error=error)
    client = make_client(transport)
    with pytest.raises(PgmeiClientError) as caught:
        client.request("GERARDASPDF21", CONTRIBUINTE, "202608")
    rendered = f"{caught.value!r} {caught.value} {client!r}"
    assert TOKEN not in rendered
    assert "late" not in rendered
    assert "wire failed" not in rendered


@pytest.mark.parametrize(
    "response, message",
    [
        (StubResponse(status_code=503, payload={}), "http status invalido"),
        (StubResponse(json_error=ValueError("body secret")), "json invalido"),
        (StubResponse(payload={**valid_envelope("GERARDASPDF21"), "status": 500}), "status interno invalido"),
        (StubResponse(payload={**valid_envelope("GERARDASPDF21"), "sistema": "OUTRO"}), "sistema divergente"),
        (StubResponse(payload={**valid_envelope("GERARDASPDF21"), "servico": "GERARDASCODBARRA22"}), "servico divergente"),
        (StubResponse(payload={key: value for key, value in valid_envelope("GERARDASPDF21").items() if key != "dados"}), "dados ausentes"),
    ],
)
def test_invalid_responses_fail_closed(response, message):
    transport = RecordingTransport(response)
    with pytest.raises(PgmeiClientError, match=message) as caught:
        make_client(transport).request("GERARDASPDF21", CONTRIBUINTE, "202608")
    assert TOKEN not in repr(caught.value)
    assert TOKEN not in str(caught.value)


def test_authentication_never_enters_payload_and_result_repr_has_no_token():
    transport = RecordingTransport(StubResponse(payload=valid_envelope("GERARDASPDF21")))
    client = make_client(transport)
    result = client.request("GERARDASPDF21", CONTRIBUINTE, "202608")
    assert TOKEN not in json.dumps(transport.calls[0]["json"])
    assert TOKEN not in repr(client)
    assert TOKEN not in repr(result)
