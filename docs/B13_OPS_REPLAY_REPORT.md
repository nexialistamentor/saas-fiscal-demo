# B13-OPS-05 — Replay Operacional dos Bugs B13

**Data:** 2026-06-29  
**Suite:** `tests/test_ops_replay_b13.py`  
**Enquadramento:** L3 Soberano — fundação, não MVP  

---

## Princípio

Bugs deixam de depender do Miguel como sensor manual.  
Cada bug vira: **evento → sentinela → teste → regressão → memória operacional.**

Motor-first. LLM-last. Tokens = zero para eventos conhecidos.

---

## Resultados do Replay

| Evento | Classificação esperada | Resultado | Tokens usados | BudgetGuard | LLMRouter | Próximo passo |
|--------|----------------------|-----------|---------------|-------------|-----------|---------------|
| B13-P0-01 — CNAE SaaS → 5811 | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Regressão activa |
| B13-P0-02 — MEI 500k sem alerta | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Regressão activa |
| B13-P0-03 — faturamento zero → 422 | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Regressão activa |
| B13-P0-06 — race condition termos | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Regressão activa |
| B13-P0-07 — CTA login sem email | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Regressão activa |
| Vercel — VITE_API_URL vazia | P0 | ✔ P0 | 0 | Não chamado | Não chamado | Monitorizar deploy |
| Evento desconhecido (fallback) | P2 | ✔ P2 | 0 | Chamado | Não chamado | Análise humana |

---

## Garantias L3 provadas

- ✔ Eventos conhecidos resolvidos por sentinela local — zero tokens
- ✔ BudgetGuard não é chamado para eventos conhecidos
- ✔ LLMRouter não é chamado para eventos conhecidos
- ✔ Evento desconhecido passa por BudgetGuard antes do LLMRouter
- ✔ `LLM_ALLOW_REAL_CALLS=false` bloqueia chamada real
- ✔ Bloqueio devolve P2 seguro sem exception
- ✔ Output valida contra `AgentOutputSchema` em todos os casos

---

## Estado do circuito OPS

| Commit | Entrega |
|--------|---------|
| `1a72819` | B13-OPS-02 LLMRouter dry-run |
| `27ea5aa` | B13-OPS-02.1 sanitização L3 |
| `07b8404` | B13-OPS-02.2 AgentOutputSchema |
| `298f3a8` | B13-OPS-03 AgentErroOperacional motor-first |
| `05bdbf9` | B13-P0-07 CTA login preserva email |
| `d550d3e` | B13-OPS-04 BudgetGuard |
| *(este)* | B13-OPS-05 Replay controlado |

---

## Próximos passos L3

1. Piloto 0 manual — `www.fiscosoberano.com.br` T1–T8
2. `PILOTO_0_FEEDBACK.md` — evidência operacional
3. B13-OPS-01 — manifest.json fontes tributárias
4. Activação supervisionada DeepSeek (quando `LLM_ALLOW_REAL_CALLS=true` aprovado por Miguel/GPT)
