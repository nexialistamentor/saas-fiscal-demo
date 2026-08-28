"""RED: o writer CPF autenticado deve persistir proveniencia verificavel."""

from copy import deepcopy
from types import SimpleNamespace

from app.services import assistente_service
from app.services.resultado_provenance_service import (
    PROVENANCE_KEY,
    fingerprint_resultado_json,
    verificar_resultado_persistido,
)


def test_cpf_writer_persiste_envelope_verificavel_sem_expor_proveniencia(
    monkeypatch,
):
    payload_original = {
        "tributos": {"imposto": 321.45},
        "alertas": ["alerta deterministico", "segundo alerta"],
        "_ano_referencia": 2026,
        "_estado_temporal": "resolvido",
    }
    payload_antes = deepcopy(payload_original)
    resposta_negocio = "Resposta CPF deterministica."
    estado = SimpleNamespace(relatorio=None, commits=0)

    class _QueryFake:
        def filter(self, *_args):
            return self

        def first(self):
            return estado.relatorio

    class _DBFake:
        def add(self, relatorio):
            estado.relatorio = relatorio
            relatorio.id = 741

        def commit(self):
            estado.commits += 1

        def refresh(self, _relatorio):
            pass

        def query(self, _model):
            return _QueryFake()

    def _responder_cpf_deterministico(_pergunta):
        return {
            "resposta": resposta_negocio,
            "payload": payload_original,
        }

    monkeypatch.setattr(
        assistente_service,
        "responder_cpf",
        _responder_cpf_deterministico,
    )

    resposta_externa = assistente_service.responder_pergunta(
        "quanto pago de imposto autonomo em 2026 com faturamento de 5000 por mes",
        usuario=SimpleNamespace(id=123, empresas=[], consulta_paga=False),
        db=_DBFake(),
    )

    relatorio = estado.relatorio
    assert relatorio.analysis_type == "cpf_tax"
    assert relatorio.resultado_json[PROVENANCE_KEY]
    assert relatorio.fingerprint == fingerprint_resultado_json(
        relatorio.resultado_json
    )

    payload_verificado = verificar_resultado_persistido(relatorio)
    assert payload_verificado == payload_antes
    assert PROVENANCE_KEY not in payload_verificado
    assert PROVENANCE_KEY not in resposta_externa["preview"]
    assert PROVENANCE_KEY not in resposta_externa
    assert PROVENANCE_KEY not in resposta_externa["resposta"]

    assert resposta_externa["resposta"] == resposta_negocio
    assert resposta_externa["preview"] == payload_antes
    assert resposta_externa["requires_payment"] is False
    assert relatorio.total_alertas == 2
    assert estado.commits == 2
    assert payload_original == payload_antes
