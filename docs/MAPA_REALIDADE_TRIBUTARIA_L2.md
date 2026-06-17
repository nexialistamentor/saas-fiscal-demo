# MAPA_REALIDADE_TRIBUTARIA_L2.md

**Versão:** 1.0
**Data:** 2026-06-17
**Natureza:** Documento de descoberta — prova a realidade do sistema, não o que foi planeado.
**Método:** leitura directa de ficheiros + execução de testes. Zero suposições.

---

## 1. ESTADO DO REPOSITÓRIO

| Item | Valor |
|------|-------|
| HEAD | `8f5ce25` — docs(roadmap): marcar nucleo empresarial V1 em producao |
| Branch | `main` — limpa, sincronizada com `origin/main` |
| Untracked | `.cursor/rules.md` |
| Alembic head (repo) | `0009_add_documento_sha256` |
| Alembic head (test.db local) | `0000_baseline` (8 revisões atrás — esperado) |
| Testes | 228 passed, 4 skipped |

---

## 2. STACK REAL EM PRODUÇÃO

| Componente | Stack | Deploy |
|------------|-------|--------|
| Backend | FastAPI + Python | Railway — Nixpacks |
| BD | PostgreSQL (Railway) | `alembic upgrade head` no preDeployCommand |
| Frontend | React 19 + Vite | Vercel (`dist/` em repo) |
| Redis/RQ | Configurado, **inactivo em produção** | Sem worker Railway activo |
| Healthcheck | `GET /health` | Confirmado no railway.toml |

---

## 3. CAPACIDADES REAIS (provadas por código)

| Funcionalidade | Estado | Prova |
|----------------|--------|-------|
| Login / Auth | ✅ FUNCIONA | `auth_router.py` + JWT + token revocation |
| Registo utilizador | ✅ FUNCIONA | `auth_router.py` |
| Upload XML (persistência) | ✅ PARCIAL | `main.py → processar_e_persistir_xml` — sem InsightEngine nem score |
| Análise XML canónica | ✅ FUNCIONA (com empresa_id) | `fiscal_router.py → processar_xml_job → executar_e_registrar_analise_xml` |
| Análise XML efémera | ✅ FUNCIONA (sem empresa_id) | `fiscal_router.py → executar_analise_xml` — sem persistência |
| Análise em lote | ⚠️ PARCIAL | `lote_router.py → executar_analise_xml` — sem persistência, TTL em memória |
| Dashboard CPF | ✅ FUNCIONA | `cpf_router.py` + `useCpfDashboard.js` |
| Dashboard Empresa | ✅ FUNCIONA | `empresa_router.py` + `useEmpresaDashboard.js` |
| Dashboard MEI | ✅ FUNCIONA | `routers/` + `useMeiDashboard.js` |
| InsightEngine | ✅ FUNCIONA (canónico) | `insights_engine.py` chamado via `executar_e_registrar_analise_xml` |
| Score global tributário | ✅ FUNCIONA (canónico) | `score_global_tributario_service.py` |
| PDF Relatório | ✅ FUNCIONA | `pdf_report_service.py` + `RelatorioPDFButton.jsx` |
| Mercado Pago | ✅ IMPLEMENTADO | `pagamento_service.py` + tabelas `pagamentos/pagamento_tentativas` |
| OCR / Ingestion documental | ✅ IMPLEMENTADO | `ingestion_router.py` + `document_ingestion/` pipeline |
| AgentScheduler | ⚠️ DESLIGADO | Instanciado em `main.py` mas loop comentado no lifespan |
| Redis/RQ worker | ❌ INACTIVO | Fallback síncrono activo (`ANALISE_XML_INLINE` ou except) |
| NormativeAgent | ❌ NÃO FUNCIONAL | `normative_watchdog_agent.py` existe, pipeline vazio |
| MVA nacional | ❌ PARCIAL | Só Pará (`mvas_pa.py`) + `app/data/mva.json` |

---

## 4. FLUXOS REAIS (provados por leitura de código)

### 4.1 Pipeline Canónico (completo e auditável)
POST /fiscal/analisar-xml?empresa_id=N

→ _enqueue_or_run_sync()

→ processar_xml_job()                    [analysis_job.py]

→ executar_e_registrar_analise_xml()   [registro_analise_service.py]

1. verificar_limite_analises

2. executar_analise_xml            [analysis_orchestrator.py]

3. processar_e_persistir_xml       [xml_service.py]

4. dedup por xml_chave

5. criar_registro_analise          → relatorios_analise

6. InsightEngine.gerar_insights_empresa → alertas_fiscais + insights

7. calcular_score_global_tributario

8. finalizar_registro_analise + incrementar_uso_analise

### 4.2 Upload XML (parcial — sem auditoria completa)
POST /upload-xml

→ validar_upload_xml

→ ler_xml_unico

→ processar_e_persistir_xml    ← persistência sim

✗ sem relatorios_analise

✗ sem InsightEngine

✗ sem score

✗ sem verificar_limite_analises

### 4.3 Análise Efémera (sem persistência)
POST /fiscal/analisar-xml (sem empresa_id)

→ executar_analise_xml

→ resposta em memória

✗ nada persiste

### 4.4 Lote (sem persistência)
POST /lote/analisar-lote

→ loop executar_analise_xml por ficheiro

→ dict jobs em memória (TTL ~1h)

✗ nada persiste

### 4.5 Ingestão Documental (domínio separado)
POST /ingestao/documentos  (PDF/imagem)

→ classificar → extrair → confiança → normalizar

→ documentos_ingeridos           ← tabela diferente de documentos_fiscais

→ homologacao_service            ← fluxo contador

---

## 5. MODELO DE AUTORIDADE

A plataforma hoje:

| Função | Estado |
|--------|--------|
| **Observa** | ✅ Logs, RequestLog, métricas |
| **Calcula** | ✅ Motores fiscais, score, MVA/ST |
| **Recomenda** | ✅ InsightEngine, alertas_fiscais |
| **Decide** | ❌ Não decide — apresenta resultados ao utilizador |

Pergunta não respondida formalmente: **qual é a autoridade da plataforma quando dois motores divergem?** Não existe árbitro declarado.

---

## 6. SCHEMA EM PRODUÇÃO (Railway)

| Migração | Conteúdo | Estado Railway |
|----------|----------|----------------|
| 0000_baseline | Tabelas core (usuarios, planos, documentos_fiscais, itens_fiscais, etc.) | ✅ |
| 0001–0008 | Expansões (planos, pagamentos, perfil_contador, ingestion, empresa, etc.) | ✅ |
| 0009_add_documento_sha256 | `conteudo_sha256` + constraint unique em `documentos_fiscais` | ⏳ próximo deploy |

---

## 7. DÍVIDAS TÉCNICAS MAPEADAS

| ID | Descrição | Bloqueia |
|----|-----------|---------|
| DT-DB-01 | Import circular `database.py → ensure_sqlite_schema_compat` bloqueia `alembic current` local | Desenvolvimento local |
| DT-DB-02 | `test.db` local em `0000_baseline` — não reflecte produção | Desenvolvimento local |
| DT-FLUXO-01 | `/upload-xml` persiste sem fechar ciclo auditável (sem `relatorios_analise`, `InsightEngine`, score) | Auditabilidade |
| DT-FLUXO-02 | `/lote/analisar-lote` sem persistência — resultados efémeros em memória | Auditabilidade lote |
| DT-FLUXO-03 | Dedup por `xml_chave` em `registro_analise_service` ocorre após `processar_e_persistir_xml` — risco de duplicata em `relatorios_analise` | Consistência |
| DT-AGENTE-01 | `AgentScheduler` instanciado mas loop desligado — agentes não correm em produção | Observabilidade |
| DT-AGENTE-02 | `NormativeAgent` existe mas pipeline vazio | Normativo |
| DT-MVA-01 | MVA só Pará — cobertura nacional inexistente | Fiscal (ST nacional) |
| DT-REDIS-01 | Redis/RQ inactivo — fallback síncrono activo; sem worker em Railway | Performance / escala |
| DT-AUTH-01 | Autoridade não declarada quando motores divergem | Arquitectura |

---

## 8. RISCOS ARQUITECTURAIS

1. **Dois pipelines XML paralelos** — `/upload-xml` e `/fiscal/analisar-xml` têm comportamentos diferentes para o mesmo tipo de ficheiro. Um utilizador que use o errado perde auditabilidade sem aviso.

2. **Redis inactivo com fallback silencioso** — o sistema parece assíncrono mas corre síncrono. Sob carga, bloqueia.

3. **AgentScheduler desligado** — 16 agentes declarados, nenhum a correr. Observabilidade zero em produção.

4. **Autoridade não declarada** — a plataforma calcula e recomenda, mas não tem árbitro quando resultados divergem.

---

## 9. O QUE ESTÁ PROVADO vs. O QUE É INTENÇÃO

| Item | Provado | Intenção |
|------|---------|----------|
| Pipeline canónico XML | ✅ | — |
| InsightEngine + score | ✅ | — |
| Pagamentos Mercado Pago | ✅ código | ⚠️ não validado em produção |
| Agentes operacionais | ❌ | ✅ planeado |
| NormativeAgent | ❌ | ✅ planeado |
| MVA nacional | ❌ | ✅ planeado |
| Multi-tenancy | ❌ | ✅ roadmap futuro |
| Constituição institucional | ❌ | ✅ próxima sessão |

---

## 10. PRÓXIMO PASSO LEGÍTIMO

A realidade está mapeada. A fundação existe mas é parcial.

Antes de qualquer agente ou funcionalidade nova:

**CONSTITUIÇÃO DA PLATAFORMA TRIBUTÁRIA L2**

Pergunta central a responder:

> Qual é a autoridade da Plataforma Tributária L2?

Sem essa resposta, qualquer arquitectura nova assenta em suposições.
