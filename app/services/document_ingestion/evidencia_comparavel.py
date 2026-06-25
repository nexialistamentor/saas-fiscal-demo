"""
app/services/document_ingestion/evidencia_comparavel.py

DTO neutro para conciliação entre evidências documentais.

Responsabilidade única:
  Definir o contrato de dados comparáveis entre documentos de origens distintas:
  XML fiscal, DANFE PDF, DANFE imagem/OCR, e futuros tipos.

Princípio:
  Este módulo não depende de nenhuma origem específica.
  XML fiscal importa daqui. DANFE PDF importa daqui. Conciliação importa daqui.
  Nenhum adapter importa de outro adapter.

Fora de escopo:
  - Sem ORM, sem banco, sem motor fiscal, sem OCR, sem upload
  - Sem lógica de extracção
  - Sem lógica de conciliação
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class EvidenciaFiscalComparavel:
    """
    DTO puro para conciliação entre evidências documentais.

    Campos:
      origem        → "xml_fiscal" | "danfe_pdf" | "danfe_imagem"
      chave_nfe     → 44 dígitos (identificador único SEFAZ)
      cnpj_emitente → 14 dígitos
      cnpj_dest     → 14 dígitos ou CPF do destinatário
      numero_nota   → número da NF
      serie         → série da NF (campo obrigatório para conciliação sem chave)
      valor_total   → Decimal — tolerância ±0.01 na conciliação
      modelo        → "55" (NF-e) | "65" (NFC-e)
      protocolo     → número de protocolo SEFAZ (auxiliar de conciliação)
      uf_emit       → UF do emitente
      uf_dest       → UF do destinatário
      erro          → preenchido se extracção falhou; demais campos podem ser None
    """
    origem: str
    chave_nfe: str | None
    cnpj_emitente: str | None
    cnpj_destinatario: str | None
    numero_nota: str | None
    serie: str | None
    valor_total: Decimal | None
    modelo: str | None
    protocolo: str | None
    uf_emit: str | None
    uf_dest: str | None
    erro: str | None = None
