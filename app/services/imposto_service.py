"""
Serviço de cálculo de impostos para CPF e MEI.
"""

from datetime import datetime

from app.services.tax_engines.mei_constants import (
    MEI_ATIVIDADE_SERVICOS,
    MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE,
    MEI_LIMITE_ANUAL_FATURAMENTO,
    calcular_das_mei,
    normalizar_atividade_mei,
    obter_salario_minimo,
)


def calcular_imposto_simples(
    faturamento: float,
    despesas: float = 0,
    tipo: str = "MEI",
    atividade: str | None = None,
) -> dict:
    """
    Calcula imposto estimado para CPF ou MEI.
    Retorna imposto e lista de alertas.
    """
    alertas = []
    imposto = 0.0
    ano_atual = datetime.now().year

    if tipo.upper() == "MEI":
        sal_min = obter_salario_minimo(ano_atual)
        imposto = calcular_das_mei(sal_min, atividade)
        faturamento_anual_projetado = faturamento * 12
        if faturamento_anual_projetado >= MEI_LIMITE_ANUAL_FATURAMENTO:
            alertas.append("faturamento excedeu o limite anual do MEI")
        elif faturamento_anual_projetado >= MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE:
            alertas.append("faturamento próximo do limite anual")
    else:
        # CPF / autônomo: base real
        base = max(0, faturamento - despesas)

        # Tabela IRPF mensal (simplificada)
        imposto = 0

        if base <= 2112:
            imposto = 0
        elif base <= 2826.65:
            imposto = (base * 0.075) - 158.4
        elif base <= 3751.05:
            imposto = (base * 0.15) - 370.4
        elif base <= 4664.68:
            imposto = (base * 0.225) - 651.73
        else:
            imposto = (base * 0.275) - 884.96

        imposto = max(0, round(imposto, 2))

        alertas.append("Cálculo baseado em tabela progressiva IRPF (estimado)")

    if tipo.upper() == "MEI":
        if normalizar_atividade_mei(atividade) == MEI_ATIVIDADE_SERVICOS:
            aliquota_info = "DAS fixo (serviços)"
        else:
            aliquota_info = "DAS fixo (comércio/indústria)"
    else:
        aliquota_info = "Tabela progressiva IRPF (estimado mensal)"
    base = faturamento - despesas if tipo.upper() != "MEI" else faturamento
    base = max(0, base) if tipo.upper() != "MEI" else base

    return {
        "imposto": round(imposto, 2),
        "ano_atual": ano_atual,
        "alertas": alertas,
        "base_calculo": base,
        "aliquota_info": aliquota_info,
        "faturamento": faturamento,
        "despesas": despesas,
        "tipo": tipo.upper(),
    }


def calcular_imposto(valor: float, aliquota: float = 0.06) -> dict:
    imposto = valor * aliquota

    return {
        "valor_base": valor,
        "aliquota": aliquota,
        "imposto": imposto,
        "total_com_imposto": valor + imposto
    }


# =========================
# SIMPLES NACIONAL (Empresas com CNPJ)
# Tabelas 2025/2026 - 6 faixas por anexo
# Fórmula: (RBT12 × Alíquota − Parcela a deduzir) ÷ RBT12 = alíquota efetiva
# DAS mensal ≈ receita_mês × alíquota_efetiva
# =========================

# (faixa_min, faixa_max, aliquota_nominal, parcela_deduzir)
_ANEXO_I = [  # Comércio
    (0, 180_000, 0.04, 0),
    (180_000.01, 360_000, 0.073, 5_940),
    (360_000.01, 720_000, 0.095, 13_860),
    (720_000.01, 1_800_000, 0.107, 22_500),
    (1_800_000.01, 3_600_000, 0.143, 87_300),
    (3_600_000.01, 4_800_000, 0.19, 378_000),
]
_ANEXO_II = [  # Indústria
    (0, 180_000, 0.045, 0),
    (180_000.01, 360_000, 0.079, 5_940),
    (360_000.01, 720_000, 0.10, 13_860),
    (720_000.01, 1_800_000, 0.112, 22_500),
    (1_800_000.01, 3_600_000, 0.147, 85_500),
    (3_600_000.01, 4_800_000, 0.30, 720_000),
]
_ANEXO_III = [  # Serviços gerais (prestação de serviços)
    (0, 180_000, 0.06, 0),
    (180_000.01, 360_000, 0.112, 9_360),
    (360_000.01, 720_000, 0.135, 17_640),
    (720_000.01, 1_800_000, 0.16, 35_640),
    (1_800_000.01, 3_600_000, 0.21, 125_640),
    (3_600_000.01, 4_800_000, 0.33, 648_000),
]
_ANEXO_IV = [  # Serviços com INSS separado (segurança, limpeza etc.)
    (0, 180_000, 0.045, 0),
    (180_000.01, 360_000, 0.09, 8_100),
    (360_000.01, 720_000, 0.102, 12_420),
    (720_000.01, 1_800_000, 0.14, 39_780),
    (1_800_000.01, 3_600_000, 0.22, 183_780),
    (3_600_000.01, 4_800_000, 0.33, 828_000),
]
_ANEXO_V = [  # Serviços intelectuais (consultoria, TI, publicidade etc.)
    (0, 180_000, 0.155, 0),
    (180_000.01, 360_000, 0.18, 4_500),
    (360_000.01, 720_000, 0.195, 9_900),
    (720_000.01, 1_800_000, 0.205, 17_100),
    (1_800_000.01, 3_600_000, 0.23, 62_100),
    (3_600_000.01, 4_800_000, 0.305, 540_000),
]

_ANEXOS = {
    "I": ("Comércio", _ANEXO_I),
    "II": ("Indústria", _ANEXO_II),
    "III": ("Serviços gerais", _ANEXO_III),
    "IV": ("Serviços com INSS separado", _ANEXO_IV),
    "V": ("Serviços intelectuais", _ANEXO_V),
}


def _obter_faixa_simples(rbt12: float, tabela: list) -> tuple:
    """
    Retorna (faixa_min, faixa_max, aliquota_nominal, parcela_deduzir) para o RBT12 dado.
    Permite retornar a faixa real da tabela progressiva na resposta.
    """
    for faixa_min, faixa_max, aliquota, parcela in tabela:
        if faixa_min <= rbt12 <= faixa_max:
            return faixa_min, faixa_max, aliquota, parcela
    # Acima do teto (4,8 mi) - usar última faixa
    if rbt12 > 4_800_000:
        fmin, fmax, aliq, par = tabela[-1]
        return fmin, fmax, aliq, par
    # Abaixo da primeira faixa
    fmin, fmax, aliq, par = tabela[0]
    return fmin, fmax, aliq, par


def calcular_imposto_simples_nacional(
    rbt12: float,
    receita_mes: float = None,
    anexo: str = "I",
) -> dict:
    """
    Calcula DAS estimado para empresa no Simples Nacional.
    rbt12: Receita bruta dos últimos 12 meses (R$)
    receita_mes: Receita do mês atual (se None, usa rbt12/12)
    anexo: I (comércio), II (indústria), III (serviços), IV (INSS sep.), V (intelectual)
    """
    if anexo.upper() not in _ANEXOS:
        anexo = "I"
    nome_anexo, tabela = _ANEXOS[anexo.upper()]
    faixa_min, faixa_max, aliquota_nom, parcela = _obter_faixa_simples(rbt12, tabela)

    # Alíquota efetiva: (RBT12 × A − PD) ÷ RBT12
    if rbt12 <= 0:
        aliquota_efetiva = 0.0
    else:
        aliquota_efetiva = (rbt12 * aliquota_nom - parcela) / rbt12
        aliquota_efetiva = max(0, min(aliquota_efetiva, 1))

    receita_mes = receita_mes if receita_mes is not None else (rbt12 / 12)
    das_mensal = round(receita_mes * aliquota_efetiva, 2)
    das_anual = round(rbt12 * aliquota_efetiva, 2)

    alertas = [
        "Valor estimado. A alíquota efetiva pode variar conforme o faturamento acumulado."
    ]
    if rbt12 > 4_800_000:
        alertas.append("Faturamento acima do teto do Simples Nacional (R$ 4,8 milhões)")

    return {
        "das_mensal": das_mensal,
        "das_anual": das_anual,
        "rbt12": rbt12,
        "receita_mes": receita_mes,
        "anexo": anexo.upper(),
        "nome_anexo": nome_anexo,
        "aliquota_efetiva_pct": round(aliquota_efetiva * 100, 2),
        "faixa_simples_min": faixa_min,
        "faixa_simples_max": faixa_max,
        "aliquota_nominal_pct": round(aliquota_nom * 100, 2),
        "parcela_deduzir": parcela,
        "alertas": alertas,
    }