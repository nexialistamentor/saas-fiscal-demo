"""
app/services/document_ingestion/xml_fiscal_adapter.py

B5-02 — Adaptador XML fiscal para EvidenciaFiscalComparavel.

Responsabilidade única:
  - Receber bytes de XML_FISCAL (NF-e mod 55 / NFC-e mod 65)
  - Chamar ler_xml_unico (já existente) para campos principais
  - Extrair campos ausentes em ler_xml_unico: modelo, serie, protocolo, CNPJ dest
  - Devolver EvidenciaFiscalComparavel (DTO neutro de evidencia_comparavel.py)

Princípio:
  XML_FISCAL não passa pelo extractor.py (pipeline de texto bruto).
  XML estruturado tem parser próprio (ler_xml_unico).
  Este adapter é a ponte entre classificação e conciliação.

Fora de escopo:
  - Não valida assinatura digital
  - Não persiste nada
  - Não chama motor fiscal
  - Não faz OCR
  - Não altera xml_service.py
"""

from decimal import Decimal, InvalidOperation

import defusedxml.ElementTree as ET

from app.services.document_ingestion.evidencia_comparavel import EvidenciaFiscalComparavel
from app.xml_service import ler_xml_unico

# Namespace canónico SEFAZ NF-e
_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def extrair_evidencia_xml_fiscal(conteudo: bytes) -> EvidenciaFiscalComparavel:
    """
    Extrai EvidenciaFiscalComparavel de bytes XML_FISCAL.
    Chama ler_xml_unico para campos principais.
    Extrai directamente: modelo, serie, protocolo, CNPJ destinatário.
    """
    # 1. Parse via ler_xml_unico (reutiliza lógica existente)
    try:
        dados = ler_xml_unico(xml_bytes=conteudo)
    except Exception as exc:
        return EvidenciaFiscalComparavel(
            origem="xml_fiscal",
            chave_nfe=None,
            cnpj_emitente=None,
            cnpj_destinatario=None,
            numero_nota=None,
            serie=None,
            valor_total=None,
            modelo=None,
            protocolo=None,
            uf_emit=None,
            uf_dest=None,
            erro=f"Erro ao parsear XML fiscal: {exc}",
        )

    # 2. Campos ausentes em ler_xml_unico — extrair directamente
    modelo    = _extrair_campo_ide(conteudo, "mod")
    serie     = _extrair_campo_ide(conteudo, "serie")
    protocolo = _extrair_protocolo(conteudo)
    cnpj_dest = _extrair_cnpj_destinatario(conteudo)

    return EvidenciaFiscalComparavel(
        origem="xml_fiscal",
        chave_nfe=dados.get("chave_nfe"),
        cnpj_emitente=dados.get("cnpj"),
        cnpj_destinatario=cnpj_dest,
        numero_nota=dados.get("numero_nota"),
        serie=serie,
        valor_total=_parse_decimal(dados.get("valor_total")),
        modelo=modelo,
        protocolo=protocolo,
        uf_emit=dados.get("uf_emit"),
        uf_dest=dados.get("uf_dest"),
        erro=None,
    )


# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _extrair_campo_ide(conteudo: bytes, campo: str) -> str | None:
    """Extrai campo textual de <ide> pelo nome do elemento."""
    try:
        root = ET.fromstring(conteudo)
        ide = root.find(".//nfe:ide", _NS)
        if ide is None:
            return None
        el = ide.find(f"nfe:{campo}", _NS)
        return el.text.strip() if el is not None and el.text else None
    except Exception:
        return None


def _extrair_protocolo(conteudo: bytes) -> str | None:
    """Extrai número de protocolo SEFAZ de <protNFe>/<infProt>/<nProt>."""
    try:
        root = ET.fromstring(conteudo)
        # Estrutura canónica: nfeProc/protNFe/infProt/nProt
        prot = root.find(".//nfe:protNFe/nfe:infProt/nfe:nProt", _NS)
        if prot is not None and prot.text:
            return prot.text.strip()
        # Fallback: infProt em qualquer posição
        prot = root.find(".//nfe:infProt/nfe:nProt", _NS)
        return prot.text.strip() if prot is not None and prot.text else None
    except Exception:
        return None


def _extrair_cnpj_destinatario(conteudo: bytes) -> str | None:
    """Extrai CNPJ ou CPF do destinatário (<dest>)."""
    try:
        root = ET.fromstring(conteudo)
        dest = root.find(".//nfe:dest", _NS)
        if dest is None:
            return None
        cnpj = dest.find("nfe:CNPJ", _NS)
        if cnpj is not None and cnpj.text:
            return cnpj.text.strip()
        cpf = dest.find("nfe:CPF", _NS)
        return cpf.text.strip() if cpf is not None and cpf.text else None
    except Exception:
        return None


def _parse_decimal(valor: object) -> Decimal | None:
    """Converte valor (str, float, None) para Decimal. None se inválido."""
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None
