"""
Motor de confiança documental soberano.

Responsabilidade única: dado texto extraído, calcular score de confiança
e determinar o caminho de processamento.

AVISO ARQUITECTURAL: Este é confidence heurístico V1 baseado em presença de campos.
Futuramente evoluir para: score_ocr + score_campos + score_consistencia + score_estrutura + score_fiscal.
Campos críticos ausentes (CNPJ, chave de acesso) devem derrubar score drasticamente — V2.
Detecção de fraude, duplicidade e inconsistência fiscal — V3 (ML/embeddings).

Política soberana:
    ≥ 95  → auto_processar
    70–94 → fila_homologacao (contador parceiro)
    < 70  → rejeitar

Princípio: nunca processar fiscalmente dados com confiança insuficiente.
"""

from dataclasses import dataclass
from enum import Enum


class DecisaoProcessamento(str, Enum):
    AUTO_PROCESSAR = "auto_processar"
    FILA_HOMOLOGACAO = "fila_homologacao"
    REJEITAR = "rejeitar"


@dataclass
class ResultadoConfianca:
    score: float  # 0.0 – 100.0
    decisao: DecisaoProcessamento
    motivos: list[str]
    campos_detectados: list[str]


# Limites soberanos — não alterar sem decisão arquitectural documentada
LIMITE_AUTO = 95.0
LIMITE_FILA = 70.0

# Campos fiscais com peso por relevância
_CAMPOS_FISCAIS: dict[str, float] = {
    "cnpj": 15.0,
    "cpf": 10.0,
    "nota fiscal": 10.0,
    "nfe": 10.0,
    "danfe": 10.0,
    "cfop": 10.0,
    "icms": 8.0,
    "pis": 5.0,
    "cofins": 5.0,
    "valor total": 8.0,
    "base de calculo": 5.0,
    "aliquota": 5.0,
    "ncm": 5.0,
    "chave de acesso": 8.0,
    "emitente": 5.0,
    "destinatario": 5.0,
    "data de emissao": 5.0,
}

# Score base garantido por ter texto extraível
_SCORE_BASE_COM_TEXTO = 30.0
_SCORE_MAX_CAMPOS = 70.0  # soma máxima dos campos = 100 - base


def calcular(texto: str, requer_ocr: bool = False) -> ResultadoConfianca:
    """
    Calcula score de confiança e decisão de processamento.

    requer_ocr=True penaliza o score (OCR introduz incerteza).
    """
    if not texto or not texto.strip():
        return ResultadoConfianca(
            score=0.0,
            decisao=DecisaoProcessamento.REJEITAR,
            motivos=["Texto vazio — documento não contém dados extraíveis"],
            campos_detectados=[],
        )

    texto_lower = texto.lower()
    campos_detectados = []
    score_campos = 0.0

    for campo, peso in _CAMPOS_FISCAIS.items():
        if campo in texto_lower:
            campos_detectados.append(campo)
            score_campos += peso

    # Normaliza score de campos para máximo de 70 pontos
    score_campos_normalizado = min(score_campos, _SCORE_MAX_CAMPOS)
    score = _SCORE_BASE_COM_TEXTO + score_campos_normalizado

    # Penalidade OCR — introduz incerteza de 15 pontos
    if requer_ocr:
        score = max(0.0, score - 15.0)
        motivos_ocr = ["Penalidade OCR aplicada (-15): documento requer reconhecimento óptico"]
    else:
        motivos_ocr = []

    score = round(min(score, 100.0), 2)
    motivos = _gerar_motivos(score, campos_detectados, motivos_ocr)
    decisao = _decidir(score)

    return ResultadoConfianca(
        score=score,
        decisao=decisao,
        motivos=motivos,
        campos_detectados=campos_detectados,
    )


def _decidir(score: float) -> DecisaoProcessamento:
    if score >= LIMITE_AUTO:
        return DecisaoProcessamento.AUTO_PROCESSAR
    if score >= LIMITE_FILA:
        return DecisaoProcessamento.FILA_HOMOLOGACAO
    return DecisaoProcessamento.REJEITAR


def _gerar_motivos(
    score: float,
    campos: list[str],
    motivos_extra: list[str],
) -> list[str]:
    motivos = list(motivos_extra)

    if not campos:
        motivos.append("Nenhum campo fiscal reconhecido no documento")
    else:
        motivos.append(f"{len(campos)} campo(s) fiscal(is) detectado(s): {', '.join(campos)}")

    if score >= LIMITE_AUTO:
        motivos.append("Confiança suficiente para processamento automático")
    elif score >= LIMITE_FILA:
        motivos.append("Confiança intermédia — requer homologação por contador parceiro")
    else:
        motivos.append("Confiança insuficiente — documento rejeitado")

    return motivos
