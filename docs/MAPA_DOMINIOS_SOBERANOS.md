# MAPA DE DOMÍNIOS SOBERANOS L2

**Versão:** 1.0

**Data:** 2026-06-18

**Autoridade:** Miguel (fundador e autoridade final de produto)

**Natureza:** Documento de descoberta — classifica os domínios soberanos da plataforma,
  prova o estado operacional de cada um e regista desalinhamentos com evidência de código.

**Base:**

- MAPA_REALIDADE_TRIBUTARIA_L2.md v1.0
- CONSTITUICAO_TRIBUTARIA_L2.md v1.0

**Método:** leitura directa de ficheiros + verificação de fluxos de execução. Zero suposições.

**HEAD de referência:** `f10bf21` — docs: CONSTITUICAO_TRIBUTARIA_L2 v1.0

---

## 1. OS CINCO DOMÍNIOS SOBERANOS

A plataforma opera (ou declara operar) em cinco domínios distintos.
Cada domínio tem autoridade, tabelas e fluxos próprios.
Nenhum domínio substitui outro.

| ID | Domínio | Autoridade | Estado operacional |
|----|---------|------------|-------------------|
| D1 | **Fiscal** | Plataforma (motores + pipeline XML) | ✅ Parcial — pipeline canónico activo; rotas paralelas incompletas |
| D2 | **Documental** | Plataforma + contador (homologação) | ✅ Parcial — ingestão implementada; produção não validada |
| D3 | **Normativo** | Estado (fonte) → Plataforma (tabela_mva) | ⚠️ Parcial — cobertura PA; fallback JSON activo |
| D4 | **Operacional** | Plataforma (agentes + observabilidade) | ❌ Inactivo — scheduler desligado; agent_estoque fora do registry |
| D5 | **Institucional** | Plataforma (auth, planos, pagamentos) | ✅ Parcial — auth e paywall activos; contador pendente de produção |

---

## 2. DOMÍNIO D1 — FISCAL

**Autoridade:** cálculo, enquadramento, score, insights, alertas, planejamento tributário.

**Motores soberanos:** `motor_fiscal.py`, `tax_engines/`, `regime_router.py`, `analysis_orchestrator.py`

**Pipeline canónico (provado):**

```
POST /fiscal/analisar-xml?empresa_id=N
→ executar_e_registrar_analise_xml
  → executar_analise_xml
  → processar_e_persistir_xml
  → InsightEngine.gerar_insights_empresa
  → calcular_score_global_tributario
  → relatorios_analise + alertas_fiscais
```

**Tabelas operacionais:**

| Tabela | Função |
|--------|--------|
| `documentos_fiscais` | Cabeçalho NF-e persistido |
| `itens_fiscais` | Itens por documento (classe ORM: `ItemFiscal`) |
| `relatorios_analise` | Registo auditável por análise |
| `alertas_fiscais` | Alertas gerados por agentes e InsightEngine |
| `inteligencia_snapshots` | Score e métricas agregadas |
| `engine_resultados` | Resultados por motor fiscal |

**Alias ORM:** `NotaFiscalItem = ItemFiscal` (`app/models.py:336`) — mesma tabela `itens_fiscais`.

**Evidência de capacidade:** 228 testes passando; pipeline canónico referenciado em `registro_analise_service.py`.

**Classificação:** operacional (parcial) — pipeline principal activo; rotas alternativas sem auditabilidade completa.

---

## 3. DOMÍNIO D2 — DOCUMENTAL

**Autoridade:** OCR, confiança, homologação, pool de contadores, governança de documentos ingeridos.

**Pipeline (provado):**

```
POST /ingestao/documentos
→ classificar → extrair → confiança → normalizar
→ documentos_ingeridos
→ homologacao_service (fluxo contador)
```

**Tabelas operacionais:**

| Tabela | Função |
|--------|--------|
| `documentos_ingeridos` | Documentos PDF/imagem ingeridos (domínio separado de NF-e) |
| `homologacoes_documentais` | Fila e decisões de contador |
| `perfis_contador` | CRC, status, reputação |

**Fronteira declarada:** `documentos_ingeridos` ≠ `documentos_fiscais` — pipelines e tabelas separadas (CONSTITUIÇÃO, Artigo IV).

**Evidência de capacidade:** `tests/test_homologacao_service.py`, `tests/test_document_confidence.py`.

**Classificação:** parcial — código e testes existem; utilização em produção não comprovada.

---

## 4. DOMÍNIO D3 — NORMATIVO

**Autoridade:** tabelas normativas internas como fonte de verdade em tempo de execução.

**Funções canónicas:** `buscar_mva`, `carregar_mva` (`tabela_normativa_service.py`, `motor_fiscal.py`)

**Tabelas operacionais:**

| Tabela | Função |
|--------|--------|
| `tabela_mva` | MVA por estado + NCM + vigência |
| `tabela_pmpf` | PMPF quando aplicável |

**Agentes normativos declarados:**

| Agente | Ficheiro | Estado |
|--------|----------|--------|
| NormativeWatchdogAgent | `normative_watchdog_agent.py` | ⚠️ Código existe; ciclo scheduler desligado |
| NormativeValidationAgent | `normative_validation_agent.py` | ⚠️ Invocado no scheduler; scheduler desligado |

**Evidência de lacuna:** MVA só Pará (`mvas_pa.py` + seed); `carregar_mva` tem fallback para `app/data/mva.json` quando `buscar_mva` não encontra regra.

**Classificação:** parcial — fonte primária declarada (`tabela_mva`); fallback JSON activo; cobertura geográfica incompleta.

---

## 5. DOMÍNIO D4 — OPERACIONAL

**Autoridade:** observabilidade, agentes autónomos, métricas, recuperação de estado, auditoria de estoque.

**Componentes centrais:**

| Componente | Ficheiro | Estado |
|------------|----------|--------|
| AgentScheduler | `agent_scheduler.py` | ❌ Instanciado; loop comentado em `main.py:134-136` |
| AgentExecutor | `agent_executor.py` | ⚠️ Funcional; depende de scheduler activo |
| AgentRegistry | `agent_registry.py` | 11 agentes registados |
| agent_estoque | `agent_estoque.py` | ⚠️ Activo via rota; **não registado** no AgentRegistry |

**agent_estoque — comportamento provado:**

- Consulta `itens_fiscais` via SQL directo (`text()` em `agent_estoque.py:9-23`).
- Persiste resultado em `auditoria_estoque` via `salvar_auditoria`.
- Invocado por `POST /auditar` (`app/routes/auditoria.py`) — **fora** do ciclo AgentExecutor.

**InsightEngine — acesso ao mesmo dado:**

- Usa alias ORM `NotaFiscalItem` (mesma tabela `itens_fiscais`) em `insights_engine.py`.
- Lógica de agregação, ST e oportunidades distinta da query de estoque fiscal.

**Tabelas operacionais:**

| Tabela | Função |
|--------|--------|
| `itens_fiscais` / alias ORM `NotaFiscalItem` | Dados fiscais por item (dois caminhos de acesso) |
| `auditoria_estoque` | Snapshot de estoque fiscal por NCM |
| `request_logs` | Observabilidade HTTP |

**Classificação:** inactivo — scheduler desligado; swarm de agentes não corre em produção; `agent_estoque` opera isoladamente sob demanda HTTP.

---

## 6. DOMÍNIO D5 — INSTITUCIONAL

**Autoridade:** identidade, planos, monetização, perfis de contribuinte, contador parceiro.

**Componentes:**

| Componente | Ficheiro | Estado |
|------------|----------|--------|
| Auth JWT | `auth_router.py` | ✅ Produção |
| Planos e limites | `models.Plano`, `usage_service.py` | ✅ Produção |
| Paywall | `consulta_paga` + `pagamento_service.py` | ✅ Código; Mercado Pago não validado em produção |
| Perfil contador | `models.PerfilContador` | ⚠️ Schema existe; pool operacional não comprovado |

**Tabelas operacionais:**

| Tabela | Função |
|--------|--------|
| `usuarios` | Identidade + role + CPF |
| `planos` | Limites de análise e tipo de acesso |
| `pagamentos` / `pagamento_tentativas` | Transacções Mercado Pago |
| `perfis_contador` | CRC, status, reputação |

**Classificação:** parcial — auth e paywall activos; canal contador B2B não operacional em produção.

---

## 7. TABELA DE DESALINHAMENTOS PROVADOS

| ID | Domínio | Desalinhamento | Evidência | Risco |
|----|---------|----------------|-----------|-------|
| DT-FLUXO-01 | D1 Fiscal | `/upload-xml` persiste sem `relatorios_analise`, InsightEngine nem score | `main.py → processar_e_persistir_xml` sem registro | Auditabilidade |
| DT-FLUXO-02 | D1 Fiscal | `/lote/analisar-lote` sem persistência — TTL em memória | `lote_router.py` | Auditabilidade lote |
| DT-FLUXO-03 | D1 Fiscal | Dedup por `xml_chave` após persistência | `registro_analise_service.py` | Duplicatas |
| DT-NORM-01 | D3 Normativo | MVA só Pará; cobertura nacional inexistente | `mvas_pa.py`, seed PA | ST fora do PA |
| DT-NORM-02 | D3 Normativo | Fallback JSON (`mva.json`) activo quando `buscar_mva` falha | `motor_fiscal.py:120-125` | Fonte normativa duplicada |
| DT-OP-01 | D4 Operacional | Dois caminhos de acesso sem árbitro canónico | Ver §7.1 | Divergência de lógica |
| DT-OP-02 | D4 Operacional | `agent_estoque` fora do AgentRegistry e do AgentExecutor | `agent_registry.py` vs `auditoria.py` | Observabilidade fragmentada |
| DT-OP-03 | D4 Operacional | AgentScheduler instanciado mas loop desligado | `main.py:134-136` | Agentes inactivos em produção |
| DT-OP-04 | D4 Operacional | 11 agentes registados; nenhum corre periodicamente | `agent_registry.py` + scheduler off | Consciência operacional zero |
| DT-INST-01 | D5 Institucional | Critério "lei exige CRC" não modelado como entidade | CONSTITUIÇÃO §1 Art. I | Gatilho contador incompleto |
| DT-REDIS-01 | Transversal | Redis/RQ inactivo; fallback síncrono silencioso | `redis_queue.py`, Railway | Performance / escala |
| DT-AUTH-01 | Transversal | Autoridade não declarada quando motores divergem | MAPA_REALIDADE §5 | Arquitectura |

---

### 7.1 DT-OP-01 — Dois caminhos de acesso sem árbitro canónico

**agent_estoque** consulta `itens_fiscais` via SQL directo.

**InsightEngine** usa o alias ORM `NotaFiscalItem` (mesma tabela `itens_fiscais`).

Não há árbitro declarado sobre qual caminho de acesso é canónico —
risco de divergência de **lógica**, não de dados em tabelas separadas.

**Tabela operacional:**

- `itens_fiscais` / alias ORM `NotaFiscalItem` (mesma tabela, dois acessos)
- `auditoria_estoque`

**Prova de alias ORM:**

```python
# app/models.py
class ItemFiscal(Base):
    __tablename__ = "itens_fiscais"
    ...

NotaFiscalItem = ItemFiscal
```

**Prova de SQL directo:**

```python
# app/agents/agent_estoque.py
query = text("""
    SELECT i.ncm, SUM(...) as estoque_fiscal
    FROM itens_fiscais i
    JOIN documentos_fiscais d ON i.documento_id = d.id
    ...
""")
```

---

## 8. MATRIZ DOMÍNIO × CRITÉRIO OPERACIONAL

| Domínio | Código | Fluxo activo | Produção | Resultado auditável |
|---------|--------|--------------|----------|---------------------|
| D1 Fiscal | ✅ | ✅ (canónico) | ✅ | ✅ (canónico) |
| D2 Documental | ✅ | ✅ | ⚠️ | ⚠️ |
| D3 Normativo | ✅ | ⚠️ | ⚠️ | ⚠️ |
| D4 Operacional | ✅ | ❌ | ❌ | ⚠️ (só agent_estoque sob demanda) |
| D5 Institucional | ✅ | ✅ (auth) | ✅ (auth) | ⚠️ (pagamentos) |

Legenda: ✅ comprovado | ⚠️ parcial ou não validado | ❌ inactivo

---

## 9. FRONTEIRAS ENTRE DOMÍNIOS (provadas)

| Fronteira | Regra | Estado |
|-----------|-------|--------|
| D1 ↔ D2 | NF-e XML ≠ documentos ingeridos OCR | ✅ Respeitada |
| D1 ↔ D3 | Motores consultam `tabela_mva`; não legislam | ✅ Declarada; fallback JSON viola espírito |
| D1 ↔ D4 | Agentes interpretam dados persistidos; não processam XML bruto | ✅ Declarada em `.cursorrules` |
| D4 ↔ D1 | InsightEngine e agent_estoque acedem `itens_fiscais` por caminhos distintos | ❌ Sem árbitro (DT-OP-01) |
| D5 ↔ D2 | Contador actua em homologação documental | ✅ Schema separado |

---

## 10. HIERARQUIA NORMATIVA DESTE DOCUMENTO

Lei → Constituição Tributária L2 → **MAPA DE DOMÍNIOS SOBERANOS** → ADRs → Invariantes → Contratos → Código → Testes

Este mapa não altera a Constituição. Declara a realidade operacional que a Constituição assume.

---

## INVARIANTE DE DESCOBERTA

A existência de código não constitui prova de capacidade operacional.

Um domínio só é considerado operacional quando:

- existe código;
- existe fluxo de execução activo;
- existe evidência de utilização em produção;
- existe resultado observável e auditável.

Na ausência de qualquer destes elementos,
o domínio é classificado como parcial ou inactivo.

```
código ≠ capacidade
capacidade ≠ autoridade
autoridade ≠ instituição
```

Esta separação é o que permite que a plataforma continue coerente
quando houver novos agentes, novas normas e novas tecnologias.

---

*Este mapa foi escrito após auditoria completa da realidade do sistema
(MAPA_REALIDADE_TRIBUTARIA_L2.md v1.0) e validação constitucional
(CONSTITUICAO_TRIBUTARIA_L2.md v1.0). Não foi escrito sobre suposições.*

*O conhecimento não está na conversa. Está no repositório.*
