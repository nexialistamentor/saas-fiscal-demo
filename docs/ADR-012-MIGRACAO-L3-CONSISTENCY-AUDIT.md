# ADR-012 — Migração L3 B14.3D: ConsistencyAuditAgent em Sombra

**Status:** RATIFICADA v1.3 — Miguel e GPT
**Data:** 2026-07-17
**Versão:** 1.3 — rectificação soberana L3 anterior ao Commit 2
**Autores:** Claude — redactor inicial; GPT — auditor e redactor final; Miguel — fundador e ratificador
**Bloco:** B14.3D
**Repositório:** `nexialistamentor/saas-fiscal-demo`
**Depende de:** ADR-008 v1.5, ADR-010 v1.4, ADR-011 v1.2
**Baseline confirmado:** `HEAD = origin/main = 0da6f7f99da94277bd4395f747393338bcdcee24`; B14.3C: `81 passed / 0 failed`

---

## 1. Contexto

A fundação contratual soberana B14.0+B14.1 está institucionalizada.

B14.3C fechou o `DataSanitizationAgent` em sombra, validando a entrada
antes dos motores fiscais.

B14.3D é o segundo canário da brigada. O `ConsistencyAuditAgent` actua
depois dos motores, comparando valores declarados num documento fiscal
com valores calculados pelo motor fiscal para esse mesmo documento.

Evidência auditada do legado:

- não usa BD, LLM, HTTP, persistência ou relógio;
- delega integralmente ao `TaxConsistencyEngine`;
- aceita `dados_xml` e `dados_motor` como `dict` livres;
- não distingue campo omitido de `None` explícito;
- permite coerções de `float()` incompatíveis com a fronteira L3;
- inclui valores fiscais brutos nas divergências;
- não possui testes próprios;
- permanece inerte no scheduler genérico porque o contexto necessário
  não é fornecido.

Decisão ratificada:

> O `ConsistencyAuditAgent` será activado exclusivamente por missão L3
> explícita. O adapter não instanciará nem chamará o agente legado. O
> módulo L3 de motor reutilizará directamente o `TaxConsistencyEngine`,
> preservado byte a byte.

---

## 2. Ficheiros preservados

| Ficheiro | SHA256 |
|---|---|
| `app/agents/consistency_audit_agent.py` | `2BC7EEAF8F2B2EFD1B807CA7CEE4D979A2661BA61E950E00F4020C9199B0F052` |
| `app/services/tax_consistency/tax_consistency_engine.py` | `29389DB6FEC85C25A6D28153EA108044B4951B9EA49E979A05466DD88198A774` |

Ambos permanecerão byte a byte inalterados durante B14.3D.

Nenhum método `run_mission()` será adicionado ao agente legado.

O adapter L3 não pode importar directamente:

```python
app.services.tax_consistency.tax_consistency_engine
```

Somente `app/agents/engines/consistency_audit.py` poderá importar esse
serviço.

---

## 3. Problemas comprovados no legado

### 3.1 Contexto livre

O agente legado recebe `dados_xml` e `dados_motor` como dicionários
arbitrários e usa `or {}`. Valores falsy de tipos errados podem ser
convertidos silenciosamente em dicionários vazios.

### 3.2 Omissão indistinguível de `None`

O `TaxConsistencyEngine` considera uma verificação não aplicável quando
qualquer lado do par é `None`. Assim, omissão e `None` explícito produzem
o mesmo comportamento.

B14.3D elimina esta ambiguidade usando `model_fields_set`.

### 3.3 Coerções por `float()`

O serviço protegido executa:

```python
abs(float(valor_xml) - float(valor_motor)) > 0.01
```

Strings numéricas e booleanos podem ser convertidos silenciosamente.
Inteiros de magnitude extrema podem causar `OverflowError`.

A fronteira L3 rejeitará estes casos antes de chamar o serviço.

### 3.4 Exposição de valores fiscais

As divergências legadas contêm os valores de ambos os lados da
comparação. Esses valores permanecerão estritamente internos ao módulo
de motor L3 e nunca serão usados em mensagens, alertas públicos,
`AgentExecutionResult` ou payload.

### 3.5 Semântica numérica preservada

B14.3D preserva exactamente a comparação `float()` e a tolerância
`0.01` do serviço protegido.

A migração para `Decimal` fica registada separadamente:

```text
OBS-NUMERIC-CONSISTENCY-001
Estado: ABERTA / ADIADA
Destino: ADR própria após paridade integral de B14.3D
```

B14.3D não rejeita valores negativos sem evidência normativa, porque
essa rejeição alteraria a semântica do legado.

---

## 4. Decisão arquitectural

```text
AgentMission
→ adapter soberano
→ ConsistencyAuditContext
→ app/agents/engines/consistency_audit.py
    → constrói os dois dicionários mínimos
    → chama TaxConsistencyEngine.verificar_consistencia()
    → valida a resposta legada em fail-closed
    → descarta todos os valores fiscais devolvidos
    → reconstrói alertas canónicos
    → constrói ConsistencyAuditPayload
→ validação independente payload–contexto
→ AgentExecutionResult
→ validate_result_against_mission()
→ assert_result_sanitized()
```

Separação obrigatória:

- contrato: tipos e invariantes;
- motor L3: transformação determinística e chamada ao serviço protegido;
- adapter: fronteira da missão e envelope operacional;
- testes: prova contratual e estrutural;
- sem reader;
- sem BD;
- sem LLM;
- sem HTTP;
- sem filesystem;
- sem persistência;
- sem scheduler, registry ou executor activos.

---

## 5. Identificadores canónicos

```python
contract_version = "1.0"

mission_type = "auditar_consistencia_fiscal"
target_agent = "consistency_audit_agent"

context_schema = "consistency_audit.context"
context_version = "1.0"

output_schema = "consistency_audit.result"
output_version = "1.0"

agent_version = "1.0"

scope = "documento"
entity_type = "documento_fiscal"

authority_level = "leitura"
requested_by ∈ {"user", "system"}

execution_mode permitido = {"sombra", "dry_run"}
execution_mode bloqueado = "activo"

sources = []
budget_policy = BudgetPolicy()
reference_at = opcional
```

---

## 6. Invariantes da missão

### 6.1 Tenant e actor

```python
tenant_id: inteiro positivo, não booleano
actor_id: inteiro positivo, não booleano
actor_id e tenant_id representam identidades distintas; a autorização pertence a fronteira própria
```

### 6.2 Entidade documental

```python
entity_type == "documento_fiscal"
entity_id: inteiro positivo, não booleano
entity_id == context.documento_id
```

`entity_id` individualiza a auditoria por documento e evita colisões
entre documentos diferentes da mesma empresa.

### 6.3 Origem

```python
source_request_id: presente, string e não vazio após strip
source_event_id: ausente
schedule_slot: ausente
```

### 6.4 Limite de autoridade desta fase

B14.3D comprova apenas coerência interna entre os identificadores da
missão, do contexto e do payload.

B14.3D não consulta BD e não comprova:

- existência do documento;
- propriedade do documento;
- autorização do actor sobre o documento;
- relação entre `empresa_id`, `documento_id` e `tenant_id`.

Qualquer prova de propriedade ou autorização exigirá reader e ADR
próprios. Não faz parte deste canário.

A agilidade criptográfica e a preparação pós-quântica serão governadas por ADR transversal própria. Esta ADR não fixa algoritmos criptográficos nem acopla o contrato fiscal a uma tecnologia de assinatura específica.

---

## 7. Contrato do contexto

```python
class ConsistencyAuditContext(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
    )

    empresa_id: StrictInt
    documento_id: StrictInt

    icms_st_xml:   StrictInt | StrictFloat | None = None
    icms_st_motor: StrictInt | StrictFloat | None = None

    mva_xml:   StrictInt | StrictFloat | None = None
    mva_motor: StrictInt | StrictFloat | None = None

    base_st_xml:   StrictInt | StrictFloat | None = None
    base_st_motor: StrictInt | StrictFloat | None = None
```

Invariantes:

```python
empresa_id > 0
documento_id > 0
```

Booleanos, strings, `Decimal`, listas, mappings e outros tipos não são
aceites nos seis campos de comparação.

### 7.1 Pares canónicos

```python
PARES_CANONICOS: tuple[tuple[str, str], ...] = (
    ("icms_st_xml", "icms_st_motor"),
    ("mva_xml", "mva_motor"),
    ("base_st_xml", "base_st_motor"),
)
```

### 7.2 Regra conjunta dos pares

A validação será feita por um único:

```python
@model_validator(mode="after")
```

Para cada par:

| Estado em `model_fields_set` | Resultado |
|---|---|
| ambos omitidos | verificação não aplicável |
| apenas um presente | contexto inválido |
| ambos presentes e qualquer valor é `None` | contexto inválido |
| ambos presentes com números estritos válidos | verificação aplicável |

`None` explícito nunca equivale a omissão.

O contexto exige pelo menos um par comparável completo. Se os três pares forem omitidos, o contexto é inválido e o adapter devolve `AG_CONSISTENCY_AUDIT_CONTEXT_INVALID`, impedindo sucesso sem auditoria efectiva.

A falha do contrato será convertida pelo adapter em:

```text
AG_CONSISTENCY_AUDIT_CONTEXT_INVALID
```

sem reproduzir mensagens internas da validação.

### 7.3 Conversibilidade para `float`

Cada valor presente deve ser validado sem substituir o valor original:

```python
try:
    convertido = float(valor)
except (TypeError, ValueError, OverflowError):
    raise ValueError

if not math.isfinite(convertido):
    raise ValueError
```

Esta regra cobre, inclusive, `float(10**1000)`.

Valores negativos finitos permanecem aceites nesta fase.

---

## 8. Transformação mínima para o serviço protegido

Somente pares aplicáveis entrarão nos dicionários.

Mapeamento exacto:

| Contexto L3 | Dicionário | Chave do serviço |
|---|---|---|
| `icms_st_xml` | `dados_xml` | `valor_st` |
| `icms_st_motor` | `dados_motor` | `icms_st` |
| `mva_xml` | `dados_xml` | `mva_xml` |
| `mva_motor` | `dados_motor` | `mva_utilizada` |
| `base_st_xml` | `dados_xml` | `base_st` |
| `base_st_motor` | `dados_motor` | `base_st_calculada` |

Os dicionários não conterão outras chaves.

O motor L3 chamará exactamente:

```python
TaxConsistencyEngine().verificar_consistencia(
    dados_xml,
    dados_motor,
)
```

O serviço protegido não receberá `AgentMission`, relógio, sessão,
tenant, actor, IDs, objetos ORM ou XML bruto.

---

## 9. Contrato literal da resposta protegida

### 9.1 Estrutura raiz

O resultado deve ser um `Mapping` com exactamente estas chaves:

```python
{"consistente", "divergencias"}
```

Tipos exactos:

```python
type(resultado["consistente"]) is bool
type(resultado["divergencias"]) is list
```

Coerência obrigatória:

```python
resultado["consistente"] is (len(resultado["divergencias"]) == 0)
```

Chaves adicionais ou ausentes bloqueiam a execução.

### 9.2 Estrutura de cada divergência

Cada item deve ser um `Mapping`.

O campo canónico do código legado é exactamente:

```python
"tipo"
```

#### ICMS-ST

```python
{
    "tipo": "ICMS_ST_DIVERGENTE",
    "valor_xml": <valor original de icms_st_xml>,
    "valor_motor": <valor original de icms_st_motor>,
}
```

Conjunto exacto de chaves:

```python
{"tipo", "valor_xml", "valor_motor"}
```

#### MVA

```python
{
    "tipo": "MVA_DIVERGENTE",
    "mva_xml": <valor original de mva_xml>,
    "mva_motor": <valor original de mva_motor>,
}
```

Conjunto exacto de chaves:

```python
{"tipo", "mva_xml", "mva_motor"}
```

#### Base ST

```python
{
    "tipo": "BASE_ST_DIVERGENTE",
    "base_xml": <valor original de base_st_xml>,
    "base_motor": <valor original de base_st_motor>,
}
```

Conjunto exacto de chaves:

```python
{"tipo", "base_xml", "base_motor"}
```

### 9.3 Validação dos valores internos devolvidos

Os valores brutos são aceites apenas para validação interna e devem:

- ser `int` ou `float` estritos;
- não ser booleanos;
- ser finitos após conversão;
- ter o mesmo tipo e o mesmo valor do campo correspondente no contexto;
- pertencer a um par aplicável.

Depois da validação, serão descartados.

### 9.4 Fail-closed

A execução falha perante qualquer uma destas condições:

- resultado raiz não é `Mapping`;
- chaves raiz ausentes ou adicionais;
- `consistente` não é `bool` exacto;
- `divergencias` não é `list` exacta;
- incoerência entre `consistente` e o tamanho da lista;
- item de divergência não é `Mapping`;
- chave `tipo` ausente ou não textual;
- código desconhecido;
- código duplicado;
- código fora da ordem canónica;
- código relativo a par não aplicável;
- conjunto de chaves incompleto ou adicional;
- valor bruto com tipo ou valor divergente do contexto;
- valor bruto não finito;
- qualquer estrutura inesperada.

Nenhuma mensagem ou valor bruto devolvido pelo legado será copiado para
o payload.

---

## 10. Alertas canónicos

```python
ConsistencyAuditAlertCode = Literal[
    "ICMS_ST_DIVERGENTE",
    "MVA_DIVERGENTE",
    "BASE_ST_DIVERGENTE",
]
```

Anotação e implementação correctas da tabela:

```python
from collections.abc import Mapping
from types import MappingProxyType

ALERTAS_CONSISTENCY_CANONICOS: Mapping[
    str,
    tuple[Literal["alto"], str],
] = MappingProxyType({
    "ICMS_ST_DIVERGENTE": (
        "alto",
        "O valor de ICMS-ST declarado no XML diverge do valor "
        "calculado pelo motor fiscal.",
    ),
    "MVA_DIVERGENTE": (
        "alto",
        "A MVA declarada no XML diverge da MVA utilizada "
        "pelo motor fiscal.",
    ),
    "BASE_ST_DIVERGENTE": (
        "alto",
        "A base de cálculo do ICMS-ST declarada no XML diverge "
        "da base calculada pelo motor fiscal.",
    ),
})
```

```python
class ConsistencyAuditAlert(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    codigo: ConsistencyAuditAlertCode
    severidade: Literal["alto"]
    mensagem: str
```

O model validator do alerta exigirá correspondência exacta entre:

- código;
- severidade;
- mensagem;
- tabela canónica.

Ordem canónica:

```python
(
    "ICMS_ST_DIVERGENTE",
    "MVA_DIVERGENTE",
    "BASE_ST_DIVERGENTE",
)
```

Códigos duplicados são proibidos.

Alertas fiscais existirão exclusivamente dentro do payload.
`AgentExecutionResult.alerts` permanecerá vazio no sucesso.

---

## 11. Payload canónico

```python
class ConsistencyAuditPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    analysis_type: Literal["auditoria_consistencia_fiscal"]
    schema_type: Literal["ConsistencyAuditPayload"]
    versao: Literal["1.0"]

    empresa_id: StrictInt
    documento_id: StrictInt

    dados_coerentes: StrictBool
    total_alertas: StrictInt
    alertas: tuple[ConsistencyAuditAlert, ...]

    publication_allowed: Literal[False] = False
```

Invariantes:

```python
empresa_id > 0
documento_id > 0

total_alertas >= 0
total_alertas == len(alertas)

dados_coerentes is True  iff alertas == ()
dados_coerentes is False iff len(alertas) > 0

códigos únicos
ordem canónica
publication_allowed is False
```

O payload não conterá:

- valores XML;
- valores do motor;
- diferenças;
- percentagens;
- dicionários legados;
- mensagens legadas;
- XML bruto.

---

## 12. Motor determinístico L3

Ficheiro:

```text
app/agents/engines/consistency_audit.py
```

Responsabilidades exclusivas:

1. receber `ConsistencyAuditContext`;
2. identificar pares aplicáveis;
3. construir os dois dicionários mínimos;
4. chamar o serviço protegido;
5. validar integralmente a resposta literal;
6. extrair somente códigos canónicos;
7. descartar todos os valores fiscais brutos;
8. construir `ConsistencyAuditAlert`;
9. construir `ConsistencyAuditPayload`.

Função pública principal:

```python
def construir_payload_consistency_audit(
    context: ConsistencyAuditContext,
) -> ConsistencyAuditPayload:
```

O motor L3:

- não recebe missão;
- não usa relógio;
- não importa adapter;
- não usa BD, ORM, HTTP, LLM ou filesystem;
- não chama o agente legado;
- não persiste;
- não publica;
- não propõe nem executa acções.

---

## 13. Validação independente payload–contexto

Função pública:

```python
def validate_consistency_audit_payload_against_context(
    *,
    context: ConsistencyAuditContext,
    payload: ConsistencyAuditPayload,
) -> None:
```

A validação independente:

- não chama `construir_payload_consistency_audit()`;
- não reutiliza o helper principal de transformação dos pares;
- não reutiliza o parser principal da resposta protegida;
- instancia separadamente `TaxConsistencyEngine`;
- reconstrói independentemente os dois dicionários mínimos;
- inspecciona independentemente a estrutura raiz;
- inspecciona independentemente cada divergência;
- deriva independentemente a sequência esperada de códigos;
- reconstrói a estrutura primitiva esperada do payload;
- compara integralmente todos os campos do payload;
- levanta `ValueError` sem dados fiscais perante qualquer divergência.

Pode reutilizar somente:

- contratos tipados;
- constantes imutáveis;
- tabela canónica de alertas;
- serviço protegido por hash.

O uso comum do `TaxConsistencyEngine` é deliberado: B14.3D prova paridade
e encapsulamento do serviço protegido, não reimplementa a sua aritmética.

Falha desta validação durante a execução será convertida em:

```text
AG_CONSISTENCY_AUDIT_EXECUTION_ERROR
```

---

## 14. Erros pré-execução

```python
ConsistencyAuditPreExecutionErrorCode = Literal[
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
    "AG_CONSISTENCY_AUDIT_CONTEXT_INVALID",
]
```

Classes tipadas:

```python
ConsistencyAuditPreExecutionError
ConsistencyAuditResultValidationError
ConsistencyAuditResultSafetyError
```

Os erros tipados não incluirão contexto, valores, `str(exc)`, traceback
ou causa pública.

---

## 15. Ordem da fronteira e execução

Ordem obrigatória:

1. validar identificadores e fronteira da missão;
2. validar `scope`, tenant e actor;
3. validar entidade documental e `entity_id`;
4. validar `requested_by`, autoridade, origem, budget e sources;
5. construir `ConsistencyAuditContext`;
6. validar `mission.entity_id == context.documento_id`;
7. verificar `agent_version_required`;
8. bloquear modo `activo`;
9. executar motor L3 em `sombra` ou `dry_run`;
10. validar payload–contexto independentemente;
11. construir `AgentExecutionResult`;
12. validar resultado contra a missão;
13. sanitizar integralmente o resultado.

`reference_at` é opcional e não cria erro específico neste canário.

---

## 16. Bloqueios e erros operacionais

### 16.1 Versão incompatível

```text
status = "bloqueado"
payload = {}
error_code = None
alert.code = "AGENT_VERSION_INCOMPATIBLE"
```

### 16.2 Modo activo

```text
status = "bloqueado"
payload = {}
error_code = None
alert.code = "EXECUTION_MODE_NOT_AUTHORIZED"
```

A versão é verificada antes do modo.

### 16.3 Erro de execução

```text
status = "erro"
error_code = "AG_CONSISTENCY_AUDIT_EXECUTION_ERROR"
error_message = "Não foi possível concluir a auditoria de consistência fiscal."
payload = {}
alerts = []
retryable = False
```

O erro público nunca reproduzirá:

- `str(exc)`;
- tipo da excepção;
- traceback;
- valores fiscais;
- IDs;
- estruturas internas.

### 16.4 Contexto inválido

Erro tipado pré-execução:

```text
code = "AG_CONSISTENCY_AUDIT_CONTEXT_INVALID"
```

Mensagem institucional associada:

```text
Não foi possível validar o contexto de auditoria fiscal recebido.
```

A mensagem interna de Pydantic não atravessa a fronteira.

---

## 17. Matriz integral do resultado

```text
attempt = 1
agent_id = "consistency_audit_agent"
agent_version = "1.0"

mission_type = mission.mission_type
mission_id = mission.mission_id
correlation_id = mission.correlation_id

scope = mission.scope
tenant_id = mission.tenant_id
mode = mission.execution_mode

started_at = UTC
finished_at = UTC
duration_ms >= 0

evidence = []
actions_proposed = []
actions_executed = []

requires_human_review = True

payload_schema = mission.output_schema
payload_version = mission.output_version

llm_used = False
provider = None
tokens_used = None
cost_estimated = None
cost_actual = None
currency = None

retryable = False
```

No sucesso:

```text
status = "sucesso"
AgentExecutionResult.alerts = []
error_code = None
error_message = None
```

---

## 18. Cenários contratuais obrigatórios

### 18.1 Missão e fronteira

Cobrir todos os códigos pré-execução, incluindo:

- target;
- mission type;
- schemas e versões;
- scope;
- tenant ausente, booleano, zero ou negativo;
- actor booleano, zero, negativo ou divergente do tenant;
- entity type;
- entity ID booleano, zero ou negativo;
- entity ID divergente de `context.documento_id`;
- `requested_by`;
- autoridade;
- origem;
- budget;
- sources;
- `reference_at=None` aceite.

### 18.2 Contexto e pares

Cobrir:

- `empresa_id` e `documento_id` positivos;
- IDs booleanos, strings, floats, zero e negativos rejeitados;
- par completo válido;
- par completo com zero;
- par incompleto;
- `None` explícito em qualquer lado;
- booleano;
- string numérica;
- `Decimal`;
- NaN e infinitos;
- inteiro `10**1000`;
- campo extra;
- nenhum par presente rejeitado;
- valores negativos finitos aceites;
- frozen model;
- distinção por `model_fields_set`.

### 18.3 Tolerância `0.01`

Para cada um dos três pares, usando o outro lado igual a `0.0`:

```python
abaixo = math.nextafter(0.01, 0.0)
limite = 0.01
acima = math.nextafter(0.01, math.inf)
```

Resultados:

```text
abaixo → sem divergência
limite → sem divergência
acima → divergência
```

Cobrir também pelo menos um caso com diferença no sentido inverso para
provar o uso de `abs()`.

### 18.4 Combinações e ordem

Cobrir:

- cada código isolado;
- dois códigos;
- três códigos;
- ordem ICMS-ST → MVA → base ST;
- duplicados rejeitados antes da validação de ordem;
- pares omitidos não geram alertas.

### 18.5 Resposta protegida em fail-closed

Usando patch controlado, cobrir:

- raiz não `Mapping`;
- chaves raiz adicionais ou ausentes;
- `consistente` não booleano;
- `divergencias` não lista;
- coerência booleana inválida;
- item não `Mapping`;
- `tipo` ausente;
- código desconhecido;
- código duplicado;
- ordem errada;
- código de par omitido;
- chaves de item adicionais ou ausentes;
- campo bruto com tipo divergente;
- campo bruto com valor divergente;
- valor bruto não finito.

### 18.6 Payload

Cobrir:

- tipos estritos;
- IDs positivos;
- total não negativo;
- total igual ao tamanho;
- coerência `dados_coerentes`–alertas;
- ordem canónica;
- códigos únicos;
- `publication_allowed=False`;
- adulteração de cada campo;
- validação independente detecta adulteração.

### 18.7 Segurança pública

Provar que:

- payload serializado não contém valores fiscais sentinela;
- mensagens não contêm valores, diferenças ou percentagens;
- erro público não contém segredo, tipo de excepção ou traceback;
- `AgentExecutionResult.alerts` está vazio no sucesso;
- resultado passa por `assert_result_sanitized`.

### 18.8 Integridade estrutural

Provar:

- SHA256 exacto dos dois ficheiros preservados;
- ausência de `run_mission` no legado;
- contrato não importa serviço, adapter, ORM ou infra;
- adapter não importa `TaxConsistencyEngine`;
- somente o motor L3 importa o serviço protegido;
- ausência de BD, HTTP, LLM, filesystem e persistência;
- ausência de reader;
- registry, executor e scheduler não referenciam o adapter;
- adapter é assíncrono;
- motor e validação são síncronos e determinísticos;
- nenhum `__init__.py` é alterado.

---

## 19. Escopo exacto de ficheiros

### Commit 1 — documental

```text
docs/ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT.md
```

Nenhum outro ficheiro entra no Commit 1.

### Commit 2 — implementação

```text
app/agents/contracts/consistency_audit.py
app/agents/engines/consistency_audit.py
app/agents/adapters/consistency_audit.py
tests/test_consistency_audit_mission_adapter.py
```

Nenhum outro ficheiro entra no Commit 2.

Nenhum `__init__.py` será alterado em B14.3D.

Qualquer necessidade de ampliar o escopo exige rectificação prévia da
ADR-012, auditoria do GPT e ratificação de Miguel antes da alteração.

---

## 20. Alterações locais anteriores fora do escopo

As seguintes alterações locais já existiam antes de B14.3D e não podem
ser tocadas, staged ou incluídas nos commits desta ADR:

```text
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py
```

Antes de cada staging será executado `git status --short`.

O staging usará caminhos explícitos.

Antes de cada commit serão executados:

```text
git status --short
git diff --cached --check
git diff --cached --name-only
```

Cada comando será executado e validado separadamente.

---

## 21. Estratégia de commits

### Commit 1

```text
docs: ratificar ADR-012 migracao L3 ConsistencyAuditAgent (B14.3D)
```

### Commit 2

```text
feat: adapter L3 ConsistencyAuditAgent em sombra (B14.3D)
```

Commits atómicos, sem `git add .`, sem staging implícito e sem mistura
com alterações anteriores.

---

## 22. Critério de conclusão

B14.3D somente será fechado quando:

- ADR-012 estiver ratificada e publicada em Commit 1 atómico;
- os quatro ficheiros de implementação estiverem em Commit 2 atómico;
- testes dirigidos B14.3D estiverem verdes;
- suite global terminar com `0 failed`;
- contagem exacta da suite global for registada no fecho;
- hashes dos dois ficheiros protegidos permanecerem exactos;
- registry, executor e scheduler permanecerem inalterados;
- nenhum `__init__.py` tiver sido alterado;
- alterações anteriores fora do escopo permanecerem não staged e
  inalteradas;
- `HEAD == origin/main` após cada push.

A existência de alterações anteriores fora do escopo não impede o
fecho, desde que permaneçam não staged e inalteradas.

---

## 23. Exclusões

Ficam fora de B14.3D:

- migração de `float` para `Decimal`;
- rejeição normativa de valores negativos;
- reader;
- prova de propriedade ou autorização em BD;
- scheduler;
- registry;
- executor;
- `run_all`;
- endpoint público;
- persistência;
- publicação;
- modo activo;
- acções propostas ou executadas;
- novos tipos de divergência;
- alteração do `TaxConsistencyEngine`;
- alteração do agente legado;
- alteração de `__init__.py`.

Observações abertas:

```text
OBS-NUMERIC-CONSISTENCY-001 — ABERTA / ADIADA
OBS-MOTOR-MEI-001 — ABERTA / ADIADA
```

---

## 24. Ratificação

| Papel | Nome | Estado |
|---|---|---|
| Fundador e Arquitecto Soberano | Miguel | ✅ RATIFICADO v1.3 |
| Auditor e Redactor Arquitectural | GPT | ✅ RATIFICADO v1.3 |

Nenhum ficheiro de implementação B14.3D poderá ser incorporado em commit antes:

1. da ratificação explícita de Miguel, cumprida na v1.3;
2. da gravação exacta desta ADR;
3. da validação do ficheiro;
4. do Commit 1 documental;
5. do push e prova `HEAD == origin/main`.

---

*O conhecimento institucional não permanece na conversa. Permanece no
repositório, nos contratos, nos testes e nas evidências.*
