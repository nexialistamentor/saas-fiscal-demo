"""
Testes normativos B13-OPS-12B-P0C — mei_constants.

Prova que SALARIO_MINIMO_POR_ANO está correctamente internalizado
e que obter_salario_minimo() devolve valores canónicos.

Regressão anti-silenciosa: 2026 não pode repetir 2025.
"""
from decimal import Decimal

import pytest

from app.services.tax_engines.mei_constants import (
    SALARIO_MINIMO_POR_ANO,
    obter_salario_minimo,
    calcular_das_mei,
    normalizar_atividade_mei,
)


def test_salario_minimo_2025_correcto():
    assert Decimal(str(SALARIO_MINIMO_POR_ANO[2025])) == Decimal("1518.00")


def test_salario_minimo_2026_nao_repete_2025():
    """Decreto nº 12.797/2025 fixa 2026 em R$ 1.621,00."""
    assert Decimal(str(SALARIO_MINIMO_POR_ANO[2026])) == Decimal("1621.00")
    assert SALARIO_MINIMO_POR_ANO[2026] != SALARIO_MINIMO_POR_ANO[2025]


def test_obter_salario_minimo_2026_usa_valor_oficial():
    assert Decimal(str(obter_salario_minimo(2026))) == Decimal("1621.00")


def test_obter_salario_minimo_ano_nao_internalizado_bloqueia():
    with pytest.raises(ValueError, match="não internalizado"):
        obter_salario_minimo(2027)


def test_das_mei_2026_usa_salario_correcto():
    """DAS MEI 2026 deve usar 1621, não 1518."""
    sal = obter_salario_minimo(2026)
    das = calcular_das_mei(sal, "comercio")
    # 1621 * 0.05 + 1.00 = 82.05 (comércio/indústria)
    assert Decimal(str(das)) == Decimal("82.05")
    # Não pode ser o valor de 2025: 1518 * 0.05 + 1.00 = 76.90
    assert Decimal(str(das)) != Decimal("76.90")


@pytest.mark.parametrize("atividade", [None, "", "   ", "desconhecida"])
def test_mei_r001_normalizacao_e_das_bloqueiam_atividade_invalida(atividade):
    with pytest.raises(ValueError, match="Atividade MEI"):
        normalizar_atividade_mei(atividade)
    with pytest.raises(ValueError, match="Atividade MEI"):
        calcular_das_mei(obter_salario_minimo(2026), atividade)
