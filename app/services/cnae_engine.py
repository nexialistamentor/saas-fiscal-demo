"""
Motor de enquadramento CNAE soberano V1.

Responsabilidade: dado perfil do utilizador, recomendar CNAEs
com score heurístico e enquadramento empresarial.

NÃO decide regime tributário — isso é responsabilidade do regime_engine.
Devolve regimes_compativeis como lista de possibilidades para o regime_engine.

Score V1 heurístico:
    peso_keyword_exacto + peso_keyword_parcial + bonus_secao + penalidade_mei

AVISO ARQUITECTURAL V1:
    Score baseado em keywords — não em ML/embeddings.
    V2: modelo de linguagem soberano treinado em dados fiscais brasileiros.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.parsers.cnae_parser import (
    SubclasseCNAE,
    buscar_por_descricao,
    subclasses_por_secao,
)

KEYWORDS_PATH = Path("data/cnae/cnae_keywords.json")

# Regimes compatíveis por secção — base para regime_engine
_REGIMES_POR_SECAO: dict[str, list[str]] = {
    "J": ["mei", "simples", "lp", "lr"],
    "K": ["lp", "lr"],          # financeiro — MEI não permitido
    "M": ["mei", "simples", "lp", "lr"],
    "G": ["mei", "simples", "lp", "lr"],
    "I": ["mei", "simples", "lp", "lr"],
    "S": ["mei", "simples", "lp", "lr"],
}
_REGIMES_DEFAULT = ["simples", "lp", "lr"]


@dataclass
class ResultadoCNAE:
    cnae_principal_sugerido: Optional[SubclasseCNAE]
    cnaes_secundarios_sugeridos: list[SubclasseCNAE]
    score_confianca: float          # 0.0 – 100.0
    permite_mei: bool
    motivo_nao_mei: Optional[str]
    regimes_compativeis: list[str]  # possibilidades — regime_engine decide
    justificativa: list[str]
    palavras_detectadas: list[str]


def _carregar_keywords() -> dict:
    """Carrega inteligência de keywords — separado da fonte normativa IBGE."""
    if not KEYWORDS_PATH.exists():
        return {}
    with open(KEYWORDS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _detectar_palavras(descricao: str, keywords_data: dict) -> dict[str, list[str]]:
    """
    Detecta palavras-chave por secção na descrição do utilizador.
    Retorna dict {secao: [keywords_encontradas]}.
    """
    descricao_lower = descricao.lower()
    detectadas: dict[str, list[str]] = {}

    for secao, dados in keywords_data.get("secoes_prioritarias", {}).items():
        encontradas = []
        for kw in dados.get("keywords", []):
            if kw in descricao_lower:
                encontradas.append(kw)
        if encontradas:
            detectadas[secao] = encontradas

    return detectadas


def _expandir_termos_busca(keywords: list[str], keywords_data: dict) -> list[str]:
    """Expande keywords detectadas com sinónimos para match na descrição CNAE."""
    sinonimos = keywords_data.get("sinonimos_cnae", {})
    termos: set[str] = set()
    for kw in keywords:
        termos.add(kw)
        for s in sinonimos.get(kw, []):
            termos.add(s)
    return list(termos)


def _divisao_prioritaria(keywords: list[str], keywords_data: dict) -> Optional[str]:
    """Divisão CNAE preferida quando keywords mapeiam actividade conhecida."""
    mapeamento = keywords_data.get("mapeamento_divisoes", {})
    for kw in keywords:
        div = mapeamento.get(kw)
        if div:
            return div
    return None


def _calcular_score(
    secao: str,
    keywords_encontradas: list[str],
    keywords_data: dict,
    porte: str,
    permite_mei_secao: bool,
) -> float:
    """Score heurístico V1 por subclasse/secção."""
    pesos = keywords_data.get("pesos", {})
    peso_exacto = pesos.get("match_keyword_exacto", 2.0)
    peso_parcial = pesos.get("match_keyword_parcial", 1.0)
    bonus_secao = pesos.get("bonus_secao_prioritaria", 0.5)
    penalidade_mei = pesos.get("penalidade_restricao_mei", -3.0)

    score = 0.0
    for kw in keywords_encontradas:
        # Keyword com mais de uma palavra = match mais específico
        if " " in kw:
            score += peso_exacto
        else:
            score += peso_parcial

    # Bonus por secção prioritária
    peso_secao = keywords_data.get("secoes_prioritarias", {}).get(secao, {}).get("peso_secao", 1.0)
    score *= peso_secao
    score += bonus_secao

    # Penalidade se MEI e secção não permite
    if porte == "mei" and not permite_mei_secao:
        score += penalidade_mei

    return round(max(0.0, min(score * 10, 100.0)), 2)


def recomendar_cnaes(
    descricao_actividade: str,
    porte: str = "me",
    max_resultados: int = 5,
) -> ResultadoCNAE:
    """
    Recomenda CNAEs com score heurístico dado perfil do utilizador.

    Args:
        descricao_actividade: descrição livre da actividade
        porte: "mei" | "me" | "epp" | "medio" | "grande"
        max_resultados: máximo de CNAEs secundários a devolver
    """
    keywords_data = _carregar_keywords()
    justificativa = []
    palavras_detectadas_todas = []

    # 1. Detectar keywords por secção
    detectadas_por_secao = _detectar_palavras(descricao_actividade, keywords_data)

    if not detectadas_por_secao:
        # Fallback — busca textual directa no CSV
        cnaes_fallback = buscar_por_descricao(descricao_actividade, limite=max_resultados)
        justificativa.append("Nenhuma keyword sectorial detectada — busca textual directa aplicada")
        return ResultadoCNAE(
            cnae_principal_sugerido=cnaes_fallback[0] if cnaes_fallback else None,
            cnaes_secundarios_sugeridos=cnaes_fallback[1:],
            score_confianca=20.0,
            permite_mei=porte != "mei",
            motivo_nao_mei=None,
            regimes_compativeis=_REGIMES_DEFAULT,
            justificativa=justificativa,
            palavras_detectadas=[],
        )

    # 2. Calcular score por secção e ordenar
    restricoes_mei = keywords_data.get("restricoes_mei", {})
    secoes_nao_mei = set(restricoes_mei.get("secoes_nao_permitidas", []))

    scores_por_secao: list[tuple[str, float, list[str]]] = []
    for secao, kws in detectadas_por_secao.items():
        permite_mei_secao = secao not in secoes_nao_mei
        score = _calcular_score(secao, kws, keywords_data, porte, permite_mei_secao)
        scores_por_secao.append((secao, score, kws))
        palavras_detectadas_todas.extend(kws)

    scores_por_secao.sort(key=lambda x: x[1], reverse=True)
    secao_principal = scores_por_secao[0][0]
    score_principal = scores_por_secao[0][1]

    # 3. Buscar CNAEs da secção principal
    cnaes_secao = subclasses_por_secao(secao_principal)

    # Filtrar por keywords (com sinónimos) na descrição do CNAE
    termos_busca = _expandir_termos_busca(palavras_detectadas_todas, keywords_data)
    cnaes_relevantes = [
        c for c in cnaes_secao
        if any(termo in c.descricao.lower() for termo in termos_busca)
    ]

    # Priorizar divisão mapeada (ex.: software → 62, editora → 58)
    divisao_alvo = _divisao_prioritaria(palavras_detectadas_todas, keywords_data)
    if divisao_alvo and cnaes_relevantes:
        prioritarios = [c for c in cnaes_relevantes if c.codigo_divisao == divisao_alvo]
        if prioritarios:
            cnaes_relevantes = prioritarios + [c for c in cnaes_relevantes if c not in prioritarios]
    elif divisao_alvo and not cnaes_relevantes:
        cnaes_divisao = [c for c in cnaes_secao if c.codigo_divisao == divisao_alvo]
        if cnaes_divisao:
            cnaes_relevantes = cnaes_divisao[: max_resultados + 1]
            justificativa.append(
                f"Divisão {divisao_alvo} priorizada por mapeamento de keywords"
            )

    # Fallback para todos da secção se nenhum match
    if not cnaes_relevantes:
        cnaes_relevantes = cnaes_secao[:max_resultados + 1]
        justificativa.append(f"Todos os CNAEs da secção {secao_principal} incluídos por ausência de match específico")

    cnae_principal = cnaes_relevantes[0] if cnaes_relevantes else None
    cnaes_secundarios = cnaes_relevantes[1:max_resultados + 1]

    # 4. MEI check
    permite_mei = porte != "mei" or secao_principal not in secoes_nao_mei
    motivo_nao_mei = None
    if porte == "mei" and not permite_mei:
        motivo_nao_mei = restricoes_mei.get("motivo_padrao", "Atividade não permitida para MEI")
        justificativa.append(f"MEI não permitido para secção {secao_principal}: {motivo_nao_mei}")

    # 5. Regimes compatíveis — MEI só entra na lista quando o porte pedido é MEI e a actividade permite
    regimes = list(_REGIMES_POR_SECAO.get(secao_principal, _REGIMES_DEFAULT))
    if porte == "mei" and permite_mei:
        regimes = ["mei"] + [r for r in regimes if r != "mei"]
    else:
        regimes = [r for r in regimes if r != "mei"]

    justificativa.append(
        f"Secção principal detectada: {secao_principal} "
        f"({keywords_data.get('secoes_prioritarias', {}).get(secao_principal, {}).get('descricao', '')})"
    )
    justificativa.append(f"Keywords detectadas: {', '.join(palavras_detectadas_todas)}")
    justificativa.append(f"Score de confiança: {score_principal}")

    return ResultadoCNAE(
        cnae_principal_sugerido=cnae_principal,
        cnaes_secundarios_sugeridos=cnaes_secundarios,
        score_confianca=score_principal,
        permite_mei=permite_mei,
        motivo_nao_mei=motivo_nao_mei,
        regimes_compativeis=regimes,
        justificativa=justificativa,
        palavras_detectadas=list(set(palavras_detectadas_todas)),
    )
