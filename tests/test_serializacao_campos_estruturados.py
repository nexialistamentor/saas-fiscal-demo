from app.services.document_ingestion.normalizer import (
    DocumentoFiscalNormalizado,
    CampoNormalizado,
)
from app.services.document_ingestion.serializacao import (
    serializar_campos_estruturados,
    _CAMPOS_VOCABULARIO,
)


def test_serializa_todos_os_13_campos_do_vocabulario():
    doc = DocumentoFiscalNormalizado(
        campos_nao_extraidos=[],
        texto_original_len=0,
    )
    resultado = serializar_campos_estruturados(doc)
    assert len(resultado) == len(_CAMPOS_VOCABULARIO) == 13
    assert set(resultado.keys()) == set(_CAMPOS_VOCABULARIO)


def test_campo_ausente_vira_valor_none_confianca_zero():
    doc = DocumentoFiscalNormalizado(
        campos_nao_extraidos=[],
        texto_original_len=0,
    )
    resultado = serializar_campos_estruturados(doc)
    campo = resultado["chave_acesso"]
    assert campo["valor"] is None
    assert campo["confianca"] == 0.0
    assert campo["origem"] is None
    assert campo["validado_humano"] is False


def test_campo_presente_preserva_valor_confianca_origem():
    doc = DocumentoFiscalNormalizado(
        chave_acesso=CampoNormalizado(
            valor="12345678901234567890123456789012345678901234",
            confianca=95.0,
            origem="regex",
            validado_humano=False,
        ),
        campos_nao_extraidos=[],
        texto_original_len=0,
    )
    resultado = serializar_campos_estruturados(doc)
    campo = resultado["chave_acesso"]
    assert campo["valor"] == "12345678901234567890123456789012345678901234"
    assert campo["confianca"] == 95.0
    assert campo["origem"] == "regex"
    assert campo["validado_humano"] is False
