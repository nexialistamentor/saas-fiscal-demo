"""
Teste isolado da MEITaxEngine (L2) vs legado imposto_service.calcular_imposto_simples (MEI).

Executar da raiz do projeto:
    python scripts/test_mei_tax_engine.py
"""

import sys
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

from app.services.imposto_service import calcular_imposto_simples
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def _assert_parity(faturamento_mensal: float):
    engine = MEITaxEngine()
    ctx = {"faturamento": faturamento_mensal}
    l2 = engine.execute(ctx)
    legado = calcular_imposto_simples(faturamento_mensal, despesas=0, tipo="MEI")

    assert l2["regime"] == "mei"
    assert l2["tributos"]["das"] == legado["imposto"]
    assert l2["alertas"] == legado["alertas"]
    assert l2["bases_calculo"]["faturamento_mensal"] == faturamento_mensal
    assert l2["bases_calculo"]["faturamento_anual"] == faturamento_mensal * 12


def test_mei_tax_engine_vs_legado():
    cenarios = [
        5000.0,   # abaixo de 75k/ano em projeção
        6300.0,   # 75.600/ano → próximo do limite
        7000.0,   # 84.000/ano → excedeu
    ]
    for fat in cenarios:
        _assert_parity(fat)
        print(f"[OK] faturamento mensal {fat}: L2 == legado (DAS e alertas)")

    print("\n[OK] MEITaxEngine alinhada ao imposto_service (MEI).")


if __name__ == "__main__":
    test_mei_tax_engine_vs_legado()
