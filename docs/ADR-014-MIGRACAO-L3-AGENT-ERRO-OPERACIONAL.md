# ADR-014 — Migração L3 B14.3F: AgentErroOperacional Determinístico em Sombra

**Status:** RATIFICADA v1.3
**Data:** 2026-07-20
**Versão da ADR:** 1.3
**Versão dos contratos:** 1.0
**Bloco:** B14.3F
**Repositório:** `nexialistamentor/saas-fiscal-demo`
**Depende de:** ADR-008 v1.5, ADR-011 v1.2, ADR-012 v1.3, ADR-013 v1.3
**Baseline confirmado:** `HEAD = origin/main = 2042d5291a303e0abe67fe7f7184b363e1121167`
**Baseline de testes:** `1995 passed / 8 skipped / 0 failed`

---

## 1. Contexto

O `AgentErroOperacional` possui natureza distinta dos canários anteriores.

Não é um validador de contexto fiscal genérico. É um motor de reconhecimento
operacional orientado por `EventoOperacional` tipado.

B14.3F cria um adapter L3:

- determinístico;
- read-only;
- orientado por evento explícito;
- executável somente em `sombra` ou `dry_run`;
- sem autoridade executiva;
- sem autoridade de publicação;
- sem integração activa.

O canário não:

- usa LLM em qualquer modo;
- invoca BudgetGuard;
- invoca LLMRouter;
- instancia provider externo;
- chama `AgentErroOperacional.run()`;
- chama `_tentar_padrao_aprendido`;
- entra no registry;
- entra no scheduler;
- entra no executor;
- participa em `run_all`;
- executa patches;
- escreve em base de dados;
- escreve no filesystem;
- publica diagnósticos;
- abre pull requests;
- altera o agente legado.

O enriquecimento por LLM permanece fora deste bloco e exigirá missão e ADR
próprias em B14.3G.

---

## 2. Legado protegido

**Ficheiro protegido:**

```text
app/agents/agent_erro_operacional.py
```

**SHA-256 canónico:**

```text
EC55FF9B606DAF319B77AF2ECB31AEC1E0B6A3966D69982F2EF316B9ECDF281A
```

Invariantes:

- o ficheiro permanece byte a byte inalterado;
- não recebe `run_mission()`;
- `AgentErroOperacional.run()` nunca é chamado;
- `_tentar_padrao_aprendido()` nunca é chamado;
- somente o motor L3 pode importar o módulo legado;
- o hash é gate de testes e integridade do commit;
- o hash não é recalculado em runtime;
- B14.3F não introduz leitura de ficheiro em runtime.

O hash demonstra integridade do artefacto versionado. Não representa autoridade,
assinatura ou prova criptográfica de autoria.

---

## 3. Dívida arquitectural declarada

### 3.1 Ponte transitória

O motor L3 acede temporariamente à colecção privada `_SENTINELAS` do
módulo legado.

Esta decisão:

- evita reimplementar nove sentinelas;
- preserva o hash do legado;
- mantém paridade determinística;
- não converte `_SENTINELAS` numa API pública geral;
- não autoriza outros módulos a importarem símbolos privados.

A extracção futura de um núcleo determinístico público exige ADR própria,
alteração explícita do hash e provas de paridade antes e depois.

### 3.2 Importação tardia

Somente este ficheiro pode importar o módulo legado:

```text
app/agents/engines/agent_erro_operacional.py
```

O import é obrigatório dentro da função de execução do motor.

É proibido:

```python
# Proibido no topo do módulo.
from app.agents import agent_erro_operacional
```

Ordem obrigatória:

```text
adapter valida envelope
→ adapter bloqueia versão ou modo
→ adapter analisa snapshot
→ adapter sanitiza snapshot
→ adapter valida coerências
→ adapter chama motor
→ motor importa legado tardiamente
→ motor aplica guardas de runtime
→ motor percorre sentinelas
```

O modo `activo` não:

- analisa contexto;
- sanitiza contexto;
- importa o legado;
- inspecciona `_SENTINELAS`;
- chama o motor.

### 3.3 Isolamento LLM

O import tardio do módulo legado pode carregar símbolos de BudgetGuard e
contratos LLM existentes no seu grafo.

B14.3F garante ausência de **invocação**, não ausência absoluta de importação:

- `budget_verificar` não é chamado;
- `BudgetCheckRequest` não é instanciado;
- `completar` não é chamado;
- nenhum provider é chamado;
- `AgentErroOperacional.run()` não é chamado.

O isolamento absoluto do grafo de imports dependerá da futura extracção do
núcleo determinístico.

---

## 4. Sentinelas canónicas

### 4.1 Nomes e ordem

```python
NOMES_SENTINELAS_CANONICOS: tuple[str, ...] = (
    "_sentinela_race_condition_termos",
    "_sentinela_cta_login_contexto_perdido",
    "_sentinela_vercel_env_vazia",
    "_sentinela_cnae_saas_errado",
    "_sentinela_mei_limite_excedido",
    "_sentinela_faturamento_zero",
    "_sentinela_tempo_normativo_ausente",
    "_sentinela_schema_drift_undefined_column",
    "_sentinela_upload_xml_500",
)
```

A ordem é semanticamente relevante. O primeiro reconhecimento termina a
avaliação.

### 4.2 Códigos públicos

```python
MAPA_SENTINELAS_PARA_CODIGOS: Mapping[str, OperationalDiagnosisCode] = (
    MappingProxyType({
        "_sentinela_race_condition_termos":
            "RACE_CONDITION_TERMOS",
        "_sentinela_cta_login_contexto_perdido":
            "CTA_LOGIN_CONTEXTO_PERDIDO",
        "_sentinela_vercel_env_vazia":
            "VERCEL_ENV_VAZIA",
        "_sentinela_cnae_saas_errado":
            "CNAE_SAAS_ERRADO",
        "_sentinela_mei_limite_excedido":
            "MEI_LIMITE_EXCEDIDO",
        "_sentinela_faturamento_zero":
            "FATURAMENTO_ZERO",
        "_sentinela_tempo_normativo_ausente":
            "TEMPO_NORMATIVO_AUSENTE",
        "_sentinela_schema_drift_undefined_column":
            "SCHEMA_DRIFT_UNDEFINED_COLUMN",
        "_sentinela_upload_xml_500":
            "UPLOAD_XML_500",
    })
)
```

Invariante:

```python
set(NOMES_SENTINELAS_CANONICOS) == set(
    MAPA_SENTINELAS_PARA_CODIGOS
)
```

Nome Python de função privada nunca atravessa o payload ou uma mensagem pública.

---

## 5. Guardas de runtime

Antes de percorrer as sentinelas, o motor executa, nesta ordem:

```text
1. import tardio do módulo legado;
2. cópia sentinelas = tuple(_legado._SENTINELAS);
3. quantidade exacta;
4. todos os elementos callable;
5. nomes e ordem exactos;
6. coerência nomes ↔ mapa de códigos;
7. coerência códigos ↔ perfis canónicos;
8. _PADROES_APRENDIDOS exactamente vazio;
9. somente depois, execução das sentinelas.
```

Pseudocódigo obrigatório:

```python
import app.agents.agent_erro_operacional as _legado

sentinelas = tuple(_legado._SENTINELAS)

if len(sentinelas) != len(NOMES_SENTINELAS_CANONICOS):
    raise OperationalLegacyDriftError() from None

if any(not callable(func) for func in sentinelas):
    raise OperationalLegacyDriftError() from None

nomes_reais = tuple(func.__name__ for func in sentinelas)

if nomes_reais != NOMES_SENTINELAS_CANONICOS:
    raise OperationalLegacyDriftError() from None

if set(nomes_reais) != set(MAPA_SENTINELAS_PARA_CODIGOS):
    raise OperationalLegacyDriftError() from None

codigos = tuple(
    MAPA_SENTINELAS_PARA_CODIGOS[nome]
    for nome in nomes_reais
)

if set(codigos) != set(PERFIS_DIAGNOSTICOS_CANONICOS):
    raise OperationalLegacyDriftError() from None

if _legado._PADROES_APRENDIDOS != []:
    raise OperationalLegacyDriftError() from None
```

A cópia para `tuple` impede que alteração concorrente da lista mude a
iteração em curso.

Divergência de hash não é verificada em runtime. É detectada pelos testes e
pelo gate de integridade do commit.

---

## 6. Padrões aprendidos bloqueados

`_PADROES_APRENDIDOS` é uma lista global mutável sem governação contratual.

Em B14.3F v1.0:

- deve permanecer vazia;
- é verificada em runtime;
- é verificada em teste;
- `_tentar_padrao_aprendido()` não é chamado;
- `camada_reconhecimento="padrao_local"` não existe no contrato v1.

Uma futura camada de padrões locais exige contrato próprio contendo, no mínimo:

```text
pattern_id
pattern_version
approved_by
approved_at
conditions
canonical_result
```

---

## 7. Tipos canónicos estritos

```python
from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    Field,
    StrictInt,
    StrictStr,
)
```

### 7.1 Textos estruturais

```python
def validar_texto_nao_branco(valor: str) -> str:
    if not valor.strip():
        raise ValueError("texto obrigatório")
    return valor
```

```python
TipoEvento = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_tipo_evento),
]

OrigemOperacional = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_origem_operacional),
]

MensagemOperacional = Annotated[
    StrictStr,
    Field(min_length=1, max_length=2000),
    AfterValidator(validar_texto_nao_branco),
]
```

`tipo` aceita somente:

```text
A-Z a-z 0-9 _ . : -
```

Expressão equivalente:

```text
^[A-Za-z0-9_.:-]+$
```

`origem` aceita somente:

```text
A-Z a-z 0-9 _ . : -
```

Expressão equivalente:

```text
^[A-Za-z0-9_.:-]+$
```

`origem` não aceita:

- slash;
- backslash;
- drive Windows;
- path relativo;
- hostname;
- endereço IP;
- query string;
- caracteres de controlo.

### 7.2 UTC

```python
def validar_utc(valor: datetime) -> datetime:
    if valor.utcoffset() != timedelta(0):
        raise ValueError("deve estar em UTC")
    return valor
```

```python
AwareDatetimeUTC = Annotated[
    AwareDatetime,
    AfterValidator(validar_utc),
]
```

### 7.3 HTTP

```python
StatusHttp = Annotated[
    StrictInt,
    Field(ge=100, le=599),
]
```

### 7.4 Tenant

```python
IdPositivo = Annotated[
    StrictInt,
    Field(gt=0),
]
```

Valores booleanos, string, float, zero e negativos são inválidos.

### 7.5 Endpoint

```python
EndpointTemplate = Annotated[
    StrictStr,
    Field(min_length=1, max_length=200),
    AfterValidator(validar_endpoint_template),
]
```

O endpoint:

- começa com `/`;
- é relativo;
- não contém `?`;
- não contém `#`;
- não contém `://`;
- não contém `\`;
- não contém `%`;
- não contém `..`;
- não contém CR, LF, NUL ou caracteres de controlo;
- não contém hostname;
- não contém query string;
- não contém fragmento;
- não contém credencial.

Caracteres permitidos após a slash inicial:

```text
A-Z a-z 0-9 / _ - . : { }
```

---

## 8. Indicadores tipados de schema drift

### 8.1 Enumeração

```python
SchemaDriftIndicator = Literal[
    "UNDEFINED_COLUMN",
    "COLUMN_DOES_NOT_EXIST",
    "RELATORIOS_ANALISE_FINGERPRINT_MISSING",
]
```

Ordem canónica:

```python
ORDEM_SCHEMA_DRIFT_INDICADORES: tuple[
    SchemaDriftIndicator, ...
] = (
    "UNDEFINED_COLUMN",
    "COLUMN_DOES_NOT_EXIST",
    "RELATORIOS_ANALISE_FINGERPRINT_MISSING",
)
```

`contexto_indicadores`:

- possui no máximo três elementos;
- não admite duplicados;
- segue exactamente a ordem canónica;
- não transporta texto SQL livre;
- não transporta tabela ou coluna arbitrária;
- não transporta traceback.

### 8.2 Representação mínima para o legado

```python
SCHEMA_DRIFT_REPRESENTACAO_LEGADA: Mapping[
    SchemaDriftIndicator,
    tuple[str, ...],
] = MappingProxyType({
    "UNDEFINED_COLUMN": (
        "undefinedcolumn",
    ),
    "COLUMN_DOES_NOT_EXIST": (
        "column tabela.coluna does not exist",
    ),
    "RELATORIOS_ANALISE_FINGERPRINT_MISSING": (
        "relatorios_analise.fingerprint",
    ),
})
```

As colecções internas são tuples imutáveis.

O motor reconstrói apenas:

```python
contexto_legado = {
    "indicadores": tuple(
        termo
        for indicador in context.contexto_indicadores
        for termo in SCHEMA_DRIFT_REPRESENTACAO_LEGADA[indicador]
    ),
}
```

Nenhum contexto bruto é reconstruído.

Paridade obrigatória:

```text
evento seguro reconhecido pelo legado
→ indicador tipado equivalente
→ representação mínima
→ mesma sentinela
→ mesma classificação
→ mesmo risco
```

---

## 9. Snapshots tipados

### 9.1 Snapshot global

```python
class OperationalGlobalEventSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4
    occurred_at: AwareDatetimeUTC

    scope: Literal["global"]
    tenant_id: None = None

    tipo: TipoEvento
    origem: OrigemOperacional
    mensagem: MensagemOperacional
    endpoint: EndpointTemplate | None = None
    status_http: StatusHttp | None = None

    contexto_indicadores: tuple[
        SchemaDriftIndicator, ...
    ] = ()
```

### 9.2 Snapshot de tenant

```python
class OperationalTenantEventSnapshot(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    event_id: UUID4
    occurred_at: AwareDatetimeUTC

    scope: Literal["tenant"]
    tenant_id: IdPositivo

    tipo: TipoEvento
    origem: OrigemOperacional
    mensagem: MensagemOperacional
    endpoint: EndpointTemplate | None = None
    status_http: StatusHttp | None = None

    contexto_indicadores: tuple[
        SchemaDriftIndicator, ...
    ] = ()
```

### 9.3 União discriminada

```python
OperationalEventSnapshot = Annotated[
    OperationalGlobalEventSnapshot
    | OperationalTenantEventSnapshot,
    Field(discriminator="scope"),
]
```

### 9.4 Campos excluídos

Não pertencem ao snapshot v1:

```text
ficheiro_provavel
ambiente
commit_sha
contexto: dict
contexto_texto: str
headers
cookies
Authorization
query string
body HTTP
XML fiscal
traceback
SQL bruto
variáveis de ambiente
credenciais
```

---

## 10. Sanitização soberana

O adapter:

1. analisa o snapshot;
2. serializa o modelo validado;
3. chama obrigatoriamente `assert_context_sanitized`;
4. aplica as validações específicas do contrato;
5. somente depois valida coerências e chama o motor.

```python
assert_context_sanitized(
    context_model.model_dump(mode="json")
)
```

A sanitização rejeita, no mínimo:

- JWT;
- token;
- API key;
- senha;
- cookie;
- CPF;
- CNPJ;
- email;
- XML;
- traceback;
- endereço IP;
- credencial;
- Authorization;
- path interno;
- valor, atribuição ou segredo de variável de ambiente;
- query string;
- conteúdo acima dos limites contratuais.

Excepção nominal estrita para preservar a paridade determinística:

- a menção nominal a `VITE_API_URL` é permitida;
- a expressão descritiva de que `VITE_API_URL` não está definida é permitida;
- qualquer atribuição, valor, URL, token ou segredo associado é rejeitado;
- qualquer conteúdo após `VITE_API_URL=` é rejeitado;
- a excepção não autoriza o transporte de valores de ambiente.

Exemplos:

```text
VITE_API_URL não definida no Vercel       → permitido
variável de ambiente VITE_API_URL ausente → permitido
VITE_API_URL=https://exemplo              → rejeitado
VITE_API_URL=segredo                      → rejeitado
API_KEY=segredo                           → rejeitado
```

O adapter apenas rejeita.

Não mascara, substitui, trunca ou reescreve `mensagem`, porque uma transformação
poderia alterar a semântica das sentinelas.

Falha:

```text
AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID
```

Mensagem pública:

```text
Não foi possível validar o contexto do evento operacional recebido.
```

Nenhum valor rejeitado atravessa a excepção pública.

---

## 11. Conversão para EventoOperacional legado

Depois da validação e sanitização, o motor cria uma representação mínima:

```python
evento_legado = EventoOperacional(
    tipo=context.tipo,
    origem=context.origem,
    mensagem=context.mensagem,
    endpoint=context.endpoint,
    status_http=context.status_http,
    contexto=contexto_legado,
)
```

Campos excluídos permanecem ausentes ou recebem o default do contrato legado.

O motor não adiciona:

```text
ambiente
commit_sha
ficheiro_provavel
contexto livre
```

---

## 12. Códigos canónicos

### 12.1 Diagnósticos

```python
OperationalDiagnosisCode = Literal[
    "RACE_CONDITION_TERMOS",
    "CTA_LOGIN_CONTEXTO_PERDIDO",
    "VERCEL_ENV_VAZIA",
    "CNAE_SAAS_ERRADO",
    "MEI_LIMITE_EXCEDIDO",
    "FATURAMENTO_ZERO",
    "TEMPO_NORMATIVO_AUSENTE",
    "SCHEMA_DRIFT_UNDEFINED_COLUMN",
    "UPLOAD_XML_500",
]
```

### 12.2 Risco

```python
RiscoPatchCodigo = Literal[
    "baixo",
    "medio",
    "alto",
]
```

### 12.3 Informação em falta

```python
OperationalInfoEmFaltaCodigo = Literal[
    "DATABASE_COLUMNS_STATE_REQUIRED",
    "ALEMBIC_VERSION_REQUIRED",
    "RAILWAY_STACK_TRACE_REQUIRED",
    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
    "LER_XML_UNICO_SOURCE_REQUIRED",
    "SMOKE_XML_REQUIRED",
]
```

Ordem canónica:

```python
ORDEM_INFO_EM_FALTA: tuple[
    OperationalInfoEmFaltaCodigo, ...
] = (
    "DATABASE_COLUMNS_STATE_REQUIRED",
    "ALEMBIC_VERSION_REQUIRED",
    "RAILWAY_STACK_TRACE_REQUIRED",
    "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
    "LER_XML_UNICO_SOURCE_REQUIRED",
    "SMOKE_XML_REQUIRED",
)
```

Códigos não comprovados pelo legado não pertencem à versão 1.

---

## 13. Perfis canónicos profundamente imutáveis

```python
class OperationalDiagnosisProfile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    classificacao: Literal["P0", "P1", "P2"]
    risco_patch: RiscoPatchCodigo

    tem_causa_provavel: Literal[True]
    tem_evidencias: Literal[True]
    tem_teste_recomendado: Literal[True]
    tem_patch_sugerido: Literal[True]

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]
```

```python
PERFIS_DIAGNOSTICOS_CANONICOS: Mapping[
    OperationalDiagnosisCode,
    OperationalDiagnosisProfile,
] = MappingProxyType({
    "RACE_CONDITION_TERMOS":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="baixo",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "CTA_LOGIN_CONTEXTO_PERDIDO":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="baixo",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "VERCEL_ENV_VAZIA":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="baixo",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "CNAE_SAAS_ERRADO":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="medio",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "MEI_LIMITE_EXCEDIDO":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="medio",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "FATURAMENTO_ZERO":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="baixo",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "TEMPO_NORMATIVO_AUSENTE":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="medio",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(),
        ),

    "SCHEMA_DRIFT_UNDEFINED_COLUMN":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="medio",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(
                "DATABASE_COLUMNS_STATE_REQUIRED",
                "ALEMBIC_VERSION_REQUIRED",
            ),
        ),

    "UPLOAD_XML_500":
        OperationalDiagnosisProfile(
            classificacao="P0",
            risco_patch="baixo",
            tem_causa_provavel=True,
            tem_evidencias=True,
            tem_teste_recomendado=True,
            tem_patch_sugerido=True,
            informacao_em_falta=(
                "RAILWAY_STACK_TRACE_REQUIRED",
                "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",
                "LER_XML_UNICO_SOURCE_REQUIRED",
                "SMOKE_XML_REQUIRED",
            ),
        ),
})
```

Os valores internos são modelos congelados e as colecções são tuples.

---

## 14. Mapeamento de texto legado para códigos

Nenhum texto de `informacao_em_falta` atravessa o payload.

O motor aplica regras fechadas.

### 14.1 Regras exactas

```python
INFO_LEGADO_EXACTA: Mapping[
    str,
    OperationalInfoEmFaltaCodigo,
] = MappingProxyType({
    "valor actual de alembic_version em producao":
        "ALEMBIC_VERSION_REQUIRED",

    "stack trace Railway":
        "RAILWAY_STACK_TRACE_REQUIRED",

    "corpo de executar_analise_xml":
        "EXECUTAR_ANALISE_XML_SOURCE_REQUIRED",

    "corpo de ler_xml_unico":
        "LER_XML_UNICO_SOURCE_REQUIRED",

    "XML completo usado no smoke":
        "SMOKE_XML_REQUIRED",
})
```

### 14.2 Regra estrutural de schema drift

A primeira informação do schema drift deve corresponder integralmente a:

```text
^colunas reais de ([A-Za-z_][A-Za-z0-9_]*|tabela afectada) em producao$
```

Resultado:

```text
DATABASE_COLUMNS_STATE_REQUIRED
```

### 14.3 Invariantes do mapeamento

Cada texto legado:

- deve corresponder a exactamente uma regra;
- não é normalizado;
- não é truncado;
- não é publicado;
- não pode produzir dois códigos;
- não pode ficar sem correspondência.

Falha em qualquer regra:

```text
AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT
```

A ordem dos códigos produzidos deve ser exactamente a ordem do perfil canónico.

Textos duplicados, códigos duplicados ou ordem divergente representam drift.

---

## 15. Projecção interna sanitizada

```python
class OperationalDiagnosisInternal(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    reconhecido: StrictBool

    camada_reconhecimento: Literal[
        "sentinela",
        "nao_reconhecido",
    ]

    diagnostico_codigo: OperationalDiagnosisCode | None
    classificacao: Literal["P0", "P1", "P2"] | None
    risco_patch: RiscoPatchCodigo | None

    tem_causa_provavel: StrictBool
    tem_evidencias: StrictBool
    tem_teste_recomendado: StrictBool
    tem_patch_sugerido: StrictBool

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]
```

Fluxo:

```text
AgentOutputSchema legado
→ validação estrutural
→ detecção da sentinela que respondeu
→ código canónico
→ mapeamento de informação em falta
→ confronto com perfil canónico
→ OperationalDiagnosisInternal
→ descarte do AgentOutputSchema
→ payload público
```

O objecto legado e os seus textos não saem do motor.

---

## 16. Confronto com o perfil

Para diagnóstico reconhecido, o motor verifica:

```text
classificação exacta;
risco exacto;
presença não vazia de causa provável;
presença não vazia de evidências;
presença de teste recomendado;
presença de patch sugerido;
informação em falta convertida;
ordem canónica;
ausência de duplicados.
```

A presença é avaliada sem transportar os textos:

```python
tem_causa_provavel = bool(resultado.causa_provavel.strip())

tem_evidencias = bool(resultado.evidencias) and all(
    isinstance(item, str) and bool(item.strip())
    for item in resultado.evidencias
)

tem_teste_recomendado = (
    resultado.teste_recomendado is not None
    and bool(resultado.teste_recomendado.strip())
)

tem_patch_sugerido = (
    resultado.patch_sugerido_texto is not None
    and bool(resultado.patch_sugerido_texto.strip())
)
```

O conjunto resultante deve corresponder integralmente ao
`OperationalDiagnosisProfile`.

Divergência:

```text
AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT
```

Valor inesperado em `risco_patch` não é publicado nem convertido para
`nao_informado`. Representa drift.

`nao_informado` não pertence ao contrato v1.

Esse valor somente poderá ser introduzido por futura revisão contratual,
acompanhada de sentinela ratificada, perfil canónico e testes próprios.

---

## 17. Evento não reconhecido

Se nenhuma sentinela responder:

```python
OperationalDiagnosisInternal(
    reconhecido=False,
    camada_reconhecimento="nao_reconhecido",
    diagnostico_codigo=None,
    classificacao=None,
    risco_patch=None,
    tem_causa_provavel=False,
    tem_evidencias=False,
    tem_teste_recomendado=False,
    tem_patch_sugerido=False,
    informacao_em_falta=(),
)
```

Resultado:

```text
status="sucesso"
requires_human_review=True
publication_allowed=False
automation_allowed=False
```

Nenhum `P2` artificial é produzido.

Evento não reconhecido não é erro operacional do adapter.

---

## 18. Payload público

```python
class OperationalDiagnosisPayload(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    analysis_type: Literal[
        "diagnostico_evento_operacional"
    ] = "diagnostico_evento_operacional"

    schema_type: Literal[
        "OperationalDiagnosisPayload"
    ] = "OperationalDiagnosisPayload"

    versao: Literal["1.0"] = "1.0"

    event_id: UUID4

    reconhecido: StrictBool

    camada_reconhecimento: Literal[
        "sentinela",
        "nao_reconhecido",
    ]

    diagnostico_codigo: OperationalDiagnosisCode | None
    classificacao: Literal["P0", "P1", "P2"] | None
    risco_patch: RiscoPatchCodigo | None

    tem_causa_provavel: StrictBool
    tem_evidencias: StrictBool
    tem_teste_recomendado: StrictBool
    tem_patch_sugerido: StrictBool

    informacao_em_falta: tuple[
        OperationalInfoEmFaltaCodigo, ...
    ]

    publication_allowed: Literal[False] = False
    automation_allowed: Literal[False] = False
    requires_human_review: Literal[True] = True
```

### 18.1 Reconhecido

```text
reconhecido=True
diagnostico_codigo não None
classificacao não None
risco_patch não None
camada_reconhecimento="sentinela"
campos tem_* iguais ao perfil
informacao_em_falta igual ao perfil
```

### 18.2 Não reconhecido

```text
reconhecido=False
diagnostico_codigo=None
classificacao=None
risco_patch=None
camada_reconhecimento="nao_reconhecido"
tem_causa_provavel=False
tem_evidencias=False
tem_teste_recomendado=False
tem_patch_sugerido=False
informacao_em_falta=()
```

### 18.3 Universais

```text
payload.event_id == context.event_id
informacao_em_falta sem duplicados
informacao_em_falta em ordem canónica
publication_allowed=False
automation_allowed=False
requires_human_review=True
```

O payload não contém:

- causa provável;
- evidências;
- ficheiros prováveis;
- teste textual;
- patch textual;
- tabela;
- coluna;
- endpoint completo;
- mensagem original;
- contexto;
- traceback;
- SQL;
- segredo.

---

## 19. Identificadores da missão

```python
mission_type = "diagnosticar_evento_operacional"
target_agent = "agent_erro_operacional"

context_schema = "agent_erro_operacional.context"
context_version = "1.0"

output_schema = "agent_erro_operacional.result"
output_version = "1.0"

agent_version = "1.0"
```

Valores exactos:

```text
scope ∈ {"global", "tenant"}
authority_level="leitura"
requested_by="system"
actor_id=None

entity_type=None
entity_id=None

parent_mission_id=None
deadline=None
idempotency_reference_at=None

ratification_id=None
authorized_by=None
authorization_role=None

priority="alta"

source_event_id obrigatório e UUID4
source_request_id=None
schedule_slot=None

reference_at obrigatório
budget_policy=BudgetPolicy()
sources=[]
```

`agent_version_required`:

```text
None  → compatível
"1.0" → compatível
outro → AGENT_VERSION_INCOMPATIBLE
```

`execution_mode`:

```text
"sombra"  → permitido
"dry_run" → permitido
"activo"  → bloqueado
```

---

## 20. Coerências missão–snapshot

```text
mission.source_event_id == context.event_id
mission.reference_at == context.occurred_at
mission.scope == context.scope
mission.created_at >= context.occurred_at
```

Global:

```text
mission.scope="global"
mission.tenant_id=None
context.scope="global"
context.tenant_id=None
```

Tenant:

```text
mission.scope="tenant"
type(mission.tenant_id) is int
mission.tenant_id > 0
context.scope="tenant"
mission.tenant_id == context.tenant_id
```

Temporalidade:

```text
mission.created_at UTC
mission.reference_at UTC
context.occurred_at UTC
```

Não existe tolerância silenciosa de relógio na versão 1.

Violação de qualquer coerência missão–snapshot:

```text
AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID
```

---

## 21. Ordem pré-execução

Ordem obrigatória:

```text
1. target_agent;
2. mission_type;
3. context_schema;
4. context_version;
5. output_schema;
6. output_version;
7. scope;
8. tenant_id conforme scope;
9. actor_id;
10. entity_type e entity_id;
11. requested_by;
12. authority_level;
13. origem exclusiva;
14. source_event_id obrigatório;
15. source_request_id ausente;
16. schedule_slot ausente;
17. budget_policy exacta;
18. sources vazias;
19. envelope adicional exacto;
20. priority exacta;
21. reference_at presente e UTC;
22. created_at UTC;
23. compatibilidade de agent_version_required;
24. bloqueio de execution_mode="activo";
25. parsing do snapshot;
26. sanitização soberana;
27. coerências missão–snapshot;
28. chamada do motor;
29. import tardio;
30. guardas de runtime;
31. sentinelas determinísticas.
```

Envelope adicional exacto:

```text
parent_mission_id=None
deadline=None
idempotency_reference_at=None
ratification_id=None
authorized_by=None
authorization_role=None
```

Versão é verificada antes de modo.

Versão e modo são verificados antes do parsing do contexto.

---

## 22. Erros pré-execução

```python
AgentErroDiagnosisPreExecutionErrorCode = Literal[
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
    "MISSION_ENVELOPE_UNSUPPORTED",
    "MISSION_PRIORITY_UNSUPPORTED",
    "MISSION_REFERENCE_AT_REQUIRED",
    "MISSION_TEMPORALITY_UNSUPPORTED",
    "AG_OPERATIONAL_DIAGNOSIS_CONTEXT_INVALID",
]
```

Contrato:

```python
class AgentErroDiagnosisPreExecutionError(Exception):
    code: AgentErroDiagnosisPreExecutionErrorCode
    public_message: str
```

Regras:

- não produz `AgentExecutionResult`;
- não transporta objecto Pydantic;
- não transporta valor rejeitado;
- não transporta erro interno;
- não usa `str(exc)`;
- não preserva traceback público;
- é lançada com `raise ... from None`.

Mensagem estrutural genérica:

```text
A missão de diagnóstico operacional recebida não é compatível com este agente.
```

Mensagem de contexto inválido:

```text
Não foi possível validar o contexto do evento operacional recebido.
```

---

## 23. Bloqueios operacionais

### 23.1 Versão

```text
AGENT_VERSION_INCOMPATIBLE
```

Alerta exacto:

```text
alerts=("AGENT_VERSION_INCOMPATIBLE",)
```

Mensagem:

```text
A versão requerida pela missão não é compatível com o agente de diagnóstico operacional.
```

### 23.2 Modo

```text
EXECUTION_MODE_NOT_AUTHORIZED
```

Alerta exacto:

```text
alerts=("EXECUTION_MODE_NOT_AUTHORIZED",)
```

Mensagem:

```text
O modo de execução solicitado não está autorizado para o agente de diagnóstico operacional.
```

Formato:

```text
status="bloqueado"
payload={}
error_code=None
error_message=None
alerts=("AGENT_VERSION_INCOMPATIBLE",) ou alerts=("EXECUTION_MODE_NOT_AUTHORIZED",), conforme o bloqueio
requires_human_review=True
retryable=False
```

A incompatibilidade de versão precede o bloqueio de modo.

---

## 24. Erros de execução

### 24.1 Drift

Condições:

- quantidade divergente;
- elemento não callable;
- nome divergente;
- ordem divergente;
- mapa divergente;
- perfil ausente;
- perfil divergente;
- padrões locais não vazios;
- output legado estruturalmente inválido;
- classificação divergente;
- risco divergente;
- flags divergentes;
- informação em falta desconhecida;
- informação duplicada;
- informação ambígua;
- ordem divergente.

Código:

```text
AG_OPERATIONAL_DIAGNOSIS_LEGACY_DRIFT
```

Mensagem:

```text
O motor de diagnóstico detectou uma divergência no legado protegido.
```

### 24.2 Erro inesperado

Código:

```text
AG_OPERATIONAL_DIAGNOSIS_EXECUTION_ERROR
```

Mensagem:

```text
Não foi possível concluir o diagnóstico do evento operacional.
```

Formato comum:

```text
status="erro"
payload={}
alerts=[]
requires_human_review=True
retryable=False
error_code definido
error_message pública fixa
```

Nenhuma mensagem contém:

- `str(exc)`;
- traceback;
- função privada;
- texto legado;
- valor rejeitado;
- SQL;
- path;
- segredo.

---

## 25. Validação independente

Assinatura:

```python
validate_operational_diagnosis_payload(
    context=context_model,
    internal=internal_projection,
    payload=payload_model,
)
```

O validador não chama:

- motor;
- sentinelas;
- projector principal;
- construtor principal do payload;
- agente legado;
- função privada do legado.

### 25.1 Primeira reconstrução

Para diagnóstico reconhecido:

```text
internal.diagnostico_codigo
→ PERFIS_DIAGNOSTICOS_CANONICOS
→ reconstrução independente de classificação
→ reconstrução independente de risco
→ reconstrução independente dos flags
→ reconstrução independente da informação em falta
→ comparação integral com internal
```

Para não reconhecido:

```text
internal.reconhecido=False
→ reconstrução fixa de todos os campos None/False/()
→ comparação integral com internal
```

### 25.2 Segunda reconstrução

```text
internal já validado
+ context.event_id
→ reconstrução independente do payload completo
→ comparação integral com payload
```

Adulterar `internal` e `payload` de forma coerente não é suficiente para passar,
porque `internal` é primeiro reconstruído a partir do perfil canónico.

---

## 26. Validação posterior universal

Todo resultado efectivamente devolvido — sucesso, bloqueio ou erro — passa por:

```python
validate_result_against_mission(
    mission=mission,
    result=result,
)

assert_result_sanitized(result)
```

Falhas:

```python
class AgentErroDiagnosisResultValidationError(Exception):
    code = "RESULT_MISSION_VALIDATION_FAILED"


class AgentErroDiagnosisResultSafetyError(Exception):
    code = "RESULT_SANITIZATION_FAILED"
```

Ambas:

- são lançadas `from None`;
- não transportam o resultado rejeitado;
- não usam `str(exc)`;
- não produzem novo resultado de fallback.

---

## 27. Matriz universal do resultado

Em todos os resultados:

```text
attempt=1
retryable=False
requires_human_review=True

llm_used=False
provider=None
tokens_used=None
cost_estimated=None
cost_actual=None
currency=None

evidence=[]
actions_proposed=[]
actions_executed=[]

payload_schema="agent_erro_operacional.result"
payload_version="1.0"
```

### 27.1 Sucesso

```text
status="sucesso"
alerts=[]
error_code=None
error_message=None
payload=OperationalDiagnosisPayload
AgentExecutionResult.requires_human_review
    == payload.requires_human_review
```

### 27.2 Bloqueio

```text
status="bloqueado"
payload={}
alerts=("AGENT_VERSION_INCOMPATIBLE",) ou alerts=("EXECUTION_MODE_NOT_AUTHORIZED",), conforme o bloqueio
error_code=None
error_message=None
```

### 27.3 Erro

```text
status="erro"
payload={}
alerts=[]
error_code definido
error_message pública fixa
```

Diagnósticos fiscais ou operacionais nominais pertencem ao payload, não a
`AgentExecutionResult.alerts`.

---

## 28. Ficheiros de implementação

### Commit documental

Exactamente:

```text
docs/ADR-014-MIGRACAO-L3-AGENT-ERRO-OPERACIONAL.md
```

### Commit de implementação

Exactamente:

```text
app/agents/contracts/agent_erro_operacional.py
app/agents/engines/agent_erro_operacional.py
app/agents/adapters/agent_erro_operacional.py
tests/test_agent_erro_operacional_mission_adapter.py
```

Não criar ou alterar:

```text
app/agents/__init__.py
app/agents/contracts/__init__.py
app/agents/engines/__init__.py
app/agents/adapters/__init__.py
reader
projector activo
registry
scheduler
executor
router
endpoint
serviço de persistência
migração
```

---

## 29. Testes obrigatórios

### 29.1 Legado

- SHA-256 exacto;
- ficheiro byte a byte preservado;
- nove sentinelas;
- nomes exactos;
- ordem exacta;
- todos callable;
- mapa cobre todos os nomes;
- perfis cobrem todos os códigos;
- `_PADROES_APRENDIDOS == []`;
- `AgentErroOperacional.run()` nunca chamado;
- `_tentar_padrao_aprendido()` nunca chamado;
- BudgetGuard nunca chamado;
- `BudgetCheckRequest` nunca instanciado;
- LLMRouter nunca chamado;
- provider nunca chamado.

### 29.2 Import tardio

- engine não importa legado no topo;
- importar o adapter não importa o legado;
- importar o engine não importa o legado;
- missão inválida não importa o legado;
- versão incompatível não importa o legado;
- modo activo não importa o legado;
- contexto inválido não importa o legado;
- somente execução válida chega ao import tardio.

### 29.3 Missão

Cobrir individualmente:

- target divergente;
- mission type divergente;
- schemas divergentes;
- versões divergentes;
- scope inválido;
- tenant ausente;
- tenant indevido;
- tenant bool;
- tenant string;
- tenant float;
- tenant zero;
- tenant negativo;
- actor não None;
- entity type não None;
- entity id não None;
- requested_by divergente;
- autoridade divergente;
- source_event_id ausente;
- source_request_id presente;
- schedule_slot presente;
- mais de uma origem;
- budget diferente;
- sources não vazias;
- parent mission presente;
- deadline presente;
- idempotency reference presente;
- ratification presente;
- authorized_by presente;
- authorization_role presente;
- priority diferente de alta;
- reference_at ausente;
- created_at não UTC;
- reference_at não UTC;
- agent version None;
- agent version 1.0;
- agent version incompatível;
- versão antes de modo;
- modo activo bloqueado antes do contexto.

### 29.4 Snapshot

- união discriminada;
- campos extras;
- event_id não UUID4;
- occurred_at sem timezone;
- occurred_at não UTC;
- global com tenant;
- tenant sem tenant;
- tenant de tipo inválido;
- tipo vazio;
- tipo branco;
- tipo demasiado longo;
- tipo com caracteres proibidos;
- origem vazia;
- origem branca;
- origem demasiado longa;
- origem com path;
- origem com IP;
- mensagem vazia;
- mensagem branca;
- mensagem demasiado longa;
- endpoint sem slash;
- endpoint com query;
- endpoint com fragmento;
- endpoint com esquema;
- endpoint com backslash;
- endpoint com `%`;
- endpoint com `..`;
- endpoint com controlo;
- status HTTP abaixo de 100;
- status HTTP acima de 599;
- status HTTP bool;
- indicador desconhecido;
- indicador duplicado;
- indicadores fora de ordem;
- mais de três indicadores.

### 29.5 Sanitização

Rejeitar:

- JWT;
- token;
- API key;
- CPF;
- CNPJ;
- email;
- XML;
- traceback;
- IP;
- Authorization;
- cookie;
- credencial;
- path interno;
- query string;
- atribuição ou valor de variável de ambiente;
- segredo associado a variável de ambiente.

Permitir, sem qualquer valor associado:

- menção nominal a `VITE_API_URL`;
- mensagem determinística necessária à sentinela `VERCEL_ENV_VAZIA`.

Provar:

- adapter rejeita;
- adapter não mascara;
- adapter não reescreve;
- erro não contém o segredo;
- legado não é importado depois da rejeição.

### 29.6 Paridade

Para cada uma das nove sentinelas:

- evento esperado reconhecido;
- código exacto;
- classificação exacta;
- risco exacto;
- `nao_informado` rejeitado na versão 1;
- flags exactos;
- causa não vazia nem branca;
- todas as evidências não vazias nem brancas;
- teste recomendado não vazio nem branco;
- patch sugerido não vazio nem branco;
- informação em falta exacta;
- nenhuma chamada LLM.

Schema drift:

- `UNDEFINED_COLUMN`;
- `COLUMN_DOES_NOT_EXIST`;
- `RELATORIOS_ANALISE_FINGERPRINT_MISSING`;
- representação mínima;
- mesma sentinela;
- mesmo perfil.

### 29.7 Informação em falta

- cinco correspondências exactas;
- regra estrutural de colunas;
- texto desconhecido gera drift;
- texto ambíguo gera drift;
- texto duplicado gera drift;
- código duplicado gera drift;
- ordem divergente gera drift;
- nenhum texto atravessa payload.

### 29.8 Guardas de runtime

- quantidade errada;
- elemento não callable;
- nome divergente;
- ordem divergente;
- mapa incompleto;
- código sem perfil;
- perfil extra;
- padrões locais não vazios;
- todos produzem `LEGACY_DRIFT`;
- nenhuma falha produz `AttributeError` público.

### 29.9 Payload

- reconhecido completo;
- não reconhecido completo;
- `event_id == context.event_id`;
- informação sem duplicados;
- informação em ordem;
- publication false;
- automation false;
- human review true;
- nenhuma causa;
- nenhuma evidência;
- nenhum ficheiro;
- nenhum teste textual;
- nenhum patch textual;
- nenhuma mensagem original.

### 29.10 Validação independente

Adulterar individualmente:

- reconhecido;
- camada;
- código;
- classificação;
- risco;
- cada flag;
- informação em falta;
- event_id;
- analysis type;
- schema type;
- versão;
- publication allowed;
- automation allowed;
- human review.

Adulterar `internal` e `payload` coerentemente também deve falhar quando
divergirem do perfil canónico.

### 29.11 Resultados

Provar sucesso, bloqueio e erro:

- formato exacto;
- matriz LLM;
- matriz de custo;
- ausência de acções;
- validação contra missão;
- sanitização;
- mensagens públicas fixas;
- ausência de `str(exc)`;
- ausência de traceback.

### 29.12 Estrutura

- adapter assíncrono;
- motor síncrono;
- validador independente síncrono;
- nenhum `__init__.py` alterado;
- registry sem referência;
- scheduler sem referência;
- executor sem referência;
- sem reader;
- sem DB;
- sem ORM;
- sem HTTP;
- sem filesystem em runtime;
- sem integração activa.

---

## 30. Alterações locais fora do escopo

Permanecem intocadas e não staged:

```text
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py
```

Nenhuma dessas alterações pode entrar no commit documental ou no commit de
implementação de B14.3F.

---

## 31. Critério de conclusão

B14.3F fecha somente quando:

- ADR-014 ratificada;
- ADR commitada isoladamente;
- exactamente quatro ficheiros de implementação;
- escopo de staging comprovado;
- testes B14.3F verdes;
- regressão dirigida B14.3A–F verde;
- suite global com zero falhas;
- hash do legado preservado;
- nove sentinelas congeladas;
- padrões locais vazios;
- BudgetGuard nunca invocado;
- LLMRouter nunca invocado;
- `run()` nunca invocado;
- import tardio comprovado;
- payload sanitizado;
- validação independente verde;
- HEAD local igual a `origin/main`;
- alterações antigas permanecem fora do commit.

---

## 32. Futuro criptográfico e pós-quântico

B14.3F não introduz criptografia nova.

A futura fronteira criptográfica será transversal e versionada no envelope da
missão e no registo de auditoria.

Campos previstos:

```text
event_digest
mission_digest
result_digest
parent_event_digest
canonicalization_version
algorithm_id
algorithm_version
key_id
signature_format
signature
signed_at
```

Princípios:

- hash demonstra integridade, não autoridade;
- algoritmo não fica hardcoded no domínio;
- canonicalização é determinística e versionada;
- troca de algoritmo não altera o motor de diagnóstico;
- transição híbrida pode coexistir com algoritmo clássico e pós-quântico;
- resultado de LLM não se torna canónico por estar assinado;
- criptografia futura exige ADR própria.

---

## 33. Exclusões

Ficam fora de B14.3F:

- LLM;
- BudgetGuard em execução;
- LLMRouter em execução;
- provider externo;
- modo fallback;
- modo activo;
- padrões aprendidos;
- registry;
- scheduler;
- executor;
- `run_all`;
- endpoint;
- reader;
- projector de produção;
- persistência;
- patch automático;
- pull request automático;
- publicação;
- causa textual;
- evidência textual;
- ficheiro provável;
- teste textual;
- patch textual;
- contexto livre;
- ambiente;
- commit SHA;
- P2 artificial;
- assinatura criptográfica;
- alteração do legado.

B14.3G tratará enriquecimento LLM somente através de missão própria, redacção
específica, BudgetGuard e LLMRouter.

---

## 34. Observações adiadas

Permanecem abertas e fora deste bloco:

```text
OBS-MOTOR-MEI-001
OBS-NUMERIC-CONSISTENCY-001
OBS-LIMIAR-MEMORIAL-001
```

---

## 35. Ratificação

| Papel | Nome | Estado |
|---|---|---|
| Fundador e Arquitecto Soberano | Miguel | ✅ RATIFICADA |
| Auditor Arquitectural | GPT | ✅ RATIFICADA ARQUITECTURALMENTE |
| Redactor subordinado | Claude/Kimi | N/A nesta versão |

Nenhum código ou teste de B14.3F será criado antes:

1. da ratificação de Miguel;
2. da criação deste documento no repositório;
3. da auditoria do diff;
4. do Commit 1 documental isolado.

---

*O conhecimento institucional não permanece na conversa. Permanece no
repositório, nos contratos, nos testes e nas evidências.*
