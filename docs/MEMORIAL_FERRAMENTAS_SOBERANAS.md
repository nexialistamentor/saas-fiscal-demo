# MEMORIAL DE FERRAMENTAS SOBERANAS

## Finalidade

Este memorial registra ferramentas mec?nicas, determin?sticas e reutiliz?veis
criadas no projeto Fisco Soberano.

O objetivo ? impedir:
- reconstru??o de ferramentas j? existentes;
- retorno a auditorias manuais repetitivas;
- perda de conhecimento operacional;
- uso de uma ferramenta al?m da autoridade que ela realmente possui;
- classifica??o GREEN quando a pr?pria m?quina n?o conseguiu analisar algo.

## Regra de qualifica??o

Uma ferramenta s? pode ser marcada como `QUALIFICADA` depois de possuir:

1. finalidade e escopo expl?citos;
2. contrato de entrada e sa?da;
3. comportamento determin?stico;
4. testes permanentes;
5. falha fechada para incapacidade de an?lise;
6. limita??es conhecidas documentadas;
7. autoridade explicitamente delimitada;
8. prova de que n?o produz GREEN por aus?ncia silenciosa de evid?ncia.

Ferramentas em desenvolvimento permanecem como `EM_CONSTRUCAO`.

---

# FERRAMENTA-001 ? MEI Normative Census

**Status:** EM_CONSTRUCAO

**Implementa??o:**
`app/scripts/mei_normative_census.py`

**Testes:**
`tests/test_mei_normative_census.py`

## Finalidade

Construir automaticamente o censo de elementos normativos utilizados pelo
motor MEI, substituindo arqueologia manual de constantes, call-sites,
bindings, fontes, vig?ncia e autoridade.

## Princ?pios

- sem rede;
- sem LLM;
- sem altera??o de produ??o;
- an?lise determin?stica do reposit?rio;
- incapacidade de an?lise deve bloquear ou resultar em UNRESOLVED;
- aus?ncia silenciosa de evid?ncia ? proibida;
- a ferramenta descobre e verifica; n?o possui autoridade fiscal.

## Capacidade implementada at? o momento

### Descoberta de constantes

Descobre por AST as constantes f?sicas definidas em:

`app/services/tax_engines/mei_constants.py`

Estado observado durante constru??o:

`constants_total = 9`

### Descoberta de call-sites

Varre arquivos Python em `app/` e associa refer?ncias ?s constantes can?nicas.

### Fail-closed de parsing

Arquivo Python ileg?vel, inv?lido ou imposs?vel de analisar n?o ? ignorado.

A execu??o deve falhar com:

`MEI_NORMATIVE_CENSUS_SCAN_FAILED`

Teste permanente j? existente prova essa propriedade.

### Identidade can?nica

Foi detectado por RED que simples igualdade lexical produzia falso positivo
quando outro m?dulo definia uma vari?vel hom?nima.

A implementa??o foi alterada para exigir v?nculo por importa??o can?nica.

**Estado:** corre??o implementada, ainda aguardando reexecu??o do RED.

## Falhas/riscos ainda a eliminar antes de QUALIFICADA

- provar que hom?nimos n?o geram falso positivo;
- provar imports diretos;
- provar imports com alias;
- provar acesso via m?dulo;
- bloquear imports can?nicos em escopos que o analisador n?o resolve;
- tratar acesso din?mico/reflexivo de forma fail-closed;
- detectar defini??es can?nicas duplicadas ou amb?guas;
- provar cobertura completa do scan;
- impedir que `call_sites=[]` seja interpretado como aus?ncia real quando
  a an?lise n?o foi comprovadamente completa;
- classificar alcance real at? c?lculo/publica??o;
- cruzar bindings normativos;
- cruzar fonte, vers?o, vig?ncia e jurisdi??o;
- produzir estado final AUTHORIZED / BLOCKED / UNRESOLVED;
- manter sa?da est?vel e testada.

## Autoridade

`MEI Normative Census` n?o cria, altera nem interpreta verdade fiscal.

Pode:
- descobrir;
- relacionar;
- verificar;
- bloquear;
- produzir evid?ncia estrutural.

N?o pode:
- criar regra tribut?ria;
- inferir regra fiscal de comportamento de usu?rio;
- substituir fonte oficial;
- conceder autoridade normativa por conta pr?pria;
- ratificar decis?o soberana.

## Reutiliza??o potencial

A arquitetura desta ferramenta pode ser generalizada para:

- outros motores tribut?rios;
- census de constantes normativas;
- rastreamento de regras at? call-sites;
- auditoria de provenance/bindings;
- detec??o de c?digo fiscal sem autoridade;
- catracas de migra??o/schema;
- invent?rios de invariantes e enforcement boundaries.

A generaliza??o deve ocorrer somente depois que a vers?o MEI estiver
qualificada e suas invariantes estiverem comprovadas.

## Atualizacao V1 — 2026-08-18

**Status:** PRONTA_PARA_AUDITORIA (ratificacao externa pendente)

### Capacidades comprovadas

- classificacao AST deterministica por uso canonico, preservando aliases;
- categorias `DECISION`, `CALCULATION`, `PRESENTATION`, `INFRASTRUCTURE`
  e `UNRESOLVED`;
- `UsageRecord` estavel com constante, arquivo, linha, categoria e evidencia;
- descoberta local restrita a artefatos cujo objeto raiz valida como
  `NormativeBindingBatchRequest`;
- delegacao integral da decisao normativa a
  `NormativeBindingBatchRequest` e `validar_bindings_normativos()`;
- estados por item `AUTHORIZED`, `BLOCKED`, `UNRESOLVED` e
  `NON_NORMATIVE`;
- output canonico estavel sob reexecucao e permutacao da ordem dos bindings
  cobertos pelo contrato testado;
- acumulacao de findings estruturais e normativos numa unica execucao.

### Invariantes fail-closed

- scan incompleto sempre bloqueia o estado global;
- zero findings estruturais nao concede autoridade normativa;
- uso fiscal alcancavel sem binding resulta em `BLOCKED`;
- contexto AST nao coberto resulta em `UNRESOLVED`;
- ausencia de usos nao e interpretada como `NON_NORMATIVE`;
- nenhum item pode ser `AUTHORIZED` se
  `validar_bindings_normativos().autorizado_fundamentar_decisao` for falso;
- identificadores, fonte, target, jurisdicao, versao, risco, vigencia,
  completude e conflitos sao avaliados pelo contrato canonico, nao pelo
  Census;
- nenhuma data de referencia e inventada: binding que exige avaliacao
  temporal sem data resulta em `UNRESOLVED_TEMPORAL`;
- `NON_NORMATIVE` exige usos classificados exclusivamente como
  infraestrutura.
- call-sites estruturais e usages semanticos sao reconciliados pela identidade
  `(constante_id, arquivo, linha)`; unaccounted, orphan ou duplicate geram
  finding e bloqueiam o censo.

### Formato de saida

Mantem `schema_version`, `status`, `scan_complete`, `files_discovered`,
`files_parsed`, `constants_total`, `findings_total`, `findings` e `constants`.
Acrescenta `usages_total`; cada constante inclui usos, categorias,
`normative_reachability`, bindings, resumo de autoridade da fonte,
`final_status` e `reasons`. O bloco `reconciliation` publica totais e as
identidades unaccounted, orphan e duplicate em ordem canonica.

### Testes e resultado real observado

Suite focal: 34 testes aprovados. O scan real observou 231/231 arquivos,
9 constantes e 32 usos, reconciliados integralmente com os 32 call-sites
estruturais. Estado global: `BLOCKED`.

Por item: 2 `BLOCKED`, 7 `UNRESOLVED`, 0 `AUTHORIZED` e 0
`NON_NORMATIVE`. Razoes: 2 `BINDING_MISSING`, 6 `USAGE_UNRESOLVED` e
1 `NO_USAGE_EVIDENCE`. Nao foram encontrados bindings locais para as
constantes; nenhuma fonte recebeu autoridade por inferencia.

### Limitacoes conhecidas

- nao segue propagacao por alias local, reexportacao, escape ou fronteira de
  chamada: essas situacoes continuam bloqueadas pelas protecoes estruturais;
- chamadas nao explicitamente transformativas permanecem `UNRESOLVED`;
- valores transformados e atribuidos que voltam a circular sao marcados como
  `UNRESOLVED_LINEAGE`; nao existe data-flow geral;
- temporalidade so pode autorizar quando uma data de referencia e fornecida
  explicitamente ao avaliador;
- a descoberta de bindings nao pesquisa formatos arbitrarios: aceita apenas
  o envelope canonico `NormativeBindingBatchRequest` na raiz. Targets fora
  desse envelope produzem `BINDING_DISCOVERY_UNRESOLVED`;
- o manifesto descreve fontes e targets autorizados, mas nao e tratado como
  binding persistido;
- o censo nao ratifica fonte, verdade fiscal, G2, qualificacao ou candidatura
  a piloto.

---

## Regra para novas ferramentas

Toda nova ferramenta mec?nica reutiliz?vel deve receber uma entrada neste
memorial no momento em que come?a a adquirir valor reutiliz?vel.

Nunca considerar a exist?ncia do c?digo equivalente ? qualifica??o da
ferramenta.
