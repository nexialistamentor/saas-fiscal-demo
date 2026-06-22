# ADR-003 — Política de Acesso Contador ↔ Empresa/Documento

**Data:** 2026-06-20

**Estado:** Decidido. Proibições efectivas imediatamente; modelo
  operacional concreto a implementar em DT-CONTADOR-01.

**Natureza:** Decisão arquitectural de autorização e privacidade
  fiscal. Estabelece os limites do que um contador aprovado pode
  fazer no sistema, e proíbe formalmente o padrão actual de
  claim-by-ID aberto.

**Base:** auditoria de `app/routers/contador_router.py`,
  `app/services/homologacao_service.py`, e análise comparativa com
  o padrão de captura operacional documentado no caso Pizza Hut.

---

## CONTEXTO

O sistema actual permite que **qualquer contador aprovado**
(`User.role == "contador"` + `PerfilContador.status == "aprovado"`)
assuma **qualquer documento** em `fila_homologacao`, desde que
conheça (ou consiga adivinhar/enumerar) o `documento_id`.

Não existe verificação de vínculo prévio entre o contador e a
empresa dona do documento. Não existe filtro regional, de
especialidade ou de reputação. Não existe autorização explícita do
cliente para que aquele contador específico veja os seus dados
fiscais.

A única "protecção" actual é **ausência de listagem global** — o
sistema não expõe a fila de documentos não-assumidos. **A ausência
de listagem global reduz a exposição acidental, mas não constitui
autorização.** Enquanto o endpoint aceitar `documento_id` directo
sem vínculo, o risco permanece — só está latente.

---

## O PADRÃO QUE ESTAMOS A PROIBIR

> Contador aprovado + `documento_id` conhecido ou tentado +
> ausência de vínculo prévio = capacidade de capturar documento
> fiscal sensível.

Isto é estruturalmente análogo ao padrão Pizza Hut / Efeito Cobra:
o operador, dotado de permissão genérica que parecia inofensiva,
aprende a optimizar contra a plataforma — neste caso, capturando
documentos antes que o cliente tenha oportunidade de escolher quem
tratará dos seus dados.

A consequência prevista, se este padrão chegar ao Bloco 13:

- Corrida operacional entre contadores por documentos recentes
- Apropriação de clientes sem o conhecimento ou consentimento destes
- Tratamento de documentos fiscais sensíveis por contadores sem
  vínculo prévio com a empresa
- Risco real de vazamento de dados fiscais entre contadores
  concorrentes
- **Assimetria de poder estrutural:** o contribuinte perde o
  controlo sobre quem acede e interpreta os seus dados fiscais,
  sem saber quem capturou, porquê capturou, ou se havia alternativa
- Perda irreversível de confiança institucional

---

## PRINCÍPIO DE AUTORIZAÇÃO (constitucional para o sistema)

Esta ADR estabelece quatro camadas hierárquicas de autorização que
qualquer acto de contador sobre documento de empresa deve satisfazer,
e uma quinta dimensão auxiliar obrigatória sobre a natureza do
vínculo:

```
Role         define capacidade   (contador aprovado pode, em geral, homologar)
Vínculo      define autorização  (este contador, sobre esta empresa)
Escopo       define limite       (este documento, neste momento, para este acto)
Auditoria    prova o acto        (quem fez o quê, quando, com que parecer)

Temporalidade qualifica o vínculo (activo, revogado, expirado, suspenso)
```

As quatro camadas principais são **conjuntivas**, não alternativas.
Um acto que satisfaça role mas não vínculo é **não autorizado**.
Um acto que satisfaça vínculo mas não escopo é **não autorizado**.

A dimensão de Temporalidade não é uma quinta camada paralela — é
um atributo obrigatório do próprio vínculo. **Todo vínculo
contador-empresa deve ter estado declarado e temporalidade
verificável:**

- `activo` — vínculo em vigor, acesso autorizado dentro do escopo
- `revogado` — vínculo encerrado por acto explícito do cliente,
  admin ou auditoria; **não pode continuar a produzir acesso, nem
  retroactivamente**
- `expirado` — vínculo cujo período de validade declarado terminou
- `suspenso` — vínculo temporariamente desactivado, recuperável

Vínculo sem temporalidade declarada é vínculo eterno por omissão,
e isso é o erro estrutural que esta ADR proíbe junto com o
claim-by-ID aberto.

---

## DECISÃO PRINCIPAL — Claim-by-ID Aberto está PROIBIDO

A partir desta ADR, o comportamento actual de `POST
/contador/homologacoes/{documento_id}/assumir`, que permite a
qualquer contador aprovado assumir qualquer documento por ID, está
formalmente **proibido para abertura ao utilizador real**.

A proibição não se limita a "assumir". **Aplica-se a qualquer acto
de contador sobre documento fiscal sensível**, incluindo, sem se
limitar a:

- Listar
- Visualizar
- Assumir
- Homologar
- Rejeitar
- Descarregar
- Comentar
- Emitir parecer
- Reabrir homologação encerrada

Qualquer endpoint futuro que envolva qualquer destes actos sobre
documento de empresa deve verificar Role + Vínculo (activo) +
Escopo + Auditoria, conjuntivamente, antes de proceder.

A proibição é efectiva imediatamente — o endpoint actual não pode
ser exposto no Bloco 13 (piloto controlado) na sua forma actual.

A implementação técnica desta proibição (DT-CONTADOR-01) decidirá
**como** bloquear (revogação do endpoint, exigência de novo header
de autorização, redesenho do fluxo, ou substituição por outro
endpoint). Mas a regra de autorização declarada por esta ADR não
depende da implementação — está em vigor desde já.

---

## REGRA FUNDAMENTAL — Vínculo precede acesso

> O vínculo deve preceder o acesso; se nasce depois do acesso, não
> é autorização — é captura regularizada.

Não é admissível "vínculo implícito criado pelo primeiro acesso do
contador" — esse padrão é precisamente o problema que esta ADR
proíbe, disfarçado de solução. O facto de o sistema *registar* que
o contador X assumiu o documento Y não constitui autorização
retroactiva para o ter assumido.

A sequência institucionalmente correcta é, sempre:

```
1. Vínculo estabelecido (por um dos modelos admissíveis abaixo)
2. Vínculo verificado no momento do acto
3. Acto autorizado e executado
4. Auditoria registada
```

Inverter os passos 1 e 3 — primeiro acto, depois vínculo — é
inverter a soberania do contribuinte.

---

## MODELOS DE AUTORIZAÇÃO ADMISSÍVEIS (hierarquia de soberania)

Os modelos abaixo estão ordenados por grau de soberania conferida
ao contribuinte, do mais soberano para o mais permissivo. Qualquer
um (ou combinação) é admissível para implementação em
DT-CONTADOR-01, **desde que satisfaça vínculo prévio com
temporalidade declarada.**

### Modelo A — Cliente escolhe/autoriza contador (preferencial)
A empresa selecciona explicitamente, na plataforma, qual contador
parceiro tem autorização para ver e homologar os seus documentos.
Vínculo: tabela `contador_empresa_autorizacao` (ou equivalente)
criada pelo cliente, com campos `criado_em`, `estado`, `revogado_em`.
Sem este registo no estado `activo`, o contador não vê o documento.
**É o modelo mais alinhado com soberania do contribuinte.**

### Modelo B — Admin atribui contador (admissível para piloto)
Autoridade Operacional (definida em DC-004) atribui contador a
empresa/documento caso a caso. Adequado para piloto controlado com
1-3 empresas e 1 contador. Vínculo é decisão administrativa,
registada em tabela própria com temporalidade. **Menos escalável
que Modelo A; aceitável para piloto, mas não como visão final.**

### Modelo C — Pool regional com restrições explícitas
Contador só vê/assume documentos de empresas dentro do seu âmbito
regional (UF do `crc_uf` do contador, ou regra explícita
declarada). **Pool regional nunca dispensa auditoria nem vínculo
operacional** — "mesma UF" é critério de elegibilidade, não
autorização por si só. Exige, ainda assim, registo de vínculo
activo entre contador e empresa antes do acesso.

### Modelo D — Composição (futuro)
Qualquer combinação dos anteriores (ex.: cliente escolhe entre
contadores do pool regional aprovado pelo admin). Decisão de
DT-CONTADOR-01.

---

## MODELOS NÃO ADMISSÍVEIS

- **Claim-by-ID aberto** (estado actual) — proibido por esta ADR
- **Pool aberto puro** (qualquer contador vê tudo, primeiro a ver
  ganha) — viola privacidade do cliente
- **Auto-atribuição por proximidade temporal** (contador X assume
  porque foi o mais rápido, sem critério de vínculo) — viola
  princípio de vínculo
- **Vínculo implícito criado pelo primeiro acesso do contador** —
  é captura regularizada, não autorização (ver Regra Fundamental
  acima)
- **Vínculo eterno por omissão** — sem temporalidade declarada,
  qualquer vínculo criado hoje passa a ser perpétuo amanhã
- **Qualquer mecanismo que dependa apenas de ocultar IDs** —
  segurança por obscuridade, viola desenho soberano

---

## RELAÇÃO COM A CONSTITUIÇÃO TRIBUTÁRIA L2

Esta ADR materializa, para o domínio de contador↔documento, três
artigos já estabelecidos na Constituição:

- **Art. I (Soberania do Contribuinte):** a empresa é dona dos seus
  dados fiscais; ninguém os vê sem vínculo autorizado pela própria
  empresa, **ou por Autoridade Operacional formalmente delegada
  (DC-004)** — esta delegação é admissível apenas no piloto
  controlado e dentro dos limites de admissibilidade declarados em
  DC-004
- **Art. III (Não Causar Dano):** dado fiscal exposto a contador
  sem vínculo é vector de dano real
- **Art. V (Auditabilidade):** quem viu, quem assumiu, quem
  decidiu — todos os actos devem ter trilha completa

A camada "Vínculo" desta ADR é a expressão técnica directa do
Art. I para o subsistema contador.

---

## EFEITO IMEDIATO

A partir desta ADR:

1. O endpoint `POST /contador/homologacoes/{documento_id}/assumir`
   está marcado como **bloqueante para Bloco 13** — não pode
   abrir ao piloto na sua forma actual.

2. Qualquer endpoint futuro que permita acesso de contador a
   documento de empresa deve satisfazer Role + Vínculo (activo) +
   Escopo + Auditoria, conjuntivamente.

3. A implementação concreta (escolha entre Modelos A/B/C/D, código,
   migration, endpoint) é matéria de DT-CONTADOR-01 — não decidida
   aqui.

4. **Até DT-CONTADOR-01 estar implementado, qualquer uso operacional
   dos endpoints `/contador/*` na sua forma actual deve ser tratado
   como interno e excepcional**, restrito a teste com Autoridade
   Operacional como única contraparte. **Não é adequado ao piloto
   com utilizadores reais.** Esta cláusula impede a interpretação:
   *"já que a implementação fica para depois, podemos usar assim
   temporariamente com clientes reais"* — não pode.

---

## PRINCÍPIO DE FECHO

> Permissão sem vínculo vira captura.
> Capacidade técnica nunca substitui autorização institucional.

Estes princípios ficam registados como aforismos institucionais da
plataforma, aplicáveis a qualquer subsistema futuro (não apenas
contador) onde role conceda capacidade sem vínculo específico de
autorização.

---

*O conhecimento não está na conversa. Está no repositório.*
