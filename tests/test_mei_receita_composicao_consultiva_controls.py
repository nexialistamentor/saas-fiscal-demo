"""Controlos negativos adicionais; contrato RED original permanece imutavel."""
import pytest

from app.services.mei_receita_composicao_consultiva import compor_receitas_mei


def fontes():
    return (
        {
            "empresa_id": 7,
            "ano_calendario": 2026,
            "completude_anual_comprovada": False,
            "total_receitas_incluidas": "100.30",
            "pendencias": [],
        },
        {
            "empresa_id": 7,
            "ano_calendario": 2026,
            "completude_anual_comprovada": False,
            "documentos_para_revisao": [],
            "documentos_sem_periodo": [],
            "receitas_confirmadas": [],
            "total_receita_confirmada": None,
        },
    )


@pytest.mark.parametrize(
    "valor",
    ["01.00", ".00", "0001.00", "１２.３０", "1.００"],
)
def test_bloqueia_valores_monetarios_nao_canonicos(valor):
    apuracao, documental = fontes()
    apuracao["total_receitas_incluidas"] = valor
    with pytest.raises(ValueError):
        compor_receitas_mei(
            empresa_id=7,
            ano_calendario=2026,
            apuracao=apuracao,
            selecao_documental=documental,
        )


@pytest.mark.parametrize("campo", ["pendencias", "documentos_para_revisao"])
def test_bloqueia_entrada_acima_do_limite(campo):
    apuracao, documental = fontes()
    destino = apuracao if campo == "pendencias" else documental
    destino[campo] = [None] * 100001
    with pytest.raises(ValueError):
        compor_receitas_mei(
            empresa_id=7,
            ano_calendario=2026,
            apuracao=apuracao,
            selecao_documental=documental,
        )