# ADR-001 — Governação da Canonicidade

**Status:** Proposto

**Data:** 2026-06-18

**Ratificação institucional:** Autoridade Final de Produto (Constituição Art. X)

**Auditoria arquitectural:** Papel de Auditoria Independente

**Evidência:** Produzida por leitura directa de código e documentação

**Pré-requisito:** DC-001 (Canonicidade Operacional Sem Institucionalização)

---

## 1. CONTEXTO

DC-001 provou, por evidência directa de código e documentação, que a
Plataforma Tributária L2 possui canonicidade operacional — declarações
funcionais sobre qual caminho, motor ou fonte de dados deve prevalecer —
sem possuir canonicidade institucionalizada.

A fonte actual dessa canonicidade operacional é `.cursorrules`, que
declara explicitamente uma "ARQUITETURA OFICIAL (NÃO VIOLAR)" para o
pipeline de processamento de XML e para `tabela_mva` como fonte de
verdade normativa.

`.cursorrules` não integra a hierarquia normativa definida no Artigo XI
da Constituição (Lei → Constituição → ADRs → Invariantes → Contratos →
Código → Testes). Nenhum ADR, invariante ou contrato adoptou
formalmente o que `.cursorrules` declara. A declaração existe; o
mandato institucional para a fazer, não.

Esta lacuna não é teórica. O MAPA_AUTORIDADES_L2.md identificou três
padrões estruturais recorrentes (PAD-001, PAD-002, PAD-003) e o
PM_L2_001_PRE_MORTEM_ESTRATEGICO.md identificou sete mecanismos de
falha (PM-01 a PM-07). Em quatro deles — PM-02, PM-05, PM-06, PM-07 —
a mesma pergunta de fundo reaparece, formulada de formas diferentes:
quem tem legitimidade para declarar o que a instituição reconhece
como verdade, quando existem caminhos, normas ou intervenções
concorrentes para o mesmo facto?

A pergunta institucional central deste ADR não é *quem calcula* nem
*quem executa*. É *quem tem legitimidade para declarar o que é verdade
dentro do sistema*.

---

## 2. DECISÃO

### 2(a) — Canonicidade institucional é distinta de canonicidade operacional

Canonicidade operacional é uma declaração funcional: um router escolhe
um motor, um comentário identifica um caminho como "oficial", um teste
cobre um componente e não outro. Estas declarações podem estar
tecnicamente correctas e ainda assim serem institucionalmente órfãs —
sem mandato que as torne vinculativas para toda a plataforma e todos
os seus colaboradores, presentes e futuros.

Canonicidade institucional é uma declaração que sobrevive a quem a fez.
Não depende de quem escreveu o código, quem geriu a sessão, ou qual
geração de ferramentas (humanas ou de IA) estava activa no momento.
Depende apenas do processo descrito em 2(b).

### 2(b) — Processo exigido para qualquer declaração de canonicidade

Toda declaração de canonicidade institucional exige, sem excepção,
as três etapas seguintes, nesta ordem:

Evidência → Auditoria Independente → Ratificação Institucional

**Evidência:** prova directa, reproduzível, extraída do código, dados
ou documentação real do sistema — nunca suposição, nunca intenção
declarada sem verificação.

**Auditoria Independente:** revisão da evidência por um papel distinto
de quem a produziu, com mandato de verificar coerência arquitectural,
não apenas correcção factual.

**Ratificação Institucional:** confirmação formal, registada e datada,
por quem exerce a Autoridade Final de Produto.

Nenhuma das três etapas é dispensável. Nenhuma substitui as outras.
Evidência sem auditoria é opinião documentada. Auditoria sem
ratificação é recomendação sem efeito. Ratificação sem evidência e
auditoria prévias é decisão arbitrária disfarçada de processo.

### 2(c) — O papel de Ratificação é institucional, não pessoal

Este ADR institucionaliza um papel, não uma pessoa. O papel de
Ratificação Institucional é hoje exercido por Miguel, na sua qualidade
de Autoridade Final de Produto (Constituição Art. X). O ADR não vincula
este papel a Miguel como indivíduo — vincula-o à função, para que a
canonicidade da plataforma continue válida independentemente de quem,
no futuro, ocupar esse papel, seja humano ou outro tipo de autoridade
institucional que venha a ser formalmente designada.

O mesmo princípio aplica-se ao papel de Auditoria Independente,
hoje exercido por revisão arquitectural externa ao processo de
produção de código.

### 2(d) — `.cursorrules` desce na hierarquia

`.cursorrules` deixa de ser fonte de canonicidade e passa a ser
consequência de canonicidade já ratificada. Nenhuma regra em
`.cursorrules` é válida por si própria; cada regra deve ser
rastreável a um ADR que a originou.

Hierarquia resultante:

Constituição
↓
ADRs
↓
Invariantes
↓
Contratos
↓
.cursorrules (implementa, não declara)
↓
Código

Regras existentes em `.cursorrules` à data deste ADR permanecem
operacionalmente válidas até serem formalmente ratificadas ou
substituídas por ADRs específicos — mas deixam de ter autoridade
institucional própria a partir da adopção deste documento.

`.cursorrules` não pertence à camada de decisão institucional.
Pertence à camada de execução operacional assistida — orienta
ferramentas de IA e automação, mas não governa a instituição.

### 2(e) — Critério de transição: experimental → canónico

Um caminho, motor ou fonte de dados só pode ser declarado canónico
após cumprir o processo completo de 2(b). Não existe canonicidade
por omissão, por antiguidade no código, ou por ser o caminho mais
usado — apenas por ratificação explícita.

### 2(f) — Critério de transição: canónico → legado

Um caminho canónico só perde esse estatuto através do mesmo processo
de 2(b) aplicado à decisão de o substituir. A marcação `DEPRECATED`
no código (como já existe em `mei_engine.py`) é evidência de
intenção, não substituto da ratificação formal.

### 2(g) — Protocolo para declarações concorrentes

Quando duas ou mais declarações de canonicidade coexistem para o
mesmo facto — caso já comprovado em PAD-001, PAD-002 e PAD-003 — a
resolução exige que o caso passe pelo processo completo de 2(b).
Nenhuma divergência se resolve por precedência implícita (código
mais recente, caminho mais usado, ou decisão informal).

### 2(h) — Princípio de Resolução

Quando Evidência, Auditoria e Ratificação entram em conflito entre
si durante o processo de 2(b), a decisão final deve ser explicitamente
registada, justificada por escrito, e vinculada ao ADR ou documento
de decisão que a originou.

Nenhuma etapa do processo pode substituir, ignorar ou invalidar
silenciosamente outra etapa. Um conflito não resolvido não produz
canonicidade — produz um caso em aberto, que deve permanecer
declarado como tal até ser formalmente fechado.

Este princípio existe para impedir que "Ratificação" seja interpretada,
no futuro, como autoridade absoluta que dispensa evidência ou
auditoria — o que reproduziria exactamente o problema que este ADR
foi escrito para resolver.

---

## 3. CONSEQUÊNCIAS

A partir da adopção deste ADR:

- Nenhuma declaração futura de canonicidade é institucionalmente
  válida sem ter passado pelas três etapas de 2(b).

- `.cursorrules` deve, progressivamente, referenciar os ADRs que
  justificam cada uma das suas regras.

- Qualquer ADR subsequente que declare um caminho específico como
  canónico (por exemplo, sobre MEI, MVA, ou o pipeline XML) deve
  demonstrar que cumpriu o processo de 2(b), citando explicitamente
  a evidência, a auditoria e a ratificação que o sustentam.

- PM-02, PM-05, PM-06 e PM-07 passam a ter um mecanismo institucional
  através do qual podem ser resolvidos — mas este ADR não os resolve.

---

## 4. O QUE ESTE ADR NÃO DECIDE

Este ADR não declara qual caminho, motor, ou fonte de dados é
canónico em nenhum caso concreto. Não resolve:

- PM-02 — qual caminho prevalece entre MEI legado/oficial, ou entre
  os caminhos paralelos de InsightEngine, estoque, ou normas

- PM-05 — qual fonte normativa (BD ou JSON legado) é fonte de verdade

- PM-06 — como a recomendação de regime ou de homologação se conecta
  à execução

- PM-07 — qual classificação (Legítima, Insuficiência de Evidência,
  Arquitectural, Artificial) se aplica a cada caso de intervenção
  humana já identificado

Estas decisões pertencem a ADRs subsequentes, e cada um deles deve
demonstrar conformidade com o processo definido neste documento.

---

*Este ADR é o primeiro da Plataforma Tributária L2. Não fala de
imposto, de XML, ou de MVA. Fala de legitimidade institucional —
porque sem ela, qualquer decisão técnica posterior nasce sem
fundamento que sobreviva a quem a tomou.*

*O conhecimento não está na conversa. Está no repositório.*
