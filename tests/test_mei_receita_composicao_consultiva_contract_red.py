"""Contrato RED imutavel da composicao consultiva MEI V1."""
import pytest

from app.services.mei_receita_composicao_consultiva import compor_receitas_mei


def fontes(empresa=7, ano=2026):
    apuracao = {
        "empresa_id": empresa,
        "ano_calendario": ano,
        "completude_anual_comprovada": False,
        "total_receitas_incluidas": "100.30",
        "pendencias": [],
    }
    documental = {
        "empresa_id": empresa,
        "ano_calendario": ano,
        "completude_anual_comprovada": False,
        "documentos_para_revisao": [
            {"documento_id": 42, "motivos": ["ESTADO_FISCAL_NAO_COMPROVADO"]}
        ],
        "documentos_sem_periodo": [],
        "receitas_confirmadas": [],
        "total_receita_confirmada": None,
    }
    return apuracao, documental


def compor(empresa=7, ano=2026, apuracao=None, documental=None):
    padrao_a, padrao_d = fontes(empresa, ano)
    return compor_receitas_mei(
        empresa_id=empresa,
        ano_calendario=ano,
        apuracao=padrao_a if apuracao is None else apuracao,
        selecao_documental=padrao_d if documental is None else documental,
    )


def test_preserva_total_parcial_sem_certificar_xml():
    resultado = compor()
    assert resultado["total_receitas_informadas"] == "100.30"
    assert resultado["total_consolidado_comprovado"] is None
    assert resultado["completude_anual_comprovada"] is False
    assert len(resultado["documentos_para_conferencia"]) == 1


def test_nao_soma_documento_ao_total_informado():
    apuracao, documental = fontes()
    documental["documentos_para_revisao"][0]["metadados"] = {
        "valor_total": 100.30,
        "data_emissao": "2026-10-08",
    }
    resultado = compor(apuracao=apuracao, documental=documental)
    assert resultado["total_receitas_informadas"] == "100.30"
    assert resultado["total_consolidado_comprovado"] is None


@pytest.mark.parametrize("campo", ["empresa_id", "ano_calendario"])
def test_recusa_fontes_com_escopo_divergente(campo):
    apuracao, documental = fontes()
    documental[campo] += 1
    with pytest.raises(ValueError):
        compor(apuracao=apuracao, documental=documental)


def test_preserva_pendencias_sem_alterar_entradas():
    apuracao, documental = fontes()
    apuracao["pendencias"] = [{"identidade_receita": "pendente"}]
    original = repr((apuracao, documental))
    resultado = compor(apuracao=apuracao, documental=documental)
    assert resultado["pendencias_receitas"] == apuracao["pendencias"]
    assert repr((apuracao, documental)) == original


def test_recusa_documentos_convertidos_em_receita_confirmada():
    apuracao, documental = fontes()
    documental["receitas_confirmadas"] = [{"documento_id": 42}]
    with pytest.raises(ValueError):
        compor(apuracao=apuracao, documental=documental)


def test_recusa_total_documental_certificado():
    apuracao, documental = fontes()
    documental["total_receita_confirmada"] = "100.30"
    with pytest.raises(ValueError):
        compor(apuracao=apuracao, documental=documental)


def test_nao_inventa_faturamento_zero():
    apuracao, documental = fontes()
    apuracao["total_receitas_incluidas"] = "0.00"
    documental["documentos_para_revisao"] = []
    resultado = compor(apuracao=apuracao, documental=documental)
    assert resultado["total_receitas_informadas"] == "0.00"
    assert resultado["completude_anual_comprovada"] is False
    assert resultado["total_consolidado_comprovado"] is None