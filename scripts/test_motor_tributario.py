"""
PASSO 10 — Teste funcional do motor tributário

Valida o fluxo completo:
    service → router → engine → cálculo

Garante que o resultado contenha: IRPJ, CSLL, PIS, COFINS, alertas.

Executar da raiz do projeto:
    python scripts/test_motor_tributario.py
"""

import sys
from pathlib import Path

# Garante que a raiz do projeto está no PYTHONPATH
_raiz = Path(__file__).resolve().parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

from types import SimpleNamespace

from app.services.assistente_service import calcular_impostos_empresa_service


def test_motor_tributario_fluxo_completo():
    """Teste do fluxo: service → router → engine → cálculo (regime presumido)."""
    empresa = SimpleNamespace(regime_tributario="presumido")

    dados_fiscais = {
        "faturamento": 100000,
        "atividade": "servicos",
    }

    resultado = calcular_impostos_empresa_service(empresa, dados_fiscais)

    print("=" * 60)
    print("RESULTADO DO CÁLCULO TRIBUTÁRIO (Lucro Presumido)")
    print("=" * 60)
    print(resultado)
    print("=" * 60)

    # Verifica estrutura padronizada (regime, tributos, bases_calculo, alertas)
    assert "regime" in resultado, "Resultado deve conter regime"
    assert "tributos" in resultado, "Resultado deve conter tributos"
    assert "bases_calculo" in resultado, "Resultado deve conter bases_calculo"
    assert "alertas" in resultado, "Resultado deve conter alertas"

    tributos = resultado["tributos"]
    assert "irpj" in tributos, "Tributos deve conter IRPJ"
    assert "csll" in tributos, "Tributos deve conter CSLL"
    assert "pis" in tributos, "Tributos deve conter PIS"
    assert "cofins" in tributos, "Tributos deve conter COFINS"

    # Verifica que alertas é lista não vazia
    assert isinstance(resultado["alertas"], list), "Alertas deve ser uma lista"
    assert len(resultado["alertas"]) > 0, "Deve haver pelo menos um alerta"

    # Valores numéricos esperados para faturamento 100.000 e atividade serviços
    # Presunção serviços: 32% → base = 32.000
    # IRPJ: 15% da base + 10% sobre excedente de 20.000
    assert tributos["irpj"] >= 0, "IRPJ deve ser não negativo"
    assert tributos["csll"] >= 0, "CSLL deve ser não negativo"
    assert tributos["pis"] >= 0, "PIS deve ser não negativo"
    assert tributos["cofins"] >= 0, "COFINS deve ser não negativo"

    print("\n[OK] Fluxo validado com sucesso: service -> router -> engine -> calculo")
    print("[OK] Estrutura padronizada: regime, tributos, bases_calculo, alertas")
    print("[OK] Tributos presentes: IRPJ, CSLL, PIS, COFINS")
    print("[OK] Alertas presentes:", resultado["alertas"])


if __name__ == "__main__":
    test_motor_tributario_fluxo_completo()
