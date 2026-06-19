# MAPA_AUTORIDADES_L2.md

**Versão:** 1.0
**Data:** 2026-06-18
**Natureza:** Documento de descoberta — mapeia autoridade real exercida
  por cada componente, com base em evidência de código directamente lida.
**Base:** MAPA_REALIDADE_TRIBUTARIA_L2.md v1.0 + MAPA_DOMINIOS_SOBERANOS.md v1.0
**Método:** Matriz congelada (14 perguntas) aplicada a 13 actores/componentes.
  Sem conclusões. Sem ADRs. Sem propostas de correcção.

---

## MATRIZ CONGELADA (v0.1)

Perguntas aplicadas a cada actor/componente:

1. Autoridade declarada
2. Autoridade exercida
3. Inputs
4. Outputs
5. Pode bloquear?
6. Pode homologar?
7. Pode divergir?
8. Pode substituir outro?
9. Pode delegar autoridade?
10. Quem audita este componente?
11. O que acontece se desaparecer?
12. Existe autoridade sem execução?
13. É fonte de verdade para quê?
14. Transversal a quais domínios?
+ Estado (activo / parcial / inactivo)

---

## 1. INSIGHTENGINE

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Conecta Motor Fiscal, Engines, Agentes e Score a `relatorios_analise`; cada execução vira registo auditável |
| Autoridade exercida | Produz 16+ tipos de insight, grava `Insight`, `EngineResultado`, `InteligenciaSnapshot`, actualiza `RelatorioAnalise` |
| Inputs | `empresa_id`, dados fiscais persistidos, tabelas normativas |
| Outputs | `Insight`, `EngineResultado`, `InteligenciaSnapshot`, `RelatorioAnalise.resultado_json` |
| Pode bloquear? | Não |
| Pode homologar? | Não formalmente — marca `superseded=True` como auto-versionamento |
| Pode divergir? | Sim, sem reconciliação (DT-AUD-01) |
| Pode substituir outro? | É parcialmente substituído pelo caminho XML simplificado do orchestrator |
| Pode delegar autoridade? | Não — síncrono, in-process |
| Quem audita? | Nenhum auditor identificado durante a auditoria actual |
| Se desaparecer? | Pipeline XML persiste documento, mas sem insights/score/snapshot; API `/insights` quebra; Assistente perde resposta fiscal; Agentes correm sem dados |
| Fonte de verdade para quê? | Score de risco, oportunidades, créditos detectados, maturidade fiscal |
| Transversal a | Tributário, Auditoria, Operacional |
| Estado | ✅ Activo |

**Candidato descoberto:** `analysis_orchestrator._gerar_insights_por_xml()` — produz artefactos semanticamente semelhantes a insights; autoridade ainda não auditada; fora da matriz base.

---

## 2. AUDITORFISCALAGENT

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Auditoria tributária automática; identifica riscos fiscais |
| Autoridade exercida | Limiares fixos sobre `context["insights"]`: restituição >10000 ALTO, >2000 MÉDIO; MVA distorção >20 CRÍTICO |
| Inputs | `context["insights"]` montado pelo AgentScheduler |
| Outputs | `{agent, total_alertas, alertas, status}` — persistência feita por outro componente |
| Pode bloquear? | Não |
| Pode homologar? | Não |
| Pode divergir? | Sim — campos incompatíveis com InsightEngine (DT-AUD-01) |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Não |
| Quem audita? | Nenhum auditor identificado |
| Se desaparecer? | `run_all` ignora; hoje zero impacto (scheduler desligado); se reactivado, perdem-se alertas RISCO_FISCAL_*/OPERACAO_CRITICA |
| Fonte de verdade para quê? | Fonte de verdade não identificada — não executa em produção e não persiste directamente |
| Transversal a | Auditoria (nativo); depende do Tributário/Operacional |
| Estado | ❌ Inactivo |

**Descoberta estrutural preservada:** autoridade de classificação ≠ autoridade de registo — o agente decide severidade, o `AgentExecutor` persiste, sem contrato declarado entre os dois.

---

## 3. ASSISTENTE FISCAL

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Ponto de convergência conversacional para todos os perfis de contribuinte |
| Autoridade exercida | Identifica intenção/contribuinte por NLP leve, delega para o motor correcto |
| Inputs | Texto livre, `usuario` (opcional), `db` (opcional) |
| Outputs | Resposta em linguagem natural + `analysis_type`, `requires_payment`, `preview`, `payload_estruturado` |
| Pode bloquear? | Sim — anti-prompt-injection em duas camadas; paywall em créditos de empresa |
| Pode homologar? | Não |
| Pode divergir? | Não exerce cálculo próprio — divergência herdada |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | **Sim — maior delegação confirmada da auditoria.** MEI/CPF → motor; Simples → imposto_service; Empresa paga → InsightEngine; Planejamento/Recuperação → orquestrador; Abertura/Encerramento → agents directos |
| Quem audita? | Nenhum auditor identificado. Auditoria persistente só no ramo CPF autenticado |
| Se desaparecer? | Só `/perguntar` morre; motor, XML, relatórios e agents continuam por caminhos directos. Acoplamento frágil: `relatorio_router` importa helpers privados de `assistente_service` |
| Fonte de verdade para quê? | Fonte de verdade não identificada — é camada de roteamento |
| Transversal a | Todos os cinco domínios |
| Estado | ✅ Activo (sem consumo confirmado no frontend) |

**Padrão provisório registado:** InsightEngine produz → AuditorFiscalAgent interpreta → Assistente Fiscal distribui.

**Candidato/dívida descoberto:** acoplamento não declarado `relatorio_router.py` ↔ `assistente_service.py` via imports privados.

---

## 4. MOTORES TRIBUTÁRIOS (conjunto)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Cálculo determinístico de tributos por regime/perfil |
| Autoridade exercida | Calcula valores tributários a partir de inputs persistidos |
| Inputs | Dados fiscais via `executar_analise(tipo, dados, empresa)` |
| Outputs | Tributos calculados, alertas, bases de cálculo |
| Pode bloquear? | Sim — circuit breaker após 5 falhas (120s) |
| Pode homologar? | Não |
| Pode divergir? | Sim — `regime_router` com `mei` não chama `MEITaxEngine`; dois caminhos MEI (legado/oficial) |
| Pode substituir outro? | `regime_router` substitui-se a si próprio por stub em `simples`/`mei` |
| Pode delegar autoridade? | Sim, em cadeia: `executar_analise` → `ENGINE_REGISTRY` → `regime_router` → motor |
| Quem audita? | Auditoria de desempenho: sim (metrics_alert_service, engine_recovery_service, StateRecoveryAgent). Auditoria de correcção fiscal: não identificada |
| Se desaparecer? | Degradado → fallback 300s; circuit breaker → erro explícito 120s; tipo inválido → erro tipado |
| Fonte de verdade para quê? | Candidato a fonte de verdade para cálculo tributário; fragmentada entre múltiplos motores e caminhos, sem árbitro central (caso MEI) |
| Transversal a | Tributário (nativo); consumido por Auditoria, Empresarial |
| Estado | ✅ Activo |

> **Nota crítica:** quando PAD-001 ocorre em motores, há risco de cálculo divergente. Quando PAD-001 ocorre em normas, há risco de verdade fiscal divergente.

---

## 5a. REGIMEROUTER (autoridade de selecção runtime)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Despachar `empresa.regime_tributario` para o motor correcto |
| Autoridade exercida | Lê `regime_tributario`, despacha por if/elif; placeholder para simples/mei |
| Inputs | `empresa.regime_tributario`, `dados_fiscais` |
| Outputs | Resultado do motor delegado ou placeholder |
| Pode bloquear? | Não — sempre devolve algo |
| Pode homologar? | Não |
| Pode divergir? | Sim, silenciosamente — sem validar se regime persistido corresponde ao óptimo |
| Pode substituir outro? | Não — único `v1` registado |
| Pode delegar autoridade? | Sim — para LP/LR; textual (não computacional) para simples/mei |
| Quem audita? | Nenhum auditor identificado. Zero testes dedicados |
| Se desaparecer? | `empresa_tax` quebra inteiramente |
| Fonte de verdade para quê? | Fonte de verdade operacional para escolha do motor usado em runtime, mas não fonte de verdade para regime ideal ou correcto |
| Transversal a | Tributário (nativo); consumido por Empresarial |
| Estado | ✅ Activo |

## 5b. REGIME_ENGINE.COMPARAR_REGIMES (autoridade de recomendação)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Simular e recomendar o regime mais vantajoso |
| Autoridade exercida | Simula internamente LP/LR/Simples/MEI, compara, recomenda — sem persistir |
| Inputs | Faturamento, folha, lucro contábil, secção CNAE |
| Outputs | Regime recomendado, economia estimada, regimes compatíveis/inelegíveis |
| Pode bloquear? | Não |
| Pode homologar? | Não |
| Pode divergir? | Sim — sem ponte com regime_router |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Sim — simula lógica paralela aos motores |
| Quem audita? | 14 testes dedicados (`test_regime_engine.py`) — único componente com cobertura própria confirmada |
| Se desaparecer? | `/formalizacao/comparar-regimes` e `/simular-empresa` quebram; cálculo runtime não é afectado |
| Fonte de verdade para quê? | Fonte de verdade não identificada — recomenda, não persiste nem força adopção |
| Transversal a | Empresarial (nativo) |
| Estado | ✅ Activo (stateless) |

**Achado central:** não existe ponte entre `regime_engine` (recomenda) e `regime_router` (executa). Uma empresa pode receber recomendação de Lucro Real e continuar calculada como Presumido indefinidamente.

---

## 6. PIPELINE DOCUMENTAL (confidence.py + audit.py)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Classificar confiança de documento e decidir caminho de processamento |
| Autoridade exercida | `_decidir(score)`: ≥95 auto-processa, 70-94 fila, <70 rejeita |
| Inputs | Texto extraído, flag `requer_ocr` |
| Outputs | `ResultadoConfianca`, `EvidenciaDocumental` |
| Pode bloquear? | Sim — REJEITAR impede; FILA_HOMOLOGACAO impede auto até decisão do contador |
| Pode homologar? | Não directamente — condiciona se homologação será necessária |
| Pode divergir? | Sem evidência de divergência interna — motor único de confiança |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Sim, mas de forma indirecta e incompleta. Depende da persistência de `decisao="fila_homologacao"` e acção posterior — sem accionamento automático |
| Quem audita? | Nenhum auditor identificado para correcção do score. `criar_evidencia()` rastreia, não audita |
| Se desaparecer? | Pipeline documental para completamente |
| Fonte de verdade para quê? | Fonte de verdade para decisão de roteamento; não para o conteúdo do documento |
| Transversal a | Documental (nativo) |
| Estado | ✅ Activo |

---

## 7. TABELAS NORMATIVAS (MVA, PMPF)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Fonte de verdade normativa para alíquotas, MVA e PMPF |
| Autoridade exercida | `buscar_mva`/`buscar_pmpf` com hierarquia por vigência e nível de confiança |
| Inputs | UF, NCM, data de referência (marca/embalagem para PMPF) |
| Outputs | Valor MVA/PMPF aplicável, com fonte e nível de confiança |
| Pode bloquear? | Pode bloquear ou degradar indirectamente — alguns caminhos retornam indisponível; outros caem em fallback legado, dependendo da API usada |
| Pode homologar? | Não |
| Pode divergir? | **Sim, confirmado.** Duas APIs: `buscar_mva` (sem fallback) e `carregar_mva` (cai para `mva.json` quando UF ausente). `insights_engine` importa ambas |
| Pode substituir outro? | `carregar_mva` substitui silenciosamente BD por JSON legado sem aviso |
| Pode delegar autoridade? | Não — é destino final da consulta |
| Quem audita? | Agentes normativos existem e têm permissões de leitura, mas não foi identificada verificação normativa activa em produção |
| Se desaparecer? | Cálculos de ST ficam sem base normativa; `carregar_mva` tem fallback parcial, `buscar_mva` não tem nenhum |
| Fonte de verdade para quê? | Candidato a fonte de verdade normativa para ST, fragmentada entre BD e `mva.json`, sem reconciliação declarada |
| Transversal a | Tributário (nativo); Auditoria, Operacional |
| Estado | ⚠️ Parcial — cobertura nacional ausente (DT-MVA-01) |

---

## 8. AGENTSCHEDULER / AGENTEXECUTOR / 11 AGENTES

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Executar agentes periodicamente; orquestrar observação, auditoria, recovery e normativa |
| Autoridade exercida | **Nenhuma em produção** — loop comentado em `main.py` (linhas 134-136) |
| Inputs | `empresa_id`, `insights`, `tabela_normativa` |
| Outputs | `AlertaFiscal` persistido, resultado por agente |
| Pode bloquear? | Não |
| Pode homologar? | Não |
| Pode divergir? | Sim — já provado (DT-AUD-01) |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Sim, internamente — distribui contexto para 11 agentes |
| Quem audita? | Nenhum auditor identificado. Seria o auditor de outros componentes, mas não corre |
| Se desaparecer? | Zero impacto runtime enquanto permanecer desligado. Se reactivado no futuro, a remoção eliminaria a camada de auditoria, recovery e validação periódica |
| Fonte de verdade para quê? | Fonte de verdade não identificada — mecanismo de execução, não de decisão |
| Transversal a | Todos os cinco domínios |
| Estado | ❌ **Inactivo** (DT-AGENTE-01) |

**Achado central:** dos 11 agentes registados, nenhum corre autonomamente. Capacidade inteira de auditoria, recovery e validação existe apenas como intenção arquitectural — prova máxima de "código ≠ capacidade operacional."

---

## 9. PIPELINE CANÓNICO (executar_e_registrar_analise_xml)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Conecta Motor Fiscal, Engines, Agentes e Score; cada execução vira registo auditável |
| Autoridade exercida | Limite → análise → persistência → dedup → registo → InsightEngine → score → finalização |
| Inputs | `xml_bytes`, `user_id`, `empresa_id` |
| Outputs | `RelatorioAnalise` completo, `DocumentoFiscal`, `Insight`, `AlertaFiscal`, `InteligenciaSnapshot` |
| Pode bloquear? | Sim — `verificar_limite_analises` |
| Pode homologar? | Fecha o ciclo auditável e institucionaliza a análise, mas não homologa juridicamente nem contabilmente |
| Pode divergir? | Sim — DT-FLUXO-03 (dedup após persistência) |
| Pode substituir outro? | Não — único caminho que fecha o ciclo completo |
| Pode delegar autoridade? | Sim, cadeia completa |
| Quem audita? | É mecanismo de auditoria de outros, sem auditor externo de si próprio |
| Se desaparecer? | Nenhuma análise de empresa fica auditável |
| Fonte de verdade para quê? | Fonte de verdade institucional para análise auditável |
| Transversal a | Tributário, Auditoria, Operacional |
| Estado | ✅ Activo — não é o único caminho de entrada de XML |

---

## 10. /UPLOAD-XML

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Não declarada — endpoint genérico de upload |
| Autoridade exercida | Persistência directa, sem pipeline canónico |
| Inputs | `xml_bytes` via HTTP |
| Outputs | `DocumentoFiscal`/`ItemFiscal` — sem `RelatorioAnalise`, sem InsightEngine, sem score |
| Pode bloquear? | Não verifica limite de uso |
| Pode homologar? | Não |
| Pode divergir? | Sim — diverge estruturalmente do canónico para o mesmo input |
| Pode substituir outro? | Substitui parcialmente o pipeline canónico ao nível da persistência, mas não ao nível da autoridade analítica produzida |
| Pode delegar autoridade? | Parcial — só persistência |
| Quem audita? | Nenhum identificado |
| Se desaparecer? | Pipeline canónico não é afectado |
| Fonte de verdade para quê? | Fonte de verdade para persistência crua — não para análise auditável |
| Transversal a | Tributário (parcial) |
| Estado | ✅ Activo, não-canónico (DT-FLUXO-01) |

---

## 11. /LOTE/ANALISAR-LOTE

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Análise de múltiplos XML em lote |
| Autoridade exercida | Loop de `executar_analise_xml` — sem persistência |
| Inputs | Múltiplos ficheiros XML |
| Outputs | Dict `jobs` em memória, TTL ~1h |
| Pode bloquear? | Não |
| Pode homologar? | Não |
| Pode divergir? | Não aplicável — não compete porque não persiste |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Não |
| Quem audita? | Nenhum — resultado desaparece após TTL |
| Se desaparecer? | Nenhum impacto em dados persistidos |
| Fonte de verdade para quê? | Nenhuma — resultado nunca se torna persistente |
| Transversal a | Tributário (efémero) |
| Estado | ⚠️ Parcial — zero artefacto auditável (DT-FLUXO-02) |

---

## 12. UTILIZADOR / CONTRIBUINTE

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Constituição Art. I §1: receptor de cálculo, comparação e recomendação; decisão final é sempre dele |
| Autoridade exercida | Decide regime tributário, decide se paga, decide se age sobre alertas/insights |
| Inputs | Recomendações, cálculos, alertas, checklists de todos os componentes |
| Outputs | Decisões não-rastreadas estruturalmente |
| Pode bloquear? | Sim — único actor com poder de veto real sobre toda a plataforma |
| Pode homologar? | Não identificado. Exerce decisão final, mas não existe mecanismo formal de homologação equivalente ao do Contador CRC |
| Pode divergir? | Sim — pode manter regime diferente do recomendado indefinidamente, sem aviso (PAD-002) |
| Pode substituir outro? | Não |
| Pode delegar autoridade? | Sim — para o contador, ou implicitamente para a plataforma |
| Quem audita? | Nenhum componente audita se o utilizador agiu correctamente sobre recomendações recebidas |
| Se desaparecer? | Não aplicável — beneficiário final |
| Fonte de verdade para quê? | Fonte de verdade para a decisão final |
| Transversal a | Todos os cinco domínios |
| Estado | ✅ Activo |

---

## 13. CONTADOR CRC (PARCEIRO)

| Campo | Evidência |
|-------|-----------|
| Autoridade declarada | Constituição Art. VII: actor soberano nos domínios reservados por lei ou quando confiança documental é insuficiente |
| Autoridade exercida | Homologa documentos, gera assinatura lógica, transição auto_processar/rejeitado |
| Inputs | Documento em `fila_homologacao` — descoberto manualmente, não notificado |
| Outputs | `HomologacaoDocumental` com parecer auditável, `validado_humano=True` |
| Pode bloquear? | Sim — pode rejeitar |
| Pode homologar? | **Sim — único actor com autoridade de homologação formal e auditável confirmada por evidência** |
| Pode divergir? | Não testado/observado |
| Pode substituir outro? | Não — único actor com este tipo de autoridade executiva |
| Pode delegar autoridade? | Não — lei reserva-lhe a assinatura |
| Quem audita? | Nenhum auditor identificado — `PerfilContador.status` controla elegibilidade, não qualidade das decisões |
| Se desaparecer? | Documentos em fila ficam permanentemente pendentes — sem fallback nem timeout identificado |
| Fonte de verdade para quê? | Fonte de verdade jurídica/contábil para documentos que exigem assinatura habilitada |
| Transversal a | Documental (nativo); Empresarial |
| Estado | ✅ Activo |

---

## PADRÕES ESTRUTURAIS IDENTIFICADOS (PAD)

### PAD-001 — Caminhos paralelos sem árbitro

Presença recorrente de caminhos paralelos para o mesmo facto, sem árbitro explícito identificado.

Ocorrências confirmadas: InsightEngine (caminho XML paralelo), Operacional/Estoque (SQL directo vs ORM), MEI (legado vs oficial), Tabelas Normativas (BD vs JSON legado).

> Quando PAD-001 ocorre em motores, há risco de cálculo divergente.
> Quando PAD-001 ocorre em normas, há risco de verdade fiscal divergente.

### PAD-002 — Recomendação/decisão e execução desconectadas

Ocorrências confirmadas: regime_engine (recomenda) vs RegimeRouter (executa) — sem ponte de validação automática; confidence.py (decide fila_homologacao) vs contador (assume manualmente) — sem notificação automática.

### PAD-003 — Mesmo input, autoridade institucional diferente conforme o caminho

O mesmo input pode atravessar caminhos distintos e produzir níveis diferentes de autoridade institucional.

Exemplo confirmado: XML → Pipeline Canónico (auditável) / /upload-xml (persistido sem auditoria) / /lote (efémero, sem persistência).

Nenhum dos três padrões constitui ADR, dívida técnica ou proposta de correcção.

São observações estruturais recorrentes, registadas para informar o futuro Pré-Mortem (PM-L2-001) e os ADRs subsequentes.

---

## DESCOBERTA CENTRAL DA MATRIZ

Das 13 linhas auditadas, **apenas um actor exerce autoridade executiva formal confirmada por evidência dentro dos fluxos auditados**: o **Contador CRC**.

```
InsightEngine        → produz
Motores               → calculam
Assistente            → distribui
RegimeRouter          → selecciona
regime_engine         → recomenda
confidence.py         → roteia
AgentScheduler        → observa (quando activo — hoje não está)
Tabelas Normativas    → sustentam
Utilizador            → decide (sem mecanismo formal de homologação)
Contador CRC          → executa e homologa
```

---

## INVARIANTE DE AUTORIDADE

Produzir autoridade não é o mesmo que executar autoridade.

Calcular não é homologar.
Recomendar não é decidir.
Persistir não é institucionalizar.
Observar não é governar.

A autoridade executiva confirmada permanece distinta da autoridade analítica.

---

*Documento produzido sobre evidências de código lido directamente.*
*Matriz congelada antes do preenchimento — comparabilidade garantida entre todas as 13 linhas.*
*Conclusões apenas quando derivadas da matriz. Zero ADRs. Zero propostas de correcção.*
*O conhecimento não está na conversa. Está no repositório.*
