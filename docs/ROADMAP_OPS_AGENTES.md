# ROADMAP_OPS_AGENTES.md — Circuito Operacional e Agentes em Modo Aprendizagem

**Versão:** 1.1  
**Data:** 2026-06-28  
**Contexto:** Fisco Soberano — B13 em estabilização operacional  
**Princípio:** Agente aprende, classifica e sugere. Humano aprova. Sistema regista.

> **Regra soberana:** Agente pode aprender, sugerir, alertar, classificar e propor patch.  
> Agente NÃO pode: auto-commitar, auto-deployar, escrever directamente no banco, decidir fiscalmente, substituir gov.br/REDESIM/contador quando aplicável.

---

## Kill Switches — variáveis obrigatórias antes de qualquer agente activo

```env
AGENTS_ENABLED=false
AGENT_LEARNING_MODE=true
AGENT_AUTO_PATCH=false
AGENT_AUTO_COMMIT=false
AGENT_AUTO_DEPLOY=false
DEEPSEEK_DRY_RUN=true
```

**Regra:** Se `AGENTS_ENABLED=false`, nenhum agente chama LLM em produção.  
**Regra:** Se `AGENT_LEARNING_MODE=true`, agente só diagnostica e sugere — nunca actua.

---

## Estado Real (mapeado em 2026-06-28)

### Agentes existentes mas desligados

| Ficheiro | Função declarada | Estado |
|---------|-----------------|--------|
| `repair_agent.py` | Reparação autónoma | Existe, desligado |
| `normative_watchdog_agent.py` | Vigilância normativa | Existe, desligado |
| `normative_validation_agent.py` | Validação normativa | Existe, desligado |
| `agent_scheduler.py` | Agendamento de jobs | Existe, não verificado |
| `consistency_audit_agent.py` | Auditoria de consistência | Existe, desligado |
| `performance_agent.py` | Monitorização de performance | Existe, desligado |
| `security_audit_agent.py` | Auditoria de segurança | Existe, desligado |
| `state_recovery_agent.py` | Recuperação de estado | Existe, desligado |

### Serviços de actualização existentes mas não provados

| Ficheiro | Função declarada |
|---------|-----------------|
| `atualizacao_normativa_service.py` | Actualização normativa |
| `pipeline_normativo.py` | Pipeline de normas |
| `tabela_normativa_service.py` | Tabelas normativas |
| `normative_update_service.py` | Actualização normativa |
| `jobs/analysis_job.py` | Job de análise |

### Constantes hardcoded que precisam de prova de alinhamento

| Constante | Valor | Fonte oficial | Diploma legal |
|-----------|-------|--------------|--------------|
| `MEI_LIMITE_ANUAL_FATURAMENTO` | 81_000 | gov.br/mei | LC 155/2016 art. 18-A |
| `MEI_FATURAMENTO_ALERTA_PROXIMO_LIMITE` | 75_000 | Derivado | — |
| `SALARIO_MINIMO_POR_ANO[2026]` | 1518.00 | gov.br | Decreto 12.302/2026 |
| `PARCELA_FIXA_COMERCIO` | 1.00 | Res. CGSN 140/2018 | — |
| `PARCELA_FIXA_SERVICOS` | 5.00 | Res. CGSN 140/2018 | — |

---

## O que o Piloto 0 revelou (e um circuito operacional teria capturado)

Evento que ocorreu manualmente e devia ser automático:

```json
{
  "tipo": "race_condition_frontend",
  "origem": "validarSessao — App.jsx",
  "endpoint": "/empresas/",
  "status_http": 403,
  "mensagem": "Termos de Uso não aceites",
  "classificacao": "P0",
  "causa_provavel": "setUsuario() disparava hooks antes de has-accepted-terms resolver",
  "ficheiros_provaveis": ["frontend-dashboard/src/App.jsx"],
  "teste_recomendado": "login com termos=false não deve chamar /empresas/",
  "patch_sugerido_texto": "mover has-accepted-terms para antes de setUsuario()",
  "estado": "corrigido",
  "commit_correcao": "d9f31b4"
}
```

---

## FASE 0 — Fechar B13 (bloqueante)

### B13-P0-06 — Gate de termos antes de setUsuario() ✔
Commit `d9f31b4` — race condition eliminada.

### B13-P0-07 — Registo/login no domínio customizado sem falha silenciosa

**Critério de saída:**
- [ ] Registo novo em `www.fiscosoberano.com.br` funciona sem erro silencioso
- [ ] Email já cadastrado mostra CTA "Fazer login aqui"
- [ ] Login válido entra no dashboard
- [ ] Gate de termos aparece antes do dashboard
- [ ] Nenhuma chamada crítica gera ecrã apagado
- [ ] Console do browser sem erros CORS/403 após login

### B13-Piloto — Teste manual T1-T8
Executar em `www.fiscosoberano.com.br` em modo anónimo.

### PILOTO_0_FEEDBACK.md
Criar após teste com: HEAD testado, URL, cenários, P0 resolvidos/pendentes, decisão fechar/pendente.

---

## FASE 1 — Prova de Fontes Tributárias (B13-OPS-01)

**Objectivo:** provar que constantes tributárias têm fonte rastreável, versão e alinhamento com o motor.

### 1.1 — Auditar mecanismos existentes (antes de criar novo)

```powershell
Get-Content app\agents\agent_scheduler.py | Select-Object -First 60
Get-Content app\agents\normative_watchdog_agent.py | Select-Object -First 60
Get-Content app\services\atualizacao_normativa_service.py | Select-Object -First 60
Get-Content app\services\pipeline_normativo.py | Select-Object -First 60
```

Mapear: o que estes ficheiros fazem? Estão activos? Têm testes?

### 1.2 — Criar docs/FONTES_TRIBUTARIAS.md (leitura humana)

| Constante | Valor | Fonte | Diploma legal | Vigência | Última verificação |
|-----------|-------|-------|--------------|----------|-------------------|
| MEI_LIMITE_ANUAL_FATURAMENTO | 81_000 | gov.br/mei | LC 155/2016 art. 18-A | 2018→ | 2026-06-28 |
| SALARIO_MINIMO_2026 | 1518.00 | gov.br | Decreto 12.302/2026 | Jan/2026→ | 2026-06-28 |
| PARCELA_FIXA_COMERCIO | 1.00 | Res. CGSN 140/2018 | | 2018→ | 2026-06-28 |
| PARCELA_FIXA_SERVICOS | 5.00 | Res. CGSN 140/2018 | | 2018→ | 2026-06-28 |

### 1.3 — Criar data/fontes_tributarias_manifest.json (leitura por máquina)

```json
{
  "versao": "1.0",
  "ultima_atualizacao": "2026-06-28",
  "fontes": {
    "MEI_LIMITE_ANUAL_FATURAMENTO": {
      "valor": 81000,
      "fonte": "gov.br/mei",
      "diploma": "LC 155/2016 art. 18-A",
      "vigencia_inicio": "2018-01-01",
      "ultima_verificacao": "2026-06-28",
      "status": "verificado"
    },
    "SALARIO_MINIMO_2026": {
      "valor": 1518.00,
      "fonte": "gov.br",
      "diploma": "Decreto 12.302/2026",
      "vigencia_inicio": "2026-01-01",
      "ultima_verificacao": "2026-06-28",
      "status": "verificado"
    }
  }
}
```

### 1.4 — Teste de alinhamento manifest ↔ motor

```python
# tests/test_fontes_tributarias_manifest.py
def test_mei_limite_alinhado_com_manifest():
    manifest = json.loads(Path("data/fontes_tributarias_manifest.json").read_text())
    assert MEI_LIMITE_ANUAL_FATURAMENTO == manifest["fontes"]["MEI_LIMITE_ANUAL_FATURAMENTO"]["valor"]
```

### 1.5 — Sentinelas de prova (3 obrigatórias)

| Sentinela | Teste | Estado |
|-----------|-------|--------|
| S1 — MEI limite | MEI + R$500k → inelegível com motivo | ✔ passa (B13-P0-02) |
| S2 — CNAE software | "SaaS fiscal" → 62xx/63xx | ✔ passa (B13-P0-01) |
| S3 — Fonte versionada | manifest.json existe e alinhado com motor | ⬜ criar em FASE 1 |

**Critério de aprovação FASE 1:** S1 + S2 + S3 passam + manifest.json existe + FONTES_TRIBUTARIAS.md criado.

---

## FASE 2 — LLMRouter DeepSeek (B13-OPS-02)

**Objectivo:** provedor LLM para análise e diagnóstico. DeepSeek analisa — não decide.

### Ficheiros a criar

```
app/services/llm_router.py
app/services/llm_providers/__init__.py
app/services/llm_providers/deepseek_provider.py
app/services/llm_providers/mock_provider.py   ← obrigatório para testes
app/schemas/llm_schema.py
tests/test_llm_router_deepseek.py
```

### Variáveis de ambiente

```env
DEEPSEEK_API_KEY=           # nunca hardcodar
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash    # NÃO usar deepseek-chat (depreciado 2026-07-24)
DEEPSEEK_TIMEOUT_SECONDS=30
DEEPSEEK_MAX_RETRIES=2
DEEPSEEK_DRY_RUN=true
LLM_PROVIDER=deepseek
```

> **Nota:** `deepseek-chat` e `deepseek-reasoner` estão em rota de depreciação para 2026-07-24.  
> Usar `deepseek-v4-flash` (diagnóstico rápido) ou `deepseek-v4-pro` (auditoria pesada).

### Schemas

```python
class LLMRequest(BaseModel):
    tarefa: str          # "diagnostico_erro" | "sugestao_teste" | "analise_cnae"
    contexto: dict       # dados sanitizados — NUNCA dados fiscais brutos
    provider: str = "deepseek"
    dry_run: bool = True

class LLMResponse(BaseModel):
    provider: str
    modelo: str
    output: dict         # sempre JSON estruturado
    tokens_usados: int
    latencia_ms: int
    dry_run: bool
    erro: str | None
```

### Testes — mock obrigatório

```python
# tests/test_llm_router_deepseek.py
# Por defeito usa mock_provider — sem internet, sem saldo, sem key
# Integração real só com: DEEPSEEK_INTEGRATION=1
import pytest, os
skip_sem_deepseek = pytest.mark.skipif(
    os.environ.get("DEEPSEEK_INTEGRATION") != "1",
    reason="DEEPSEEK_INTEGRATION=1 não definido"
)
```

### Regras invariantes do LLMRouter

- Nunca expor `DEEPSEEK_API_KEY` em logs ou respostas
- Sanitização obrigatória antes de qualquer envio (ver FASE 3 — EventoOperacional)
- Output sempre JSON estruturado
- DeepSeek não escreve no banco
- DeepSeek não faz commit/deploy
- DeepSeek não decide CNAE/regime de forma canónica

---

## FASE 3 — Agentes em Modo Aprendizagem (B13-OPS-03)

### Contrato EventoOperacional

```python
class EventoOperacional(BaseModel):
    id: str                      # UUID
    timestamp: datetime
    ambiente: str                # "producao" | "local"
    commit_sha: str
    origem: str                  # ficheiro/componente
    tipo: str                    # "cors" | "race_condition" | "deploy" | "ux" | "fiscal"
    endpoint: str | None
    status_http: int | None
    mensagem: str
    payload_redigido: dict       # NUNCA dados fiscais brutos
    usuario_id_hash: str | None  # hash do id, nunca email/CPF
    classificacao: str | None    # P0/P1/P2 — preenchido pelo agente
    estado: str                  # "aberto" | "em_analise" | "corrigido" | "regressao_criada"
    teste_recomendado: str | None
    ficheiros_provaveis: list[str]
    patch_sugerido_texto: str | None
    commit_correcao: str | None
```

### Regra de sanitização obrigatória

**Antes de qualquer envio ao LLM:**

```python
CAMPOS_PROIBIDOS = ["cpf", "cnpj", "email", "token", "password", "xml", "documento"]

def sanitizar_contexto(contexto: dict) -> dict:
    """Remove dados sensíveis antes de enviar ao LLM."""
    return {k: "[REDIGIDO]" if any(p in k.lower() for p in CAMPOS_PROIBIDOS) else v
            for k, v in contexto.items()}
```

### Agentes prioritários

| Prioridade | Agente | Aprende com | Saída |
|-----------|--------|------------|-------|
| 1 | **AgentErroOperacional** | CORS, 401/403, race condition, deploy errado, bundle antigo | P0/P1/P2 + causa + teste |
| 2 | **AgentUX** | Ecrã branco, mensagem técnica, botão invisível, fluxo sem próximo passo | Melhoria texto + CTA + teste leigo |
| 3 | **AgentQA** | Bug que escapou, teste fraco, falso positivo | Novo teste + assert + critério bloqueio |
| 4 | **AgentFiscal/CNAE** | CNAE errado, MEI indevido, limite mal tratado | Ajuste regra + teste + alerta baixa confiança |
| 5 | **AgentAberturaEmpresa** | Dúvidas CNPJ/MEI/ME, contador obrigatório | Dossiê + checklist + próximo passo |
| 6 | **AgentDeploy/Infra** | Vercel env vazia, Railway antigo, CORS, DNS, health | Smoke test + checklist deploy + alerta |

### Prompt base (aplicar a todos)

```
Tu és um agente de diagnóstico operacional soberano.
NÃO alteras código directamente.
NÃO decides fiscalmente.
NÃO assumes causa sem evidência.
NÃO inventas dados ausentes.
NÃO recebes dados fiscais brutos — todo contexto chega sanitizado.

Classificação obrigatória: P0 (bloqueia piloto) | P1 (antes abertura) | P2 (melhoria futura)

Output JSON com campos obrigatórios:
{
  "classificacao": "P0|P1|P2",
  "causa_provavel": "...",
  "evidencias": [...],
  "ficheiros_provaveis": [...],
  "teste_recomendado": "...",
  "patch_sugerido_texto": "...",
  "risco_patch": "baixo|medio|alto",
  "informacao_em_falta": "..."
}

Se faltarem dados, indica o menor comando de diagnóstico possível.
```

---

## FASE 4 — Circuito Fechado (B13-OPS-04)

```
Erro em produção / Piloto
    ↓
EventoOperacional criado (sanitizado)
    ↓
AgentErroOperacional analisa via LLMRouter
    ↓
Classificação P0/P1/P2 + causa + teste sugerido
    ↓
Miguel aprova
    ↓
Patch criado → suite green → commit → deploy
    ↓
Teste de regressão entra na suite
    ↓
EventoOperacional.estado = "regressao_criada"
    ↓
Memória operacional actualizada (FONTES_TRIBUTARIAS.md / manifest.json)
```

**Meta operacional:** erro real → diagnóstico → teste → patch sugerido → aprovação humana em < 30 min.

---

## Critérios de aprovação por fase

| Fase | Critério |
|------|---------|
| FASE 0 | B13-P0-06 ✔, B13-P0-07 passa, Piloto T1-T8 sem P0 aberto, PILOTO_0_FEEDBACK.md criado |
| FASE 1 | manifest.json criado, S1+S2+S3 passam, teste alinhamento motor ↔ manifest verde |
| FASE 2 | LLMRouter responde com JSON, mock provider nos testes, sem API key exposta, DEEPSEEK_INTEGRATION=1 opcional |
| FASE 3 | AgentErroOperacional classifica race_condition como P0, sanitização activa, EventoOperacional gravado |
| FASE 4 | Erro real → diagnóstico automático → teste de regressão criado < 30 min |

---

## O que NÃO fazer em nenhuma fase

- Auto-commit sem aprovação humana
- Auto-deploy sem aprovação humana  
- Escrita directa no banco sem trilha de auditoria
- Decisão fiscal canónica por LLM
- Envio de dados fiscais brutos ao DeepSeek
- Substituir gov.br/REDESIM/Receita
- Tornar contador obrigatório sem base legal
- Activar todos os agentes simultaneamente sem contrato
- Usar `deepseek-chat` (depreciado 2026-07-24)
