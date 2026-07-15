# ADR-009 — Migração Canário B14.3A: AgAberturaAgent

**Status:** RATIFICADO PELO GPT v1.5 — aguarda ratificação final de Miguel
**Data:** 2026-07-14
**Versão:** 1.5 — fecho cirúrgico da v1.4, sem reabertura arquitectural
**Autores:** GPT — redactor e auditor arquitectural; Miguel — fundador e ratificador
**Bloco:** B14.3A
**Repositório:** nexialistamentor/saas-fiscal-demo
**Depende de:** ADR-008 v1.5 (`HEAD` e `origin/main` em `668da07` no início deste bloco)

---

## 1. Contexto

A fundação contratual B14.0+B14.1 está institucionalizada em `origin/main`, com
`1346 passed`, `0 failed` e `8 skipped`.

O conjunto legado de agentes continua a operar pela interface:

```python
async def run(context: dict) -> dict
```

chamada pelo fluxo legado de `AgentExecutor.run_all()`.

B14.3A é a primeira migração operacional individual. O objectivo não é activar agentes
automaticamente, mas provar, num canário de baixo risco técnico, a adaptação entre:

```text
AgentMission
→ adapter soberano
→ agente legado inalterado
→ payload canónico
→ AgentExecutionResult
→ validação cruzada
→ sanitização integral
```

---

## 2. Agente canário seleccionado

**Ficheiro:** `app/agents/ag_abertura_agent.py`
**Classe:** `AgAberturaAgent`
**Identidade canónica:** `ag_abertura`
**Versão:** `1.0`

Evidência auditada directamente do código:

| Dimensão | Evidência |
|---|---|
| Imports | apenas `typing` e `app.constants` |
| BD | nenhuma referência |
| HTTP externo | nenhuma referência |
| LLM | nenhuma referência |
| Escrita de ficheiros | nenhuma |
| Efeitos laterais | transformação de contexto em `dict` |
| Método | `async def run(context)` |
| Instância global | `ag_abertura_agent` |
| Registry | instância já registada pelo fluxo legado |
| Testes próprios | inexistentes antes de B14.3A |

### 2.1 Regra de preservação

`app/agents/ag_abertura_agent.py` permanece **byte a byte inalterado**.

Antes do Commit 2 será registado o SHA256 do ficheiro. Depois da implementação e dos
testes, o mesmo hash deverá ser obtido novamente.

Nenhum método `run_mission()` será adicionado ao agente legado.

---

## 3. Lacunas que impedem publicação

### 3.1 Lacuna normativa

O agente contém afirmações ainda não ligadas a `SourceRef`, vigência ou evidência
soberana, incluindo:

- “Abrir o MEI é gratuito”;
- “100% online”;
- “CNPJ sai na hora”;
- referências temporais fixas a `2026`.

Estas afirmações não podem ser promovidas a resposta soberana publicável neste bloco.

### 3.2 Lacuna comercial

O resultado legado inclui:

```python
"requires_payment": False
```

Esse campo não pode ser propagado para o payload L3 porque o serviço privado da
plataforma é remunerado.

São relações económicas diferentes:

- o procedimento oficial pode ou não possuir taxa pública, conforme acto, localidade e
  situação;
- a plataforma cobra pelos serviços privados contratados de orientação, automação,
  validação, organização, acompanhamento e suporte.

B14.3A não fixa preço, não cria cobrança e não activa pagamento.

### 3.3 Dívidas bloqueadas

Permanecem fora do escopo deste ADR:

- remoção do hardcode temporal;
- substituição de `permissions` mutável;
- fundamentação normativa por fontes soberanas;
- política comercial e tabela de preços;
- publicação do conteúdo;
- integração do adapter no executor selectivo.

Essas lacunas justificam:

```text
requires_human_review = True
publication_allowed = False
```

em todo resultado nominal deste bloco.

---

## 4. Decisão arquitectural

Criar adapter externo assíncrono, sem modificar o agente legado:

```text
app/agents/contracts/ag_abertura.py
app/agents/adapters/__init__.py
app/agents/adapters/ag_abertura.py
tests/test_ag_abertura_mission_adapter.py
```

Assinatura pública:

```python
async def execute_ag_abertura_mission(
    mission: AgentMission,
    agent: AgAberturaAgent = ag_abertura_agent,
) -> AgentExecutionResult:
    ...
```

O adapter:

1. valida a fronteira específica do canário;
2. valida e normaliza o contexto;
3. bloqueia modo ou versão não autorizados sem chamar `run()`;
4. chama `await agent.run(context_dict)` apenas no caminho executável;
5. reconstrói o output legado em contrato Pydantic próprio;
6. elimina a semântica legada `requires_payment=False`;
7. aplica divulgação comercial;
8. constrói `AgentExecutionResult`;
9. valida missão × resultado;
10. sanitiza o resultado completo;
11. devolve apenas resultado validado e sanitizado.

---

## 5. Identificadores canónicos

| Campo | Valor |
|---|---|
| `target_agent` | `"ag_abertura"` |
| `mission_type` | `"orientar_abertura_empresa"` |
| `context_schema` | `"ag_abertura.context"` |
| `context_version` | `"1.0"` |
| `output_schema` | `"ag_abertura.result"` |
| `output_version` | `"1.0"` |
| `agent_version` | `"1.0"` |

Os identificadores são independentes de nomes de classes e ficheiros Python.

---

## 6. Missão canário

Toda missão de teste ou execução nasce exclusivamente por:

```python
create_agent_mission(...)
```

É proibido instanciar `AgentMission(...)` directamente.

Restrições obrigatórias:

| Campo | Regra |
|---|---|
| `target_agent` | `"ag_abertura"` |
| `mission_type` | `"orientar_abertura_empresa"` |
| `context_schema` | `"ag_abertura.context"` |
| `context_version` | `"1.0"` |
| `output_schema` | `"ag_abertura.result"` |
| `output_version` | `"1.0"` |
| `scope` | `"utilizador"` |
| `tenant_id` | `None` |
| `actor_id` | obrigatório e válido |
| `requested_by` | `"user"` ou `"system"` |
| `authority_level` | `"leitura"` |
| `source_event_id` | `None` |
| `schedule_slot` | `None` |
| `source_request_id` | obrigatório |
| `agent_version_required` | `None` ou `"1.0"` para execução |
| `budget_policy` | perfil nulo exacto |
| `sources` | `[]` |

### 6.1 Identidade do actor

Erro específico:

```text
MISSION_ACTOR_UNSUPPORTED
```

Regras:

- `None`: rejeitado;
- `bool`: rejeitado, apesar de `bool` ser subtipo de `int`;
- `str` vazia: rejeitada;
- `str` apenas com espaços: rejeitada;
- `str` não vazia após verificação com `strip()`: aceite;
- `int` não booleano: aceite por compatibilidade com o contrato comum vigente.

B14.3A não inventa uma regra de positividade ausente em `AgentMission`.

### 6.2 Origem

Para este canário:

```text
source_request_id = obrigatório
source_event_id = None
schedule_slot = None
```

A validação usa `source_request_id.strip()` apenas para verificar vazio. O adapter não
reescreve silenciosamente a identidade persistida da missão.

`AgentMission` já normaliza origem textual durante a criação. O adapter mantém a
verificação defensiva da sua própria fronteira.

---

## 7. Perfil nulo de BudgetPolicy

A missão deve corresponder exactamente a:

```python
BudgetPolicy(
    allow_llm=False,
    allowed_providers=[],
    max_calls=0,
    max_input_chars=0,
    max_output_tokens=0,
    max_cost=Decimal("0"),
    currency="BRL",
    on_unavailable="deterministic",
)
```

Qualquer divergência produz erro pré-execução:

```text
MISSION_BUDGET_UNSUPPORTED
```

`sources` deve ser exactamente `[]`.

Aceitar fontes numa missão cujo conteúdo ainda é hardcoded criaria falsa aparência de
fundamentação normativa.

---

## 8. Erros pré-execução

Erros pré-execução:

- não criam `AgentExecutionResult`;
- não chamam `agent.run()`;
- não passam pela validação cruzada;
- não são convertidos silenciosamente em bloqueio.

```python
AdapterPreExecutionErrorCode = Literal[
    "MISSION_TARGET_MISMATCH",
    "MISSION_TYPE_UNSUPPORTED",
    "CONTEXT_SCHEMA_UNSUPPORTED",
    "CONTEXT_VERSION_UNSUPPORTED",
    "OUTPUT_SCHEMA_UNSUPPORTED",
    "OUTPUT_VERSION_UNSUPPORTED",
    "MISSION_SCOPE_UNSUPPORTED",
    "MISSION_ACTOR_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "AG_ABERTURA_CONTEXT_INVALID",
]


class AgAberturaPreExecutionError(Exception):
    def __init__(self, code: AdapterPreExecutionErrorCode):
        self.code = code
        super().__init__(code)
```

| Código | Condição |
|---|---|
| `MISSION_TARGET_MISMATCH` | destino diferente de `ag_abertura` |
| `MISSION_TYPE_UNSUPPORTED` | tipo de missão divergente |
| `CONTEXT_SCHEMA_UNSUPPORTED` | schema de contexto divergente |
| `CONTEXT_VERSION_UNSUPPORTED` | versão de contexto divergente |
| `OUTPUT_SCHEMA_UNSUPPORTED` | schema de saída divergente |
| `OUTPUT_VERSION_UNSUPPORTED` | versão de saída divergente |
| `MISSION_SCOPE_UNSUPPORTED` | scope divergente ou `tenant_id` presente |
| `MISSION_ACTOR_UNSUPPORTED` | actor inválido conforme §6.1 |
| `MISSION_AUTHORITY_UNSUPPORTED` | autoridade ou `requested_by` incompatível |
| `MISSION_ORIGIN_UNSUPPORTED` | origem diferente da definida em §6.2 |
| `MISSION_BUDGET_UNSUPPORTED` | budget diferente do perfil nulo |
| `MISSION_SOURCES_UNSUPPORTED` | `sources` não vazio |
| `AG_ABERTURA_CONTEXT_INVALID` | contexto falha o contrato específico |

---

## 9. Contratos Pydantic específicos

Localização:

```text
app/agents/contracts/ag_abertura.py
```

O módulo é puro: não importa agentes operacionais, ORM, BD, HTTP, serviços ou providers.

### 9.1 Contexto

```python
TIPOS_VALIDOS = frozenset({
    "mei",
    "me",
    "epp",
    "empresa",
    "ltda",
    "slu",
    "ei",
})


class AgAberturaContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo_contribuinte: str = "mei"

    @field_validator("tipo_contribuinte")
    @classmethod
    def validar_tipo(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("tipo_contribuinte deve ser str")

        normalizado = value.strip().casefold()

        if not normalizado:
            raise ValueError("tipo_contribuinte não pode ser vazio")

        if normalizado not in TIPOS_VALIDOS:
            raise ValueError("tipo_contribuinte não reconhecido")

        return normalizado
```

O adapter passa ao legado:

```python
context_model.model_dump(mode="python")
```

Nunca passa o modelo Pydantic directamente.

### 9.2 Checklist

```python
class AgAberturaChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passo: int
    titulo: str
    descricao: str
    link: str | None = None
```

### 9.3 Allowlist soberana de links

```python
EXPECTED_LINKS = {
    "portal_empreendedor":
        "https://www.gov.br/empresas-e-negocios/pt-br/empreendedor",
    "redesim":
        "https://redesim.gov.br",
    "receita_federal":
        "https://www.gov.br/receitafederal",
}

EXPECTED_LINK_CODES = tuple(EXPECTED_LINKS)
```

```python
class AgAberturaLink(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "portal_empreendedor",
        "redesim",
        "receita_federal",
    ]
    url: str

    @model_validator(mode="after")
    def validar_allowlist(self) -> Self:
        if not self.url.startswith("https://"):
            raise ValueError("link deve usar HTTPS")

        if self.url != EXPECTED_LINKS[self.code]:
            raise ValueError("link divergente da allowlist soberana")

        return self
```

O payload deve conter:

- exactamente os três códigos;
- exactamente uma ocorrência de cada;
- ordem canónica de `EXPECTED_LINK_CODES`;
- nenhuma ausência;
- nenhuma chave adicional;
- nenhuma URL divergente;
- nenhum link vindo do contexto do utilizador.

Link inseguro ou ausente torna o payload inválido. Não é aceite apenas com alerta.

### 9.4 Divulgação comercial

```python
class CommercialDisclosure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform_service_requires_payment: Literal[True] = True
    official_process_cost_separate: Literal[True] = True
    pricing_status: Literal[
        "pendente_ratificacao"
    ] = "pendente_ratificacao"

    pricing_policy_id: None = None
    price_amount: None = None
    currency: Literal["BRL"] = "BRL"
    requires_explicit_consent: Literal[True] = True
```

### 9.5 Razões obrigatórias de revisão

```python
ReviewReason = Literal[
    "NORMATIVE_SOURCES_MISSING",
    "COMMERCIAL_POLICY_PENDING",
    "TEMPORAL_HARDCODE_PRESENT",
]

EXPECTED_REVIEW_REASONS: tuple[ReviewReason, ...] = (
    "NORMATIVE_SOURCES_MISSING",
    "COMMERCIAL_POLICY_PENDING",
    "TEMPORAL_HARDCODE_PRESENT",
)
```

### 9.6 Payload nominal

```python
class AgAberturaPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resposta: str
    analysis_type: str
    schema_type: str
    versao: str
    tipo_contribuinte: str

    checklist: tuple[AgAberturaChecklistItem, ...]
    avisos_legais: tuple[str, ...]
    links_uteis: tuple[AgAberturaLink, ...]

    commercial_disclosure: CommercialDisclosure
    review_reasons: tuple[ReviewReason, ...]
    publication_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validar_invariantes_canarios(self) -> Self:
        if self.review_reasons != EXPECTED_REVIEW_REASONS:
            raise ValueError(
                "review_reasons deve conter exactamente as três "
                "razões canónicas, na ordem ratificada"
            )

        codes = tuple(link.code for link in self.links_uteis)
        if codes != EXPECTED_LINK_CODES:
            raise ValueError(
                "links_uteis deve conter exactamente a allowlist "
                "soberana, na ordem canónica"
            )

        return self
```

As três razões são introduzidas pelo adapter. Não vêm do resultado legado.

---

## 10. Garantia de cópia defensiva

B14.3A não promete imutabilidade profunda de `AgentExecutionResult.payload`, porque o
contrato partilhado define:

```python
payload: dict
```

A garantia ratificada é:

> reconstrução canónica, cópia defensiva e ausência de aliasing com o resultado legado,
> com `CHECKLIST_ABERTURA_*` e com outras execuções.

O adapter:

1. não modifica `legacy_result`;
2. não usa `pop()` no objecto legado;
3. reconstrói checklist, avisos e links;
4. valida `AgAberturaPayload`;
5. converte por `model_dump(mode="python")`;
6. entrega um novo `dict` a cada execução.

Testes obrigatórios:

- mutar `result.payload` não altera `legacy_result`;
- não altera `CHECKLIST_ABERTURA_MEI`;
- não altera `CHECKLIST_ABERTURA_ME_EPP`;
- uma segunda execução não herda mutações feitas na primeira.

---

## 11. Resultados bloqueados

Condições de bloqueio pertencentes à missão:

| Condição | Alerta |
|---|---|
| `execution_mode="activo"` | `EXECUTION_MODE_NOT_AUTHORIZED` |
| `agent_version_required` incompatível | `AGENT_VERSION_INCOMPATIBLE` |

Regras:

```text
status = "bloqueado"
payload = {}
payload_schema = mission.output_schema
payload_version = mission.output_version
error_code = None
error_message = None
requires_human_review = True
retryable = False
attempt = 1
llm_used = False
alerts = [um AgentAlert estruturado]
evidence = []
actions_proposed = []
actions_executed = []
```

O agente legado não é chamado.

Alertas usam `evidence_refs=[]`.

---

## 12. Erro interno do legado

Excepção produzida por `await agent.run(...)`:

```text
status = "erro"
error_code = "AG_ABERTURA_EXECUTION_ERROR"
error_message = "Erro interno na execução do agente de abertura"
payload = {}
payload_schema = mission.output_schema
payload_version = mission.output_version
requires_human_review = True
retryable = False
attempt = 1
llm_used = False
alerts = []
evidence = []
actions_proposed = []
actions_executed = []
```

É proibido incluir:

- `str(exc)`;
- traceback;
- contexto;
- caminhos internos;
- payload parcialmente construído.

---

## 13. Semântica do payload por estado

`payload_schema="ag_abertura.result"` representa o contrato de saída solicitado pela
missão.

A validação de conteúdo por `AgAberturaPayload` é obrigatória apenas quando:

```text
status = "sucesso"
```

Para:

```text
status = "bloqueado"
status = "erro"
```

o payload deve ser exactamente:

```python
{}
```

Bloqueio e erro continuam a propagar `mission.output_schema` e `mission.output_version`
para preservar a correspondência missão × resultado no validador comum.

---

## 14. Matriz integral de resultados

Em todos os resultados:

```text
attempt = 1
retryable = False
requires_human_review = True
llm_used = False
provider = None
tokens_used = None
cost_estimated = None
cost_actual = None
currency = None
evidence = []
actions_proposed = []
actions_executed = []
```

| Campo | Sucesso | Bloqueado | Erro interno |
|---|---|---|---|
| `status` | `"sucesso"` | `"bloqueado"` | `"erro"` |
| `payload` | `AgAberturaPayload.model_dump(mode="python")` | `{}` | `{}` |
| `payload_schema` | `mission.output_schema` | `mission.output_schema` | `mission.output_schema` |
| `payload_version` | `mission.output_version` | `mission.output_version` | `mission.output_version` |
| `alerts` | `[]` | um alerta | `[]` |
| `error_code` | `None` | `None` | `"AG_ABERTURA_EXECUTION_ERROR"` |
| `error_message` | `None` | `None` | mensagem pública estável |
| `run()` | uma vez | zero | uma tentativa |
| publicável | não | sem conteúdo | sem conteúdo |

---

## 15. Temporalidade

Para cada resultado:

```python
started_at = datetime.now(timezone.utc)
started_tick = time.perf_counter_ns()

# execução ou construção do bloqueio

finished_tick = time.perf_counter_ns()
duration_ms = max(
    0,
    round((finished_tick - started_tick) / 1_000_000),
)
finished_at = started_at + timedelta(milliseconds=duration_ms)
```

Regras:

- `started_at` é UTC aware;
- `duration_ms` é inteiro e monotónico;
- `finished_at` é derivado por construção;
- `finished_at >= started_at`;
- tolerância temporal do contrato comum é respeitada.

---

## 16. Ordem canónica obrigatória

### 16.1 Caminho nominal

```text
1. validar missão, identidade, origem, budget e sources;
2. validar AgAberturaContext;
3. verificar modo e versão;
4. started_at + started_tick;
5. await agent.run(context_dict);
6. reconstruir e validar AgAberturaPayload;
7. payload_dict = payload_model.model_dump(mode="python");
8. construir AgentExecutionResult;
9. validate_result_against_mission(mission, result);
10. assert_result_sanitized(result.model_dump(mode="json"));
11. devolver.
```

### 16.2 Bloqueio e erro interno

Também constroem `AgentExecutionResult` com:

```text
payload_schema = mission.output_schema
payload_version = mission.output_version
payload = {}
```

Depois:

```text
1. validate_result_against_mission(mission, result);
2. assert_result_sanitized(result.model_dump(mode="json"));
3. devolver.
```

A validação cruzada comum não compara `agent_version_required`; essa verificação é local
no adapter.

---

## 17. Falhas pós-construção

### 17.1 Falha de validação cruzada

```python
class AgAberturaResultValidationError(Exception):
    code = "RESULT_MISSION_VALIDATION_FAILED"
```

Quando `validate_result_against_mission()` falhar:

- nenhum resultado é devolvido;
- nenhuma mensagem original é exposta;
- nenhum resultado parcial é convertido em sucesso ou erro;
- a excepção é distinta dos erros pré-execução.

### 17.2 Falha de sanitização

O símbolo real exportado pelo contrato é:

```python
assert_result_sanitized(result: dict) -> None
```

Quando esse guard falhar:

```python
class AgAberturaResultSafetyError(Exception):
    code = "RESULT_SANITIZATION_FAILED"
```

Regras:

- o resultado inseguro nunca é devolvido;
- a mensagem original do `ValueError` não é exposta;
- não se produz resultado parcial;
- não se converte a falha em sucesso;
- é falha pós-construção, separada da pré-execução e da falha interna do legado.

---

## 18. O que este ADR não autoriza

- modificar qualquer byte de `ag_abertura_agent.py`;
- adicionar `run_mission()` ao agente;
- activar adapter em `AgentExecutor`;
- activar adapter em `AgentScheduler`;
- modificar `AgentRegistry`;
- ligar `run_all()` ao fluxo B14;
- execução real em modo activo;
- persistência em BD;
- chamada LLM;
- provider externo;
- publicar o conteúdo;
- cobrar utilizador;
- criar preço ou plano;
- declarar o serviço da plataforma gratuito;
- migrar outro agente;
- criar timeout;
- criar executor selectivo;
- instanciar `AgentMission` directamente;
- alterar contratos comuns da ADR-008;
- adicionar terceiro commit técnico.

---

## 19. Estratégia de commits

### Commit 1 — documentação

```text
docs: ratificar ADR-009 migração canário AgAberturaAgent
```

Ficheiro único:

```text
docs/ADR-009-MIGRACAO-CANARIO-AG-ABERTURA.md
```

### Commit 2 — implementação canário

```text
feat: adapter L3 AgAberturaAgent em sombra (B14.3A)
```

Ficheiros exactos:

```text
app/agents/contracts/ag_abertura.py
app/agents/adapters/__init__.py
app/agents/adapters/ag_abertura.py
tests/test_ag_abertura_mission_adapter.py
```

Nenhum outro ficheiro.

O SHA256 do agente legado é evidência de teste e fecho; não cria terceiro commit.

---

## 20. Cenários contratuais obrigatórios

A contagem final será registada depois da implementação. Parametrização pode alterar o
número físico de testes.

### 20.1 Missão e fronteira

- missão criada por `create_agent_mission()`;
- adapter é assíncrono;
- target divergente;
- mission type divergente;
- context schema divergente;
- context version divergente;
- output schema divergente;
- output version divergente;
- scope divergente;
- `tenant_id` presente;
- authority divergente;
- `requested_by` divergente;
- actor `None`;
- actor booleano;
- actor string vazia;
- actor apenas com espaços;
- actor string válida;
- actor inteiro não booleano;
- origem ausente;
- `source_event_id` presente;
- `schedule_slot` presente;
- `source_request_id` vazio ou espaços;
- budget divergente em cada campo relevante;
- providers não vazios;
- sources não vazio.

### 20.2 Contexto

- `tipo_contribuinte=None`;
- número;
- string vazia;
- espaços;
- valor desconhecido;
- campo extra;
- normalização por `strip().casefold()`;
- adapter passa `model_dump(mode="python")`.

### 20.3 Nominal

- sombra;
- `dry_run`;
- `run()` aguardado exactamente uma vez;
- `status="sucesso"`;
- `attempt=1`;
- `retryable=False`;
- `requires_human_review=True`;
- `publication_allowed=False`;
- divulgação comercial rígida;
- três razões exactas;
- payload schema/version propagados;
- validação cruzada passa;
- sanitização passa;
- ausência de BD/HTTP/scheduler/LLM.

### 20.4 Review reasons

Rejeitar:

- tupla vazia;
- razão em falta;
- razão duplicada;
- razão adicional;
- ordem divergente.

Aceitar somente `EXPECTED_REVIEW_REASONS`.

### 20.5 Allowlist

Rejeitar:

- HTTP;
- código desconhecido;
- URL divergente;
- link ausente;
- link adicional;
- código duplicado;
- ordem divergente;
- link originado do contexto.

Aceitar somente `EXPECTED_LINKS`.

### 20.6 Bloqueio

- modo activo;
- versão incompatível;
- `run()` não chamado;
- `status="bloqueado"`;
- alerta correcto;
- `error_code=None`;
- `error_message=None`;
- `payload={}`;
- missão e correlação propagadas;
- validação cruzada passa;
- sanitização passa.

### 20.7 Erro interno

- excepção do legado;
- `status="erro"`;
- código público estável;
- mensagem pública estável;
- `payload={}`;
- sem traceback;
- sem texto bruto da excepção;
- validação cruzada passa;
- sanitização passa.

### 20.8 Falhas pós-construção

- validação cruzada falha;
- `AgAberturaResultValidationError`;
- nenhum resultado parcial;
- sanitização falha;
- `AgAberturaResultSafetyError`;
- nenhum resultado inseguro;
- mensagem original não exposta.

### 20.9 Cópia defensiva e ausência de aliasing

- mutar `result.payload` não altera `legacy_result`;
- não altera `CHECKLIST_ABERTURA_MEI`;
- não altera `CHECKLIST_ABERTURA_ME_EPP`;
- não altera as estruturas Pydantic já validadas;
- duas execuções consecutivas não partilham payload;
- mutação da primeira não contamina a segunda.

### 20.10 Integridade do legado

- SHA256 antes e depois idêntico;
- `run(context)` continua funcional;
- `AgentRegistry` continua a registar a mesma instância;
- `AgentExecutor.run_all()` permanece inalterado;
- nenhum outro agente é modificado.

---

## 21. Critério de conclusão de B14.3A

- [ ] ADR-009 v1.5 ratificada por Miguel;
- [ ] Commit 1 documental atómico;
- [ ] quatro ficheiros exactos do Commit 2;
- [ ] todos os cenários contratuais verdes;
- [ ] suite global com zero falhas;
- [ ] os 1346 testes anteriores preservados;
- [ ] contador final registado após execução;
- [ ] SHA256 de `ag_abertura_agent.py` idêntico antes e depois;
- [ ] AgentRegistry inalterado;
- [ ] AgentExecutor inalterado;
- [ ] AgentScheduler inalterado;
- [ ] nenhum outro agente modificado;
- [ ] cópia defensiva e ausência de aliasing provadas;
- [ ] review reasons exactas;
- [ ] allowlist exacta;
- [ ] divulgação comercial rígida;
- [ ] resultado nominal não publicável;
- [ ] validação cruzada antes da sanitização;
- [ ] falhas pós-construção não devolvem resultado parcial;
- [ ] working tree limpa após Commit 2;
- [ ] `origin/main` alinhado após push.

---

## 22. Ratificação

| Papel | Nome | Estado |
|---|---|---|
| Fundador e Arquitecto | Miguel | ⏳ PENDENTE |
| Auditor e Redactor Arquitectural | GPT | ✅ RATIFICADO v1.5 |

**Nenhum código ou teste de B14.3A será escrito antes da ratificação de Miguel e do
Commit 1 documental.**

---

O conhecimento institucional não permanece na conversa. Permanece no repositório, nos
contratos, nos testes e nas evidências.
