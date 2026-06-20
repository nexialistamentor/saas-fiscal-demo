"""
DT-DOC-03 -- Elegibilidade fiscal para promotion (CT-DOC-001 secao 5).

Determina se um DocumentoFiscalNormalizado, combinado com o resultado
de classificacao (detectou_danfe), e elegivel para promotion automatica
nesta versao.

Regra V1 (conservadora):
  DANFE detectado
    + campos obrigatorios completos (chave_acesso, data_emissao, valor_total)
    + chave de acesso valida (44 digitos apos normalizacao)
    + CFOP valido (4 digitos apos normalizacao, primeiro != 0)
    + NCM valido (8 digitos apos normalizacao)
    = ELEGIVEL

  Nao-DANFE (mesmo com campos fiscais sintacticamente presentes)
    = NAO ELEGIVEL nesta versao (evidencia estrutural insuficiente)

Esta funcao nao toca em classifier.py. Consome detectou_danfe ja
calculado pelo classificador, conforme decisao registada: nao
duplicar nem extrair _detectar_danfe nesta fase.

Validacao de digitos e feita apos remocao de nao-digitos (espacos,
pontuacao), porque OCR/PDF pode introduzir formatacao na chave de
acesso, CFOP ou NCM extraidos -- a evidencia numerica subjacente
continua valida mesmo com ruido de formatacao.
"""

import re
from enum import Enum

from app.services.document_ingestion.normalizer import DocumentoFiscalNormalizado


class ElegibilidadeFiscal(str, Enum):
    ELEGIVEL = "elegivel"
    NAO_ELEGIVEL_DANFE_NAO_DETECTADO = "nao_elegivel_danfe_nao_detectado"
    NAO_ELEGIVEL_CAMPOS_INCOMPLETOS = "nao_elegivel_campos_incompletos"
    NAO_ELEGIVEL_CHAVE_INVALIDA = "nao_elegivel_chave_invalida"
    NAO_ELEGIVEL_CFOP_INVALIDO = "nao_elegivel_cfop_invalido"
    NAO_ELEGIVEL_NCM_INVALIDO = "nao_elegivel_ncm_invalido"


def _somente_digitos(valor: str | None) -> str:
    """Remove tudo que nao for digito (espacos, pontuacao, ruido de OCR)."""
    return re.sub(r"\D", "", valor or "")


def _cfop_valido(valor: str | None) -> bool:
    """CFOP: 4 digitos apos normalizacao, primeiro digito != 0."""
    digits = _somente_digitos(valor)
    return len(digits) == 4 and digits[0] != "0"


def _ncm_valido(valor: str | None) -> bool:
    """NCM: exactamente 8 digitos apos normalizacao."""
    digits = _somente_digitos(valor)
    return len(digits) == 8


def _chave_valida(valor: str | None) -> bool:
    """Chave de acesso NF-e: exactamente 44 digitos apos normalizacao."""
    digits = _somente_digitos(valor)
    return len(digits) == 44


def avaliar_elegibilidade_fiscal(
    documento_normalizado: DocumentoFiscalNormalizado,
    detectou_danfe: bool,
) -> ElegibilidadeFiscal:
    """
    Avalia elegibilidade fiscal para promotion, conforme CT-DOC-001 secao 5.

    Campos sintacticamente validos nunca sao suficientes isoladamente
    para documentos nao-DANFE (CT-DOC-001: "necessario, nao suficiente").
    """
    if not detectou_danfe:
        return ElegibilidadeFiscal.NAO_ELEGIVEL_DANFE_NAO_DETECTADO

    chave = documento_normalizado.chave_acesso
    data = documento_normalizado.data_emissao
    valor = documento_normalizado.valor_total
    cfop = documento_normalizado.cfop
    ncm = documento_normalizado.ncm

    if chave is None or data is None or valor is None:
        return ElegibilidadeFiscal.NAO_ELEGIVEL_CAMPOS_INCOMPLETOS

    if not _chave_valida(chave.valor):
        return ElegibilidadeFiscal.NAO_ELEGIVEL_CHAVE_INVALIDA

    if cfop is None or not _cfop_valido(cfop.valor):
        return ElegibilidadeFiscal.NAO_ELEGIVEL_CFOP_INVALIDO

    if ncm is None or not _ncm_valido(ncm.valor):
        return ElegibilidadeFiscal.NAO_ELEGIVEL_NCM_INVALIDO

    return ElegibilidadeFiscal.ELEGIVEL
