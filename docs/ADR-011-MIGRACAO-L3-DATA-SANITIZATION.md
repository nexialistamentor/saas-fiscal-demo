ADR-011 — Migração L3 B14.3C: DataSanitizationAgent em Sombra

Status: PROPOSTA GPT v1.1 — aguarda ratificação de Miguel
Data: 2026-07-17
Versão: 1.1
Autores: GPT — redactor e auditor arquitectural; Miguel — fundador e ratificador
Bloco: B14.3C
Repositório: nexialistamentor/saas-fiscal-demo
Depende de: ADR-008 v1.5, ADR-009 v1.5 e ADR-010 v1.4
Baseline conhecido: HEAD = origin/main = 96bfc7b; 1559 passed / 0 failed / 8 skipped

1. Contexto

A fundação contratual soberana B14.0+B14.1 está institucionalizada através de:

AgentMission
MissionFactory
AgentExecutionResult
canonicalização
idempotência
validação cruzada
sanitização integral
BudgetPolicy
SourceRef

O agente legado:

app/agents/data_sanitization_agent.py

está registado no AgentRegistry, mas não executa trabalho útil no ciclo actual do scheduler.

O scheduler fornece apenas:

{
    "empresa_id": empresa_id,
    "insights": insights.get("oportunidades", []),
    "tabela_normativa": listar_base_normativa(db),
}

O DataSanitizationAgent espera campos fiscais como faturamento, custos, lucro e bases de cálculo. Consequentemente, no ciclo legado ele recebe contexto incompatível e retorna silenciosamente um resultado sem alertas.

Não existem testes próprios ou indirectos que invoquem o agente.

A decisão arquitectural ratificada para a brigada inicial é:

O DataSanitizationAgent não será alimentado pelo scheduler genérico. Será executado somente por missão explícita, no momento em que existir um contexto fiscal real a validar.

B14.3C não activa o agente no fluxo público. Cria apenas a camada soberana em sombra e dry_run.

2. Evidência do agente legado

Ficheiro: app/agents/data_sanitization_agent.py
Classe: DataSanitizationAgent
Instância: data_sanitization_agent
Identidade canónica L3: data_sanitization_agent
Versão L3 inicial: 1.0

Dimensão	Evidência
Interface	async def run(context: dict) -> Dict
Base de dados	Não acede
ORM ou Session	Não utiliza
HTTP externo	Não utiliza
Filesystem	Não utiliza
LLM	Não utiliza
Relógio interno	Não utiliza
Escrita	Não executa
Efeitos laterais	Nenhum
Testes próprios	Zero
Integração útil no scheduler	Nenhuma
Registry legado	Presente
Mensagens	Expõem valores recebidos
Constantes sem uso	LIMITE_ALIQUOTA e LIMITE_MVA
3. Problemas comprovados
3.1 Contexto livre e não versionado

O legado aceita qualquer dict, sem:

schema
versão
escopo
tenant
entidade
origem
autoridade
idempotência
3.2 Falso positivo em contexto vazio

Se nenhum dos campos fiscais esperados estiver presente, o agente retorna:

contexto_valido = True
total_alertas = 0

Nenhuma validação real ocorreu.

3.3 Exposição de dados

As mensagens legadas incluem valores financeiros e identificadores:

f"Campo '{campo}' não é numérico: {valor!r}"
f"Campo '{campo}' é negativo ({v:.2f})"
f"Faturamento ({v:.2f}) excede limite razoável"
f"empresa_id inválido: {empresa_id}"

Esses valores não podem atravessar a fronteira pública ou ser persistidos em texto livre.

3.4 Ausência de coerência entre empresa, entidade e tenant

O legado recebe empresa_id, mas não possui tenant_id, actor_id, entity_type ou entity_id.

3.5 Regras não implementadas

As constantes:

LIMITE_ALIQUOTA = 1.0
LIMITE_MVA = 5.0

não participam da lógica actual.

B14.3C não as transformará em novas regras. Permanecem dívida documentada do legado.

4. Decisão

Será criada uma implementação L3 paralela composta por:

AgentMission
→ adapter soberano
→ contexto tipado
→ motor determinístico puro
→ payload canónico
→ AgentExecutionResult
→ validação cruzada
→ sanitização integral

O adapter não chamará o agente legado.

O legado permanecerá byte a byte inalterado.

Não haverá reader, porque B14.3C:

não lê dados;
não consulta empresa;
não comprova propriedade;
não estabelece autorização;
apenas sanitiza um contexto previamente autorizado.

A futura integração num endpoint ou pipeline deverá provar, em ADR própria, qual guard, serviço ou fronteira autorizou:

actor_id
tenant_id
empresa_id

B14.3C não será integrado em rota pública, scheduler, registry soberano ou executor activo.

5. Identificadores canónicos
contract_version = "1.0"

mission_type = "sanitizar_contexto_fiscal"
target_agent = "data_sanitization_agent"

context_schema = "DataSanitizationContext"
context_version = "1.0"

output_schema = "DataSanitizationPayload"
output_version = "1.0"

scope = "tenant"
entity_type = "empresa"

authority_level = "leitura"

execution_mode permitido:
- "sombra"
- "dry_run"

execution_mode bloqueado:
- "activo"

requested_by = "system"

origem obrigatória:
- source_request_id presente e não vazio

origens proibidas:
- source_event_id
- schedule_slot

priority = "alta"

sources = []
budget_policy.allow_llm = False

ratification_id, authorized_by e authorization_role permanecem ausentes, porque não existe autoridade elevada nem execução activa.

agent_version_required, quando informado, deve ser exactamente:

1.0
6. Invariantes da missão
6.1 Tenant e actor
tenant_id:
- inteiro positivo
- booleano proibido

actor_id:
- inteiro positivo
- booleano proibido

actor_id == tenant_id
6.2 Entidade
entity_type == "empresa"

entity_id:
- inteiro positivo
- booleano proibido

entity_id == context.empresa_id

Esta igualdade comprova coerência interna da missão, mas não substitui a autorização externa da empresa.

6.3 Temporalidade
created_at:
- timezone-aware
- UTC

reference_at:
- obrigatório
- timezone-aware
- UTC
- não pode ser posterior a created_at

deadline:
- quando presente, não pode ser anterior a created_at
6.4 Origem

A missão exige exactamente:

source_request_id

Não aceita source_event_id nem schedule_slot.

B14.3C não será disparado por scheduler.

6.5 Autoridade e orçamento
authority_level = "leitura"
budget_policy.allow_llm = False
sources = []

Nenhum LLM, fonte normativa ou autoridade elevada é necessário para validar estrutura e domínio numérico.

7. Contrato de contexto

Será criado:

DataSanitizationContext

Características:

Pydantic
frozen=True
extra="forbid"
sem coerção silenciosa

Campos:

empresa_id — obrigatório, inteiro positivo não booleano

faturamento — opcional
custos — opcional
lucro_contabil — opcional
lucro — opcional
base_calculo — opcional
icms_pago — opcional
icms_devido — opcional
custo_fiscal_entradas — opcional

Os campos fiscais aceitam apenas valores brutos JSON controlados:

inteiro estrito
float estrito
string estrita
booleano estrito
null

O contrato não converte:

"1000" → 1000
True → 1
False → 0

O motor deve distinguir:

campo ausente
campo presente com null
campo presente com tipo inválido
campo presente com número válido

Valores não finitos não constituem contexto soberano serializável. Quando NaN ou infinito forem rejeitados pela canonicalização ou pela MissionFactory, a falha será tratada como contexto inválido antes da execução do motor.

B14.3C não enfraquecerá build_context_hash para aceitar valores não canónicos.

8. Campos e regras determinísticas

Ordem canónica de avaliação:

1. faturamento
2. custos
3. lucro_contabil
4. lucro
5. base_calculo
6. icms_pago
7. icms_devido
8. custo_fiscal_entradas
8.1 Campo ausente

Não produz alerta.

8.2 Campo presente como null

Produz:

CAMPO_NAO_NUMERICO
8.3 Booleano

True e False não são aceites como números.

Produzem:

CAMPO_NAO_NUMERICO
8.4 String ou outro tipo não numérico

Produz:

CAMPO_NAO_NUMERICO

Não existe conversão automática.

8.5 Valor negativo

Qualquer campo monetário numérico negativo produz:

CAMPO_NEGATIVO

Esta regra preserva o comportamento do legado. A validade fiscal de prejuízo ou saldo negativo não será redefinida neste bloco.

8.6 Faturamento acima do limite legado

Quando:

faturamento > 1_000_000_000

produz:

FATURAMENTO_ACIMA_LIMITE
8.7 Contexto sem campos fiscais

Quando nenhum dos oito campos fiscais estiver presente:

CONTEXTO_SEM_CAMPOS_FISCAIS

O contexto não pode ser declarado válido se nada foi efectivamente verificado.

9. Alertas canónicos

Será criado um modelo imutável:

DataSanitizationAlert

Campos:

codigo
severidade
campo
mensagem

campo aceita um dos oito nomes canónicos ou None.

Código	Severidade	Campo	Mensagem pública
CAMPO_NAO_NUMERICO	critico	Campo afectado	O campo fiscal recebido não contém um valor numérico válido.
CAMPO_NEGATIVO	alto	Campo afectado	O campo fiscal recebido contém um valor negativo.
FATURAMENTO_ACIMA_LIMITE	alto	faturamento	O faturamento informado excede o limite de validação configurado.
CONTEXTO_SEM_CAMPOS_FISCAIS	critico	None	Nenhum campo fiscal foi fornecido para sanitização.

Nenhum alerta pode conter:

valor recebido
empresa_id
tenant_id
actor_id
payload bruto
excepção
traceback
10. Resultado da sanitização
contexto_valido = True

somente quando:

total_alertas == 0

Qualquer alerta, independentemente da severidade, resulta em:

contexto_valido = False

B14.3C opera em sombra. Portanto, contexto_valido=False não bloqueia ainda o pipeline real.

Transformar a sanitização num gate activo exige ADR e ratificação posteriores.

11. Payload canónico

Será criado:

DataSanitizationPayload

Características:

Pydantic
frozen=True
extra="forbid"

Estrutura:

{
    "analysis_type": "sanitizacao_contexto_fiscal",
    "schema_type": "DataSanitizationPayload",
    "versao": "1.0",
    "empresa_id": int,
    "contexto_valido": bool,
    "total_alertas": int,
    "alertas": tuple[DataSanitizationAlert, ...],
    "publication_allowed": False,
}

Não inclui:

tipo_contribuinte
valores fiscais
contexto original
LLM
SourceRef
conteúdo normativo
12. Motor determinístico

Será criado:

DataSanitizationEngine

O motor:

recebe apenas DataSanitizationContext;
não recebe AgentMission;
não recebe relógio;
não recebe sessão;
não recebe ORM;
não recebe serviços;
não recebe LLM;
não lê ambiente;
não persiste;
não chama o legado.

Produz deterministicamente:

alertas
contexto_valido
total_alertas

A ordem dos alertas deve ser estável e seguir a ordem canónica dos campos.

13. Adapter L3

Será criado:

DataSanitizationAdapter

Responsabilidades:

validar fronteira da missão;
validar identificadores canónicos;
validar tenant, actor e entidade;
validar origem;
validar autoridade;
validar orçamento;
validar temporalidade;
validar e congelar o contexto;
bloquear modo activo;
executar o motor em sombra ou dry run;
validar payload contra contexto;
construir AgentExecutionResult;
executar validate_result_against_mission;
executar sanitização integral;
devolver resultado sem persistência.

O adapter não:

chama o agente legado;
abre BD;
consulta empresa;
escreve alerta;
altera scheduler;
publica conteúdo;
executa acções;
usa LLM;
converte identificadores com int();
devolve str(exc).
14. Validação independente

Será criada:

validate_data_sanitization_payload_against_context(
    context,
    payload,
)

A validação deve reconstruir independentemente:

empresa_id
alertas esperados
ordem dos alertas
contexto_valido
total_alertas
publication_allowed
analysis_type
schema_type
versao

Não pode limitar-se a chamar a mesma função principal do motor.

Qualquer divergência produz erro público estável:

AG_DATA_SANITIZATION_EXECUTION_ERROR
15. Resultados bloqueados

O adapter bloqueia antes de executar o motor quando:

Condição	Código
execution_mode="activo"	EXECUTION_MODE_NOT_AUTHORIZED
versão requerida diferente de 1.0	AGENT_VERSION_INCOMPATIBLE
target divergente	MISSION_TARGET_MISMATCH
mission type divergente	MISSION_TYPE_UNSUPPORTED
context schema divergente	CONTEXT_SCHEMA_UNSUPPORTED
context version divergente	CONTEXT_VERSION_UNSUPPORTED
output schema divergente	OUTPUT_SCHEMA_UNSUPPORTED
output version divergente	OUTPUT_VERSION_UNSUPPORTED
scope divergente	MISSION_SCOPE_UNSUPPORTED
tenant ausente ou inválido	MISSION_TENANT_REQUIRED
actor inválido	MISSION_ACTOR_UNSUPPORTED
actor diferente do tenant	MISSION_ACTOR_TENANT_MISMATCH
entidade inválida ou divergente	MISSION_ENTITY_UNSUPPORTED
origem inválida	MISSION_ORIGIN_UNSUPPORTED
autoridade divergente	MISSION_AUTHORITY_UNSUPPORTED
budget permite LLM	MISSION_BUDGET_UNSUPPORTED
sources não vazio	MISSION_SOURCES_UNSUPPORTED
reference_at inválido	MISSION_REFERENCE_AT_UNSUPPORTED
contexto inválido	AG_DATA_SANITIZATION_CONTEXT_INVALID

Resultado bloqueado:

status = "bloqueado"
payload = {}
retryable = False
actions_executed = []
llm_used = False

O literal exacto dos demais campos de AgentExecutionResult deve ser copiado do contrato real e dos adapters B14.3A/B, sem invenção.

16. Mensagens públicas
Código	Mensagem
AG_DATA_SANITIZATION_CONTEXT_INVALID	Não foi possível validar o contexto fiscal recebido.
AG_DATA_SANITIZATION_EXECUTION_ERROR	Não foi possível concluir a sanitização do contexto fiscal.

Não haverá enumeração pública de:

empresa inexistente
empresa de outro tenant
actor divergente
campo interno inválido
erro Pydantic
erro de canonicalização
17. Matriz obrigatória de resultado
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

publication_allowed=False permanece também no payload.

18. Preservação do legado

Antes do Commit 2:

Get-FileHash app\agents\data_sanitization_agent.py -Algorithm SHA256

O hash será registado como evidência.

Após implementação e testes, o mesmo hash deve ser obtido.

É proibido:

alterar o legado;
adicionar run_mission;
corrigir as mensagens legadas;
remover as constantes sem uso;
alterar o registry;
alterar o executor;
alterar o scheduler.

Essas decisões pertencem a blocos posteriores.

19. Ficheiros
Commit 1 — documental
docs/ADR-011-MIGRACAO-L3-DATA-SANITIZATION.md
Commit 2 — implementação
app/agents/contracts/data_sanitization.py
app/agents/engines/data_sanitization.py
app/agents/adapters/data_sanitization.py
tests/test_data_sanitization_mission_adapter.py

Não haverá reader.

Os __init__.py só podem entrar se forem realmente alterados e se a alteração for necessária para B14.3C.

20. Testes obrigatórios
20.1 Contrato da missão
contract version divergente;
target divergente;
mission type divergente;
schemas divergentes;
versões divergentes;
scope divergente;
tenant None, booleano, string, float, zero ou negativo;
actor inválido;
actor diferente do tenant;
entity type divergente;
entity id inválido;
entity id diferente de context.empresa_id;
origem ausente;
origens concorrentes;
schedule_slot proibido;
source_event_id proibido;
requested by divergente;
autoridade divergente;
budget com LLM;
sources não vazio;
reference at ausente, naïve, não UTC ou posterior a created at;
modo activo;
versão do agente incompatível.
20.2 Contexto
empresa_id inválido;
campo extra;
contexto sem campos fiscais;
campo ausente;
campo presente como null;
string numérica não convertida;
string não numérica;
booleano;
inteiro;
float;
zero;
negativo;
faturamento igual ao limite;
faturamento acima do limite.
20.3 Motor
zero alertas para contexto válido;
alerta de contexto vazio;
alerta não numérico;
alerta negativo;
alerta de faturamento;
múltiplos alertas;
ordem determinística;
nenhum valor bruto nas mensagens;
nenhum identificador nas mensagens;
nenhuma dependência proibida.
20.4 Payload
empresa correcta;
total exacto;
ordem exacta;
contexto_valido=True apenas sem alertas;
contexto_valido=False com qualquer alerta;
publication_allowed=False;
adulteração de qualquer campo detectada.
20.5 Adapter
sombra executa;
dry run executa;
activo bloqueia;
legado nunca é chamado;
sem persistência;
sem LLM;
sem acções;
sem integração em registry, executor ou scheduler;
validação cruzada;
sanitização integral;
nenhuma fuga de excepção.
20.6 Integridade
SHA256 do legado;
ausência de run_mission;
ausência de imports proibidos;
ausência de referências ao adapter L3 no fluxo legado;
somente ficheiros ratificados no commit.
21. Estratégia de commits
Commit 1
docs: ratificar ADR-011 migracao L3 DataSanitizationAgent (B14.3C)

Escopo exacto:

docs/ADR-011-MIGRACAO-L3-DATA-SANITIZATION.md
Commit 2
feat: adapter L3 DataSanitizationAgent em sombra (B14.3C)

Escopo exacto:

app/agents/contracts/data_sanitization.py
app/agents/engines/data_sanitization.py
app/agents/adapters/data_sanitization.py
tests/test_data_sanitization_mission_adapter.py
22. Critério de conclusão

B14.3C só estará fechado quando houver:

ADR-011 ratificada e commitada
Commit 1 atómico
Commit 2 atómico
testes direccionados verdes
suite global >= 1559 passed
0 failed
8 skipped ou número justificado
SHA256 do legado preservado
registry inalterado
executor inalterado
scheduler inalterado
nenhuma integração activa
nenhuma escrita
nenhum LLM
HEAD = origin/main

O working tree deve ficar sem alterações pertencentes a B14.3C.

Qualquer alteração preexistente fora do escopo deve permanecer documentada, preservada e fora dos commits.

23. Exclusões

B14.3C não decide:

activação no scheduler;
integração no run_all;
integração em endpoint público;
persistência automática;
publicação;
modo activo;
validação de XML;
comparação XML versus motor;
consistência fiscal;
regras de alíquota ou MVA;
elegibilidade MEI;
CNAE;
regimes tributários;
alterações em motores existentes;
autorização da empresa na BD;
remoção do agente legado do registry.

A observação OBS-MOTOR-MEI-001 permanece aberta e adiada para o futuro bloco de motores empresariais.

24. Ratificação
Papel	Nome	Estado
Fundador e Arquitecto Soberano	Miguel	⬜ PENDENTE
Auditor e Redactor Arquitectural	GPT