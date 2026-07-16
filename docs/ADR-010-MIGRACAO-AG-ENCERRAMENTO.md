
# ADR-010 — Migração L3 do AgEncerramentoAgent (canário MEI)



**Status:** RATIFICADA v1.4

**Data:** 2026-07-16

**Versão:** 1.4

**Autores:** GPT — auditor e redactor arquitectural; Miguel — fundador e arquitecto soberano

**Bloco:** B14.3B

**Repositório:** nexialistamentor/saas-fiscal-demo

**Depende de:** ADR-008 v1.5 e ADR-009 v1.5

**HEAD de referência no início do bloco:** 206c2ca



---



## 1. Contexto e problema



A fundação contratual B14.0+B14.1 encontra-se institucionalizada em `origin/main`, com:



- 1443 passed

- 0 failed

- 8 skipped



O canário B14.3A, aplicado ao `AgAberturaAgent`, provou o padrão adapter L3 para um agente de orientação pura, sem acesso a dados persistidos nem efeitos externos.



O `AgEncerramentoAgent` é o segundo candidato à migração. O método legado `run(context: dict) -> dict` apresenta dependências e riscos inexistentes no canário anterior:



- recebe uma `Session` SQLAlchemy através do contexto;

- consulta dados fiscais reais de `Insight` e `RelatorioAnalise`;

- expõe `str(exc)` no payload quando a consulta falha;

- usa `datetime.utcnow()` sem timezone;

- executa imports condicionais de SQLAlchemy dentro de `run()`;

- aplica conteúdo específico de MEI a outros tipos de empresa.



A migração exige:



```text

missão serializável

→ autorização de tenant

→ reader read-only

→ snapshot factual imutável

→ motor determinístico

→ payload canónico

→ AgentExecutionResult

```



A sessão ORM nunca atravessa a fronteira da missão.



---



## 2. Escopo restrito a MEI



B14.3B cobre exclusivamente `tipo_contribuinte = "mei"`.



O checklist, o aviso de irreversibilidade e os avisos legais do legado são específicos de MEI. O legado aplica incorrectamente o mesmo conteúdo a ME, EPP, LTDA, SLU, EI e empresas genéricas. Esses tipos ficam explicitamente excluídos.



Apoiar outros tipos exigirá, em bloco posterior: contrato próprio, checklist próprio, avisos próprios, fontes normativas próprias, testes próprios e ratificação documental própria.



---



## 3. Evidência do legado



**Ficheiro:** `app/agents/ag_encerramento_agent.py`

**Classe:** `AgEncerramentoAgent`

**Identidade canónica:** `ag_encerramento`

**Versão:** `1.0`

**SHA256 protegido:** `11E76504E33480BC53BC543D25EE2F0A66EC0750B4F23D5D3A2656E78560C743`



O hash deve permanecer idêntico antes do Commit 1 e após o Commit 2.



### 3.1 Características provadas



| Dimensão | Evidência |

|---|---|

| BD | Sim — SQLAlchemy através de `db` no contexto |

| HTTP externo | Não |

| LLM | Não |

| Escrita em ficheiros | Não |

| Escrita explícita na BD | Não |

| `str(exc)` exposto | Sim |

| Relógio interno | `datetime.utcnow()` |

| Instância global | `ag_encerramento_agent` |

| Testes próprios anteriores | Não existentes |



### 3.2 Lógica temporal do legado



```python

meses = (datetime.utcnow() - ultimo_relatorio.created_at).days // 30

if meses > 3:

    # relatório desactualizado

```



O limiar real é `idade >= 120 dias`:



- `119 // 30 = 3` → não desactualizado

- `120 // 30 = 4` → desactualizado



### 3.3 Constantes históricas preservadas



`CHECKLIST_ENCERRAMENTO` — 8 passos com campos `passo`, `titulo`, `descricao`, `severidade` (`"alta"`/`"media"`), `link` (opcional).



`AVISO_ENCERRAMENTO_IRREVERSIVEL` — string literal UTF-8.



```python

AVISOS_LEGAIS_ENCERRAMENTO: tuple[str, ...] = (

    "Débitos não quitados migram para o CPF do titular.",

    "Documentos fiscais devem ser guardados 5 anos (CTN art. 195).",

    "Consulte um contador antes de iniciar o encerramento.",

)

```



Estas strings não constituem autoridade normativa; não possuem `SourceRef` neste bloco; permanecem sujeitas a revisão humana; não podem ser publicadas; não podem ser usadas em modo activo; `NORMATIVE_SOURCES_MISSING` permanece obrigatório. Não se estendem a outros tipos de empresa.



---



## 4. Perfil de risco



Agente read-only com dados fiscais tenant-sensitive, restrito a MEI, sem autoridade de escrita, mas com obrigação de autorização, isolamento de tenant, temporalidade fail-closed e não enumeração. Não é equivalente ao canário simples B14.3A.



---



## 5. Autoridade e isolamento de tenant



### 5.1 Identidade obrigatória



```text

scope = "tenant"

tenant_id = inteiro positivo não booleano

actor_id = inteiro positivo não booleano

actor_id == tenant_id

```



### 5.2 Recurso autorizado



```text

Empresa.id == context.empresa_id

Empresa.user_id == tenant_id

```



### 5.3 Política canónica de referência



A política existente em `app/security.py` é materializada por:



```python

db.query(Empresa).filter(

    Empresa.id == empresa_id,

    Empresa.user_id == usuario.id,

).first()

```



O reader L3 implementa o mesmo predicado como regra de domínio, sem reutilizar `verificar_empresa_do_usuario` (que depende de `HTTPException`). Uma futura extracção para serviço partilhado fica fora deste bloco.



### 5.4 Acesso de contador



`ContadorEmpresaVinculo` explicitamente excluído.



### 5.5 Não enumeração



Os seguintes casos são publicamente indistinguíveis:



- empresa inexistente

- empresa pertencente a outro titular

- empresa não autorizada para o actor



Todos produzem:



```text

status = "bloqueado"

payload = {}

alert code = "AG_ENCERRAMENTO_ACCESS_DENIED"

error_code = None

error_message = None

```



Mensagem pública exacta: `"Não foi possível autorizar o acesso à empresa solicitada."`



---



## 6. Missão canónica



Toda a missão deve nascer exclusivamente por `create_agent_mission(...)`. É proibida a instanciação directa de `AgentMission(...)`.



### 6.1 Valores exactos



| Campo | Valor |

|---|---|

| `target_agent` | `"ag_encerramento"` |

| `mission_type` | `"orientar_encerramento_empresa"` |

| `context_schema` | `"ag_encerramento.context"` |

| `context_version` | `"1.0"` |

| `output_schema` | `"ag_encerramento.result"` |

| `output_version` | `"1.0"` |

| `agent_version` | `"1.0"` |

| `scope` | `"tenant"` |

| `authority_level` | `"leitura"` |

| `requested_by` | `"user"` ou `"system"` |

| `source_request_id` | obrigatório, não vazio |

| `source_event_id` | `None` |

| `schedule_slot` | `None` |

| `agent_version_required` | `None` ou `"1.0"` |

| `budget_policy` | perfil nulo exacto |

| `sources` | `[]` |



### 6.2 Identidade



`tenant_id` e `actor_id` devem ser inteiros positivos não booleanos. `actor_id == tenant_id`.



### 6.3 Instante de referência



`reference_at` é obrigatório, timezone-aware, offset UTC zero, não posterior a `mission.created_at`. O reader e o motor nunca criam `reference_at`.



---



## 7. Contexto canónico



```python

TIPOS_VALIDOS_ENCERRAMENTO: frozenset[str] = frozenset({"mei"})





class AgEncerramentoContext(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    empresa_id: StrictInt

    tipo_contribuinte: str = "mei"



    @field_validator("empresa_id")

    @classmethod

    def validar_empresa_id(cls, value: int) -> int:

        if value <= 0:

            raise ValueError("empresa_id deve ser positivo")

        return value



    @field_validator("tipo_contribuinte", mode="before")

    @classmethod

    def validar_tipo_contribuinte(cls, value: object) -> str:

        if value is None:

            raise ValueError("tipo_contribuinte não pode ser None")

        if isinstance(value, bool) or not isinstance(value, str):

            raise ValueError("tipo_contribuinte deve ser string")

        normalizado = value.strip().casefold()

        if not normalizado:

            raise ValueError("tipo_contribuinte não pode ser vazio")

        if normalizado != "mei":

            raise ValueError("tipo_contribuinte não suportado neste canário")

        return normalizado

```



### 7.1 Pré-validação raw pelo adapter



- chave ausente → usar default `"mei"`

- `None` → `AG_ENCERRAMENTO_CONTEXT_INVALID`

- booleano ou não textual → `AG_ENCERRAMENTO_CONTEXT_INVALID`

- vazio ou espaços → `AG_ENCERRAMENTO_CONTEXT_INVALID`

- string normalizada diferente de `"mei"` → `AG_ENCERRAMENTO_TIPO_UNSUPPORTED`



### 7.2 Conteúdo proibido



O contexto nunca pode conter: `db`, `Session`, `AsyncSession`, objectos ORM, funções, ficheiros, sockets, clientes HTTP, ou qualquer objecto não serializável canonicamente.



---



## 8. Erros de domínio do reader



```python

class EncerramentoAccessDeniedError(Exception):

    """Empresa inexistente ou não autorizada para o tenant."""

    pass





class EncerramentoDataUnavailableError(Exception):

    """Dados não puderam ser obtidos ou validados com segurança."""

    pass

```



Nenhuma destas excepções transporta `str(exc)`, traceback, SQL, nome de tabela, nome de coluna, caminho interno ou identificadores fiscais.



### 8.1 Ordem obrigatória de captura



```python

try:

    ...

except EncerramentoAccessDeniedError:

    raise

except EncerramentoDataUnavailableError:

    raise

except Exception:

    raise EncerramentoDataUnavailableError() from None

```



### 8.2 Conversão pelo adapter



- `EncerramentoAccessDeniedError` → bloqueado → `AG_ENCERRAMENTO_ACCESS_DENIED`

- `EncerramentoDataUnavailableError` → erro → `AG_ENCERRAMENTO_DATA_UNAVAILABLE`

- Falha do motor, renderer ou validação payload-snapshot → erro → `AG_ENCERRAMENTO_EXECUTION_ERROR`



---



## 9. Porta EncerramentoPendenciaReader



```python

class EncerramentoPendenciaReader(Protocol):

    def obter_snapshot(

        self,

        *,

        tenant_id: int,

        actor_id: int,

        empresa_id: int,

        reference_at: datetime,

    ) -> "EncerramentoPendenciaSnapshot":

        ...

```



A porta é deliberadamente síncrona porque reflecte `sqlalchemy.orm.Session`. Uma futura implementação com `AsyncSession` exigirá nova versão da porta e alteração explícita do adapter. Não haverá adaptação implícita.



O reader síncrono não será integrado no executor, scheduler nem executado concorrentemente. Uma futura activação concorrente exigirá `AsyncSession` ou sessão criada e encerrada dentro de fronteira de thread segura.



---



## 10. Implementação SQLAlchemy do reader



**Ficheiro:** `app/agents/readers/ag_encerramento.py`



A sessão é injectada exclusivamente no construtor. Nunca entra na missão, contexto, adapter, snapshot, motor ou resultado.



### 10.1 Defesa em profundidade



```python

if actor_id != tenant_id:

    raise EncerramentoAccessDeniedError() from None

```



### 10.2 Prevenção de autoflush



```python

with self._db.no_autoflush:

    ...

```



### 10.3 Verificação inicial de autorização



```python

empresa_autorizada = (

    self._db.query(Empresa.id)

    .filter(

        Empresa.id == empresa_id,

        Empresa.user_id == tenant_id,

    )

    .first()

)



if empresa_autorizada is None:

    raise EncerramentoAccessDeniedError() from None

```



### 10.4 Predicado repetido nas consultas fiscais



Cada consulta fiscal repete a condição `Empresa.id == empresa_id AND Empresa.user_id == tenant_id` através de EXISTS ou predicado ORM equivalente.



### 10.5 Contagem de insights activos



```python

total_insights_ativos = (

    self._db.query(func.count(Insight.id))

    .filter(

        Insight.empresa_id == empresa_id,

        Insight.superseded.is_(False),

    )

    .scalar()

)

```



### 10.6 Consulta agregada dos relatórios



```python

total_relatorios, ultimo_created_at = (

    self._db.query(

        func.count(RelatorioAnalise.id),

        func.max(RelatorioAnalise.created_at),

    )

    .filter(RelatorioAnalise.empresa_id == empresa_id)

    .one()

)

```



`MAX` ignora valores `NULL`. A consulta única evita que `COUNT` e `MAX` observem estados diferentes entre duas instruções independentes.



### 10.7 Reconfirmação final



Antes de devolver o snapshot, o reader volta a confirmar `Empresa.id == empresa_id AND Empresa.user_id == tenant_id`. Falha → `EncerramentoAccessDeniedError`. Todo o snapshot é descartado.



### 10.8 Operações proibidas



`text()`, SQL arbitrário, `add()`, `delete()`, `flush()`, `commit()`, devolver objectos ORM, devolver a sessão, propagar excepções internas, consultar outra empresa.



---



## 11. Snapshot factual



```python

class EncerramentoPendenciaSnapshot(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    empresa_id: StrictInt

    reference_at: AwareDatetime

    total_insights_ativos: StrictInt



    estado_ultimo_relatorio: Literal[

        "ausente",

        "timestamp_ausente",

        "timestamp_naive",

        "timestamp_aware",

    ]

    ultimo_relatorio_em: AwareDatetime | None



    @model_validator(mode="after")

    def validar_invariantes(self) -> Self:

        if self.empresa_id <= 0:

            raise ValueError("empresa_id deve ser positivo")

        if self.total_insights_ativos < 0:

            raise ValueError("total_insights_ativos não pode ser negativo")

        if self.reference_at.utcoffset() != timedelta(0):

            raise ValueError("reference_at deve estar em UTC")

        if self.estado_ultimo_relatorio in {

            "ausente", "timestamp_ausente", "timestamp_naive",

        }:

            if self.ultimo_relatorio_em is not None:

                raise ValueError("estado sem timestamp não admite ultimo_relatorio_em")

        if self.estado_ultimo_relatorio == "timestamp_aware":

            if self.ultimo_relatorio_em is None:

                raise ValueError("timestamp_aware exige ultimo_relatorio_em")

            if self.ultimo_relatorio_em.utcoffset() != timedelta(0):

                raise ValueError("ultimo_relatorio_em deve estar em UTC")

            if self.ultimo_relatorio_em > self.reference_at:

                raise ValueError("ultimo_relatorio_em não pode ser futuro")

        return self

```



### 11.1 Determinação do estado



```text

total_relatorios == 0

→ estado = "ausente", ultimo_relatorio_em = None



total_relatorios > 0 e ultimo_created_at is None

→ estado = "timestamp_ausente", ultimo_relatorio_em = None



ultimo_created_at naïve

→ estado = "timestamp_naive", ultimo_relatorio_em = None



ultimo_created_at aware com offset não-zero

→ converter com astimezone(timezone.utc)

→ estado = "timestamp_aware"



ultimo_created_at aware UTC

→ estado = "timestamp_aware"

```



Proibido: `value.replace(tzinfo=timezone.utc)` sobre timestamp naïve.



---



## 12. Verificação snapshot–missão



```python

if snapshot.empresa_id != context_model.empresa_id:

    raise EncerramentoDataUnavailableError() from None



if snapshot.reference_at != mission.reference_at:

    raise EncerramentoDataUnavailableError() from None

```



Não se usa `assert`. Divergência produz `status="erro"`, `error_code="AG_ENCERRAMENTO_DATA_UNAVAILABLE"`, `payload={}`.



---



## 13. Política temporal fail-closed



```python

RELATORIO_DESACTUALIZADO_APOS_DIAS = 120



desactualizado = (

    snapshot.reference_at - snapshot.ultimo_relatorio_em

) >= timedelta(days=RELATORIO_DESACTUALIZADO_APOS_DIAS)

```



| Estado | Resultado |

|---|---|

| `ausente` | `RELATORIO_AUSENTE` |

| `timestamp_ausente` | `RELATORIO_TIMESTAMP_AUSENTE` |

| `timestamp_naive` | `RELATORIO_TIMESTAMP_NAIVE` |

| `timestamp_aware`, `< 120 dias` | sem alerta de relatório |

| `timestamp_aware`, `>= 120 dias` | `RELATORIO_DESACTUALIZADO` |



---



## 14. Contratos canónicos



**Ficheiro:** `app/agents/contracts/ag_encerramento.py`



### 14.1 Divulgação comercial



```python

class AgEncerramentoCommercialDisclosure(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    platform_service_requires_payment: Literal[True] = True

    official_process_cost_separate: Literal[True] = True

    pricing_status: Literal["pendente_ratificacao"] = "pendente_ratificacao"

    pricing_policy_id: None = None

    price_amount: None = None

    currency: Literal["BRL"] = "BRL"

    requires_explicit_consent: Literal[True] = True

```



Não importa `CommercialDisclosure` de `ag_abertura.py`.



### 14.2 Checklist



```python

class AgEncerramentoChecklistItem(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    passo: StrictInt

    titulo: str

    descricao: str

    severidade: Literal["alta", "media"] | None = None

    link: str | None = None

```



### 14.3 Cópia canónica imutável



```python

CHECKLIST_ENCERRAMENTO_CANONICO = tuple(

    AgEncerramentoChecklistItem.model_validate(item)

    for item in CHECKLIST_ENCERRAMENTO

)

```



O motor nunca utiliza directamente a lista mutável do legado.



---



## 15. Alertas de plataforma



### 15.1 Códigos



```python

AlertaEncerramentoCode = Literal[

    "INSIGHTS_ATIVOS",

    "RELATORIO_AUSENTE",

    "RELATORIO_TIMESTAMP_AUSENTE",

    "RELATORIO_TIMESTAMP_NAIVE",

    "RELATORIO_DESACTUALIZADO",

]

```



### 15.2 Tabela canónica imutável



```python

from types import MappingProxyType



ALERTAS_ENCERRAMENTO_CANONICOS = MappingProxyType({

    "INSIGHTS_ATIVOS": (

        "alto",

        "Existem análises fiscais activas que devem ser revistas antes do encerramento.",

    ),

    "RELATORIO_AUSENTE": (

        "medio",

        "Nenhum relatório fiscal foi encontrado para esta empresa.",

    ),

    "RELATORIO_TIMESTAMP_AUSENTE": (

        "medio",

        "Existe relatório fiscal sem data registada; confirme-o antes do encerramento.",

    ),

    "RELATORIO_TIMESTAMP_NAIVE": (

        "medio",

        "A data do relatório fiscal não pôde ser validada temporalmente.",

    ),

    "RELATORIO_DESACTUALIZADO": (

        "medio",

        "O relatório fiscal tem pelo menos 120 dias; confirme a situação actual.",

    ),

})

```



### 15.3 Modelo



```python

class AgEncerramentoAlertaPlataforma(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    code: AlertaEncerramentoCode

    severidade: Literal["alto", "medio"]

    descricao_publica: str

    quantidade: StrictInt | None = None



    @model_validator(mode="after")

    def validar_contrato(self) -> Self:

        severidade_esperada, mensagem_esperada = ALERTAS_ENCERRAMENTO_CANONICOS[self.code]

        if self.severidade != severidade_esperada:

            raise ValueError("severidade diverge da tabela canónica")

        if self.descricao_publica != mensagem_esperada:

            raise ValueError("descricao_publica diverge da tabela canónica")

        if self.code == "INSIGHTS_ATIVOS":

            if self.quantidade is None or self.quantidade <= 0:

                raise ValueError("INSIGHTS_ATIVOS exige quantidade positiva")

        elif self.quantidade is not None:

            raise ValueError("apenas INSIGHTS_ATIVOS admite quantidade")

        return self

```



---



## 16. Ordem e unicidade dos alertas



Ordem canónica:



1. `INSIGHTS_ATIVOS`, quando presente

2. exactamente um alerta de relatório, quando aplicável



Invariantes: sem duplicados; máximo dois alertas; máximo um alerta de relatório; `INSIGHTS_ATIVOS` sempre primeiro quando presente; alerta de relatório sempre na posição 1 (sem `INSIGHTS_ATIVOS`) ou 2 (com `INSIGHTS_ATIVOS`).



---



## 17. Razões de revisão



```python

ReviewReasonEncerramento = Literal[

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

    "TEMPORAL_EVIDENCE_INCOMPLETE",

]



BASE_REVIEW_REASONS_ENCERRAMENTO = (

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

)



TEMPORAL_REVIEW_REASONS_ENCERRAMENTO = (

    "NORMATIVE_SOURCES_MISSING",

    "COMMERCIAL_POLICY_PENDING",

    "TEMPORAL_EVIDENCE_INCOMPLETE",

)

```



Usar `TEMPORAL_REVIEW_REASONS_ENCERRAMENTO` apenas quando presente `RELATORIO_TIMESTAMP_AUSENTE` ou `RELATORIO_TIMESTAMP_NAIVE`. Nos restantes estados, usar `BASE_REVIEW_REASONS_ENCERRAMENTO`.



---



## 18. Payload nominal



```python

class AgEncerramentoPayload(BaseModel):

    model_config = ConfigDict(extra="forbid", frozen=True)



    resposta: str

    analysis_type: Literal["encerramento_empresa"] = "encerramento_empresa"

    schema_type: Literal["HowTo"] = "HowTo"

    versao: Literal["1.0"] = "1.0"

    tipo_contribuinte: Literal["mei"] = "mei"



    checklist: tuple[AgEncerramentoChecklistItem, ...]

    avisos_legais: tuple[str, ...]

    alertas_plataforma: tuple[AgEncerramentoAlertaPlataforma, ...]

    aviso_irreversivel: str



    commercial_disclosure: AgEncerramentoCommercialDisclosure

    review_reasons: tuple[ReviewReasonEncerramento, ...]

    publication_allowed: Literal[False] = False



    @model_validator(mode="after")

    def validar_alertas_e_review_reasons(self) -> Self:

        codigos = [a.code for a in self.alertas_plataforma]

        if len(codigos) != len(set(codigos)):

            raise ValueError("alertas_plataforma contém códigos duplicados")

        if len(self.alertas_plataforma) > 2:

            raise ValueError("no máximo dois alertas de plataforma")

        if codigos and codigos[0] != "INSIGHTS_ATIVOS" and "INSIGHTS_ATIVOS" in codigos:

            raise ValueError("INSIGHTS_ATIVOS deve ser o primeiro alerta")

        codigos_relatorio = {

            "RELATORIO_AUSENTE", "RELATORIO_TIMESTAMP_AUSENTE",

            "RELATORIO_TIMESTAMP_NAIVE", "RELATORIO_DESACTUALIZADO",

        }

        alertas_relatorio = [c for c in codigos if c in codigos_relatorio]

        if len(alertas_relatorio) > 1:

            raise ValueError("no máximo um alerta de relatório")

        tem_alerta_temporal = bool(

            set(codigos) & {"RELATORIO_TIMESTAMP_AUSENTE", "RELATORIO_TIMESTAMP_NAIVE"}

        )

        if tem_alerta_temporal:

            if self.review_reasons != TEMPORAL_REVIEW_REASONS_ENCERRAMENTO:

                raise ValueError("alertas temporais exigem TEMPORAL_REVIEW_REASONS_ENCERRAMENTO")

        else:

            if self.review_reasons != BASE_REVIEW_REASONS_ENCERRAMENTO:

                raise ValueError("ausência de alertas temporais exige BASE_REVIEW_REASONS_ENCERRAMENTO")

        return self

```



---



## 19. Motor determinístico



**Ficheiro:** `app/agents/engines/ag_encerramento.py`



```python

def construir_orientacao_encerramento(

    context: AgEncerramentoContext,

    snapshot: EncerramentoPendenciaSnapshot,

) -> AgEncerramentoPayload:

    ...

```



O motor não pode utilizar BD, sessão, relógio (`datetime.now()`, `datetime.utcnow()`, `date.today()`), LLM, HTTP, agente legado, `str(exc)` ou dados externos ao snapshot.



### 19.1 Derivação dos alertas



```text

total_insights_ativos > 0 → INSIGHTS_ATIVOS (quantidade = total_insights_ativos)



ausente             → RELATORIO_AUSENTE

timestamp_ausente   → RELATORIO_TIMESTAMP_AUSENTE

timestamp_naive     → RELATORIO_TIMESTAMP_NAIVE

timestamp_aware, >= 120 dias → RELATORIO_DESACTUALIZADO

timestamp_aware, < 120 dias  → nenhum alerta de relatório

```



---



## 20. Renderização canónica da resposta



O título exacto é:



```python

titulo = (

    f"Como encerrar o MEI em {snapshot.reference_at.year} "

    "— Orientação Preliminar"

)

```



A expressão "Passo a Passo Oficial" é proibida enquanto `NORMATIVE_SOURCES_MISSING` e `publication_allowed=False`.



```python

def renderizar_resposta_encerramento(

    *,

    ano: int,

    checklist: tuple[AgEncerramentoChecklistItem, ...],

    alertas: tuple[AgEncerramentoAlertaPlataforma, ...],

    aviso_irreversivel: str,

    avisos_legais: tuple[str, ...],

) -> str:

    titulo = f"Como encerrar o MEI em {ano} — Orientação Preliminar"

    partes: list[str] = [f"**{titulo}**", "", f"⚠️ {aviso_irreversivel}", ""]



    if alertas:

        partes.append("**Pendências detectadas na plataforma:**")

        for alerta in alertas:

            icone = "🔴" if alerta.severidade == "alto" else "🟡"

            texto = f"{icone} {alerta.descricao_publica}"

            if alerta.code == "INSIGHTS_ATIVOS":

                texto += f" Quantidade: {alerta.quantidade}."

            partes.append(texto)

        partes.append("")



    partes.append("**Checklist de encerramento:**")

    for item in checklist:

        if item.severidade == "alta":

            icone = "🔴"

        elif item.severidade == "media":

            icone = "🟡"

        else:

            icone = "•"

        link = f" → [Ver]({item.link})" if item.link else ""

        partes.append(

            f"{icone} **{item.passo}.** {item.titulo}: {item.descricao}{link}"

        )



    partes.extend(["", "**Avisos sujeitos a revisão humana:**"])

    for aviso in avisos_legais:

        partes.append(f"• {aviso}")



    return "\n".join(partes)

```



O ano nasce exclusivamente de `snapshot.reference_at.year`.



---



## 21. Validação independente payload–snapshot



Antes de construir `AgentExecutionResult`, o adapter chama:



```python

validate_ag_encerramento_payload_against_snapshot(

    context=context_model,

    snapshot=snapshot,

    payload=payload_model,

)

```



Esta função não chama `construir_orientacao_encerramento` nem confia no output do motor. Reconstrói os valores esperados a partir do snapshot e dos contratos canónicos.



Deve provar integralmente: `tipo_contribuinte`, `analysis_type`, `schema_type`, `versao`, `publication_allowed`, checklist exacto, avisos legais exactos, aviso irreversível exacto, divulgação comercial exacta, alertas exactos com ordem e quantidades, `review_reasons` exactas, resposta integral exacta e ano exacto.



Falha produz `status="erro"`, `error_code="AG_ENCERRAMENTO_EXECUTION_ERROR"`, `payload={}`, `alerts=[]`.



---



## 22. Mensagens públicas operacionais



| Código | Mensagem |

|---|---|

| `AG_ENCERRAMENTO_ACCESS_DENIED` | `"Não foi possível autorizar o acesso à empresa solicitada."` |

| `AG_ENCERRAMENTO_DATA_UNAVAILABLE` | `"Não foi possível obter os dados necessários para esta orientação."` |

| `AG_ENCERRAMENTO_EXECUTION_ERROR` | `"Não foi possível concluir a orientação de encerramento."` |



Nenhuma mensagem pode conter: `empresa_id`, `tenant_id`, existência da empresa, SQL, BD, tabela, coluna, classe de excepção, `str(exc)` ou traceback.



---



## 23. Erros pré-execução



```python

AdapterEncerramentoPreExecutionErrorCode = Literal[

    "MISSION_TARGET_MISMATCH",

    "MISSION_TYPE_UNSUPPORTED",

    "CONTEXT_SCHEMA_UNSUPPORTED",

    "CONTEXT_VERSION_UNSUPPORTED",

    "OUTPUT_SCHEMA_UNSUPPORTED",

    "OUTPUT_VERSION_UNSUPPORTED",

    "MISSION_SCOPE_UNSUPPORTED",

    "MISSION_TENANT_REQUIRED",

    "MISSION_ACTOR_UNSUPPORTED",

    "MISSION_ACTOR_TENANT_MISMATCH",

    "MISSION_REFERENCE_AT_REQUIRED",

    "MISSION_AUTHORITY_UNSUPPORTED",

    "MISSION_ORIGIN_UNSUPPORTED",

    "MISSION_BUDGET_UNSUPPORTED",

    "MISSION_SOURCES_UNSUPPORTED",

    "AG_ENCERRAMENTO_TIPO_UNSUPPORTED",

    "AG_ENCERRAMENTO_CONTEXT_INVALID",

]

```



| Código | Condição |

|---|---|

| `MISSION_TARGET_MISMATCH` | target diferente |

| `MISSION_TYPE_UNSUPPORTED` | mission type diferente |

| `CONTEXT_SCHEMA_UNSUPPORTED` | schema diferente |

| `CONTEXT_VERSION_UNSUPPORTED` | versão de contexto diferente |

| `OUTPUT_SCHEMA_UNSUPPORTED` | output schema diferente |

| `OUTPUT_VERSION_UNSUPPORTED` | output version diferente |

| `MISSION_SCOPE_UNSUPPORTED` | scope diferente de tenant |

| `MISSION_TENANT_REQUIRED` | tenant ausente, inválido ou não positivo |

| `MISSION_ACTOR_UNSUPPORTED` | actor ausente, inválido ou não positivo |

| `MISSION_ACTOR_TENANT_MISMATCH` | actor diferente de tenant |

| `MISSION_REFERENCE_AT_REQUIRED` | ausente, naïve, não UTC ou futuro |

| `MISSION_AUTHORITY_UNSUPPORTED` | authority ou requested_by inválido |

| `MISSION_ORIGIN_UNSUPPORTED` | origem ausente ou concorrente |

| `MISSION_BUDGET_UNSUPPORTED` | budget diferente do perfil nulo |

| `MISSION_SOURCES_UNSUPPORTED` | sources não vazio |

| `AG_ENCERRAMENTO_TIPO_UNSUPPORTED` | string normalizada diferente de `"mei"` |

| `AG_ENCERRAMENTO_CONTEXT_INVALID` | contexto inválido por outra razão |



Falhas pré-execução não criam `AgentExecutionResult`, não chamam reader nem motor.



---



## 24. Bloqueios operacionais



`status="bloqueado"`, `payload={}`, `error_code=None`, `error_message=None`.



| Condição | Código do alerta |

|---|---|

| `execution_mode="activo"` | `EXECUTION_MODE_NOT_AUTHORIZED` |

| `agent_version_required` incompatível | `AGENT_VERSION_INCOMPATIBLE` |

| Acesso negado | `AG_ENCERRAMENTO_ACCESS_DENIED` |



Todos passam por `validate_result_against_mission` e `assert_result_sanitized`.



---



## 25. Erros operacionais



`status="erro"`, `payload={}`, `alerts=[]`.



| Condição | `error_code` |

|---|---|

| Falha técnica reader, BD indisponível, snapshot inválido, divergência empresa/reference_at | `AG_ENCERRAMENTO_DATA_UNAVAILABLE` |

| Falha do motor, renderer, payload ou validação payload-snapshot | `AG_ENCERRAMENTO_EXECUTION_ERROR` |



---



## 26. Matriz integral do resultado



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

payload_schema = mission.output_schema

payload_version = mission.output_version

```



| Campo | Sucesso | Bloqueado | Erro |

|---|---|---|---|

| `status` | `"sucesso"` | `"bloqueado"` | `"erro"` |

| `payload` | payload canónico | `{}` | `{}` |

| `alerts` | `[]` | um alerta | `[]` |

| `error_code` | `None` | `None` | código estável |

| `error_message` | `None` | `None` | mensagem estável |

| legado | nunca | nunca | nunca |



---



## 27. Modos de execução



- `sombra` e `dry_run`: executam reader + motor; legado nunca chamado

- `activo`: bloqueio `EXECUTION_MODE_NOT_AUTHORIZED`; reader não chamado

- `actions_executed` sempre vazio



---



## 28. Ordem canónica do adapter



```python

async def execute_ag_encerramento_mission(

    mission: AgentMission,

    reader: EncerramentoPendenciaReader,

) -> AgentExecutionResult:

    ...

```



1. Validar fronteira da missão

2. Resolver `tipo_contribuinte` ausente como `"mei"`

3. Pré-validar o tipo raw

4. Validar `AgEncerramentoContext`

5. Verificar versão e modo

6. `started_at = datetime.now(timezone.utc)` + `started_tick`

7. `snapshot = reader.obter_snapshot(...)`

8. Comparar snapshot com contexto e missão

9. `payload_model = construir_orientacao_encerramento(context_model, snapshot)`

10. `validate_ag_encerramento_payload_against_snapshot(...)`

11. `payload_dict = payload_model.model_dump(mode="python")`

12. Calcular duração monotónica

13. Construir `AgentExecutionResult`

14. `validate_result_against_mission(mission, result)`

15. `assert_result_sanitized(result.model_dump(mode="json"))`

16. Devolver



---



## 29. Sanitização



Missão nasce por factory com `assert_context_sanitized`. Resultado validado por `assert_result_sanitized(result.model_dump(mode="json"))`. Snapshot e payload nunca contêm CPF, CNPJ, email, token, traceback, SQL, caminhos internos, sessão, objectos ORM ou dados de outra empresa. `requires_payment=False` do legado nunca propagado.



---



## 30. Papel restrito do legado



`app/agents/ag_encerramento_agent.py` permanece byte-a-byte inalterado.

SHA256: `11E76504E33480BC53BC543D25EE2F0A66EC0750B4F23D5D3A2656E78560C743`



`AgEncerramentoAgent.run()` não é chamado pelo adapter, reader, motor, validação nem testes contratuais de execução. Serve apenas como evidência histórica, referência documental, origem das constantes históricas e alvo de verificação SHA256.



---



## 31. Cópia defensiva



Snapshot, contexto e payload são Pydantic frozen. Checklist, avisos e tabela de alertas em estruturas imutáveis. Duas execuções consecutivas não partilham estado mutável. O motor nunca altera `CHECKLIST_ENCERRAMENTO`, `AVISO_ENCERRAMENTO_IRREVERSIVEL`, `AVISOS_LEGAIS_ENCERRAMENTO` nem `ALERTAS_ENCERRAMENTO_CANONICOS`.



---



## 32. Estrutura de ficheiros



**Commit 1:**

```text

docs/ADR-010-MIGRACAO-AG-ENCERRAMENTO.md

```



**Commit 2:**

```text

app/agents/contracts/ag_encerramento.py

app/agents/readers/ag_encerramento.py

app/agents/engines/ag_encerramento.py

app/agents/adapters/ag_encerramento.py

tests/test_ag_encerramento_mission_adapter.py

```



Condicionalmente, apenas se ainda não existirem:

```text

app/agents/readers/__init__.py

app/agents/engines/__init__.py

```



---



## 33. Cenários contratuais obrigatórios



### 33.1 Missão

Target divergente; mission type divergente; schemas divergentes; versões divergentes; scope divergente; tenant ausente ou inválido; actor ausente ou inválido; actor diferente de tenant; `reference_at` ausente, naïve, offset não UTC, futuro; origem ausente ou concorrente; budget divergente; sources não vazio.



### 33.2 Contexto

Tipo ausente → default `"mei"`; `None` → context invalid; booleano → context invalid; numérico → context invalid; vazio → context invalid; espaços → context invalid; `" MEI "` → `"mei"`; `"EPP"` → tipo unsupported. `empresa_id` None, booleano, string, float, zero, negativo, campo extra.



### 33.3 Reader

Actor diferente de tenant; empresa inexistente; empresa de outro titular; sessão indisponível; erro técnico; `no_autoflush`; ausência de métodos de escrita; predicado tenant nas consultas; consulta agregada única; cada estado de `estado_ultimo_relatorio`; timestamp futuro; reconfirmação final da autorização.



### 33.4 Snapshot

`empresa_id` booleano ou `<= 0`; insights negativos; `reference_at` não UTC; combinações inválidas de estado e timestamp; timestamp futuro; imutabilidade.



### 33.5 Alertas

Código inválido; severidade divergente; mensagem divergente; quantidade booleano, string, float, zero, negativa; quantidade em alerta não permitido; duplicados; mais de dois alertas; dois alertas de relatório; ordem incorrecta; quantidade exacta de insights.



### 33.6 Motor

Zero insights; insights activos; cada estado de relatório; limiar exacto 119/120 dias; título com ano de `reference_at`; expressão "Orientação Preliminar"; ausência de "Oficial"; resposta integral exacta; checklist exacto; avisos exactos; divulgação comercial exacta; `review_reasons` exactas.



### 33.7 Payload–snapshot

Divergência em tipo, analysis type, schema type, versão, checklist, avisos legais, aviso irreversível, divulgação comercial, alertas, quantidade, ordem, `review_reasons`, resposta, ano — todas produzem `AG_ENCERRAMENTO_EXECUTION_ERROR`.



### 33.8 Modos

Sombra; dry_run; activo bloqueado; reader não chamado em activo; legado nunca chamado.



### 33.9 Resultados

Sucesso, bloqueio, erro — matriz comum completa; validação cruzada; sanitização; `__cause__=None`, `__suppress_context__=True` nas falhas pós-construção.



### 33.10 Integridade do legado

SHA256 exacto; ausência de `run_mission`; ausência de modificação; ausência de referências no registry, executor e scheduler.



---



## 34. Estratégia de commits



**Commit 1:** `docs: ratificar ADR-010 migracao L3 AgEncerramentoAgent MEI (B14.3B)`

Escopo exacto: `docs/ADR-010-MIGRACAO-AG-ENCERRAMENTO.md`



**Commit 2:** `feat: adapter L3 AgEncerramentoAgent MEI em sombra (B14.3B)`

Escopo exacto: ficheiros do §32, nenhum outro.



---



## 35. Critério de conclusão



ADR-010 commitada; Commit 1 atómico; Commit 2 atómico; testes novos verdes; suite global ≥ 1443 passed / 0 failed; SHA256 do legado inalterado; registry, executor e scheduler inalterados; working tree limpa; HEAD = origin/main.



---



## 36. Dívidas excluídas



Encerramento de ME, EPP, LTDA, SLU, EI e outros tipos; acesso de contador; `ContadorEmpresaVinculo`; publicação do conteúdo; `SourceRef`; vigência normativa; política comercial definitiva; conversão institucional de `DATETIME` naïve para UTC; extracção da autorização para serviço neutro; activação concorrente do reader; integração com registry, executor ou scheduler; execução em modo activo.



---



## 37. Ratificação



| Papel | Nome | Estado |

|---|---|---|

| Fundador e Arquitecto Soberano | Miguel | ✅ RATIFICADO |

| Auditor e Redactor Arquitectural | GPT | ✅ RATIFICADO |



**Nenhum código ou teste de B14.3B será criado antes do Commit 1 documental.**



---



*O conhecimento institucional não permanece na conversa. Permanece no repositório, nos contratos, nos testes e nas evidências.*
