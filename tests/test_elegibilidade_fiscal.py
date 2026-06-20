from app.services.document_ingestion.normalizer import (
    DocumentoFiscalNormalizado,
    CampoNormalizado,
)
from app.services.document_ingestion.elegibilidade_fiscal import (
    avaliar_elegibilidade_fiscal,
    ElegibilidadeFiscal,
)


def _campo(valor: str) -> CampoNormalizado:
    return CampoNormalizado(valor=valor, confianca=95.0, origem="regex")


def _doc_danfe_valido() -> DocumentoFiscalNormalizado:
    return DocumentoFiscalNormalizado(
        chave_acesso=_campo("12345678901234567890123456789012345678901234"),
        data_emissao=_campo("19/06/2026"),
        valor_total=_campo("1.000,00"),
        cfop=_campo("5102"),
        ncm=_campo("22030000"),
        campos_nao_extraidos=[],
        texto_original_len=500,
    )


def test_danfe_com_todos_os_campos_validos_e_elegivel():
    doc = _doc_danfe_valido()
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.ELEGIVEL


def test_nao_danfe_com_campos_validos_nao_e_elegivel():
    doc = _doc_danfe_valido()
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=False)
    assert resultado == ElegibilidadeFiscal.NAO_ELEGIVEL_DANFE_NAO_DETECTADO


def test_danfe_com_chave_invalida_nao_e_elegivel():
    doc = _doc_danfe_valido()
    doc.chave_acesso = _campo("123")  # menos de 44 dígitos
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.NAO_ELEGIVEL_CHAVE_INVALIDA


def test_danfe_com_cfop_invalido_nao_e_elegivel():
    doc = _doc_danfe_valido()
    doc.cfop = _campo("0102")  # primeiro dígito = 0
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.NAO_ELEGIVEL_CFOP_INVALIDO


def test_danfe_com_ncm_invalido_nao_e_elegivel():
    doc = _doc_danfe_valido()
    doc.ncm = _campo("123")  # não tem 8 dígitos
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.NAO_ELEGIVEL_NCM_INVALIDO


def test_danfe_com_campo_obrigatorio_ausente_nao_e_elegivel():
    doc = _doc_danfe_valido()
    doc.valor_total = None
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.NAO_ELEGIVEL_CAMPOS_INCOMPLETOS


def test_chave_com_espacos_e_pontuacao_mas_44_digitos_reais_e_valida():
    doc = _doc_danfe_valido()
    # mesma chave, com ruído de formatação típico de OCR
    doc.chave_acesso = _campo("1234 5678 9012 3456 7890 1234 5678 9012 3456 7890 1234")
    resultado = avaliar_elegibilidade_fiscal(doc, detectou_danfe=True)
    assert resultado == ElegibilidadeFiscal.ELEGIVEL
