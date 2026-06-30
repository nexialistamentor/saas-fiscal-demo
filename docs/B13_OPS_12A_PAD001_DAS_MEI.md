# B13-OPS-12A — PAD-001 DAS MEI: Eliminação da Divergência Funcional

**Data:** 2026-06-30  
**HEAD antes do commit:** `ff56cc4`  
**Referência:** B13-OPS-12 — auditoria de dependências normativas hardcoded (documento a criar em bloco seguinte)

---

## O que foi feito

PAD-001 confirmado e eliminado: dois caminhos paralelos calculavam DAS MEI com bases diferentes.

**Antes:**
- `/imposto/calcular` → `mei_constants.calcular_das_mei()` (canónico)
- `/formalizacao/comparar-regimes` → `Decimal("756.00")` hardcoded (2024, desactualizado)
- `mei_engine.py` → `1412 * 0.05 + 1` hardcoded (2024, desactualizado)

**Depois:**
- Todos os caminhos → `calcular_das_mei(obter_salario_minimo(ano_atual))`
- Limite MEI unificado em `MEI_LIMITE_ANUAL_FATURAMENTO` (mei_constants)

---

## Estado após B13-OPS-12A

| Critério | Estado |
|----------|--------|
| Consistência funcional inter-endpoints | ✔ Resolvido |
| Fonte normativa com hash | ✗ Pendente |
| Vigência declarada | ✗ Pendente |
| Fallback silencioso controlado | ✗ Pendente |

**Classificação L3:** funcionalmente consistente / normativamente parcial.

---

## Pendência B13-OPS-12B

1. Adicionar `SALARIO-MINIMO-001` ao manifesto de fontes com `fonte_id`, `vigência`, `hash_referencia`.
2. Controlar ou expor o fallback silencioso de `obter_salario_minimo()` — hoje usa último ano conhecido sem aviso ao caller.
3. Definir processo de actualização anual obrigatório para `SALARIO_MINIMO_POR_ANO`.

---

## Invariante PAD-001 (regressão activa)

`tests/test_regime_engine.py::test_pad001_das_mei_sem_hardcoded_legacy`  
`tests/test_regime_engine.py::test_pad001_das_mei_usa_fonte_canonica`
