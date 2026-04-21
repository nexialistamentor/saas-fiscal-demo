"""
Teste isolado do CPF Tax Engine (IRPF mensal progressivo 2025)

Executar da raiz do projeto:
    venv311\Scripts\python scripts\test_cpf_tax_engine.py
"""

import sys
from pathlib import Path

_raiz = Path(__file__).resolve().parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

from app.services.tax_engines.cpf_tax_engine import CPFTaxEngine


def printar(titulo, resultado):
    print(f"\n{'=' * 60}")
    print(f"  {titulo}")
    print(f"{'=' * 60}")
    for k, v in resultado.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        elif isinstance(v, list):
            print(f"  {k}:")
            for item in v:
                print(f"    - {item}")
        else:
            print(f"  {k}: {v}")


engine = CPFTaxEngine()

# ── CASO 1: Sem despesas, sem INSS ─────────────────────────────────────────
# Faturamento 5000 → base_bruta 5000 → desconto_simpl. min(1000, 1396.19)=1000
# base_simplificada = 4000 → faixa 4: 22,5% – 662,77 = 237,23
r1 = engine.execute({"faturamento": 5000})
printar("CASO 1 — Faturamento R$5.000 | Sem despesas | Sem INSS", r1)
assert r1["tributos"]["imposto"] == 237.23, f"Esperado 237.23, obtido {r1['tributos']['imposto']}"
assert r1["bases_calculo"]["metodo_deducao"] == "desconto_simplificado"
assert "explicacao_resumida" in r1
assert "IRPF 2025" in r1["explicacao_resumida"]
assert "tabela progressiva" in r1["explicacao_resumida"]
assert "alíquota efetiva" in r1["explicacao_resumida"]
print("  [OK] Imposto e método corretos")

# ── CASO 2: Com INSS pago ──────────────────────────────────────────────────
# Faturamento 6000, INSS 770 → base_bruta 5230
# desconto_simpl = min(1046, 1396.19) = 1046 → base_simpl = 4184
# Sem despesas → base_real = 5230 → usa simplificado (4184 < 5230)
# Faixa 4: 4184 ≤ 4664.68 → 22,5% – 662,77 = 278,63
r2 = engine.execute({"faturamento": 6000, "inss_pago": 770})
printar("CASO 2 — Faturamento R$6.000 | INSS R$770 | Sem despesas", r2)
assert r2["tributos"]["imposto"] == 278.63, f"Esperado 278.63, obtido {r2['tributos']['imposto']}"
assert r2["bases_calculo"]["metodo_deducao"] == "desconto_simplificado"
print("  [OK] Imposto e método corretos")

# ── CASO 3: Despesas reais maiores que desconto simplificado ──────────────
# Faturamento 8000, INSS 0, despesas 4000
# base_bruta = 8000, desconto_simpl = min(1600, 1396.19) = 1396.19
# base_simpl = 6603.81, base_real = 4000
# base_real < base_simpl → usa despesas_reais
# Faixa 5: 4000 > 3751.05? Não → faixa 4: 4000 ≤ 4664.68 → 22,5% – 662,77 = 237.23
r3 = engine.execute({"faturamento": 8000, "despesas": 4000})
printar("CASO 3 — Faturamento R$8.000 | Despesas R$4.000", r3)
assert r3["bases_calculo"]["metodo_deducao"] == "despesas_reais", f"Esperado despesas_reais, obtido {r3['bases_calculo']['metodo_deducao']}"
assert r3["tributos"]["imposto"] == 237.23, f"Esperado 237.23, obtido {r3['tributos']['imposto']}"
print("  [OK] Imposto e método corretos")

# ── CASO 4: Faturamento abaixo da isenção ─────────────────────────────────
# Faturamento 2000 → base_bruta 2000, desconto_simpl = 400
# base_simpl = 1600 ≤ 2259.20 → imposto = 0
r4 = engine.execute({"faturamento": 2000})
printar("CASO 4 — Faturamento R$2.000 | Abaixo da isenção", r4)
assert r4["tributos"]["imposto"] == 0, f"Esperado 0, obtido {r4['tributos']['imposto']}"
print("  [OK] Imposto zero (isento)")

print("\n" + "=" * 60)
print("  TODOS OS CASOS PASSARAM COM SUCESSO")
print("=" * 60)
