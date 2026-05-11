"""
Testes do normalizador documental soberano — V1.
"""

from app.services.document_ingestion.normalizer import (
    CampoNormalizado,
    DocumentoFiscalNormalizado,
    normalizar,
)

TEXTO_DANFE = (
    "DANFE DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA "
    "Emitente CNPJ 12.345.678/0001-90 "
    "Destinatário CNPJ 98.765.432/0001-11 "
    "Chave de Acesso 12345678901234567890123456789012345678901234 "
    "CFOP 5102 NCM 84713012 "
    "Valor Total R$ 1.500,00 Base de Cálculo R$ 1.200,00 "
    "Alíquota ICMS 12% PIS 1,65% COFINS 7,60% "
    "Data de Emissão 01/05/2026"
)


# ---------------------------------------------------------------------------
# Schema e tipos
# ---------------------------------------------------------------------------
def test_retorna_documento_fiscal_normalizado():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert isinstance(doc, DocumentoFiscalNormalizado)


def test_campos_sao_campo_normalizado_ou_none():
    doc = normalizar(TEXTO_DANFE, 95.0)
    for attr in ["cnpj_emitente", "cfop", "valor_total", "chave_acesso"]:
        campo = getattr(doc, attr)
        assert campo is None or isinstance(campo, CampoNormalizado)


# ---------------------------------------------------------------------------
# Extracção de campos
# ---------------------------------------------------------------------------
def test_extrai_cnpj_emitente():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.cnpj_emitente is not None
    assert "12.345.678" in doc.cnpj_emitente.valor


def test_extrai_cnpj_destinatario():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.cnpj_destinatario is not None
    assert "98.765.432" in doc.cnpj_destinatario.valor


def test_extrai_chave_acesso_44_digitos():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.chave_acesso is not None
    assert len(doc.chave_acesso.valor.replace(" ", "")) == 44


def test_extrai_cfop():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.cfop is not None
    assert doc.cfop.valor == "5102"


def test_extrai_valor_total():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.valor_total is not None
    assert "1.500,00" in doc.valor_total.valor


def test_extrai_data_emissao():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.data_emissao is not None
    assert "2026" in doc.data_emissao.valor


def test_extrai_aliquota_icms():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.aliquota_icms is not None


# ---------------------------------------------------------------------------
# Confiança herdada
# ---------------------------------------------------------------------------
def test_confianca_herdada_do_score_global():
    doc = normalizar(TEXTO_DANFE, 87.5)
    assert doc.cnpj_emitente.confianca == 87.5
    assert doc.cfop.confianca == 87.5


def test_validado_humano_false_por_defeito():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.cnpj_emitente.validado_humano is False


def test_origem_regex():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.cnpj_emitente.origem == "regex"


# ---------------------------------------------------------------------------
# Campos não extraídos
# ---------------------------------------------------------------------------
def test_texto_vazio_sem_campos():
    doc = normalizar("", 0.0)
    assert doc.cnpj_emitente is None
    assert len(doc.campos_nao_extraidos) > 0


def test_campos_nao_extraidos_listados():
    doc = normalizar("texto sem campos fiscais", 30.0)
    assert "cnpj_emitente" in doc.campos_nao_extraidos


def test_texto_original_len():
    doc = normalizar(TEXTO_DANFE, 95.0)
    assert doc.texto_original_len == len(TEXTO_DANFE)


# ---------------------------------------------------------------------------
# Ambiguidade documental — V1 heurístico (primeiro match ganha)
# ---------------------------------------------------------------------------
def test_multiplos_cnpjs_primeiro_match_emitente_v1():
    """V1: primeiro CNPJ encontrado = emitente. Resolução semântica é V2."""
    texto = (
        "Emitente CNPJ 11.111.111/0001-11 "
        "Destinatario CNPJ 22.222.222/0001-22 "
        "Transportadora CNPJ 33.333.333/0001-33"
    )
    doc = normalizar(texto, 90.0)
    assert doc.cnpj_emitente is not None
    assert "11.111.111" in doc.cnpj_emitente.valor  # primeiro match


# ---------------------------------------------------------------------------
# Formato monetário — V1 assume padrão brasileiro (R$ 1.200,00)
# ---------------------------------------------------------------------------
def test_valor_padrao_monetario_brasileiro():
    """V1 assume R$ com separador brasileiro. Formato internacional é V2."""
    texto = "Valor Total R$ 1.200,00"
    doc = normalizar(texto, 95.0)
    assert doc.valor_total is not None
    assert "1.200,00" in doc.valor_total.valor
