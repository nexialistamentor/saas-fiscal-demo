# ADR-008 — Contratos Soberanos dos Agentes L3

**Status:** RATIFICADO E IMPLEMENTADO — FUNDAÇÃO CONTRATUAL B14.0 + B14.1 CONCLUÍDA

**Data:** 2026-07-13  
**Versão:** 1.5

**Autores:** GPT — auditor e redactor arquitectural; Miguel — fundador e ratificador  
**Bloco:** B14.0 + B14.1  
**Repositório:** nexialistamentor/saas-fiscal-demo

---

## 1. Contexto

A plataforma possui 13 agentes executáveis:

- 11 registados no AgentRegistry;
- 2 executados fora do Registry;
- scheduler automático desligado em produção;
- outputs, contextos e níveis de autoridade ainda heterogéneos.

O executor actual utiliza:

```
run_all(context)
```

Esse modelo envia o mesmo contexto genérico a todos os agentes registados, sem distinguir:

- competência;
- tipo de missão;
- escopo global, tenant, documento ou utilizador;
- autoridade;
- idempotência;
- custo LLM;
- efeito de escrita;
- rede externa;
- modo activo, sombra ou dry-run.

A activação directa desse scheduler provocaria riscos já comprovados:

- agentes de abertura e encerramento executados fora de contexto;
- agentes globais repetidos por tenant;
- recuperação de engines executada mais de uma vez;
- possíveis alertas persistidos em duplicado;
- promoção normativa automática sem ratificação;
- incompatibilidade de assinatura entre agentes;
- chamadas externas e LLM sem política central uniforme.

O fluxo técnico automatizado do Pilot 0 está desbloqueado, com smoke 5/5 verde. A abertura pública permanece bloqueada até existir uma camada L3 de contratos, despacho selectivo, auditabilidade e controlo de efeitos.

---

## 2. Decisão

Introduzir contratos soberanos comuns para missões e resultados dos agentes.

A fundação terá:

**Contratos principais**

- `AgentMission`
- `AgentExecutionResult`

**Contratos partilhados**

- `BudgetPolicy`
- `SourceRef`
- `AgentAlert`
- `AgentEvidence`
- `AgentAction`

**Utilitários e validações obrigatórias**

- serialização canónica;
- geração de `context_hash`;
- geração de `idempotency_key`;
- sanitização recursiva de contexto e resultado;
- factory soberana de criação de missões;
- validação cruzada entre missão e resultado.

Nenhum agente será migrado antes desta fundação estar implementada e testada.

---

## 3. Princípios não negociáveis

### 3.1 Uma missão, um agente

Cada `AgentMission` possui apenas um `target_agent`.

Quando um evento exigir vários agentes, o MissionPlanner cria missões independentes:

```
evento
├── missão A → agent_erro_operacional
├── missão B → auditor_fiscal_agent
└── missão C → agente de suporte
```

Cada missão possui:

- `mission_id` próprio;
- chave de idempotência própria;
- escopo próprio;
- autoridade própria;
- resultado próprio.

### 3.2 Sem chamadas directas entre agentes

Um agente nunca chama outro agente directamente.

O agente pode:

- devolver uma `AgentAction` proposta;
- emitir um evento;
- recomendar nova missão.

O MissionPlanner decide se cria a missão seguinte.

### 3.3 Escritor único

O agente não persiste `AgentExecutionResult`.

O `AgentExecutor` é o único responsável por:

- validar o resultado;
- sanitizar o resultado;
- comparar o resultado com a missão original;
- persistir a execução;
- encaminhar acções propostas;
- impedir duplicações.

Alterações no domínio serão executadas por um futuro `ActionExecutor`, após autorização.

### 3.4 Motor-first, LLM-last

Nenhuma missão usa LLM por omissão.

A ordem soberana é:

```
motor determinístico
→ cache
→ padrão local aprendido
→ modelo local
→ provider externo autorizado
→ revisão humana
```

A indisponibilidade ou esgotamento do orçamento LLM bloqueia apenas a chamada externa. Nunca interrompe a função nuclear da plataforma.

### 3.5 Sem `run_all()` em produção

Após B14.5:

```
AgentExecutor.run_all()
```

fica proibido no fluxo de produção.

Pode permanecer temporariamente apenas para:

- testes legados;
- compatibilidade durante migração;
- diagnóstico controlado.

---

## 4. Estrutura de directórios

```
app/agents/
├── contracts/
│   ├── __init__.py
│   ├── canonical.py
│   ├── sanitization.py
│   ├── shared.py
│   ├── mission.py
│   ├── execution_result.py
│   └── validation.py
├── mission_factory.py
└── agentes existentes...
```

### Regra de pureza

`app/agents/contracts/` é um módulo puro.

Pode importar apenas:

- biblioteca padrão;
- Pydantic;
- outros contratos puros.

É proibido importar:

- agentes;
- ORM;
- sessões de BD;
- routers;
- HTTP;
- providers LLM;
- serviços com efeitos secundários.

`mission_factory.py` poderá chamar guards e serviços, mas os contratos não.

---

## 5. Serialização canónica

**Ficheiro:** `app/agents/contracts/canonical.py`

Uma única implementação será usada por todos os hashes e chaves.

```python
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")

    raise TypeError(f"Tipo não serializável canonicamente: {type(obj)!r}")


def canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=json_default,
    )


def canonical_sha256(data: Any) -> str:
    return hashlib.sha256(
        canonical_json(data).encode("utf-8")
    ).hexdigest()


def build_context_hash(context: dict) -> str:
    return canonical_sha256(context)
```

### Invariantes

- dicionários com a mesma informação produzem o mesmo hash;
- ordem das chaves não altera o hash;
- `datetime`, `date`, `UUID`, `Decimal` e modelos Pydantic são suportados;
- tipos não previstos são rejeitados;
- nenhuma implementação paralela de serialização canónica será permitida.

---

## 6. Sanitização soberana

**Ficheiro:** `app/agents/contracts/sanitization.py`

A sanitização é aplicada tanto à missão quanto ao resultado.

Deve bloquear recursivamente:

- CPF;
- CNPJ;
- email completo;
- tokens;
- JWT;
- senha;
- chave de API;
- header Authorization;
- XML fiscal bruto;
- body HTTP integral;
- traceback completo;
- IP em mensagens destinadas a utilizadores ou LLM;
- campos de outro tenant.

A sanitização deve inspeccionar:

- nomes das chaves;
- valores textuais;
- listas;
- dicionários aninhados;
- payloads de modelos Pydantic.

### Interface obrigatória

```python
def assert_context_sanitized(context: dict) -> None:
    ...


def assert_result_sanitized(data: dict) -> None:
    ...
```

A violação levanta erro de contrato antes de:

- criar a missão;
- persistir a missão;
- enviar contexto a LLM;
- persistir o resultado;
- apresentar resultado ao utilizador.

A sanitização não substitui o isolamento multi-tenant. É uma barreira adicional.

---

## 7. Contratos partilhados

**Ficheiro:** `app/agents/contracts/shared.py`

Todos os modelos usam:

```python
model_config = ConfigDict(extra="forbid")
```

### 7.1 SourceRef

```python
class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fonte_id: str

    uso_pretendido: Literal[
        "fundamentar_decisao",
        "validar_fato_operacional",
        "apoiar_explicacao_ux",
        "contexto_llm",
    ]
```

A existência de `SourceRef` não prova autorização.

A `MissionFactory` deve executar o `SourceAuthorityGuard` para cada fonte antes de criar a missão.

Uma fonte bloqueada impede a criação da missão.

### 7.2 BudgetPolicy

```python
class BudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_llm: bool = False
    allowed_providers: list[str] = Field(default_factory=list)

    max_calls: int = Field(default=0, ge=0)
    max_input_chars: int = Field(default=0, ge=0)
    max_output_tokens: int = Field(default=0, ge=0)

    max_cost: Decimal = Decimal("0")
    currency: str = "BRL"

    on_unavailable: Literal[
        "deterministic",
        "cache",
        "local_model",
        "queue",
        "human_review",
    ] = "deterministic"
```

**Invariantes:**

- `allow_llm=False`
  - → `allowed_providers` vazio
  - → `max_calls=0`
  - → `max_input_chars=0`
  - → `max_output_tokens=0`
  - → `max_cost=0`
- `allow_llm=True`
  - → `allowed_providers` não vazio
  - → `max_calls > 0`
  - → `max_input_chars > 0`
  - → `max_output_tokens > 0`

`max_cost`:

- usa `Decimal`;
- rejeita `float`;
- não pode ser negativo.

O `BudgetGuard` real deverá validar ainda:

- plano;
- empresa;
- utilizador;
- missão;
- agente;
- provider;
- modelo;
- saldo diário;
- saldo mensal;
- franquia;
- custo efectivo.

### 7.3 AgentEvidence

```python
class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: UUID4 = Field(default_factory=uuid4)

    evidence_type: Literal[
        "log_ref",
        "event_ref",
        "document_ref",
        "source_ref",
        "metric_ref",
        "rule_ref",
    ]

    reference: str
    sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
    redacted: bool = True
```

A evidência referencia um registo controlado.

Não deve copiar:

- documento;
- XML;
- log integral;
- dados pessoais;
- traceback;
- body de request.

### 7.4 AgentAlert

```python
class AgentAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    severity: Literal[
        "critico",
        "alto",
        "medio",
        "baixo",
        "informativo",
    ]
    message: str
    evidence_refs: list[UUID4] = Field(default_factory=list)
```

Cada `evidence_ref` deve existir em `AgentExecutionResult.evidence`.

### 7.5 AgentAction

```python
class AgentAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: str
    target_type: str | None = None
    target_id: str | int | None = None

    status: Literal[
        "proposta",
        "executada",
        "bloqueada",
    ]

    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
```

**Invariantes:**

- `status="executada"` exige `idempotency_key`;
- acções propostas que possam futuramente causar efeito devem receber chave antes da execução;
- acções em modo sombra ou dry-run nunca aparecem em `actions_executed`.

---

## 8. AgentMission

**Ficheiro:** `app/agents/contracts/mission.py`

```python
class AgentMission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"

    # Identidade
    mission_id: UUID4
    correlation_id: UUID4
    mission_type: str
    target_agent: str

    # Contratos de contexto e output
    context_schema: str
    context_version: str = "1.0"
    output_schema: str
    output_version: str = "1.0"

    # Escopo
    scope: Literal[
        "global",
        "tenant",
        "documento",
        "utilizador",
    ]

    tenant_id: int | None = None
    actor_id: str | int | None = None
    entity_type: str | None = None
    entity_id: str | int | None = None

    # Origem
    source_event_id: UUID4 | None = None
    schedule_slot: str | None = None
    source_request_id: str | None = None
    parent_mission_id: UUID4 | None = None

    requested_by: Literal[
        "system",
        "user",
        "scheduler",
        "agent",
        "admin",
    ]

    # Contexto
    context: dict = Field(default_factory=dict)
    context_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    # Autoridade
    authority_level: Literal[
        "leitura",
        "proposta",
        "execucao",
        "elevada",
    ]

    execution_mode: Literal[
        "activo",
        "sombra",
        "dry_run",
    ]

    ratification_id: str | None = None
    authorized_by: str | int | None = None
    authorization_role: str | None = None

    # Idempotência
    idempotency_key: str = Field(pattern=r"^[a-f0-9]{64}$")

    # Versão do agente
    agent_version_required: str | None = None

    # Prioridade e temporalidade
    priority: Literal[
        "critica",
        "alta",
        "normal",
        "baixa",
    ]

    created_at: AwareDatetime
    deadline: AwareDatetime | None = None

    # Data normativa ou operacional da missão
    reference_at: AwareDatetime | None = None

    # Só entra na chave de idempotência quando fizer parte do efeito
    idempotency_reference_at: AwareDatetime | None = None

    # Políticas
    budget_policy: BudgetPolicy = Field(default_factory=BudgetPolicy)
    sources: list[SourceRef] = Field(default_factory=list)
```

### 8.1 Escopo

| Escopo | Requisitos |
|--------|------------|
| `global` | `tenant_id` ausente |
| `tenant` | `tenant_id` obrigatório |
| `documento` | `tenant_id`, `entity_type` e `entity_id` obrigatórios |
| `utilizador` | `actor_id` obrigatório |

### 8.2 Origem

Exactamente uma origem deve estar presente:

- `source_event_id`;
- `schedule_slot`;
- `source_request_id`.

`parent_mission_id` não conta como origem.

### 8.3 Autoridade

| Nível | Regras |
|-------|--------|
| `leitura` | sem alteração de domínio |
| `proposta` | pode propor `AgentAction`; não pode executar efeito |
| `execucao` + `activo` | depende de `AuthorityGuard` e política executável; não exige ratificação humana por omissão |
| `elevada` + `activo` | exige `ratification_id`; exige `authorized_by`; exige `authorization_role` |

Autoridade elevada pode executar em:

- sombra;
- dry-run;
- proposta;

sem ratificação humana, desde que não execute efeito real.

### 8.4 Temporalidade

Todos os datetimes devem possuir:

```
utcoffset() == timedelta(0)
```

`deadline` não pode ser anterior a `created_at`.

### 8.5 Contexto

O modelo valida:

- hash;
- serialização;
- ausência de campos extras;
- invariantes estruturais.

A sanitização é obrigatória e executada pela factory antes da instanciação operacional.

### 8.6 Idempotência

A chave é criada a partir de:

- `mission_type`
- `target_agent`
- `scope`
- `tenant_id`
- `entity_type`
- `entity_id`
- origem estável
- `idempotency_reference_at`
- `contract_version`

`reference_at` não entra automaticamente na chave.

---

## 9. Builder de idempotência

**Ficheiro:** `app/agents/contracts/canonical.py`

```python
def build_mission_idempotency_key(
    *,
    mission_type: str,
    target_agent: str,
    scope: str,
    tenant_id: int | None,
    entity_type: str | None,
    entity_id: str | int | None,
    source_event_id: UUID | None,
    schedule_slot: str | None,
    source_request_id: str | None,
    idempotency_reference_at: datetime | None,
    contract_version: str,
) -> str:
    payload = {
        "mission_type": mission_type,
        "target_agent": target_agent,
        "scope": scope,
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "entity_id": (
            str(entity_id)
            if entity_id is not None
            else None
        ),
        "source_event_id": source_event_id,
        "schedule_slot": schedule_slot,
        "source_request_id": source_request_id,
        "idempotency_reference_at": idempotency_reference_at,
        "contract_version": contract_version,
    }

    return canonical_sha256(payload)
```

O validator de `AgentMission` recalcula e compara a chave fornecida.

---

## 10. MissionFactory

**Ficheiro:** `app/agents/mission_factory.py`

Nenhum fluxo de produção cria `AgentMission` directamente.

O caminho obrigatório é:

```
create_agent_mission(...)
```

A factory deve:

1. receber os dados da missão;
2. validar o escopo;
3. sanitizar o contexto;
4. verificar as fontes no `SourceAuthorityGuard`;
5. resolver política de autoridade;
6. validar `BudgetPolicy`;
7. calcular `context_hash`;
8. calcular `idempotency_key`;
9. gerar `mission_id`;
10. gerar ou propagar `correlation_id`;
11. criar `AgentMission`;
12. devolver missão validada.

### Interface conceptual

```python
def create_agent_mission(
    *,
    mission_type: str,
    target_agent: str,
    context: dict,
    context_schema: str,
    output_schema: str,
    scope: str,
    requested_by: str,
    authority_level: str,
    execution_mode: str,
    source_event_id=None,
    schedule_slot=None,
    source_request_id=None,
    ...
) -> AgentMission:
    ...
```

### Regra de arquitectura

Instanciação directa de `AgentMission` é permitida apenas em:

- testes de contrato;
- desserialização de registos persistidos;
- migrações controladas.

Testes arquitecturais deverão impedir criação directa nos fluxos de produção.

---

## 11. AgentExecutionResult

**Ficheiro:** `app/agents/contracts/execution_result.py`

```python
class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["1.0"] = "1.0"

    # Identidade da tentativa
    execution_id: UUID4
    attempt: int = Field(ge=1)

    agent_id: str
    agent_version: str

    mission_type: str
    mission_id: UUID4
    correlation_id: UUID4

    # Resultado
    status: Literal[
        "sucesso",
        "erro",
        "bloqueado",
        "pulado",
        "parcial",
    ]

    scope: Literal[
        "global",
        "tenant",
        "documento",
        "utilizador",
    ]

    tenant_id: int | None = None

    # Tempo
    started_at: AwareDatetime
    finished_at: AwareDatetime
    duration_ms: int = Field(ge=0)

    # Modo
    mode: Literal[
        "activo",
        "sombra",
        "dry_run",
    ]

    # Resultado operacional
    alerts: list[AgentAlert] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    actions_proposed: list[AgentAction] = Field(default_factory=list)
    actions_executed: list[AgentAction] = Field(default_factory=list)

    requires_human_review: bool = False

    # Payload
    payload_schema: str
    payload_version: str = "1.0"
    payload: dict = Field(default_factory=dict)

    # LLM
    llm_used: bool = False
    provider: str | None = None
    tokens_used: int | None = Field(default=None, ge=0)

    cost_estimated: Decimal | None = None
    cost_actual: Decimal | None = None
    currency: str | None = None

    # Erro
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
```

### 11.1 Escopo

| Escopo | Requisitos |
|--------|------------|
| `global` | `tenant_id` ausente |
| `tenant` ou `documento` | `tenant_id` obrigatório |

### 11.2 Tempo

- timezone UTC obrigatório;
- `finished_at >= started_at`;
- `duration_ms` deve corresponder ao intervalo, com tolerância de 1 ms.

### 11.3 Status

| Status | Regras |
|--------|--------|
| `erro` | `error_code` obrigatório; `error_message` obrigatório; `actions_executed` vazio |
| `bloqueado` ou `pulado` | `actions_executed` vazio |
| status diferente de `erro` | `error_code` ausente; `error_message` ausente |

### 11.4 Modo

- `sombra` ou `dry_run` → `actions_executed` vazio

### 11.5 Evidências

Todos os IDs em:

```
AgentAlert.evidence_refs
```

devem existir em:

```
AgentExecutionResult.evidence
```

### 11.6 Metadados LLM

Quando `llm_used=False`, devem estar vazios:

- `provider`;
- `tokens_used`;
- `cost_estimated`;
- `cost_actual`;
- `currency`.

Quando `llm_used=True`:

- `provider` é obrigatório;
- `tokens_used`, se presente, é não negativo;
- custos são `Decimal`;
- custos rejeitam `float`;
- custos não podem ser negativos;
- moeda é obrigatória quando existir custo.

---

## 12. Validação cruzada missão × resultado

**Ficheiro:** `app/agents/contracts/validation.py`

```python
def validate_result_against_mission(
    mission: AgentMission,
    result: AgentExecutionResult,
) -> None:
    ...
```

A função compara obrigatoriamente:

```
result.agent_id            == mission.target_agent
result.mission_id          == mission.mission_id
result.mission_type        == mission.mission_type
result.correlation_id      == mission.correlation_id
result.scope               == mission.scope
result.tenant_id           == mission.tenant_id
result.mode                == mission.execution_mode
result.payload_schema      == mission.output_schema
result.payload_version     == mission.output_version
```

Também valida:

- provider autorizado em `BudgetPolicy`;
- número de chamadas permitido;
- limite de tokens;
- custo máximo;
- versão mínima do agente;
- autoridade das acções executadas.

Essa validação será sempre executada pelo `AgentExecutor`.

---

## 13. Sanitização do resultado

Antes da persistência, o `AgentExecutor` aplica:

```python
assert_result_sanitized(
    result.model_dump(mode="json")
)
```

Devem ser inspeccionados:

- `alerts.message`;
- `evidence.reference`;
- `payload`;
- `error_message`;
- `actions_proposed`;
- `actions_executed`.

Nenhuma mensagem bruta de excepção será persistida ou apresentada.

Excepções serão convertidas para:

- `error_code` interno controlado;
- mensagem sanitizada;
- referência segura ao log.

---

## 14. Responsabilidades

### AgentMission

Define:

- o que foi solicitado;
- quem pode executar;
- qual o escopo;
- qual a autoridade;
- qual o modo;
- quais as fontes;
- qual o orçamento;
- qual o contrato de output.

### Agente

Executa apenas a missão autorizada.

**Não:**

- escolhe outro agente;
- aumenta autoridade;
- altera orçamento;
- persiste resultado;
- chama provider directamente;
- executa acções fora do contrato.

### AgentExecutor

Responsável por:

- seleccionar o agente;
- validar compatibilidade;
- controlar tentativa;
- validar e sanitizar resultado;
- comparar resultado com missão;
- persistir execução;
- aplicar idempotência;
- encaminhar acções.

### LLMRouter

Responsável apenas quando houver uso LLM:

- `BudgetGuard`;
- `SourceAuthorityGuard`;
- sanitização;
- provider;
- timeout;
- circuit breaker;
- validação do schema de output;
- uso e custo.

### AuthorityGuard

Responsável por:

- validar `execucao` + `activo`;
- validar papel autorizante;
- bloquear autoridade incompatível;
- exigir ratificação humana em autoridade elevada.

---

## 15. Estratégia de migração

### Grupo 1 — baixo risco

- `ag_abertura_agent`
- `ag_encerramento_agent`
- `performance_agent`
- `repair_agent`
- `memorial_validator_agent`

### Grupo 2 — pipeline fiscal

- `data_sanitization_agent`
- `consistency_audit_agent`
- `auditor_fiscal_agent`
- `agent_erro_operacional`

### Grupo 3 — autoridade e escopo global

- `security_audit_agent`
- `state_recovery_agent`
- `normative_watchdog_agent`
- `normative_validation_agent`

### Fora do contrato de agente por enquanto

`agent_estoque.py` permanece serviço até decisão específica.

Não será registado artificialmente como agente.

---

## 16. Testes obrigatórios

### Contratos partilhados

**Ficheiro:** `tests/test_agent_shared_contracts.py`

Provar:

- `SourceRef`;
- `BudgetPolicy`;
- `AgentEvidence`;
- `AgentAlert`;
- `AgentAction`;
- campos extras proibidos;
- UUID de evidência;
- idempotência de acção;
- coerência financeira.

### Serialização e sanitização

- `tests/test_agent_canonical_contract.py`
- `tests/test_agent_contract_sanitization.py`

Provar:

- hashes determinísticos;
- suporte a UUID, datetime e Decimal;
- bloqueio de CPF;
- bloqueio de CNPJ;
- bloqueio de email;
- bloqueio de token;
- bloqueio de XML;
- bloqueio em campos aninhados;
- sanitização de resultados.

### AgentMission

- `tests/test_agent_mission_contract.py`
- `tests/test_agent_mission_factory.py`

Provar:

- escopos;
- origem única;
- UTC;
- deadline;
- autoridade;
- ratificação;
- fontes;
- hash;
- idempotência;
- criação somente pela factory no fluxo operacional.

### AgentExecutionResult

- `tests/test_agent_execution_result_contract.py`

Provar:

- status;
- modo;
- tempo;
- escopo;
- evidências;
- LLM;
- custos;
- acções;
- erros;
- sanitização.

### Validação cruzada

- `tests/test_agent_mission_result_validation.py`

Provar divergências em:

- agente;
- missão;
- correlação;
- tipo;
- escopo;
- tenant;
- modo;
- schema;
- versão;
- provider;
- custo.

### Teste arquitectural

- `tests/test_agent_contract_architecture.py`

Provar:

- contratos não importam ORM, HTTP ou providers;
- agentes não chamam agentes;
- produção não cria `AgentMission` directamente fora da factory;
- nenhum agente chama provider LLM directamente;
- `run_all()` não será usado no fluxo B14.

---

## 17. Estratégia de commits

| Commit | Mensagem |
|--------|----------|
| 1 | `docs: ratificar ADR-008 contratos soberanos L3` |
| 2 | `feat: serialização canónica e sanitização dos contratos` |
| 3 | `feat: contratos partilhados dos agentes` |
| 4 | `feat: contrato AgentMission e MissionFactory` |
| 5 | `feat: contrato AgentExecutionResult e validação cruzada` |
| 6 | `test: invariantes arquitecturais dos contratos L3` |

Cada commit deve:

- ser atómico;
- deixar os testes relevantes verdes;
- não modificar agentes existentes;
- não activar scheduler;
- não activar LLM real.

---

## 18. O que este ADR não autoriza

Este ADR **não** autoriza:

- modificar agentes existentes;
- ligar o scheduler;
- activar `run_all()` em produção;
- activar DeepSeek real;
- criar escrita normativa automática;
- abrir a plataforma ao público;
- criar ou executar acções elevadas sem ratificação;
- alterar o `AgentRegistry`;
- migrar `agent_estoque.py` para agente.

Essas alterações pertencem aos blocos seguintes.

---

## 19. Critério de conclusão de B14.0 + B14.1

- [x] ADR-008 ratificado e commitado;
- [x] `canonical.py` criado;
- [x] `sanitization.py` criado;
- [x] `shared.py` criado;
- [x] `mission.py` criado;
- [x] `execution_result.py` criado;
- [x] `validation.py` criado;
- [x] `mission_factory.py` criado;
- [x] testes dos contratos partilhados verdes;
- [x] testes de sanitização verdes;
- [x] testes de missão e factory verdes;
- [x] testes de resultado verdes;
- [x] testes de validação cruzada verdes;
- [x] teste arquitectural verde;
- [x] suite global mantém pelo menos 870 testes aprovados;
- [x] nenhum agente existente modificado;
- [x] working tree limpa após commit.

---

## 20. Ratificação

| Papel | Nome | Estado |
|-------|------|--------|
| Fundador e Arquitecto | Miguel | ✅ RATIFICADO |
| Auditor Arquitectural | GPT | ✅ RATIFICADO v1.5 |
| Redactor | GPT | ✅ CONCLUÍDO |

---

## 21. Evidência de fecho

- baseline operacional anterior: `30cbb0f` (Pilot 0 desbloqueado);
- cadeia técnica ratificada: `e20f55c → f77684f → eed4bdf → e71047c → 2641729 → 7e7d764`;
- Commit 1: `e20f55c` — ratificação documental da ADR-008;
- Commit 2: `f77684f` — serialização canónica e sanitização;
- Commit 3: `eed4bdf` — contratos partilhados;
- Commit 4: `e71047c` — `AgentMission` e `MissionFactory`;
- Commit 5: `2641729` — `AgentExecutionResult` e validação cruzada;
- Commit 6: `7e7d764` — invariantes arquitecturais dos contratos L3;
- teste arquitectural: 51 aprovados, 0 falhas;
- suite global: 1346 aprovados, 8 ignorados, 0 falhas;
- `HEAD` técnico pré-fecho documental e `origin/main` verificados em `7e7d764253e899c0de47ac5d50dc65388c05996c`;
- SHA256 de `tests/test_agent_contract_architecture.py`: `C5D849661CBC9934DAE2FF14355F845131FFF6EE7F9340B397CDBB0472EB0BA7`;
- working tree limpa após o Commit 6.

Este fecho comprova a fundação contratual B14.0 + B14.1. Não declara a migração operacional dos agentes existentes, nem activa agentes, scheduler ou LLM real.

Qualquer activação, autoridade executiva, consumo LLM real, escrita automática ou integração no fluxo de produção exige bloco posterior explicitamente ratificado, com testes, budget guard, idempotência, auditoria e rollback.

O conhecimento institucional não permanece na conversa. Permanece no repositório, nos contratos, nos testes e nas evidências.
