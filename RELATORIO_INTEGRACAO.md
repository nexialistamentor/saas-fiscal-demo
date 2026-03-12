# Relatório de Integração — Pipeline, Oportunidades e Score

**Data da auditoria:** 09/03/2025  
**Objetivo:** Confirmar se os 3 blocos (Pipeline, Oportunidades, Score) estão implementados e conectados no código real.

---

## 1. PIPELINE DE ANÁLISE XML — ✅ INTEGRADO

| Componente | Arquivo | Status | Uso |
|------------|---------|--------|-----|
| **fiscal_router** | `app/routes/fiscal_router.py` | OK | Incluído em `main.py` (prefix `/fiscal`) |
| **xml_service** | `app/xml_service.py` | OK | `ler_xml_unico`, `persistir_documento_fiscal`, `enriquecer_st_se_necessario` |
| **motor_fiscal** | `app/motor_fiscal.py` | OK | `analisar_xml` chamado no fluxo de upload |

**Fluxo conectado em `main.py` (linhas 85-147):**
```
POST /upload-xml → ler_xml_unico() → analisar_xml() → TaxConsistencyEngine → 
enriquecer_st_se_necessario() → persistir_documento_fiscal()
```

**TaxConsistencyEngine** integrado diretamente no pipeline (linhas 119-124).

---

## 2. MOTOR DE OPORTUNIDADES (Insights/Divergências) — ✅ INTEGRADO

| Componente | Arquivo | Status | Integração |
|------------|---------|--------|------------|
| **Insights Engine** | `app/services/insights_engine.py` | OK | Orquestra 10+ fontes de insights |
| **insights_router** | `app/routers/insights_router.py` | OK | `GET /insights/{empresa_id}` |
| **relatorio_router** | `app/routes/relatorio_router.py` | OK | Usa `InsightEngine.gerar_insights_empresa()` |
| **agent_scheduler** | `app/agents/agent_scheduler.py` | OK | Passa oportunidades para agents |
| **assistente_service** | `app/services/assistente_service.py` | OK | `formatar_resposta_insights()` |

**Fontes de insights no `InsightEngine`:**
- Detecção de créditos ST
- Oportunidades de recuperação
- Distorções tributárias
- Radar tributário
- Oportunidades preditivas
- Ranking estratégico
- Impacto financeiro
- Score global tributário (conectado ao bloco Score)

---

## 3. SCORING TRIBUTÁRIO — ✅ IMPLEMENTADO E CONECTADO

| Componente | Arquivo | Status | Integração |
|------------|---------|--------|------------|
| **score_global_tributario_service** | `app/services/score_global_tributario_service.py` | OK | Usado por insights_engine, relatorio_router, inteligencia_router |
| **score_tributario_service** | `app/services/score_tributario_service.py` | OK | Score por NCM — usado em radar, prioridade_auditoria |
| **risco_tributario_service** | `app/services/risco_tributario_service.py` | OK | `score_risco_tributario` — entra no score global |
| **maturidade_tributaria_service** | `app/services/maturidade_tributaria_service.py` | OK | `score_maturidade_tributaria` — entra no score global |
| **complexidade_tributaria_service** | `app/services/complexidade_tributaria_service.py` | OK | `score_complexidade` |

**Endpoints de score:**
- `GET /inteligencia/score-tributario/{empresa_id}` → `calcular_score_tributario`
- `GET /inteligencia/score-global-tributario/{empresa_id}` → `calcular_score_global_tributario`
- `GET /dashboard/score-risco/{empresa_id}` → score de risco simplificado

**Modelo de dados:** `models.py` possui coluna `score_global` (Float) para histórico.

**Fluxo de integração:**  
`InsightEngine.gerar_insights_empresa()` chama `calcular_score_global_tributario()` e inclui o score no resultado (linha 75-81).

---

## 4. RESUMO EXECUTIVO

| Bloco | Status | Observação |
|-------|--------|------------|
| **Pipeline (Upload XML)** | ✅ Integrado | Fluxo completo: XML → motor → consistência → persistência |
| **Oportunidades (Insights)** | ✅ Integrado | InsightEngine + routers + scheduler + assistente |
| **Score Tributário** | ✅ Integrado | Múltiplos scores, API dedicada, consumido pelo Insights |

---

## 5. CONEXÕES ENTRE BLOCOS

```
[Pipeline XML] ──→ [Motor Fiscal] ──→ [TaxConsistencyEngine]
       │                    │
       └────────────────────┴──→ [Persistência] ──→ [InsightEngine]
                                                           │
[Score Tributário] ◄───────────────────────────────────────┘
       │
       └──→ [relatorio_router] [inteligencia_router] [dashboard_router]
```

**Conclusão:** Os três blocos estão implementados e conectados. O Pipeline alimenta os dados, o InsightEngine consolida oportunidades e scores, e o Score Tributário é consumido pelo motor de insights e pelos endpoints de inteligência/dashboard.
