# PLATAFORMA SOBERANA L2 — DOCUMENTO MESTRE
> Versão: 2026-04-25 | Confidencial | Uso interno

---

## 1. IDENTIDADE DO PROJECTO

**Nome:** Plataforma de Inteligência Tributária Soberana L2  
**Missão:** Democratizar a consultoria fiscal de elite (Big4) para PMEs, MEIs e CPFs brasileiros através de automação inteligente, agentes fiscais autónomos e uma rede de contadores parceiros.  
**Diferencial absoluto:** Motor fiscal soberano — toda lógica de cálculo vive no backend como código auditável, nunca delegada a APIs externas. Nenhum concorrente pode replicar sem reconstruir do zero.

**Posicionamento:** Não somos um SaaS de gestão. Somos uma infraestrutura de protocolo fiscal — a camada de inteligência que transforma dados brutos em segurança jurídica accionável.

---

## 2. STACK TÉCNICA (PRODUÇÃO)

| Componente | Tecnologia | URL |
|---|---|---|
| Backend | FastAPI + Python 3.13 | Railway |
| Frontend | React 19 + Vite 8 | Vercel |
| Base de dados | PostgreSQL (Railway) | Interno |
| Filas | Redis/RQ (configurado, não activo) | Railway |
| Migrações | Alembic | `migrations/versions/` |
| Deploy | GitHub → Railway (auto) | `origin/main` |
| Segurança XML | defusedxml + validação em camadas | `app/xml_security.py` |

**Regra absoluta:** `motor fiscal = código`. API externa = orientação/tradução, nunca verdade fiscal.

---

## 3. ARQUITECTURA DO SISTEMA

### 3.1 Pipeline Principal
```
Upload XML/Foto
    ↓
xml_security.py (validação + sanitização)
    ↓
xml_service.py (parsing estruturado)
    ↓
analysis_orchestrator.py (despacho por tipo)
    ↓
ENGINE_REGISTRY → tax_engines/ (22 motores)
    ↓
InsightEngine (geração de insights + snapshots)
    ↓
AgentScheduler → AgentExecutor → 4 Agentes
    ↓
AlertaFiscal + InteligenciaSnapshot (BD)
    ↓
Dashboard (frontend apresenta, nunca calcula)
```

### 3.2 Motores Fiscais (22 engines)
| Motor | Ficheiro | Função |
|---|---|---|
| Base | `base_tax_engine.py` | Contrato base (abstract) |
| CPF | `cpf_engine.py` / `cpf_tax_engine.py` | IRPF, simulação rendimentos |
| MEI | `mei_engine.py` / `mei_tax_engine.py` | DAS mensal, limites MEI |
| Lucro Presumido | `lucro_presumido_engine.py` | IRPJ/CSLL presumido |
| Lucro Real | `lucro_real_engine.py` | IRPJ/CSLL real |
| CSLL | `csll_engine.py` | Contribuição social |
| IRPJ | `irpj_engine.py` | Imposto renda PJ |
| PIS/COFINS | `pis_cofins_engine.py` | Contribuições federais |
| Tax Recovery | `tax_recovery_engine.py` | Recuperação ICMS-ST |
| Tax Planning | `tax_planning_engine.py` | Comparação de regimes |
| Regime Router | `regime_router.py` | Roteamento por regime |

### 3.3 Agentes (Swarm Soberana)
| Agente | Ficheiro | Função | Estado |
|---|---|---|---|
| AuditorFiscalAgent | `auditor_fiscal_agent.py` | Detecta riscos fiscais via insights | ✔ Activo |
| RepairAgent | `repair_agent.py` | Verifica integridade de contexto | ⚠ Superficial |
| PerformanceAgent | `performance_agent.py` | Monitora volume de insights | ⚠ Superficial |
| NormativeAgent | `normative_agent.py` | Verifica base normativa | ❌ Vazio (sem dados) |
| AgentEstoque | `agent_estoque.py` | Calcula estoque fiscal por NCM | ✔ Activo |
| AgentScheduler | `agent_scheduler.py` | Orquestra ciclos de agentes | ✔ Activo |
| AgentExecutor | `agent_executor.py` | Executa todos os agentes + persiste alertas | ✔ Activo |

### 3.4 Routers Activos
```
/auth          → registo, login, sessão
/empresas      → CRUD empresas
/fiscal        → análise XML, lote
/lote          → processamento em lote
/relatorio     → relatórios PDF
/imposto       → cálculo MEI/CPF
/cpf           → dashboard CPF + documentos rendimento
/inteligencia  → mapa oportunidades, histórico, tendência
/dashboard     → dashboard empresa
/documentos    → listagem documentos fiscais
/insights      → insights por empresa
/analise-st    → substituição tributária
/estoque       → auditoria estoque
/system        → métricas de sistema
/assistente    → assistente fiscal
/admin         → administração
```

---

## 4. MODELO DE DADOS (TABELAS PRINCIPAIS)

```
usuarios          → id, email, cpf, hashed_password, plano_id, consulta_paga, role
empresas          → id, user_id, cnpj, razao_social, regime_tributario
documentos_fiscais → id, empresa_id, usuario_id, chave_nfe, tipo, valor_total, uf_emit, uf_dest
itens_fiscais     → id, documento_id, ncm, cfop, valor_produto, base_icms, valor_st
tabela_mva        → id, estado, ncm, mva, aliquota_interna, vigencia
inteligencia_snapshots → id, empresa_id, score_global, risco_tributario, maturidade, criado_em
insights          → id, empresa_id, tipo, valor_estimado, impacto, descricao, recomendacao, ncm
alertas_fiscais   → id, empresa_id, agente, tipo, descricao, nivel, relatorio_analise_id
relatorios_analise → id, user_id, empresa_id, analysis_type, status, resultado_json
engine_resultados → id, empresa_id, engine_nome, resultado
documentos_rendimento → id, user_id, tipo_rendimento, valor, fonte_pagadora, confianca_extracao, campos_corrigidos
auditoria_estoque → id, empresa_id, ncm, estoque_fiscal, estoque_erp, diferenca
```

**Migrações activas:**
- `0d4ae9c` — uf_emit/uf_dest em documentos_fiscais
- `617775975` — uf_cobertura em inteligencia_snapshots
- `9196733` — cpf em usuarios ✔
- `2e580ff` — documentos_rendimento ✔

---

## 5. PERFIS DE UTILIZADOR

| Perfil | Regime | Motor Principal | Upload | Dashboard |
|---|---|---|---|---|
| CPF | Pessoa singular | `cpf_engine` | PDF/Imagem rendimentos | IRPF estimado + documentos |
| MEI | MEI | `mei_engine` | XML NF-e | DAS estimado |
| Empresa/Simples | Simples Nacional | `regime_router` | XML NF-e | Recuperação ST + insights |
| Empresa/Presumido | Lucro Presumido | `lucro_presumido_engine` | XML NF-e + SPED | IRPJ/CSLL |
| Empresa/Real | Lucro Real | `lucro_real_engine` | XML NF-e + SPED | IRPJ/CSLL real |
| Contador | B2B | Todos | Gestão carteira | Multi-cliente |

---

## 6. MODELO DE NEGÓCIO

### 6.1 Fluxo de Monetização
```
Utilizador entra → Scan gratuito → "Tens R$ X para recuperar"
    ↓
Paywall (consulta_paga = false → bloqueado)
    ↓
Pagamento → consulta_paga = true → Relatório completo
    ↓
Success Fee sobre valor recuperado (a implementar)
```

### 6.2 Três Camadas de Receita
1. **B2C Transaccional** — micro-taxa por auditoria (R$ 5-50 por relatório)
2. **B2C Recorrente** — planos mensais por perfil (Básico/Pro/Ilimitado)
3. **B2B Contador** — licença mensal + % sobre cada operação assinada

### 6.3 Restrições Regulatórias (CRÍTICO)
- ⚠️ Emissão de DAS/GPS em nome de terceiros exige credenciamento Receita Federal
- ⚠️ Success Fee sobre recuperação pode ser interpretado como exercício irregular de contabilidade
- ⚠️ Abertura de empresa na plataforma exige parceiro contador credenciado (CRC activo)
- **Acção:** Formalizar parceria com contador CRC antes de activar Sprint 4

---

## 7. RISCOS IDENTIFICADOS

### 7.1 Riscos Técnicos
| Risco | Severidade | Estado | Mitigation |
|---|---|---|---|
| `tabela_mva` só tem dados do Pará | 🔴 Crítico | Aberto | Importar MVA todos estados |
| `NormativeAgent` sem dados reais | 🔴 Crítico | Aberto | Integrar Diário Oficial API |
| Redis/RQ configurado mas inactivo | 🟡 Médio | Aberto | Activar para lote em produção |
| `RepairAgent` superficial | 🟡 Médio | Aberto | Implementar leitura de logs reais |
| Ficheiros XML guardados em disco Railway | 🟡 Médio | Aberto | Migrar para processamento em memória |
| Sem testes unitários nos motores fiscais | 🔴 Crítico | Aberto | Criar suite de testes por engine |
| `consulta_paga` flag sem auditoria de quem pagou | 🟡 Médio | Aberto | Log de transacções |

### 7.2 Riscos de Negócio
| Risco | Severidade | Mitigation |
|---|---|---|
| Emissão guias sem credenciamento | 🔴 Crítico | Parceiro contador antes Sprint 4 |
| Success Fee juridicamente ambíguo | 🟡 Médio | Parecer jurídico |
| Dados fiscais de clientes (LGPD) | 🔴 Crítico | Política privacidade + criptografia repouso |
| Dependência único utilizador produtor | 🟡 Médio | Onboarding estruturado |

### 7.3 Pontos Fracos Actuais
1. **Sem Memorial de Cálculo** — o produto está calculado mas não é exportável com embasamento legal
2. **Sem actualizações normativas automáticas** — as leis mudam diariamente, o sistema não acompanha
3. **Sem Human-in-the-Loop** — tudo automático, sem aprovação humana para casos de alto risco
4. **Sem multi-tenancy real** — estrutura existe mas sem isolamento de memória entre empresas durante processamento
5. **Sem OCR** — barreira de entrada alta para utilizadores sem XMLs estruturados

---

## 8. ROADMAP DE SPRINTS

### Sprint 1 — Memorial de Cálculo (PRODUTO VENDÁVEL IMEDIATO)
**Objectivo:** Exportar relatório PDF com embasamento legal para cada centavo calculado  
**Dependências:** `AlertaFiscal`, `Insight`, `EngineResultado` (já existem)  
**Entregável:** PDF auditável que o cliente apresenta em fiscalização  
**Impacto:** Transforma cálculos em produto vendável sem dependência regulatória

### Sprint 2 — OCR Foto → Dados Estruturados
**Objectivo:** Utilizador fotografa recibo/nota → sistema extrai dados → XML sintético  
**Ferramenta:** Claude API (visão) + validação humana antes de persistir  
**Impacto:** Remove barreira de entrada para utilizadores leigos

### Sprint 3 — Agente McKinsey (Lead Magnet)
**Objectivo:** Scan gratuito automático → "Tens 3 riscos e R$ 2.000 para recuperar" → paywall  
**Base:** `AuditorFiscalAgent` já existe, falta UI de resultado + fluxo de conversão  
**Impacto:** Converte visitantes em pagadores sem intervenção humana

### Sprint 4 — Dashboard Contador (Canal B2B)
**Pré-requisito:** Parceiro contador CRC activo  
**Objectivo:** Contador gere carteira de clientes, assina documentos, recebe % por operação  
**Impacto:** Canal de distribuição B2B — 1 contador = 200 clientes

### Sprint 5 — Human-in-the-Loop
**Objectivo:** Insights de alto risco ficam em `aguardando_revisao` até aprovação humana  
**Impacto:** Segurança jurídica + diferencial vs concorrentes 100% automáticos

### Sprint 6 — NormativeAgent Real
**Objectivo:** Watchdog do Diário Oficial + CARF + STF → alerta quando decisão impacta cálculos existentes  
**Ferramenta:** Web scraping + RAG sobre base normativa  
**Impacto:** Único sistema no mercado com actualização normativa em tempo real

### Sprint 7 — MVA Nacional
**Objectivo:** Importar tabela MVA para todos os 26 estados + DF  
**Estado actual:** Só Pará  
**Impacto:** Plataforma passa a servir empresas de qualquer estado

### Sprint 8 — Multi-tenancy Blindado
**Objectivo:** Isolamento de memória durante processamento + criptografia em repouso  
**Impacto:** Permite atender grandes empresas com exigências de compliance (SOC2/ISO27001)

---

## 9. ARQUITECTURA SENTINEL-X (SWARM FUTURO)

```
CEO Agent (Claude Opus)
    ↓ decisões de alto nível, budget de API
    ├── Dev Agent (Claude Code) — refactoring, auto-healing, deploy
    ├── Auditor Agent (Motor Fiscal + RAG) — validação tributária
    └── Growth Agent (Prospecção + emails + conversão)

Guardrails obrigatórios:
- Hard limit de custo por ciclo
- RAG normativo valida qualquer afirmação fiscal antes de persistir
- Human-in-the-Loop para créditos > R$ 10.000
- Nenhum agente assina documentos legais autonomamente
```

---

## 10. PROTOCOLO SOBERANO L2 (REGRAS DE CÓDIGO)

```
1. Motor fiscal = código. API externa = orientação, nunca verdade.
2. Frontend só apresenta. Nunca calcula, nunca infere.
3. 1 commit = 1 intenção. git diff completo antes de commitar.
4. Sem código sem auditoria prévia do ficheiro.
5. Sem alterações ao núcleo sem isolamento.
6. Persistir primeiro → enriquecer depois → só então inteligência.
7. Sem shortcuts. Sem facilidades. Só robustez escalável.
8. Testes de API antes de testes manuais.
9. Sem ficheiros criados sem autorização explícita.
10. Sem commits sem autorização explícita.
```

---

## 11. VARIÁVEIS DE AMBIENTE (PRODUÇÃO)

| Variável | Função |
|---|---|
| `DATABASE_URL` | PostgreSQL Railway (interno) |
| `SECRET_KEY` | JWT signing key |
| `LIBERAR_CONSULTA_REGISTRO` | Activa `consulta_paga=true` no registo |
| `ANALISE_XML_INLINE` | Processa XML sem Redis |

---

## 12. ESTADO ACTUAL EM PRODUÇÃO

**Último commit:** `792d835` — feat(auth): botao mostrar/ocultar senha  
**Branch produção:** `main` → Railway (auto-deploy)  
**Utilizadores em produção:** 1 (jesusmiguel1320@gmail.com, id=13)  
**Migrações aplicadas:** Até `2e580ff68ad3` (add_documentos_rendimento)

**Funcional em produção:**
- ✔ Registo CPF/MEI/Empresa com validação de documento
- ✔ Login com JWT
- ✔ Dashboard por perfil (MEI/CPF/Empresa)
- ✔ Upload XML + análise NF-e
- ✔ Documentos de rendimento CPF
- ✔ Paywall (consulta_paga)
- ✔ Botão mostrar/ocultar senha

**Não funcional / Em falta:**
- ❌ Memorial de Cálculo exportável
- ❌ OCR de imagens
- ❌ Dashboard contador
- ❌ NormativeAgent com dados reais
- ❌ MVA para estados além do Pará
- ❌ Testes unitários nos motores
- ❌ Redis activo em produção

---

## 13. PRÓXIMA SESSÃO

**Prioridade 1:** Sprint 1 — Memorial de Cálculo  
**Prioridade 2:** Testes unitários nos motores fiscais  
**Prioridade 3:** Activar Claude Code / extensão no projecto

**Protocolo de início obrigatório:**
```powershell
git branch; git status --short; git log --oneline -5
```

---

*Este documento deve ser actualizado no início de cada sprint e guardado em `SOBERANA_L2_MASTER.md` na raiz do projecto.*
