# PROTOCOLO SOBERANA L2

> Versão: 2.1 | Actualizado: 2026-04-28 | HEAD: 35bc944

---

## 0. INÍCIO DE SESSÃO (obrigatório)

```powershell
git branch; git status --short; git log --oneline -5
```

Nunca actuar sem confirmar branch, ficheiros modificados e HEAD.

---

## 1. PRINCÍPIOS FUNDAMENTAIS

1. **Persistir primeiro → enriquecer → só então inteligência**
2. **Motor fiscal = código** — cálculos no backend; frontend só apresenta
3. **Zero fallback geográfico implícito** — sem `or "PA"` ou defaults de estado
4. **Fonte normativa rastreável** — toda regra MVA/PMPF tem `fonte_legal`, `url_fonte`, `nivel_confianca_fonte`, `importado_por`
5. **Nunca apagar dados fiscais** — só marcar (`superseded`, `vigencia_fim`, `silenciado`)
6. **1 intenção = 1 commit** — `git diff --cached --stat` antes de commitar
7. **Zero merge para `main` sem testes verdes**
8. **Ler antes de escrever** — `Get-Content` completo antes de qualquer alteração; nunca editar por resumo ou por output de outro agente
9. **Zero dados normativos sem fonte verificável** — nenhum MVA/alíquota/PMPF entra no repositório sem URL oficial e número do acto normativo citado explicitamente
10. **Automação total** — todo trabalho repetitivo normativo é executado por código e agentes; contador intervém exclusivamente para assinatura digital de auditoria

---

## 2. STACK

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + SQLAlchemy + PostgreSQL (Railway) |
| Cache/Queue | Redis + RQ |
| Frontend | React + Vite (Vercel) |
| Branch produção | `main` → Railway |
| Branch trabalho | feature branch → PR → `main` |

---

## 3. REGRAS DE CÓDIGO

### 3.1 Antes de qualquer alteração

- Ler o ficheiro completo (`Get-Content`) — nunca editar por resumo
- `git diff` para confirmar o estado real
- PowerShell: usar `;` em vez de `&&`
- Inspecionar output real (ex: PDF, HTML, API) antes de escrever parser

### 3.2 Proibições absolutas

- Não duplicar rotas nem fluxos XML
- Não alterar `motor_fiscal.py` sem necessidade explícita
- Não usar LLM no pipeline primário de cálculo
- Não hardcodar UF, estado ou fallback geográfico
- Não usar `func.concat()` — incompatível entre SQLite e PostgreSQL; usar concatenação Python
- Não commitar sem `py_compile` ou `pytest tests/ -q` verde
- Não usar `asyncio.run()` dentro de event loop activo — usar `await`
- Não inferir estrutura de ficheiro externo (PDF/HTML) sem inspecção real prévia

### 3.3 Padrão de commit

tipo(escopo): descrição imperativa em português

feat     — nova funcionalidade

fix      — correcção de bug

refactor — reorganização sem mudança de comportamento

perf     — optimização

chore    — infra, deps, config

---

## 4. PIPELINE NORMATIVO

### Hierarquia de confiança (prioridade decrescente)

oficial > candidata_oficial > convenio_base > convenio_base_sem_aliquota > estimativa > sem_fonte

### Hierarquia de cálculo ST

PMPF (tabela_pmpf — por marca/embalagem)

IVA-ST% (tabela_mva — por NCM/UF)

indisponivel — nunca inventar valor

### Ciclo completo de actualização normativa

Parsers (DOU/SEFAZ estaduais)

→ extracção automática

→ nivel_confianca="candidata_oficial"

→ pipeline_normativo.importar_regras(dry_run=True)

→ AG-VALIDACAO (ciclo global, fora do loop por empresa)

→ promoção automática para "oficial" se critérios passam

→ AlertaFiscal para rejeições

→ /admin/alertas-normativos → operador verifica

→ marcar_alerta_processado()

### Regras de ouro normativas

- `nivel_confianca_fonte="oficial"` nunca é sobrescrito automaticamente
- `candidata_oficial` → `oficial` apenas via AG-VALIDACAO após validação cruzada
- Portaria revogada: `expirar_regras_revogadas()` com operador identificado
- NCM inferido por mapeamento determinístico (ex: Anexo I SAIF MG → 22021000) documentado no código
- Novos dados: commit com número da portaria, data de consulta e URL oficial

### Parsers activos

| Parser | Fonte | Estado |
|--------|-------|--------|
| `dou_parser.py` | DOU/INLABS | ⏳ Aguarda `INLABS_USER`/`INLABS_PASS` |
| `sefaz_sp_parser.py` | SEFAZ-SP SRE 89/2025 | ✅ Baseline 66% NCM 2202 |
| `sefaz_mg_parser.py` | SEFAZ-MG HTML | ✅ Detecta estrutura |
| `sefaz_mg_pdf_parser.py` | SEFAZ-MG PDF SAIF 062/2025 | ✅ 791 regras PMPF |

---

## 5. AGENTES

- Só consomem dados já persistidos na BD
- Nunca processam XML bruto
- Retornam sempre: `agent`, `total_alertas`, `alertas`, `status: "executado"`
- Alertas têm `tipo`, `descricao`, `nivel` (critico/alto/medio/baixo)
- Registados em `AgentRegistry` — `name` único por agente

### Agentes activos

| Nome | Função | Escopo |
|------|--------|--------|
| `data_sanitization_agent` | Higiene de dados | Por empresa |
| `auditor_fiscal_agent` | Auditoria fiscal | Por empresa |
| `normative_agent` | NormativeWatchdogAgent — DOU + vigências | Por empresa |
| `consistency_audit_agent` | Consistência entre tabelas | Por empresa |
| `memorial_validator_agent` | Validação antes de exportar memorial | Por empresa |
| `security_audit_agent` | Padrões suspeitos de uso | Por empresa |
| `state_recovery_agent` | Circuit breaker e engines degradadas | Por empresa |
| `repair_agent` | Reparação de estados inconsistentes | Por empresa |
| `normative_validation_agent` | Promove `candidata_oficial` → `oficial` | **Global** (scheduler) |

### Regra crítica de escopo

Agentes com escopo **Global** NÃO são registados no `AgentRegistry`.

São chamados directamente em `AgentScheduler._finalizar_ciclo_metricas_e_cache()` com `await`.

---

## 6. SEGURANÇA

- `LoginThrottle`: Redis (produção) + fallback memória — 5 tentativas / 15 min
- JWT: `jti` revogado em Redis após logout — TTL = tempo restante do token
- Rate limit: por `user_id` (JWT válido) ou IP (fallback)
- `request_logs`: middleware async (`asyncio.to_thread`) — purga automática (default 30 dias)
- `SECRET_KEY`: obrigatória em produção — app não inicia sem ela
- `REDIS_URL`: obrigatória em produção para throttle e revogação JWT

---

## 7. DADOS E MIGRAÇÕES

- ORM: SQLAlchemy + Alembic
- Toda migration: verificar que só toca a tabela pretendida (autogenerate detecta ruído)
- SQLite local / PostgreSQL Railway — testar compatibilidade antes de push
- `Base.metadata.create_all` no startup (novas instâncias) + `alembic upgrade head` (instâncias existentes)
- Dados imutáveis: `superseded` (insights), `vigencia_fim` (MVA/PMPF), `processado` (alertas)
- `func.concat()` proibido — usar Python para concatenação de strings em updates ORM

---

## 8. TESTES

```powershell
python -m pytest tests\ -q   # sempre antes de commitar
```

- `testpaths = tests` no `pytest.ini` — `scripts/` excluídos
- Paths Redis: validar com `fakeredis` antes de commitar
- Paths async: `pytest-asyncio` com `asyncio_mode = auto`
- Novos serviços críticos: mínimo 1 teste unitário antes de merge
- Parsers externos: testar com mock (`patch("httpx.get")`) — nunca depender de rede em CI

---

## 9. VARIÁVEIS DE AMBIENTE

| Variável | Obrigatória | Descrição |
|----------|------------|-----------|
| `SECRET_KEY` | Produção | Chave JWT — app não inicia sem ela |
| `REDIS_URL` | Produção | Throttle + revogação JWT |
| `DATABASE_URL` | Produção | PostgreSQL Railway |
| `ENVIRONMENT` | Não | `production` activa validações estritas |
| `REQUEST_LOG_RETENTION_DAYS` | Não | Default 30 dias |
| `INLABS_USER` | Parsers DOU | Credencial INLABS Imprensa Nacional |
| `INLABS_PASS` | Parsers DOU | Credencial INLABS Imprensa Nacional |

---

## 10. ESCALAR PARA FINTECH — REGRAS NÃO NEGOCIÁVEIS

1. **Zero dados não verificados em produção** — `convenio_base_sem_aliquota` nunca vira `oficial` sem portaria real
2. **Zero cálculo ST sem fonte** — `confianca: indisponivel` bloqueia, não estima
3. **Auditoria completa** — quem importou, quando, de que fonte, com que nível de confiança
4. **Trilha imutável** — nenhum dado fiscal é apagado, só encerrado (`vigencia_fim`) ou substituído (`superseded`)
5. **Monitorização automática** — parsers + AG3 + AG-VALIDACAO; operador assina, sistema detecta e promove
6. **Testes obrigatórios** — sem excepções, sem "validado em produção"
7. **Automação total** — contador assina digitalmente apenas o relatório final; nunca alimenta dados manualmente
8. **Inspecção antes de código** — output real (PDF/HTML/API) sempre inspeccionado antes de escrever parser

---

## 11. BACKLOG REGISTADO

| Item | Descrição |
|------|-----------|
| AG-ABERTURA | Agente de abertura de empresa (MEI/ME/EPP) com REDESIM |
| AG-ENCERRAMENTO | Agente de baixa de empresa com verificação fiscal |
| INLABS | Parser DOU XML estruturado — aguarda credenciais |
| Alíquotas 26 UFs | Verificação RICMS estadual por UF |
| Rotação JWT | `kid` no header + suporte múltiplas chaves |
| AG-VALIDACAO escopo | Mover para job dedicado fora do scheduler quando volume crescer |

---

## 12. FICHEIROS DE REFERÊNCIA

| Ficheiro | Conteúdo |
|----------|---------|
| `PROTOCOLO.md` | Este ficheiro |
| `app/services/pipeline_normativo.py` | Import nacional de regras normativas |
| `app/agents/normative_watchdog_agent.py` | Monitorização DOU e vigências |
| `app/agents/normative_validation_agent.py` | Promoção `candidata_oficial` → `oficial` |
| `app/services/parsers/` | Parsers normativos por fonte |
| `app/services/parsers/orquestrador_parsers.py` | Orquestrador de todos os parsers |
| `data/mva/convenio_142_2018.csv` | Base MVA nacional (27 UFs) |
| `doc/mg_pmpf_mapping.md` | Mapeamento NCM por anexo SEFAZ-MG |

---

*Última actualização: 2026-04-28 | HEAD: 35bc944*
