# REPORT-015  Auditoria para fecho institucional do ROADMAP_OPS_AGENTES v2.1

## 1. Identificação da missão

Missão: MISSION-015. Natureza: auditoria documental e institucional para
preparação de eventual fecho do ROADMAP_OPS_AGENTES v2.1. Data da auditoria:
2026-07-24. Executor técnico: Codex. Autoridade de auditoria e supervisão:
GPT. Autoridade humana final: Miguel.

O único artefacto criado é este REPORT-015. A missão não altera o roadmap,
ADRs, reports anteriores, código, testes, configuração, migrations ou
dependências.

## 2. Natureza e fronteira de prova

Esta auditoria prova existência, conteúdo literal, identidade byte a byte,
estados declarados, relações cronológicas, cadeia de autoridade, gates e
coerência documental. Não revalida código, produção, disponibilidade,
segurança operacional, isolamento entre utilizadores, backups, desempenho,
cobertura efectiva de testes, endpoints, Railway, Vercel, integração,
pagamentos ou deploy.

As afirmações técnicas herdadas são classificadas como PROVADO
DOCUMENTALMENTE POR EVIDÊNCIA ANTERIOR e NÃO REVALIDADO OPERACIONALMENTE nesta
missão. Evidência histórica não constitui garantia operacional presente.

## 3. Baseline de execução

Foi confirmada antes da leitura material:

- branch literal `main`;
- HEAD `84cf6daa31deaaacfc34120e91e72a7cb50a1950`;
- `origin/main` `84cf6daa31deaaacfc34120e91e72a7cb50a1950`;
- working tree inicial limpo;
- stage inicial vazio.

Classificação: PROVADO. Esta é a baseline da MISSION-015, não a baseline
histórica de criação da v2.1.

## 4. Baseline histórica do roadmap

O ROADMAP v2.1 declara como baseline histórica de criação
`c6ce08147c9c9254c7a59cc0dd60188412ca9ae2`. O REPORT-014 confirma que a v2.1
foi criada nessa baseline. O commit documental posterior
`84cf6daa31deaaacfc34120e91e72a7cb50a1950` contém a reconciliação e o fecho
documental que constituem a baseline desta auditoria.

Sequência preservada:

1. criação histórica da v2.1 em
   `c6ce08147c9c9254c7a59cc0dd60188412ca9ae2`;
2. reconciliação e fecho documental no commit
   `84cf6daa31deaaacfc34120e91e72a7cb50a1950`;
3. execução da MISSION-015 sobre esse commit;
4. eventual commit posterior de reconciliação ou fecho do REPORT-015,
   dependente de autorização própria.

Classificação: COERENTE. A baseline histórica anterior não é defeito e não
deve ser substituída retroactivamente pela baseline de auditoria.

## 5. Fontes e hashes

Foram lidos integralmente o ROADMAP, ADR-011, ADR-016, REPORT-011,
REPORT-013, REPORT-014 e AGENTS.md. Foram também lidas integralmente as fontes
institucionais directamente citadas pelo roadmap como autoridade, estado,
gate, decisão, ratificação, bloqueio ou conclusão, incluindo ADR-008 a
ADR-010, ADR-012 a ADR-015, ADR-017, ADR-018, REPORT-001 a REPORT-010,
B13-OPS-12 e CCS-001. O ROADMAP_ABERTURA_UTILIZADORES foi lido para delimitar
Pilot 0, utilizador real controlado e abertura ampla.

Foi lido integralmente o conteúdo documental introduzido ou alterado pelo
commit de execução. A mensagem do commit foi tratada apenas como evidência
cronológica auxiliar.

Os cinco hashes fixados coincidiram antes da auditoria material. Classificação:
PROVADO.

## 6. Hierarquia de evidência

A hierarquia aplicada foi:

1. declaração literal e identificável de Miguel;
2. parecer literal do GPT;
3. ADRs, contratos canónicos e invariantes ratificados no seu âmbito;
4. estado interno dos documentos institucionais;
5. reports de auditoria, execução e reconciliação;
6. conteúdo documental dos commits;
7. mensagens de commit como cronologia auxiliar;
8. código e testes como evidência técnica anterior limitada;
9. inferência sem autoridade, que não pode criar decisão.

Silêncio documental, existência de classe, registry, missão, resultado, teste,
commit ou deploy não constituem autorização.

## 7. Identidade e versionamento do roadmap

O documento identifica literalmente:

- nome ROADMAP_OPS_AGENTES;
- versão 2.1;
- data 2026-07-24;
- estado histórico literal `EM AUDITORIA — FECHO DOCUMENTAL
  PÓS-RATIFICAÇÃO, SEM AUTORIZAÇÃO OPERACIONAL`;
- baseline histórica de criação;
- REPORT-013 e REPORT-014 como fontes de reconciliação;
- ausência de auto-ratificação.

A relação entre criação, reconciliação e auditoria é cronologicamente possível
e explicada pelas fontes. Classificação: PROVADO DOCUMENTALMENTE e COERENTE.

## 8. Preservação histórica da versão 2.0

A tabela de histórico preserva a versão 2.0 com:

- data 2026-07-23;
- estado histórico literal `RATIFICADO — CANÓNICO DOCUMENTAL, SEM
  AUTORIZAÇÃO OPERACIONAL`;
- baseline `a7e16f0ffa5a90189166d4f968eb62b23c69da89`;
- SHA-256
  `6EDC7FECBB04CC83790825BBC71775F3CD3D1963D97F3D479D4EFA831D585B7D`;
- REPORT-011 como reconciliação.

O roadmap declara que a v2.0 permanece canónica documental no seu histórico e
que a v2.1 não está automaticamente ratificada. Não foi encontrada reescrita
retroactiva da data, baseline, hash ou estado histórico da v2.0.
Classificação: PROVADO DOCUMENTALMENTE e COERENTE.

## 9. Auditoria documental integral dos blocos e marcos

### 9.1 Fundação e contratos

B14.0+B14.1, serialização canónica, sanitização, contratos partilhados,
AgentMission, MissionFactory, AgentExecutionResult e validações aparecem com o
estado histórico literal `CONCLUÍDO`. A força probatória é documental,
suportada por ADR-008 e reports anteriores; o funcionamento actual não foi
revalidado. AgentMission e AgentExecutionResult limitam e descrevem
autoridade, mas não a concedem nem constituem autorização produtiva.

### 9.2 Sombra, canário e fronteiras

B14.3A-F aparecem com o estado histórico literal `CONCLUÍDO` apenas como
migrações em sombra. B14.3G aparece como canário determinístico, sem chamada
real a provider. ADR-016 e ADR-017 preservam decisões arquitecturais e gates
produtivos bloqueados. ADR-018 mantém no roadmap o estado literal `EM
AUDITORIA` por ainda declarar pendência documental própria. B14-SVC-06
regista apenas uma fronteira HTTP read-only anterior.

Classificação global: PROVADO DOCUMENTALMENTE POR EVIDÊNCIA ANTERIOR; NÃO
REVALIDADO OPERACIONALMENTE.

### 9.3 Inventário e activação

O inventário separa agentes legados, orquestração legada, adapters, engines,
reader, contratos, router/providers e HTTP read-only. As classificações
literais `ABERTO`, `BLOQUEADO` e `CONCLUÍDO` são acompanhadas de limites. Não
há declaração de que presença, instanciação ou teste provem activação.

### 9.4 Dependências, futuro e dívida histórica

Dependências normativas permanecem `BLOQUEADO`; factos externos e providers
permanecem `ABERTO`; activação, integração, escrita, LLM real e assinatura
institucional permanecem `FUTURO NÃO AUTORIZADO`. B13 e Pilot 0 são marcos
históricos; P0-07, T1-T8 e feedback permanecem `ABERTO`. Nenhum desses estados
foi alterado por esta missão.

## 10. Auditoria documental integral dos ADRs e reports

| Fonte | Estado literal relevante | Força e limite |
|---|---|---|
| ADR-008 | `RATIFICADO E IMPLEMENTADO` | PROVADO DOCUMENTALMENTE POR EVIDÊNCIA ANTERIOR; operação actual não revalidada |
| ADR-009 a ADR-015 | estados históricos de migração/canário | PROVADO DOCUMENTALMENTE POR EVIDÊNCIA ANTERIOR; não autorizam produção |
| ADR-011 v1.2 | `RATIFICADO POR GPT E MIGUEL`, exclusivamente B14.3C em sombra/dry_run | PROVADO DOCUMENTALMENTE; limite produtivo expresso |
| ADR-016 | decisão arquitectural autónoma e aditiva ratificada | PROVADO DOCUMENTALMENTE; implementação produtiva bloqueada |
| ADR-017 | decisão arquitectural ratificada | PROVADO DOCUMENTALMENTE; implementação bloqueada |
| ADR-018 | decisão ratificada, com pendência documental declarada | PROVADO DOCUMENTALMENTE; roadmap preserva `EM AUDITORIA` |
| REPORT-001 a REPORT-010 | execução, auditoria, rectificação e implementação históricas | PROVADO DOCUMENTALMENTE POR EVIDÊNCIA ANTERIOR; não revalidado operacionalmente |
| REPORT-011 | reconciliação da v2.0 | PROVADO DOCUMENTALMENTE; divergências remanescentes preservadas |
| REPORT-013 | auditoria GPT e ratificação humana registadas | PROVADO DOCUMENTALMENTE; retrato anterior qualificado temporalmente |
| REPORT-014 | fecho pós-ratificação e criação da v2.1 | PROVADO DOCUMENTALMENTE; sem autorização operacional |

Não foi encontrada conversão de mensagem de commit em decisão institucional.

## 11. Auditoria integral dos gates

| Gate | Estado documental | Prova | Autoridade futura |
|---|---|---|---|
| Divergências de estado documental | `BLOQUEADO` | REPORT-011 e roadmap | Miguel após auditoria GPT e missão própria |
| ADR-011-PROVENIENCIA-001 | `RESOLVIDO POR ADR-016` | ADR-016, REPORT-013/014 | alteração futura exige cadeia própria |
| Implementação produtiva DataSanitization | `PENDENTE E BLOQUEADO` | ADR-016, REPORT-013/014 e roadmap | missão, contratos, implementação, testes, GPT e Miguel |
| ConsistencyAudit produtivo | `BLOQUEADO` | ADR-017 e roadmap | missão posterior própria |
| Memorial além de HTTP read-only | `BLOQUEADO` | ADR-018, REPORT-009/010 | missão posterior própria |
| Executor, persistência e scheduler L3 | `BLOQUEADO` | REPORT-002/003 e roadmap | proposta, auditoria e ratificação próprias |
| Dependências normativas | `BLOQUEADO` | B13-OPS-12 e roadmap | autoridade normativa e Miguel |
| AGENTS.md versus CCS-001 | `BLOQUEADO` | REPORT-011 e roadmap | Miguel após auditoria GPT |
| LLM real L3 | `BLOQUEADO` | roadmap | missão, auditoria e decisão próprias |

Os gates são distintos e não foram fundidos. Resolver decisão arquitectural
não resolve implementação, integração ou produção.

## 12. Proveniência do DataSanitizationAgent

Foi confirmado documentalmente:

- ADR-011 v1.2 exclusivamente para B14.3C em sombra/dry_run;
- preservação histórica da v1.1;
- implementação limitada de B14.3C anterior à ratificação humana;
- preservação da inversão histórica de precedência;
- ausência de saneamento retroactivo pela ratificação posterior;
- ADR-016 autónomo e aditivo;
- estado histórico anterior do ADR-016: `PROPOSTO`, GPT `PENDENTE`,
  Miguel `PENDENTE` e gate arquitectural `ABERTO`;
- gate arquitectural `RESOLVIDO POR ADR-016`;
- gate de implementação produtiva `PENDENTE E BLOQUEADO`;
- proveniência produtiva `BLOQUEADA`.

Não existe autorização documental para reader, projector, BD, persistência,
scheduler, registry, executor, endpoint, escrita, publicação, LLM real,
integração, activação, produção ou deploy. Classificação: PROVADO
DOCUMENTALMENTE e BLOQUEADO.

## 13. Invariantes soberanos L3

O roadmap preserva:

- motor-first e LLM-last;
- read-only por padrão;
- sombra/dry_run antes de modo activo;
- fail-closed, fallback determinístico e degradação segura;
- idempotência e proveniência rastreável;
- contratos explícitos de missão e resultado;
- activação apenas por missões ou eventos explícitos;
- separação entre autoridade documental e operacional;
- ausência de escrita, publicação e promoção autónomas;
- GPT como auditor e supervisor arquitectural;
- Miguel como autoridade humana final;
- Codex como executor técnico limitado.

Não concede autoridade canónica a agentes, autoridade normativa a LLMs,
decisão fiscal probabilística, escrita directa, publicação, promoção ou
execução autónomas. Não concede bypass de adapters, contratos, BudgetGuard,
LLMRouter, auditoria GPT, ratificação humana, missão explícita, gates ou
proveniência. Não alimenta a brigada inicial pelo scheduler legado genérico.

AgentExecutionResult não é autoridade canónica. AgentMission, registry,
scheduler, testes verdes, commit, ratificação documental e deploy não são
autorizações produtivas. Classificação: COERENTE.

## 14. Autoridade e fontes de verdade

Miguel é a autoridade humana final; GPT audita e supervisiona arquitectura;
Codex executa tecnicamente dentro da missão; agentes são componentes sem
autoridade canónica; LLMs são ferramentas sem autoridade fiscal ou normativa;
código é implementação; mensagens de commit são cronologia auxiliar;
AGENTS.md é orientação operacional subordinada; CCS-001 permanece em
construção e subordinado à cadeia institucional aplicável.

AGENTS.md, CCS-001, código, testes, agentes, LLMs, commits, deploy e logs não
substituem a cadeia de autoridade. Este relatório não declara aprovação em
nome do GPT nem ratificação em nome de Miguel.

## 15. Preparação para abertura do Utilizador 1

O ROADMAP_OPS_AGENTES v2.1 identifica Pilot 0 como dívida histórica e não o
converte em autorização presente. Não contém, porém, um gate completo e
versionado para o primeiro utilizador real controlado. A separação é,
portanto, PARCIAL.

O ROADMAP_ABERTURA_UTILIZADORES contém blocos sobre jornada, segurança,
produção, suporte, piloto, escala e pagamentos, mas os seus estados históricos
e operacionais não foram revalidados nesta missão. Não podem fundamentar um
Go/No-Go actual.

Ficam propostos documentalmente, sem execução:

1. fecho institucional do ROADMAP_OPS_AGENTES v2.1;
2. auditoria completa de abertura controlada do Utilizador 1;
3. correcção de bloqueadores e decisão Go/No-Go.

Os Blocos 2 e 3 devem integrar uma versão 2.2 ou, preferencialmente por
separação de finalidade, um plano operacional de abertura próprio,
identificado, versionado, auditado e ratificado. Esta preferência é uma
proposta documental, não uma decisão arquitectural.

## 16. Separação entre piloto controlado e abertura pública

Pilot 0 histórico não autoriza Utilizador 1. Utilizador 1 não autoriza abertura
pública. Abertura controlada não autoriza agentes produtivos. Agentes
produtivos não são requisito automático para Utilizador 1. Pagamentos e
abertura pública permanecem FUTURO NÃO AUTORIZADO.

O gate produtivo do DataSanitizationAgent não precisa ser aberto para uma
futura auditoria documental ou técnica de Utilizador 1. Qualquer abertura
exige missão própria; qualquer Go/No-Go exige evidência técnica própria. Esta
missão não executa nem antecipa essa decisão.

## 17. Imutabilidade da versão 2.1

Após eventual ratificação documental, a v2.1 deve permanecer imutável. Não se
devem acrescentar retroactivamente os Blocos 2 e 3, alterar significado,
ampliar alcance, apagar a v2.0, modificar baselines originais ou converter
estados históricos em actuais.

Evolução posterior exige nova versão ou documento, nova missão, nova
auditoria, nova ratificação e novo commit. A v2.1 não pode ser convertida em
autorização operacional, pública ou de agentes produtivos.

## 18. Fronteira criptográfica

SHA-256 prova apenas identidade e integridade byte a byte no momento da
medição. Divergência prova diferença de bytes, mas não prova isoladamente
corrupção, erro semântico, alteração não autorizada, autoria ou origem.

SHA-256 não prova autoria, ratificação criptograficamente vinculada, timestamp
confiável, não repúdio, posse de chave, identidade institucional ou
resistência pós-quântica. Não torna o sistema quantum-ready, quantum-safe ou
pós-quântico.

Classificação máxima: L3 DOCUMENTAL, CRIPTOGRAFICAMENTE CONSCIENTE E PREPARADO
PARA FUTURA CRIPTO-AGILIDADE, SEM ALEGAR PRONTIDÃO PÓS-QUÂNTICA.

## 19. Futura cripto-agilidade

O roadmap preserva espaço conceptual para evolução criptográfica ao exigir
versionamento, substituibilidade, independência de algoritmo e ADR próprio.
Essa preparação é PARCIAL porque ainda não existe no roadmap inventário
versionado ou perfil operacional completo.

Uma evolução futura deve prever, sem seleccionar algoritmos nesta missão:

- inventário versionado de usos criptográficos;
- algoritmo e versão por artefacto;
- separação entre hash, assinatura, autenticação, cifragem, derivação de chave
  e timestamp;
- preservação dos bytes canónicos originalmente verificados;
- metadados de algoritmo, versão, chave, certificado, política, perfil, data e
  contexto;
- rotação, revogação e expiração de chaves;
- validação de artefactos históricos;
- coexistência e migração progressiva de perfis;
- verificação dupla ou híbrida quando futuramente definida;
- substituição sem alteração da semântica fiscal;
- depreciação e retirada controlada;
- trilho auditável de migração;
- separação entre integridade documental e assinatura institucional.

Inventário, perfil, assinatura, timestamp, esquema híbrido, gestão de chaves,
migração e validação operacional exigem ADR, missão, implementação, testes,
auditoria GPT, ratificação de Miguel, commit e plano de migração próprios.

A presente auditoria prova apenas preparação documental para futura
cripto-agilidade. Não prova prontidão técnica, operacional ou pós-quântica do
sistema.

## 20. Matriz de reconciliação

| Item | Estado actual | Tipo de prova | Evidência | Divergência | Autoridade necessária | Estado máximo permitido após decisão futura |
|---|---|---|---|---|---|---|
| ROADMAP v2.1 | EM AUDITORIA | PROVADO DOCUMENTALMENTE | roadmap e REPORT-014 | nenhuma bloqueante | parecer GPT e Miguel | referência canónica documental do seu escopo, sem autorização operacional |
| Baseline histórica da v2.1 | criação em `c6ce081...` | PROVADO DOCUMENTALMENTE | roadmap e REPORT-014 | nenhuma | nenhuma para preservar | histórica preservada |
| Baseline da MISSION-015 | `84cf6daa...` | PROVADO | Git | nenhuma | nenhuma | baseline de auditoria preservada |
| ROADMAP v2.0 | estado histórico ratificado e canónico documental | PROVADO DOCUMENTALMENTE | roadmap e REPORT-011 | nenhuma | Miguel para qualquer evolução | histórica imutável |
| ADR-011 v1.2 | sombra/dry_run | PROVADO DOCUMENTALMENTE | ADR-011 e REPORT-013/014 | nenhuma actual | missão própria para evolução | apenas sombra/dry_run |
| ADR-011 v1.1 histórico | preservado | PROVADO DOCUMENTALMENTE | ADR-011 | inversão histórica preservada | nenhuma para reescrever | histórico preservado |
| ADR-016 | decisão autónoma e aditiva | PROVADO DOCUMENTALMENTE | ADR-016 e REPORT-013/014 | nenhuma actual | cadeia própria para evolução | decisão documental sem produção |
| Gate arquitectural | RESOLVIDO POR ADR-016 | PROVADO DOCUMENTALMENTE | ADR-016 e REPORT-014 | nenhuma | cadeia própria | resolvido documentalmente |
| Gate produtivo DataSanitization | PENDENTE E BLOQUEADO | PROVADO DOCUMENTALMENTE | ADR-016 e roadmap | nenhuma | missão, técnica, GPT e Miguel | sujeito a decisão futura própria |
| Invariantes L3 | COERENTE | PROVADO DOCUMENTALMENTE | AGENTS.md, ADR-008 e roadmap | nenhuma bloqueante | Miguel e GPT conforme matéria | preservados |
| Autoridade dos agentes | sem autoridade canónica | PROVADO DOCUMENTALMENTE | ADR-008 e roadmap | nenhuma | Miguel para qualquer alteração | limitada por contratos e missão |
| Abertura Utilizador 1 | FUTURO NÃO AUTORIZADO | PARCIAL | roadmaps de agentes e abertura | gate próprio ausente na v2.1 | missão, auditoria técnica, GPT e Miguel | sujeito a Go/No-Go próprio |
| Abertura pública | FUTURO NÃO AUTORIZADO | NÃO PROVADO | ausência de autorização | nenhuma autorização | missão e cadeia completas | sujeito a decisão futura própria |
| Pagamentos | FUTURO NÃO AUTORIZADO | NÃO REVALIDADO OPERACIONALMENTE | roadmap de abertura | nenhuma autorização nesta missão | missão e evidência próprias | sujeito a decisão futura própria |
| Operação e suporte | FUTURO NÃO AUTORIZADO | NÃO REVALIDADO OPERACIONALMENTE | roadmap de abertura | estado actual não provado | missão e evidência próprias | sujeito a decisão futura própria |
| Recuperação e segurança | FUTURO NÃO AUTORIZADO | NÃO REVALIDADO OPERACIONALMENTE | roadmap de abertura | estado actual não provado | missão e evidência próprias | sujeito a decisão futura própria |
| Fronteira criptográfica | limite de SHA-256 declarado | PROVADO DOCUMENTALMENTE | roadmap e REPORT-013/014 | nenhuma bloqueante | ADR próprio para evolução | integridade documental limitada |
| Futura cripto-agilidade | FUTURO NÃO AUTORIZADO | PARCIAL | princípios de substituibilidade | inventário e perfil inexistentes | cadeia própria completa | preparação documental |
| Prontidão pós-quântica | NÃO PROVADO | NÃO PROVADO | nenhuma evidência técnica | não é alegada | cadeia própria completa | FORA DO ESCOPO DESTA MISSÃO |
| Divergências documentais remanescentes | BLOQUEADO | PROVADO DOCUMENTALMENTE | roadmap e REPORT-011 | ADR-009, ADR-018 e AGENTS.md/CCS-001 preservados | GPT e Miguel por missões próprias | resolução documental futura |

## 21. Defeitos, divergências e riscos

Não foi encontrado defeito bloqueante para submissão ao GPT.

Divergências e riscos preservados:

- conflito de cadeia entre AGENTS.md e CCS-001;
- divergência textual anterior do ADR-009;
- estado do ADR-018 ainda tratado como `EM AUDITORIA` no roadmap;
- gates produtivos e normativos bloqueados;
- abertura do Utilizador 1 apenas parcialmente tratada na v2.1;
- ausência de inventário e perfil criptográficos operacionais;
- risco de converter evidência histórica em garantia presente;
- risco de confundir ratificação documental com autorização operacional.

Estas matérias não são fechadas nem corrigidas nesta missão. A separação de
Utilizador 1 deve ser resolvida em v2.2 ou plano operacional próprio, não por
alteração retroactiva da v2.1.

## 22. Conclusão a submeter ao GPT

ROADMAP v2.1 APTO PARA PARECER GPT.

Não existe bloqueio documental impeditivo para submissão. Permanecem
necessários parecer literal do GPT, ratificação documental explícita de
Miguel, missão posterior para alteração de estado e autorização própria para
eventual commit e push.

Esta conclusão não é aprovação GPT, ratificação humana, autorização
operacional, produtiva, de utilizador, pública, de pagamento ou de deploy.
Também não prova prontidão pós-quântica.

## 23. Proposta exacta de decisão humana futura

Texto proposto, não executado pelo Codex e condicionado a parecer GPT anterior:

> EU, MIGUEL, APÓS PARECER GPT LITERAL FAVORÁVEL, RATIFICO EXCLUSIVAMENTE NO
> PLANO DOCUMENTAL O ROADMAP_OPS_AGENTES V2.1 COMO REFERÊNCIA CANÓNICA
> DOCUMENTAL DO SEU ESCOPO, PRESERVANDO INTEGRALMENTE A VERSÃO 2.0, A
> BASELINE HISTÓRICA DE CRIAÇÃO DA V2.1, AS DIVERGÊNCIAS HISTÓRICAS E TODOS
> OS GATES BLOQUEADOS. ESTA DECISÃO NÃO AUTORIZA CÓDIGO, IMPLEMENTAÇÃO,
> TESTES, DEPLOY, INTEGRAÇÃO, AGENTES, READER, PROJECTOR, BD, PERSISTÊNCIA,
> SCHEDULER, REGISTRY, EXECUTOR, ENDPOINT, ESCRITA, PUBLICAÇÃO, LLM REAL,
> ABERTURA DE UTILIZADOR, ABERTURA PÚBLICA OU PAGAMENTO. O GATE PRODUTIVO DO
> DATASANITIZATIONAGENT PERMANECE PENDENTE E BLOQUEADO, E AGENTES PRODUTIVOS
> PERMANECEM NÃO AUTORIZADOS. A ABERTURA CONTROLADA DO UTILIZADOR 1 DEPENDE
> DE AUDITORIA COMPLETA, CORRECÇÃO DE BLOQUEADORES E DECISÃO GO/NO-GO
> PRÓPRIAS; SUPORTE, RECUPERAÇÃO, SEGURANÇA, CAPACIDADE E ESCALA PERMANECEM
> SUJEITOS A TRABALHO FUTURO. A ABERTURA PÚBLICA E OS PAGAMENTOS NÃO SÃO
> AUTORIZADOS POR ESTA DECISÃO. A VERSÃO 2.1 FICA IMUTÁVEL NO ESCOPO DESTA
> RATIFICAÇÃO. MISSÃO, ACTUALIZAÇÃO DOCUMENTAL, COMMIT E PUSH POSTERIORES
> APENAS REGISTAM E MATERIALIZAM ESTA DECISÃO, SEM ALTERAR OU AMPLIAR O SEU
> ALCANCE. OS BLOCOS DE ABERTURA NÃO SERÃO INCORPORADOS RETROACTIVAMENTE E
> DEVEM SEGUIR POR VERSÃO 2.2 OU PLANO OPERACIONAL PRÓPRIO, COM MISSÃO,
> AUDITORIA E RATIFICAÇÃO PRÓPRIAS. ESTA DECISÃO RECONHECE APENAS PREPARAÇÃO
> DOCUMENTAL PARA FUTURA CRIPTO-AGILIDADE E NÃO DECLARA PRONTIDÃO TÉCNICA,
> OPERACIONAL OU PÓS-QUÂNTICA. COMMIT E PUSH DEPENDEM DE AUTORIZAÇÃO
> POSTERIOR PRÓPRIA. DEPLOY PERMANECE NÃO AUTORIZADO.

O texto é uma proposta exacta para eventual decisão futura. Não constitui
ratificação, autorização ou execução nesta missão.

## 24. Alterações efectuadas

Foi criado exclusivamente este REPORT-015. Nenhuma fonte auditada, código,
teste, configuração, migration ou dependência foi alterada. Nenhum teste foi
executado.

## 25. Hashes das fontes

Algoritmo: SHA-256. Finalidade limitada: identidade e integridade byte a byte
na data 2026-07-24. Um hash de fonte não é assinatura institucional.

| Fonte | SHA-256 |
|---|---|
| ADR-011 | `1DCAAD31D1493653773659189952ACF540896AA242D1558880DD1050BB13E7CC` |
| ADR-016 | `30668F48DA492F5A894E4A48DE8A050A52B291B5B25453F8C7D88252ED12D331` |
| ROADMAP_OPS_AGENTES | `5844C700CB6899F599D54413025DD2C680EA292564FD17F64374FE8F4D1E0487` |
| REPORT-013 | `57185BC652FA0FB9C8ABF70634C98D2A41B7989D26B0DC946E288525B16C3A5E` |
| REPORT-014 | `8F0334898F2B1D3BE41835C13EE71BEF6C012611EBC54D293DB1CA837488D6FF` |

O hash final deste REPORT-015 será calculado após o fecho do ficheiro e
apresentado externamente no output da missão. O valor externo não integra os
bytes medidos e não prova autoria, ratificação ou timestamp confiável.

## 26. Estado Git final

O estado final permitido contém exclusivamente este REPORT-015 como ficheiro
não rastreado. O stage permanece vazio e nenhum ficheiro rastreado está
alterado. A evidência literal é apresentada apenas no output externo da
missão.

## 27. Recomendação única

Submeter o ROADMAP_OPS_AGENTES v2.1 e este REPORT-015 a parecer literal do GPT
e, apenas depois, a eventual ratificação documental explícita de Miguel,
preservando todos os bloqueios operacionais e remetendo os Blocos 2 e 3 para
versão 2.2 ou plano operacional próprio.
