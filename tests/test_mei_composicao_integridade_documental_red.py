"""RED adicional: integridade da estrutura documental consultiva."""
import pytest

from app.services.mei_receita_composicao_consultiva import compor_receitas_mei


@pytest.mark.parametrize("documentos", [
    [None],
    [{"motivos": ["ESTADO_FISCAL_NAO_COMPROVADO"]}],
    [{"documento_id": 42, "motivos": "texto_invalido"}],
])
def test_recusa_estrutura_documental_invalida(documentos):
    apuracao = {
        "empresa_id": 7,
        "ano_calendario": 2026,
        "completude_anual_comprovada": False,
        "total_receitas_incluidas": "100.30",
        "pendencias": [],
    }
    selecao = {
        "empresa_id": 7,
        "ano_calendario": 2026,
        "completude_anual_comprovada": False,
        "documentos_para_revisao": documentos,
        "documentos_sem_periodo": [],
        "receitas_confirmadas": [],
        "total_receita_confirmada": None,
    }

    with pytest.raises(ValueError):
        compor_receitas_mei(
            empresa_id=7,
            ano_calendario=2026,
            apuracao=apuracao,
            selecao_documental=selecao,
        )