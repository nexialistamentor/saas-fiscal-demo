# ADR-013 — Migração L3 B14.3E: MemorialValidatorAgent em Sombra

**Status:** RATIFICADA v1.3 — aprovada por Miguel e GPT
**Data:** 2026-07-19
**Versão da ADR:** 1.3 — rectificação das quatro lacunas identificadas pelo GPT
**Versão dos contratos:** 1.0
**Bloco:** B14.3E
**Repositório:** nexialistamentor/saas-fiscal-demo
**Depende de:** ADR-008 v1.5, ADR-011 v1.2 e ADR-012 v1.3
**Baseline confirmado:** HEAD = origin/main = d4c506c598a9a1f1c430266cc10aacef3375e99e
**Baseline de testes:** 1819 passed / 8 skipped / 0 failed

---

## 1. Contexto

O MemorialValidatorAgent é o terceiro canário da brigada determinística:

```text
DataSanitizationAgent
→ motores fiscais
→ ConsistencyAuditAgent
→ MemorialValidatorAgent
→ exportação fora da autoridade do agente
```

B14.3E cria um adapter L3 estritamente explícito, read-only,
determinístico e executável apenas em sombra ou dry_run.

O canário valida a completude de um snapshot mínimo de memorial. Ele
não:

- autoriza exportação;
- publica documentos;
- grava dados;
- consulta banco;
- recolhe contexto;
- executa o agente legado;
- participa do scheduler;
- participa do registry;
- participa do executor genérico;
- altera endpoints existentes.

Os endpoints de memorial e `coletar_contexto_memorial()` são apenas
a origem conceptual dos dados. O dicionário bruto produzido pelo
serviço não é entrada válida directa do adapter L3.

A criação futura de um projector, reader ou ligação entre o serviço
e o adapter exige ADR própria.

**Padrão de referência:** B14.3E reutiliza os contratos partilhados e
o padrão de fronteira de B14.3D. Divergências de assinatura, enum,
mensagem operacional ou forma de `AgentExecutionResult` são proibidas
salvo rectificação prévia da ADR.

---

## 2. Legado protegido

**Ficheiro:** `app/agents/memorial_validator_agent.py`

```python
LEGACY_HASH_ALGORITHM: Literal["sha256"] = "sha256"

LEGACY_HASH_HEX = (
    "B8B5841BB5D3F85BE412421614D01212"
    "D967C298DE4F2437A39F31FA54A546A4"
)
```

O SHA-256 serve aqui apenas como evidência de integridade do ficheiro,
não como assinatura, prova de autoria ou mecanismo de autenticação.

Invariantes:

- permanece byte a byte inalterado;
- não recebe `run_mission()`;
- não é importado pelo contrato, motor, adapter ou testes de execução;
- não é instanciado;
- não é chamado;
- não é utilizado como fallback.

---

## 3. Preparação criptográfica e pós-quântica

B14.3E não executa criptografia, assinatura, verificação de assinatura,
gestão de chaves ou estabelecimento de segredo.

Nenhum algoritmo pós-quântico e nenhuma biblioteca criptográfica serão
adicionados ao contrato, motor ou adapter.

A integração futura de evidência assinada, identidade criptográfica ou
transporte protegido exigirá ADR própria e uma fronteira criptográfica
soberana, versionada e substituível. A futura fronteira deverá
transportar, no mínimo:

```text
algorithm_id
algorithm_version
key_id
canonicalization_version
signature_format
signature
signed_at
```

Nenhum desses campos entra em B14.3E. Esta arquitectura evita
dependências irreversíveis, mantém versões explícitas e permite
substituir futuramente a fronteira criptográfica sem alterar o motor
fiscal.

---

## 4. Limites de autoridade

O adapter produz somente diagnóstico.

São proibidos:

- `pode_exportar`
- `memorial_validado`
- `publication_allowed = true`
- `actions_executed` não vazio
- modo activo

O payload terá obrigatoriamente:

```python
publication_allowed: Literal[False] = False
```

A decisão real de exportar pertence ao fluxo operacional exterior ao
agente.

---

## 5. Divergências deliberadas em relação ao legado

### 5.1 Alertas de referências incompletas

O legado pode produzir um alerta por referência sem fundamento.

B14.3E produz apenas um `MEMORIAL_REFERENCIA_INCOMPLETA`,
independentemente da quantidade de referências afectadas.

Razões:

- não expor indirectamente a quantidade de referências incompletas;
- impedir códigos duplicados;
- tornar o payload canónico e idempotente;
- representar uma condição diagnóstica, não uma contagem de ocorrências.

### 5.2 Mensagens públicas

O legado interpola código de referência e contagem de alertas.
B14.3E utiliza apenas mensagens fixas, sem valores do contexto.

### 5.3 Fundamento com whitespace

O legado usa `if not r.get("fundamento")`, que trata string vazia e
`None` como incompletos mas aceita strings de espaços como válidas.

B14.3E normaliza esta regra:

```text
fundamento is None             → incompleto
fundamento == ""               → incompleto
fundamento.strip() == ""       → incompleto
fundamento com tipo não textual → contexto inválido
```

Esta é a terceira divergência deliberada. A decisão de incompletude
pertence ao motor e ao validador independente, não ao modelo Pydantic.
O campo permanece `StrictStr | None = None`.

---

## 6. Identificadores canónicos

```python
mission_type = "validar_memorial_fiscal"
target_agent = "memorial_validator_agent"

context_schema = "memorial_validator.context"
context_version = "1.0"

output_schema = "memorial_validator.result"
output_version = "1.0"

agent_version = "1.0"

scope = "documento"
entity_type = "relatorio_analise"

authority_level = "leitura"

execution_mode permitido = {"sombra", "dry_run"}
execution_mode bloqueado = "activo"

requested_by ∈ {"user", "system"}
sources == []
budget_policy == BudgetPolicy()
source_request_id presente e não branco
source_event_id ausente
schedule_slot ausente
reference_at opcional
```

---

## 7. Estrutura arquitectural

```text
AgentMission
→ validação do envelope da missão
→ validação da versão do agente
→ bloqueio de modo activo
→ parsing do MemorialValidatorContext
→ coerência missão–contexto
→ motor determinístico puro
→ MemorialValidatorPayload
→ validação independente payload–contexto
→ AgentExecutionResult
→ validate_result_against_mission
→ assert_result_sanitized
```

Modo activo é bloqueado antes de qualquer execução do motor.

O adapter não efectua acesso a BD, ORM, HTTP, filesystem, LLM,
scheduler, registry, executor, reader ou `memorial_service`.

---

## 8. Tipos estritos

```python
from typing import Annotated
from pydantic import AfterValidator, Field, StrictInt, StrictStr


def validar_texto_nao_branco(valor: str) -> str:
    if not valor.strip():
        raise ValueError("texto obrigatório")
    return valor


TextoNaoBranco = Annotated[
    StrictStr,
    AfterValidator(validar_texto_nao_branco),
]

IdPositivo     = Annotated[StrictInt, Field(gt=0)]
IntNaoNegativo = Annotated[StrictInt, Field(ge=0)]
```

`TextoNaoBranco` valida que a string contém pelo menos um carácter não
branco. Não normaliza nem remove espaços do valor retornado.

Aplicado a:

- `relatorio.status`
- `engine_nome`

`source_request_id` é validado pelo adapter com a mesma semântica, mas
não usa `TextoNaoBranco` directamente — segue o padrão de B14.3D.

---

## 9. Contrato do contexto

```python
class MemorialRelatorioSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id:            IdPositivo
    empresa_id:    IdPositivo
    status:        TextoNaoBranco
    total_alertas: IntNaoNegativo


class MemorialEngineSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_nome: TextoNaoBranco


class MemorialReferenciaSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fundamento: StrictStr | None = None


class MemorialValidatorContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    empresa_id:        IdPositivo
    relatorio_id:      IdPositivo

    relatorio:         MemorialRelatorioSnapshot | None = None
    engines:           tuple[MemorialEngineSnapshot, ...]
    referencias_legais: tuple[MemorialReferenciaSnapshot, ...]

    @model_validator(mode="after")
    def validar_coerencia(self) -> Self:
        if self.relatorio is not None:
            if self.relatorio.id != self.relatorio_id:
                raise ValueError("relatorio.id incompatível")
            if self.relatorio.empresa_id != self.empresa_id:
                raise ValueError("relatorio.empresa_id incompatível")
        return self
```

### 9.1 Semântica

```text
relatorio omitido ou None
→ contexto válido → MEMORIAL_RELATORIO_AUSENTE

relatorio presente, mas estruturalmente inválido
→ AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID

engines omitido         → contexto inválido
engines vazio           → contexto válido → MEMORIAL_ENGINES_VAZIOS

referencias_legais omitido → contexto inválido
referencias_legais vazio   → contexto válido → MEMORIAL_REFERENCIAS_VAZIAS
```

### 9.2 Fundamento — regra de incompletude

A avaliação pertence ao motor e ao validador independente:

```text
fundamento is None         → incompleto
fundamento == ""           → incompleto
fundamento.strip() == ""   → incompleto
fundamento tipo não str    → contexto inválido (Pydantic)
```

### 9.3 Campos excluídos

Não pertencem ao contexto v1: `insights`, `alertas`, `codigo` da
referência, resultado integral da engine, conteúdo fiscal bruto,
URLs, fundamentos normativos completos.

---

## 10. Alertas canónicos

```python
MemorialAlertCode = Literal[
    "MEMORIAL_RELATORIO_AUSENTE",
    "MEMORIAL_ENGINES_VAZIOS",
    "MEMORIAL_REFERENCIAS_VAZIAS",
    "MEMORIAL_REFERENCIA_INCOMPLETA",
    "MEMORIAL_STATUS_ANALISE",
    "MEMORIAL_CONTAGEM_ALERTAS",
]

ORDEM_ALERTAS_MEMORIAL: tuple[MemorialAlertCode, ...] = (
    "MEMORIAL_RELATORIO_AUSENTE",
    "MEMORIAL_ENGINES_VAZIOS",
    "MEMORIAL_REFERENCIAS_VAZIAS",
    "MEMORIAL_REFERENCIA_INCOMPLETA",
    "MEMORIAL_STATUS_ANALISE",
    "MEMORIAL_CONTAGEM_ALERTAS",
)

ALERTAS_MEMORIAL_CANONICOS: Mapping[
    MemorialAlertCode,
    tuple[Literal["critico", "alto", "medio"], str],
] = MappingProxyType({
    "MEMORIAL_RELATORIO_AUSENTE": (
        "critico",
        "Relatório não encontrado no contexto do memorial.",
    ),
    "MEMORIAL_ENGINES_VAZIOS": (
        "alto",
        "Nenhum resultado de engine foi encontrado no memorial.",
    ),
    "MEMORIAL_REFERENCIAS_VAZIAS": (
        "alto",
        "A base normativa do memorial está vazia.",
    ),
    "MEMORIAL_REFERENCIA_INCOMPLETA": (
        "medio",
        "Existe referência legal sem fundamento no memorial.",
    ),
    "MEMORIAL_STATUS_ANALISE": (
        "alto",
        "A análise associada ao memorial apresenta estado de erro.",
    ),
    "MEMORIAL_CONTAGEM_ALERTAS": (
        "medio",
        "O relatório associado ao memorial excede o limiar de alertas para revisão.",
    ),
})
```

Nenhuma mensagem expõe: código de referência, contagem de alertas,
valor fiscal, `str(exc)` ou traceback.

---

## 11. Motor determinístico

```python
LIMIAR_ALERTAS_REVISAO: int = 10
```

**Ordem de avaliação — sem early return:**

1. Se `relatorio is None` → `MEMORIAL_RELATORIO_AUSENTE`
2. Se `engines` vazio → `MEMORIAL_ENGINES_VAZIOS`
3. Se `referencias_legais` vazio → `MEMORIAL_REFERENCIAS_VAZIAS`
4. Se existe pelo menos uma referência cujo fundamento seja `None`,
   `""` ou `fundamento.strip() == ""` → um único `MEMORIAL_REFERENCIA_INCOMPLETA`
5. Somente quando `relatorio is not None`:
   se `relatorio.status == "erro"` → `MEMORIAL_STATUS_ANALISE`
6. Somente quando `relatorio is not None`:
   se `relatorio.total_alertas > LIMIAR_ALERTAS_REVISAO` → `MEMORIAL_CONTAGEM_ALERTAS`

Todos os códigos são únicos e seguem `ORDEM_ALERTAS_MEMORIAL`.

**Exemplo com relatorio=None, engines=(), referencias_legais=():**

```text
1. MEMORIAL_RELATORIO_AUSENTE
2. MEMORIAL_ENGINES_VAZIOS
3. MEMORIAL_REFERENCIAS_VAZIAS
```

---

## 12. Payload

```python
class MemorialValidatorAlert(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    codigo:     MemorialAlertCode
    severidade: Literal["critico", "alto", "medio"]
    mensagem:   StrictStr

    @model_validator(mode="after")
    def validar_contrato(self) -> Self:
        severidade_esperada, mensagem_esperada = (
            ALERTAS_MEMORIAL_CANONICOS[self.codigo]
        )
        if self.severidade != severidade_esperada:
            raise ValueError("severidade incompatível")
        if self.mensagem != mensagem_esperada:
            raise ValueError("mensagem incompatível")
        return self


class MemorialValidatorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_type:           Literal["validacao_memorial_fiscal"]
    schema_type:             Literal["MemorialValidatorPayload"]
    versao:                  Literal["1.0"]
    empresa_id:              IdPositivo
    relatorio_id:            IdPositivo
    diagnostico_consistente: StrictBool
    total_alertas:           IntNaoNegativo
    alertas:                 tuple[MemorialValidatorAlert, ...]
    publication_allowed:     Literal[False] = False
```

Invariantes:

```text
total_alertas == len(alertas)
diagnostico_consistente is True  ↔  alertas == ()
diagnostico_consistente is False ↔  len(alertas) > 0
códigos sem duplicação
alertas em ordem canónica
publication_allowed is False
```

---

## 13. Validação independente

```python
validate_memorial_validator_payload_against_context(
    context=context_model,
    payload=payload_model,
)
```

Pode partilhar apenas: tipos contratuais, constantes, tabela canónica,
ordem canónica.

Não pode chamar: construtor principal, motor, parser, helper de
transformação, adapter ou agente legado.

A adulteração de qualquer campo do payload deve ser detectada.

---

## 14. Ordem pré-execução

1. `target_agent`
2. `mission_type`
3. `context_schema`
4. `context_version`
5. `output_schema`
6. `output_version`
7. `scope`
8. tipo e validade de `tenant_id`
9. tipo e validade de `actor_id`
10. `entity_type`
11. tipo e validade de `entity_id`
12. `requested_by`
13. `authority_level`
14. origem
15. `budget_policy`
16. `sources`
17. compatibilidade de `agent_version`
18. bloqueio de `execution_mode="activo"`
19. parsing do contexto
20. coerência `mission.entity_id == context.relatorio_id`

O modo activo não analisa o contexto nem chama o motor.

---

## 15. Erros pré-execução

```python
MemorialValidatorPreExecutionErrorCode = Literal[
    "MISSION_TARGET_MISMATCH",
    "MISSION_TYPE_UNSUPPORTED",
    "CONTEXT_SCHEMA_UNSUPPORTED",
    "CONTEXT_VERSION_UNSUPPORTED",
    "OUTPUT_SCHEMA_UNSUPPORTED",
    "OUTPUT_VERSION_UNSUPPORTED",
    "MISSION_SCOPE_UNSUPPORTED",
    "MISSION_TENANT_REQUIRED",
    "MISSION_TENANT_UNSUPPORTED",
    "MISSION_ACTOR_UNSUPPORTED",
    "MISSION_ENTITY_UNSUPPORTED",
    "MISSION_REQUESTED_BY_UNSUPPORTED",
    "MISSION_AUTHORITY_UNSUPPORTED",
    "MISSION_ORIGIN_UNSUPPORTED",
    "MISSION_BUDGET_UNSUPPORTED",
    "MISSION_SOURCES_UNSUPPORTED",
    "AG_MEMORIAL_VALIDATOR_CONTEXT_INVALID",
]


class MemorialValidatorPreExecutionError(Exception):
    def __init__(
        self,
        code: MemorialValidatorPreExecutionErrorCode,
    ) -> None:
        self.code = code
        super().__init__(code)
```

Regras:

- não transportar objecto Pydantic;
- não transportar erro interno;
- não usar `str(exc)`;
- não preservar traceback público;
- lançada com `raise ... from None`.

Mensagem pública de contexto inválido:
`"Não foi possível validar o contexto do memorial fiscal recebido."`

Erros pré-execução não produzem `AgentExecutionResult`.

---

## 16. Bloqueios operacionais

| Condição | Código do alerta |
|---|---|
| versão incompatível | `AGENT_VERSION_INCOMPATIBLE` |
| `execution_mode="activo"` | `EXECUTION_MODE_NOT_AUTHORIZED` |

Incompatibilidade de versão precede bloqueio de modo.

```text
status = "bloqueado"
payload = {}
error_code = None
error_message = None
alerts = [um alerta operacional canónico]
```

---

## 17. Erro de execução

```text
status = "erro"
payload = {}
alerts = []
error_code = "AG_MEMORIAL_VALIDATOR_EXECUTION_ERROR"
error_message = "Não foi possível concluir a validação do memorial fiscal."
```

---

## 18. Erros pós-construção

```python
class MemorialValidatorResultValidationError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_MISSION_VALIDATION_FAILED"
        super().__init__(self.code)


class MemorialValidatorResultSafetyError(Exception):
    def __init__(self) -> None:
        self.code = "RESULT_SANITIZATION_FAILED"
        super().__init__(self.code)
```

Ambas lançadas `from None`.

---

## 19. Matriz invariável

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

Sucesso:
  status = "sucesso"
  AgentExecutionResult.alerts = []
  payload = MemorialValidatorPayload

Bloqueio:
  status = "bloqueado"
  payload = {}
  error_code = None
  error_message = None
  alerts = [um alerta]

Erro:
  status = "erro"
  payload = {}
  alerts = []
  error_code = "AG_MEMORIAL_VALIDATOR_EXECUTION_ERROR"
  error_message = mensagem pública fixa

Falha validate_result_against_mission:
  → MemorialValidatorResultValidationError
  code = "RESULT_MISSION_VALIDATION_FAILED"
  __cause__ = None, __suppress_context__ = True

Falha assert_result_sanitized:
  → MemorialValidatorResultSafetyError
  code = "RESULT_SANITIZATION_FAILED"
  __cause__ = None, __suppress_context__ = True
```

Os alertas diagnósticos pertencem exclusivamente ao payload.

---

## 20. Testes obrigatórios

### 20.1 Missão

- identificadores divergentes;
- schemas e versões divergentes;
- `tenant_id`, `actor_id`, `entity_id`: None, bool, string, float,
  zero e negativos;
- `actor_id` diferente de `tenant_id` aceite;
- `source_request_id` ausente, vazio, branco e não textual;
- `source_event_id` e `schedule_slot` proibidos;
- `budget_policy` não exacto;
- `sources` não vazio;
- `reference_at=None` aceite;
- versão incompatível antes de modo activo;
- modo activo não chama parser nem motor.

### 20.2 Contexto

- `relatorio` omitido e `None`;
- `relatorio` estruturalmente inválido;
- IDs divergentes entre missão e contexto;
- `total_alertas` negativo;
- `status` vazio e com só espaços;
- `engine_nome` vazio e com só espaços;
- `fundamento` não textual;
- campos extras em qualquer submodelo;
- colecções omitidas;
- colecções vazias;
- contexto não `dict`.

### 20.3 Motor

- `relatorio=None` sem early return;
- `relatorio=None` com `engines=()` e `referencias=()` → três alertas;
- cada alerta isolado;
- todos os alertas simultaneamente;
- limiar exacto: `total_alertas=10` → sem alerta; `total_alertas=11` → alerta;
- múltiplas referências incompletas → um único `MEMORIAL_REFERENCIA_INCOMPLETA`;
- `fundamento=None` → incompleto;
- `fundamento=""` → incompleto;
- `fundamento="   "` → incompleto (divergência §5.3);
- `fundamento=" texto "` → completo (espaços em torno de conteúdo real);
- `relatorio.status == "erro"` → alerta;
- ordem canónica em resultado com múltiplos alertas;
- ausência de duplicados.

### 20.4 Independência

Provar que a validação independente não chama construtor, motor,
parser, helper de transformação ou agente legado.

### 20.5 Segurança

- segredo sentinela ausente do payload serializado;
- segredo sentinela ausente das mensagens;
- ausência de `str(exc)` por análise AST;
- ausência de traceback;
- ausência de dados brutos do contexto nas mensagens;
- sanitização de sucesso, bloqueio e erro.

### 20.6 Integridade

- hash exacto do legado;
- ausência de `run_mission()` no legado;
- adapter não importa legado;
- registry, executor, scheduler, `relatorio_router.py`,
  `memorial_service.py` e `pdf_report_service.py` não referenciam
  o novo adapter;
- nenhum `__init__.py` referencia B14.3E;
- sem BD, ORM, HTTP, filesystem ou LLM;
- adapter assíncrono;
- motor e validador independente síncronos.

---

## 21. Ficheiros ratificados

**Commit documental:**
```text
docs/ADR-013-MIGRACAO-L3-MEMORIAL-VALIDATOR.md
```

**Commit de implementação — exactamente:**
```text
app/agents/contracts/memorial_validator.py
app/agents/engines/memorial_validator.py
app/agents/adapters/memorial_validator.py
tests/test_memorial_validator_mission_adapter.py
```

Nenhum `__init__.py`, reader ou ficheiro adicional.

---

## 22. Alterações locais fora do escopo

Permanecem intocadas e não staged:

```text
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py
```

---

## 23. Critério de conclusão

B14.3E somente fecha quando:

- ADR ratificada e commitada isoladamente;
- implementação contém exactamente quatro ficheiros;
- testes dirigidos verdes;
- suite global com zero falhas;
- contagem exacta registada;
- hash legado preservado;
- integrações existentes inalteradas;
- alterações locais anteriores permanecem fora do stage;
- HEAD = origin/main;
- evidências finais registadas.

---

## 24. Ratificação

| Papel | Nome | Estado |
|---|---|---|
| Fundador e Arquitecto Soberano | Miguel | ✅ APROVADA |
| Auditor e Redactor Arquitectural | GPT | ✅ APROVADA |

**Nenhum código ou teste deve ser produzido antes do Commit 1 documental.**

---

*O conhecimento institucional não permanece na conversa. Permanece
no repositório, nos contratos, nos testes e nas evidências.*