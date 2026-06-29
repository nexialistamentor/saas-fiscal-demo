# B13-OPS-08 — Auditoria de Resolução Normativa L3

**Data:** 2026-06-29  
**HEAD:** `140f0fc`  
**Estado:** Auditoria — sem alteração de motor  
**Hierarquia:** `CONSTITUICAO_TRIBUTARIA_L2.md` → `FONTES_TRIBUTARIAS.md` → este documento → `tests/test_l3_normative_resolution_invariants.py`

---

## 1. Princípio soberano

**Nenhuma decisão fiscal pode usar MVA, alíquota, regime, limite, CNAE ou regra tributária sem resolução autorizada, rastreável, com fonte, vigência, escopo e `calculo_autorizado=True`.**

O motor de decisão fiscal (`motor_decisao_tributaria.py`) é puro e correcto.  
O risco está em quem alimenta o motor com dados normativos.

---

## 2. Resolvedor soberano

`fiscal_utils.resolver_aliquota_e_mva()` é o único caminho autorizado para alimentar decisões fiscais com MVA e alíquota.

**O que o resolvedor garante:**

| Guarda | Descrição |
|--------|-----------|
| `calculo_autorizado` | `True` só se alíquota E MVA são canónicas |
| `calculo_parcial` | Sinaliza quando só um dos dois é canónico |
| Escopo PA | Piloto restrito a Pará — bloqueia outras UF com fallback |
| `convenio_base_sem_aliquota` | MVA real + alíquota fallback 18% — parcial |
| Vigência | `data_referencia` garante regra válida na data do documento |
| Prioridade fonte | `oficial` > `convenio_base` > `estimativa` |

**Fluxo autorizado L3:**
NCM / UF / data
→ resolver_aliquota_e_mva()
→ calculo_autorizado=True?
Sim → decidir_acao_st(mva, aliquota)
Não → bloquear / alertar / não decidir

---

## 3. Bypasses identificados

### BYPASS-01 — `insights_engine.py:840` (crítico)

```python
# insights_engine.py linha 840
regra = buscar_mva(self.db, uf, item.ncm, data_referencia=item.documento.data_emissao)
decisao = decidir_acao_st(valor_produto=valor, st_pago=st_pago,
                           mva=regra["mva"] / 100, aliquota=regra["aliquota_interna"])
```

**Risco:** `buscar_mva()` devolve MVA/alíquota sem verificar `calculo_autorizado`, escopo PA, nem `convenio_base_sem_aliquota`. A decisão ST pode ser tomada com dados não autorizados.

**Classificação:** `FISCAL_DECISION_BYPASS_RISK — P1`

### BYPASS-02 — `motor_fiscal.py:114` (secundário)

```python
# motor_fiscal.py linha 114
regra = buscar_mva(db, uf, ncm)
```

**Risco:** Chamada directa sem resolvedor. Contexto: `carregar_mva()` — função legacy usada noutros sítios mas não em `decidir_acao_st()`. Menos crítico que BYPASS-01.

**Classificação:** `LEGACY_BYPASS — P2`

---

## 4. Caminhos limpos confirmados

| Ficheiro | Padrão | Estado L3 |
|----------|--------|-----------|
| `detector_creditos_service.py` | `resolver_aliquota_e_mva()` + `calculo_autorizado` | ✔ Limpo |
| `motor_preditivo_service.py` | `resolver_aliquota_e_mva()` + `calculo_autorizado` | ✔ Limpo |
| `ranking_restituicao_service.py` | `resolver_aliquota_e_mva()` + `calculo_autorizado` | ✔ Limpo |
| `analisador_distorcao_service.py` | `resolver_aliquota_e_mva()` + `mva_autorizada` | ✔ Limpo |
| `insights_engine.py:490,771` | `resolver_aliquota_e_mva()` + `calculo_autorizado` | ✔ Limpo |
| `motor_predicao_tributaria.py:46` | `resolver_aliquota_e_mva()` | ✔ Limpo |
| `motor_decisao_tributaria.py` | Motor puro — recebe valores, não resolve | ✔ Puro |
| `homologacao_service.py` | Autoridade executiva — sem MVA/alíquota | ✔ Limpo |
| `confidence.py` | Motor heurístico documental — sem fonte fiscal | ✔ Limpo |

---

## 5. Risco residual identificado

| Risco | Ficheiro | Linha | Prioridade |
|-------|----------|-------|-----------|
| `buscar_mva()` directo → `decidir_acao_st()` | `insights_engine.py` | 840 | P1 |
| `buscar_mva()` directo legacy | `motor_fiscal.py` | 114 | P2 |
| Cálculo Simples sem fonte declarada | `assistente_service.py` | 258-313 | P2 |
| CNAE sem declarar `IBGE-CNAE-001` | `cnae_engine.py` | — | P3 |
| Links REDESIM/Receita sem validação | `constants.py`, `ag_abertura_agent.py` | — | P3 |

---

## 6. Próximos passos

**B13-OPS-09** — Unificação resolução ST:
- Substituir `buscar_mva()` directo em `insights_engine.py:840` por `resolver_aliquota_e_mva()` com guarda `calculo_autorizado`
- Só avança depois de este documento e os invariantes estarem aprovados por Miguel/GPT

**B13-OPS-10/11** — Mapa Total + Teste Total:
- `1 funcionalidade prometida = 1 teste mínimo obrigatório`
- Sem teste → `nao_provada`

---

## 7. Invariante formal

```
INVARIANTE-NR-01:
Nenhum caller de decidir_acao_st() pode passar MVA/alíquota
obtidos directamente de buscar_mva() sem passar por
resolver_aliquota_e_mva() com calculo_autorizado=True.

Violação = FISCAL_DECISION_BYPASS
Detecção = tests/test_l3_normative_resolution_invariants.py
Correcção = B13-OPS-09 (aprovação Miguel/GPT obrigatória)
```
