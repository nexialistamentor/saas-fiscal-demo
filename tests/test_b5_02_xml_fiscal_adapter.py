"""
tests/test_b5_02_xml_fiscal_adapter.py

B5-02 — EvidenciaFiscalComparavel do XML fiscal.

Cobertura:
  P1  danfe2.nexialista → campos reais: modelo=55, chave, CNPJs, serie, protocolo
  P2  danfe 1.nexialista → modelo=65 (NFC-e)
  P3  XML sintético completo → todos os campos extraídos correctamente
  P4  DTO neutro: EvidenciaFiscalComparavel importado de evidencia_comparavel.py
  N1  bytes inválidos → erro preenchido, não excepção
  N2  XML sem <mod> → modelo=None, não falha
  N3  XML sem destinatário → cnpj_destinatario=None, não falha
  N4  XML sem <serie> → serie=None, não falha
  N5  XML sem protocolo → protocolo=None, não falha

Fixtures sintéticas: CNPJs e chaves fictícias (sem dados reais).
Amostras reais: skipped se ausentes (P1/P2).
"""
from decimal import Decimal
from pathlib import Path
import pytest

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.services.document_ingestion.xml_fiscal_adapter import extrair_evidencia_xml_fiscal

XMLS_DIR = Path("app/xmls_testes")
DANFE2 = XMLS_DIR / "danfe2.nexialista"
DANFE1 = XMLS_DIR / "danfe 1.nexialista"

# ---------------------------------------------------------------------------
# Fixtures sintéticas — CNPJs e chaves 100% fictícias, estrutura nfeProc real
# ---------------------------------------------------------------------------

# CNPJ fictício: 99999999000191 / 88888888000188
# Chave fictícia: 35 + data + CNPJ fictício + mod + serie + nNF + cNF + dígito
_CHAVE_SINTETICA = "35260699999999000191550010000000011000000010"
_CNPJ_EMIT = "99999999000191"
_CNPJ_DEST = "88888888000188"
_NPROT = "135260099999999999"

XML_COMPLETO = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe{_CHAVE_SINTETICA}">
      <ide>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>1</nNF>
        <tpNF>1</tpNF>
        <cUF>35</cUF>
        <cMunFG>3550308</cMunFG>
      </ide>
      <emit>
        <CNPJ>{_CNPJ_EMIT}</CNPJ>
        <xNome>EMPRESA SINTETICA EMITENTE LTDA</xNome>
        <enderEmit><UF>SP</UF></enderEmit>
      </emit>
      <dest>
        <CNPJ>{_CNPJ_DEST}</CNPJ>
        <xNome>EMPRESA SINTETICA DESTINATARIA LTDA</xNome>
        <enderDest><UF>PA</UF></enderDest>
      </dest>
      <total>
        <ICMSTot><vNF>1000.00</vNF></ICMSTot>
      </total>
    </infNFe>
  </NFe>
  <protNFe versao="4.00">
    <infProt>
      <chNFe>{_CHAVE_SINTETICA}</chNFe>
      <nProt>{_NPROT}</nProt>
    </infProt>
  </protNFe>
</nfeProc>""".encode()

XML_SEM_MOD = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe{_CHAVE_SINTETICA}">
      <ide>
        <serie>1</serie>
        <nNF>1</nNF>
        <tpNF>1</tpNF>
      </ide>
      <emit><CNPJ>{_CNPJ_EMIT}</CNPJ><xNome>EMIT SINT</xNome><enderEmit><UF>SP</UF></enderEmit></emit>
      <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
    </infNFe>
  </NFe>
</nfeProc>""".encode()

XML_SEM_DEST = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe{_CHAVE_SINTETICA}">
      <ide>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>1</nNF>
        <tpNF>1</tpNF>
      </ide>
      <emit><CNPJ>{_CNPJ_EMIT}</CNPJ><xNome>EMIT SINT</xNome><enderEmit><UF>SP</UF></enderEmit></emit>
      <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
    </infNFe>
  </NFe>
</nfeProc>""".encode()

XML_SEM_SERIE = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe{_CHAVE_SINTETICA}">
      <ide>
        <mod>55</mod>
        <nNF>1</nNF>
        <tpNF>1</tpNF>
      </ide>
      <emit><CNPJ>{_CNPJ_EMIT}</CNPJ><xNome>EMIT SINT</xNome><enderEmit><UF>SP</UF></enderEmit></emit>
      <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
    </infNFe>
  </NFe>
</nfeProc>""".encode()

XML_SEM_PROTOCOLO = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe versao="4.00" Id="NFe{_CHAVE_SINTETICA}">
      <ide>
        <mod>55</mod>
        <serie>1</serie>
        <nNF>1</nNF>
        <tpNF>1</tpNF>
      </ide>
      <emit><CNPJ>{_CNPJ_EMIT}</CNPJ><xNome>EMIT SINT</xNome><enderEmit><UF>SP</UF></enderEmit></emit>
      <total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>
    </infNFe>
  </NFe>
</nfeProc>""".encode()

BYTES_INVALIDOS = b"\x00\x01\x02 nao e xml"

# ---------------------------------------------------------------------------
# Testes com amostras reais (skipped se ausentes)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DANFE2.exists(), reason="amostra real ausente — validação local")
def test_p1_danfe2_campos_reais():
    """P1 — danfe2.nexialista → campos principais extraídos, modelo=55."""
    ev = extrair_evidencia_xml_fiscal(DANFE2.read_bytes())
    assert ev.erro is None, f"Erro inesperado: {ev.erro}"
    assert ev.origem == "xml_fiscal"
    assert ev.modelo == "55"
    assert ev.chave_nfe is not None and len(ev.chave_nfe) == 44
    assert ev.cnpj_emitente is not None
    assert ev.numero_nota is not None
    assert ev.serie is not None
    assert ev.valor_total is not None and ev.valor_total > 0


@pytest.mark.skipif(not DANFE1.exists(), reason="amostra real ausente — validação local")
def test_p2_danfe1_modelo_65():
    """P2 — danfe 1.nexialista → modelo=65 (NFC-e)."""
    ev = extrair_evidencia_xml_fiscal(DANFE1.read_bytes())
    assert ev.erro is None, f"Erro inesperado: {ev.erro}"
    assert ev.modelo == "65"


# ---------------------------------------------------------------------------
# Testes sintéticos (CI-safe — sempre correm)
# ---------------------------------------------------------------------------


def test_p3_xml_completo_todos_campos():
    """P3 — XML sintético completo → todos os campos extraídos correctamente."""
    ev = extrair_evidencia_xml_fiscal(XML_COMPLETO)
    assert ev.erro is None
    assert ev.origem == "xml_fiscal"
    assert ev.modelo == "55"
    assert ev.serie == "1"
    assert ev.numero_nota == "1"
    assert ev.cnpj_emitente == _CNPJ_EMIT
    assert ev.cnpj_destinatario == _CNPJ_DEST
    assert ev.uf_emit == "SP"
    assert ev.uf_dest == "PA"
    assert ev.valor_total == Decimal("1000.00")
    assert ev.protocolo == _NPROT
    assert ev.chave_nfe == _CHAVE_SINTETICA


def test_p4_dto_importado_de_modulo_neutro():
    """P4 — EvidenciaFiscalComparavel deve ser importável de evidencia_comparavel.py."""
    from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel as DTO
    ev = extrair_evidencia_xml_fiscal(XML_COMPLETO)
    assert isinstance(ev, DTO)


def test_n1_bytes_invalidos_erro_preenchido():
    """N1 — bytes inválidos → erro preenchido, não excepção."""
    ev = extrair_evidencia_xml_fiscal(BYTES_INVALIDOS)
    assert ev.erro is not None
    assert ev.chave_nfe is None
    assert ev.serie is None


def test_n2_xml_sem_mod_modelo_none():
    """N2 — XML sem <mod> → modelo=None, não falha."""
    ev = extrair_evidencia_xml_fiscal(XML_SEM_MOD)
    assert ev.modelo is None
    assert ev.erro is None


def test_n3_xml_sem_dest_cnpj_none():
    """N3 — XML sem destinatário → cnpj_destinatario=None, não falha."""
    ev = extrair_evidencia_xml_fiscal(XML_SEM_DEST)
    assert ev.cnpj_destinatario is None
    assert ev.erro is None


def test_n4_xml_sem_serie_serie_none():
    """N4 — XML sem <serie> → serie=None, não falha."""
    ev = extrair_evidencia_xml_fiscal(XML_SEM_SERIE)
    assert ev.serie is None
    assert ev.erro is None


def test_n5_xml_sem_protocolo_protocolo_none():
    """N5 — XML sem protocolo → protocolo=None, não falha."""
    ev = extrair_evidencia_xml_fiscal(XML_SEM_PROTOCOLO)
    assert ev.protocolo is None
    assert ev.erro is None
