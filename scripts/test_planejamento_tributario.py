from app.services.tax_engines.tax_planning_engine import simular_regimes

dados = {
    "faturamento": 100000,
    "atividade": "comercio",
    "receita_bruta": 100000,
    "custos": 40000,
    "despesas": 20000
}

resultado = simular_regimes(dados)

# Validação: motor deve retornar comparacao, melhor_regime, economia_estimada
assert "comparacao" in resultado, "Resultado deve conter 'comparacao'"
assert "melhor_regime" in resultado, "Resultado deve conter 'melhor_regime'"
assert "economia_estimada" in resultado, "Resultado deve conter 'economia_estimada'"

print("[OK] Teste passou: motor retorna todos os campos esperados")
print(resultado)
