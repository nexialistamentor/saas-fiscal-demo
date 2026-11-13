"""Catraca local do adaptador PA; zero escrita e zero ligacao a producao."""
from contextlib import nullcontext
from datetime import date

import pytest

from app.services import pa_entrada_cotejo_adapter as adapter


class SessaoFalsa:
    def __init__(self):
        self.no_autoflush = nullcontext()
        self.consultas = 0

    def get(self, *_args):
        self.consultas += 1
        raise AssertionError("nao deve consultar ORM nestes testes")


def _entrada():
    return {
        "db": SessaoFalsa(), "indice_item": 1,
        "uf_operacao": "PA", "ncm": "22021000", "cest": "0301001",
        "categoria_remetente": "distribuidor_deposito_atacadista",
        "tipo_operacao": "antecipacao_na_entrada",
        "data_referencia": date(2023, 10, 1),
        "rule_version_record_id": "rv-pa-sintetica",
    }


def _candidato():
    return {
        "estado": "CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE",
        "motivo": "PROVA_JURIDICA_EXTERNA_E_APLICABILIDADE_NAO_COMPROVADAS",
        "rule_version_record_id": "rv-pa-sintetica",
        "vinculos_declarados_cotejados": True,
        "autoridade_normativa_verificada": False,
        "calculo_autorizado": False,
        "norma_resolvida": None,
    }


def _simular(monkeypatch, resultado):
    chamadas = []

    def fake(**kwargs):
        chamadas.append(kwargs)
        return resultado

    monkeypatch.setattr(adapter, "cotejar_candidato_pa_entrada", fake)
    return chamadas


@pytest.mark.parametrize("campo,valor", [
    ("categoria_remetente", None),
    ("tipo_operacao", None),
    ("rule_version_record_id", None),
    ("cest", None),
    ("cest", "0301002"),
    ("categoria_remetente", "industrial_importador_arrematante_engarrafador"),
    ("tipo_operacao", "saida_interna"),
    ("uf_operacao", "SP"),
    ("ncm", "22029900"),
    ("data_referencia", None),
    ("indice_item", True),
    ("indice_item", 0),
    ("indice_item", 501),
    ("uf_operacao", True),
    ("ncm", 22021000),
    ("cest", 301001),
    ("tipo_operacao", True),
    ("rule_version_record_id", 123),
])
def test_falta_ou_escopo_divergente_nao_chama_consumidor(monkeypatch, campo, valor):
    chamadas = _simular(monkeypatch, _candidato())
    entrada = _entrada()
    entrada[campo] = valor
    resultado = adapter.cotejar_item_pa_entrada(**entrada)
    assert resultado["estado"] == "ABSTENCAO"
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None
    assert not chamadas
    assert entrada["db"].consultas == 0


def test_candidato_passado_somente_com_campos_negativos(monkeypatch):
    chamadas = _simular(monkeypatch, _candidato())
    entrada = _entrada()
    resultado = adapter.cotejar_item_pa_entrada(**entrada)
    assert len(chamadas) == 1
    assert "indice_item" not in chamadas[0]
    assert chamadas[0]["rule_version_record_id"] == "rv-pa-sintetica"
    assert resultado["indice_item"] == 1
    assert resultado["estado"] == _candidato()["estado"]
    assert resultado["vinculos_declarados_cotejados"] is True
    assert resultado["autoridade_normativa_verificada"] is False
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None
    assert "mva" not in resultado and "aliquota" not in resultado


@pytest.mark.parametrize("alteracao", [
    {"calculo_autorizado": True},
    {"autoridade_normativa_verificada": True},
    {"norma_resolvida": {"mva": 40}},
    {"mva_percentual": "40"},
    {"rule_version_record_id": "outra-regra"},
    {"vinculos_declarados_cotejados": False},
    {"estado": "NORMA_VERIFICADA"},
])
def test_contrato_inesperado_falha_fechado(monkeypatch, alteracao):
    retorno = {**_candidato(), **alteracao}
    _simular(monkeypatch, retorno)
    resultado = adapter.cotejar_item_pa_entrada(**_entrada())
    assert resultado["estado"] == "ABSTENCAO"
    assert resultado["motivo"] == "CONTRATO_COTEJO_INCOMPATIVEL"
    assert resultado["calculo_autorizado"] is False
    assert resultado["norma_resolvida"] is None


def test_abstencao_do_consumidor_nao_e_promovida(monkeypatch):
    retorno = {**_candidato(), "estado": "ABSTENCAO",
               "rule_version_record_id": None,
               "vinculos_declarados_cotejados": False}
    _simular(monkeypatch, retorno)
    resultado = adapter.cotejar_item_pa_entrada(**_entrada())
    assert resultado["estado"] == "ABSTENCAO"
    assert resultado["motivo"] == "COTEJO_ADR020_ABSTEVE"
    assert resultado["calculo_autorizado"] is False


def test_erro_de_leitura_nao_libera_calculo(monkeypatch):
    def falhar(**_kwargs):
        raise RuntimeError("sem conexao")

    monkeypatch.setattr(adapter, "cotejar_candidato_pa_entrada", falhar)
    resultado = adapter.cotejar_item_pa_entrada(**_entrada())
    assert resultado["motivo"] == "COTEJO_ADR020_INDISPONIVEL"
    assert resultado["calculo_autorizado"] is False
    assert resultado["vinculos_declarados_cotejados"] is False


@pytest.mark.parametrize("retorno", [None, "erro", [], 42])
def test_retorno_nao_dicionario_abstem(monkeypatch, retorno):
    _simular(monkeypatch, retorno)
    resultado = adapter.cotejar_item_pa_entrada(**_entrada())
    assert resultado["motivo"] == "CONTRATO_COTEJO_INCOMPATIVEL"
    assert resultado["calculo_autorizado"] is False
