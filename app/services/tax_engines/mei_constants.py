"""Constantes e utilitários do regime MEI usados pelo motor fiscal."""

from typing import Optional

# Limite anual de faturamento (R$).
MEI_LIMITE_ANUAL_FATURAMENTO = 81_000

# Faturamento anual estimado a partir do qual se alerta proximidade do teto.
MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE = 75_000

# DAS MEI: parcela proporcional ao salário mínimo (contribuição incorporada ao DAS).
MEI_DAS_FATOR_SALARIO_MINIMO = 0.05

# Chaves normalizadas para perfil de atividade (parcela fixa diferenciada).
MEI_ATIVIDADE_COMERCIO_INDUSTRIA = "comercio_industria"
MEI_ATIVIDADE_SERVICOS = "servicos"

# Parcela fixa mensal do DAS MEI (ICMS comércio/indústria × ISS serviços).
PARCELA_FIXA_POR_ATIVIDADE = {
    MEI_ATIVIDADE_COMERCIO_INDUSTRIA: 1.00,
    MEI_ATIVIDADE_SERVICOS: 5.00,
}

# Retrocompatível com código que só referenciava ICMS.
MEI_DAS_VALOR_FIXO_ICMS = PARCELA_FIXA_POR_ATIVIDADE[MEI_ATIVIDADE_COMERCIO_INDUSTRIA]

# Salário mínimo vigente por ano (legislação federal). Atualizar quando publicado decreto.
SALARIO_MINIMO_POR_ANO = {
    2023: 1320.00,
    2024: 1412.00,
    2025: 1518.00,
    2026: 1621.00,  # Decreto nº 12.797/2025 — vigência 1º jan 2026
}


def obter_salario_minimo(ano: int) -> float:
    """Retorna salário mínimo internalizado para o ano.

    L3: não faz fallback silencioso. Se o ano não estiver internalizado,
    bloqueia o cálculo para evitar uso normativo desactualizado.
    """
    if ano not in SALARIO_MINIMO_POR_ANO:
        raise ValueError(
            f"Salário mínimo não internalizado para o ano {ano}. "
            "Actualização normativa obrigatória antes do cálculo."
        )
    return SALARIO_MINIMO_POR_ANO[ano]


def normalizar_atividade_mei(valor: Optional[str]) -> str:
    """
    Devolve chave em PARCELA_FIXA_POR_ATIVIDADE.
    Comércio e indústria compartilham a mesma parcela fixa (ICMS).
    """
    if not valor:
        return MEI_ATIVIDADE_COMERCIO_INDUSTRIA
    v = str(valor).strip().lower()
    if v in ("servicos", "serviços", "servico", "serviço"):
        return MEI_ATIVIDADE_SERVICOS
    if v in (
        "comercio_industria",
        "comércio_indústria",
        "comercio",
        "comércio",
        "industria",
        "indústria",
    ):
        return MEI_ATIVIDADE_COMERCIO_INDUSTRIA
    return MEI_ATIVIDADE_COMERCIO_INDUSTRIA


def calcular_das_mei(salario_minimo: float, atividade: Optional[str] = None) -> float:
    """DAS MEI mensal: fator sobre salário mínimo + parcela fixa conforme atividade."""
    chave = normalizar_atividade_mei(atividade)
    parcela = PARCELA_FIXA_POR_ATIVIDADE[chave]
    return round(salario_minimo * MEI_DAS_FATOR_SALARIO_MINIMO + parcela, 2)
