"""Controlo B1: total anual agregado deve respeitar o dominio real das fontes."""
import pytest

from app.services.mei_receita_anual_apuracao import apurar_receitas_anuais
from app.services.mei_receita_composicao_consultiva import compor_receitas_mei


def documental():
    return {
        "empresa_id": 1,
        "ano_calendario": 2026,
        "completude_anual_comprovada": False,
        "documentos_para_revisao": [],
        "documentos_sem_periodo": [],
        "receitas_confirmadas": [],
        "total_receita_confirmada": None,
    }


def fonte(total):
    return {
        "empresa_id": 1,
        "ano_calendario": 2026,
        "completude_anual_comprovada": False,
        "total_receitas_incluidas": total,
        "pendencias": [],
    }


def compor(total):
    return compor_receitas_mei(
        empresa_id=1,
        ano_calendario=2026,
        apuracao=fonte(total),
        selecao_documental=documental(),
    )


def test_b1_aceita_total_real_de_duas_receitas_validas():
    receitas = []
    for identidade, data in (
        ("11111111-1111-4111-8111-111111111111", "2026-01-10"),
        ("22222222-2222-4222-8222-222222222222", "2026-02-10"),
    ):
        receitas.append({
            "identidade_receita": identidade,
            "empresa_id": 1,
            "data_receita": data,
            "valor": "9999999999999.99",
            "categoria": "servicos",
            "origem": "informada_sem_nota",
            "estado": "vigente",
        })

    apuracao = apurar_receitas_anuais(
        empresa_id=1, ano_calendario=2026, receitas=receitas
    )
    assert apuracao["total_receitas_incluidas"] == "19999999999999.98"

    resultado = compor_receitas_mei(
        empresa_id=1,
        ano_calendario=2026,
        apuracao=apuracao,
        selecao_documental=documental(),
    )
    assert resultado["total_receitas_informadas"] == "19999999999999.98"
    assert resultado["total_consolidado_comprovado"] is None
    assert resultado["completude_anual_comprovada"] is False


def test_b1_aceita_limite_matematico_das_100000_receitas():
    resultado = compor("999999999999999000.00")
    assert resultado["total_receitas_informadas"] == "999999999999999000.00"
    assert resultado["total_consolidado_comprovado"] is None


def test_b1_rejeita_total_acima_do_limite_matematico():
    with pytest.raises(ValueError, match="TOTAL_INFORMADO_INVALIDO"):
        compor("999999999999999000.01")


def test_b1_rejeita_valor_nao_canonico():
    with pytest.raises(ValueError, match="TOTAL_INFORMADO_INVALIDO"):
        compor("019999999999999.98")
