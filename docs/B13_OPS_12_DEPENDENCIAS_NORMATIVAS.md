# B13-OPS-12 — Dependências Normativas Hardcoded dos Motores Fiscais

**Data:** 2026-06-30  
**HEAD:** `6073a0c`  
**Referência:** `docs/B13_OPS_12A_PAD001_DAS_MEI.md`, `docs/FONTES_TRIBUTARIAS.md`

---

## Princípio

Nenhum motor fiscal pode usar constante normativa hardcoded sem declarar:

- `fonte_id` no manifesto
- vigência
- tipo de uso
- estado da autoridade
- risco se desactualizada

Comentário no código não é mecanismo de controlo normativo.

---

## Estado dos sub-blocos

| Sub-bloco | Entrega | Estado |
|-----------|---------|--------|
| B13-OPS-12A | Eliminar divergência DAS MEI / PAD-001 | ✔ Fechado (`6073a0c`) |
| B13-OPS-12B | Adicionar fontes ausentes ao manifesto | ✔ Este bloco |
| B13-OPS-12C | Mapear 17 constantes contra fonte_id/vigência | ⏳ Pendente |

---

## Mapa de dependências normativas hardcoded (auditoria B13-OPS-12)

| Constante/regra | Ficheiro | Linha | Motor | fonte_id manifesto | Vigência | Risco L3 | Acção |
|---|---|---|---|---|---|---|---|
| Tabela Anexo I (Comércio) | imposto_service.py | 102-108 | calcular_imposto_simples_nacional | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Tabela Anexo II (Indústria) | imposto_service.py | 110-116 | idem | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Tabela Anexo III (Serviços gerais) | imposto_service.py | 118-124 | idem | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Tabela Anexo IV (INSS separado) | imposto_service.py | 126-132 | idem | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Tabela Anexo V (Serv. intelectuais) | imposto_service.py | 134-140 | idem | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Teto Simples 4.800.000 | imposto_service.py | 161, 199 | _obter_faixa_simples | CGSN-001 | não declarada | alto | B13-OPS-12C |
| Tabela IRPF progressiva (5 faixas) | imposto_service.py | 46-55 | calcular_imposto_simples (CPF) | **IRPF-PROGRESSIVO-001** | não declarada | alto | Adicionado ao manifesto — B13-OPS-12B |
| Fator R limiar 0.28 | regime_engine.py | 15-16, 94, 118 | _anexo_por_secao_e_fator_r | CGSN-001 | não declarada | alto | B13-OPS-12C |
| LIMITE_SIMPLES_ANUAL = 4.800.000 | regime_engine.py | 31 | comparar_regimes | CGSN-001 | não declarada | médio | B13-OPS-12C |
| _SECAO_PARA_ANEXO (CNAE→Anexo) | regime_engine.py | 35-57 | _anexo_por_secao_e_fator_r | CGSN-001 | não declarada | alto | B13-OPS-12C |
| DAS MEI 756/63 hardcoded | regime_engine.py | 231-232 | comparar_regimes | — | — | — | **✔ Eliminado B13-OPS-12A** |
| MEI_LIMITE_ANUAL_FATURAMENTO = 81000 | mei_constants.py | 7 | múltiplos | CGSN-001 | não declarada | médio | B13-OPS-12C |
| MEI_DAS_FATOR_SALARIO_MINIMO = 0.05 | mei_constants.py | 13 | calcular_das_mei | CGSN-001 | não declarada | alto | B13-OPS-12C |
| PARCELA_FIXA (1.00/5.00) | mei_constants.py | 21-22 | calcular_das_mei | CGSN-001 | não declarada | alto | B13-OPS-12C |
| SALARIO_MINIMO_POR_ANO | mei_constants.py | 29-33 | calcular_das_mei | **SALARIO-MINIMO-001** | parcialmente por ano | médio | Adicionado ao manifesto — B13-OPS-12B |
| obter_salario_minimo() fallback silencioso | mei_constants.py | 37-48 | múltiplos | — | — | alto | **✔ Eliminado B13-OPS-12B-P0D** — ValueError se ano ausente |
| _SECOES_FATOR_R = {J,M,S} | regime_engine.py | 60 | _anexo_por_secao_e_fator_r | CGSN-001 | não declarada | alto | B13-OPS-12C |
| DAS MEI legado 1412*0.05+1 | mei_engine.py | 17-18 | MEIEngine (DEPRECATED) | — | — | — | **✔ Eliminado B13-OPS-12A** |

---

## Fontes adicionadas ao manifesto em B13-OPS-12B

| fonte_id | Status | pode_fundamentar_decisao | hash_referencia |
|----------|--------|--------------------------|-----------------|
| SALARIO-MINIMO-001 | em_revisao | false | null |
| IRPF-PROGRESSIVO-001 | em_revisao | false | null |

---

## Regra L3 formalizada

INVARIANTE-NR-02:

Nenhuma constante fiscal de regime, limite, anexo, alíquota, fator R
ou faixa pode existir sem fonte_id declarada no manifesto.

INVARIANTE-NR-03:

Fonte normativa com pode_fundamentar_decisao=false não pode ser
apresentada como decisão fiscal definitiva.
Só pode alimentar simulação/estimativa com aviso.

---

## B13-OPS-12B-P0D — Fallback silencioso eliminado

**Data:** 2026-06-30  
**Correcção imediata** (complementar ao motor temporal B13-OPS-13):

- `obter_salario_minimo(2026)` → `1621.00` (Decreto nº 12.797/2025) — já internalizado em P0C
- `obter_salario_minimo(ano)` **bloqueia** com `ValueError` se o ano não estiver em `SALARIO_MINIMO_POR_ANO`
- Invariante L3: nenhum cálculo MEI pode usar salário mínimo de ano anterior por fallback implícito

Teste de regressão: `test_obter_salario_minimo_ano_nao_internalizado_bloqueia` (ano 2027).

---

## Próximo: B13-OPS-12C

Mapear as 13 constantes restantes contra `fonte_id`/`vigência`/`risco` e criar invariantes de regressão para cada uma.
