"""
Helper de serializacao para CT-DOC-001 (DT-DOC-01).

Converte DocumentoFiscalNormalizado (dataclasses CampoNormalizado)
para dict puro persistivel em JSON/JSONB, preservando vocabulario
fechado completo -- inclusive campos com valor=None, porque ausencia
tambem e evidencia auditavel (campo nunca extraido != campo
analisado e nao encontrado).

Nao grava dataclass directamente. Nao altera normalizer.py.
"""

from app.services.document_ingestion.normalizer import (
    DocumentoFiscalNormalizado,
    CampoNormalizado,
)

# Vocabulario fechado -- mesma lista usada em audit.py:_campos_extraidos
_CAMPOS_VOCABULARIO = [
    "cnpj_emitente",
    "cnpj_destinatario",
    "cpf_destinatario",
    "chave_acesso",
    "cfop",
    "ncm",
    "valor_total",
    "base_calculo",
    "aliquota_icms",
    "valor_icms",
    "aliquota_pis",
    "aliquota_cofins",
    "data_emissao",
]


def _campo_para_dict(campo: CampoNormalizado | None) -> dict:
    """
    Converte um CampoNormalizado (ou None, quando o campo nunca foi
    populado pelo normalizer) para dict puro.

    Campo ausente (None) e representado com valor=None e
    confianca=0.0, distinguivel de um campo efectivamente analisado
    sem sucesso (que teria origem preenchida).
    """
    if campo is None:
        return {
            "valor": None,
            "confianca": 0.0,
            "origem": None,
            "validado_humano": False,
        }
    return {
        "valor": campo.valor,
        "confianca": campo.confianca,
        "origem": campo.origem,
        "validado_humano": campo.validado_humano,
    }


def serializar_campos_estruturados(
    documento_normalizado: DocumentoFiscalNormalizado,
) -> dict:
    """
    Serializa todos os campos do vocabulario fechado para dict puro,
    persistivel directamente na coluna campos_estruturados (JSON).

    Formato de saida:

    {
      "chave_acesso": {"valor": "...", "confianca": 95.0,
                        "origem": "regex", "validado_humano": false},
      "valor_icms":   {"valor": null, "confianca": 0.0,
                        "origem": null, "validado_humano": false},
      ...
    }

    Inclui todos os 13 campos do vocabulario, mesmo quando ausentes
    (valor=None) -- conforme decisao registada no CT-DOC-001: ausencia
    tambem e evidencia auditavel.
    """
    return {
        nome_campo: _campo_para_dict(getattr(documento_normalizado, nome_campo, None))
        for nome_campo in _CAMPOS_VOCABULARIO
    }
