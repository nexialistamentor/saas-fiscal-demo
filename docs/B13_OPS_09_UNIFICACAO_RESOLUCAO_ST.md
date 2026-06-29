# B13-OPS-09 — Unificação da Resolução Normativa ST

**Data:** 2026-06-29  
**HEAD:** `5fe9814` (pré-commit)  
**Ficheiro alterado:** `app/services/insights_engine.py`  
**Referência:** B13-OPS-08 — `docs/B13_OPS_08_RESOLUCAO_NORMATIVA_L3.md`

---

## 1. BYPASS-01 eliminado

**Antes (fluxo perigoso):**
buscar_mva(db, uf, ncm, data_referencia)
→ decidir_acao_st(mva=regra["mva"]/100, aliquota=regra["aliquota_interna"])

**Depois (fluxo L3 autorizado):**
resolver_aliquota_e_mva(db, uf, ncm, data_referencia)
→ calculo_autorizado=True + calculo_parcial=False
→ decidir_acao_st(mva=res["mva"], aliquota=res["aliquota"])

---

## 2. Guards aplicados

| Guard | Condição | Acção |
|-------|----------|-------|
| NCM ausente | `not item.ncm` | `continue` |
| Não autorizado | `calculo_autorizado=False` | `continue` |
| Parcial | `calculo_parcial=True` | `continue` |

**Regra L3:** se não há resolução normativa autorizada, a plataforma não gera decisão fiscal ST.

---

## 3. Estado dos bypasses

| Bypass | Estado | Ficheiro |
|--------|--------|----------|
| BYPASS-01 | ✔ Eliminado | `insights_engine._analisar_decisao_st` |
| BYPASS-02 | P2 Legacy — permanece | `motor_fiscal.carregar_mva` |

BYPASS-02 não é eliminado neste bloco — não alimenta `decidir_acao_st()` directamente.

---

## 4. Motor permanece puro

`motor_decisao_tributaria.py` não foi alterado.  
Recebe `mva` e `aliquota` já resolvidos e autorizados — não resolve, só decide.

---

## 5. Invariante NR-01 — estado após B13-OPS-09

INVARIANTE-NR-01 (actualizado):

_analisar_decisao_st não chama buscar_mva() directamente.
_analisar_decisao_st usa resolver_aliquota_e_mva().
Decisão ST só ocorre com calculo_autorizado=True e calculo_parcial=False.
