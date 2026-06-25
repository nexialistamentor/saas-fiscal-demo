"""
tests/test_b5_01_classifier_xml_fiscal.py

B5-01 — Classificação XML fiscal com extensão mascarada.

Cobertura:
  P1  danfe2.nexialista (NF-e mod 55) → XML_FISCAL  [amostra real, skipif ausente]
  P2  danfe 1.nexialista (NFC-e mod 65) → XML_FISCAL [amostra real, skipif ausente]
  P3  danfe3.pdf → DANFE (invariante inalterado)     [amostra real, skipif ausente]
  P4  danfe4.jpg → IMAGE (invariante inalterado)     [amostra real, skipif ausente]
  P5  XML sintético com namespace SEFAZ + nfeProc → XML_FISCAL
  P6  XML sintético com namespace SEFAZ + infNFe → XML_FISCAL
  N1  bytes desconhecidos → UNKNOWN
  N2  PDF sintético (magic bytes %PDF) → não XML_FISCAL
  N3  XML sem namespace SEFAZ → UNKNOWN
  N4  XML com marcador SEFAZ solto, sem estrutura NF-e → UNKNOWN (falso positivo bloqueado)
"""
from pathlib import Path
import pytest
from app.services.document_ingestion.classifier import TipoDocumento, classificar

# Caminhos das amostras reais
XMLS_DIR = Path("app/xmls_testes")
DANFE2 = XMLS_DIR / "danfe2.nexialista"
DANFE1 = XMLS_DIR / "danfe 1.nexialista"
DANFE3 = XMLS_DIR / "danfe3.pdf"
DANFE4 = XMLS_DIR / "danfe4.jpg"

# ---------------------------------------------------------------------------
# Fixtures sintéticas (CI-safe — sem dados reais)
# ---------------------------------------------------------------------------

XML_SEFAZ_NFEPROC = b"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe35260500000000000000550010000000011000000010">
    </infNFe>
  </NFe>
</nfeProc>"""

XML_SEFAZ_INFNFE = b"""<?xml version="1.0" encoding="UTF-8"?>
<NFe xmlns="http://www.portalfiscal.inf.br/nfe">
  <infNFe versao="4.00">
  </infNFe>
</NFe>"""

XML_SEM_NAMESPACE_SEFAZ = b"""<?xml version="1.0"?>
<root><item>dados sem namespace sefaz</item></root>"""

# N4 — marcador SEFAZ presente mas sem estrutura NF-e
XML_MARCADOR_SOLTO = b"""<?xml version="1.0"?>
<root>portalfiscal.inf.br/nfe</root>"""

PDF_MAGIC = b"%PDF-1.4"  # só magic bytes — não tenta parse

BYTES_DESCONHECIDOS = b"\x00\x01\x02\x03 dados desconhecidos"

# ---------------------------------------------------------------------------
# Testes com amostras reais (skipped se ficheiros ausentes)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DANFE2.exists(), reason="amostra real ausente — validação local")
def test_p1_danfe2_nexialista_xml_fiscal():
    """P1 — danfe2.nexialista (NF-e mod 55) → XML_FISCAL."""
    resultado = classificar(DANFE2.read_bytes(), nome_ficheiro="danfe2.nexialista")
    assert resultado.tipo == TipoDocumento.XML_FISCAL, f"Obtido: {resultado.tipo}"


@pytest.mark.skipif(not DANFE1.exists(), reason="amostra real ausente — validação local")
def test_p2_danfe1_nexialista_xml_fiscal():
    """P2 — danfe 1.nexialista (NFC-e mod 65) → XML_FISCAL."""
    resultado = classificar(DANFE1.read_bytes(), nome_ficheiro="danfe 1.nexialista")
    assert resultado.tipo == TipoDocumento.XML_FISCAL, f"Obtido: {resultado.tipo}"


@pytest.mark.skipif(not DANFE3.exists(), reason="amostra real ausente — validação local")
def test_p3_danfe3_pdf_danfe():
    """P3 — danfe3.pdf → DANFE (invariante inalterado)."""
    resultado = classificar(DANFE3.read_bytes(), nome_ficheiro="danfe3.pdf")
    assert resultado.tipo == TipoDocumento.DANFE, f"Obtido: {resultado.tipo}"
    assert resultado.detectou_danfe is True


@pytest.mark.skipif(not DANFE4.exists(), reason="amostra real ausente — validação local")
def test_p4_danfe4_jpg_image():
    """P4 — danfe4.jpg → IMAGE (invariante inalterado)."""
    resultado = classificar(DANFE4.read_bytes(), nome_ficheiro="danfe4.jpg")
    assert resultado.tipo == TipoDocumento.IMAGE, f"Obtido: {resultado.tipo}"


# ---------------------------------------------------------------------------
# Testes sintéticos (CI-safe — sempre correm)
# ---------------------------------------------------------------------------


def test_p5_xml_sintetico_nfeproc():
    """P5 — XML sintético com nfeProc + namespace SEFAZ → XML_FISCAL."""
    resultado = classificar(XML_SEFAZ_NFEPROC, nome_ficheiro="teste.nexialista")
    assert resultado.tipo == TipoDocumento.XML_FISCAL


def test_p6_xml_sintetico_infnfe():
    """P6 — XML sintético com infNFe + namespace SEFAZ → XML_FISCAL."""
    resultado = classificar(XML_SEFAZ_INFNFE, nome_ficheiro="teste.xml")
    assert resultado.tipo == TipoDocumento.XML_FISCAL


def test_n1_bytes_desconhecidos_unknown():
    """N1 — bytes desconhecidos → UNKNOWN."""
    resultado = classificar(BYTES_DESCONHECIDOS, nome_ficheiro="desconhecido.bin")
    assert resultado.tipo == TipoDocumento.UNKNOWN


def test_n2_pdf_magic_nao_xml_fiscal():
    """N2 — magic bytes %PDF → não XML_FISCAL."""
    resultado = classificar(PDF_MAGIC, nome_ficheiro="teste.pdf")
    assert resultado.tipo != TipoDocumento.XML_FISCAL


def test_n3_xml_sem_namespace_sefaz_unknown():
    """N3 — XML sem namespace SEFAZ → UNKNOWN."""
    resultado = classificar(XML_SEM_NAMESPACE_SEFAZ, nome_ficheiro="outro.xml")
    assert resultado.tipo == TipoDocumento.UNKNOWN


def test_n4_xml_marcador_solto_nao_e_fiscal():
    """N4 — XML com marcador SEFAZ solto, sem estrutura NF-e → UNKNOWN (falso positivo bloqueado)."""
    resultado = classificar(XML_MARCADOR_SOLTO, nome_ficheiro="fake.xml")
    assert resultado.tipo == TipoDocumento.UNKNOWN
