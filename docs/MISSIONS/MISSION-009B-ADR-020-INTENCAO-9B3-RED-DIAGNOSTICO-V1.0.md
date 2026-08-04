# MISSION-009B — ADR-020 — INTENÇÃO 9B3 — RED e Diagnóstico da Coerência da Decisão Soberana entre ActivationGeneration e ActivationExecution — Versão 1.0

## 1. Identificação documental

- Documento: `MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0`
- Versão: `1.0`
- Estado: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`
- Data da proposta: `2026-08-04`
- Baseline Git: `71cbc71cd45d592d661d8292b07413ee68842818`

## 2. Estado

**PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL**

Esta minuta não concede autoridade técnica, não autoriza execução e não presume auditoria ou ratificação. Somente após auditoria independente dos bytes e ratificação humana expressa futura poderá produzir a autorização estritamente limitada nela definida.

## 3. Natureza autónoma e limitada

A `MISSION-009B` é uma missão técnica autónoma e limitada. Não amplia retroactivamente a `MISSION-009A V0.2` nem o respectivo acto de autorização.

A Intenção 9 da `MISSION-009A V0.2` tratava da divergência de `authority_bindings` em `ActivationGeneration`. Não autorizava explicitamente a nova coerência decisão–execução 9B3.

O acto histórico externo `ATO-AUTORIZACAO-MISSION-009A-V0.2-R1.md` identificava o bundle `BUNDLE-AUTORIZACAO-MISSION-009A-V0.2.zip`, com SHA-256 `1907E9FB6C1AF3711AEBB38F39992F1FB3D823959EC2BAF6C2FE4104B71FC17F`. Esse acto permanece precedente histórico, mas não é fonte de autorização técnica para a `MISSION-009B`.

Nenhuma autoridade da `MISSION-009B` pode ser inferida da `MISSION-009A V0.2`, do acto histórico, do bundle ou da descoberta operacional que originou a matéria 9B3.

## 4. Autoridade canónica da invariável

A autoridade canónica vigente é a adenda ratificada:

`docs/ADENDA-ADR-020-MISSION-009A-INTENCAO-9B3-COERENCIA-DECISAO-GERACAO-EXECUCAO-V1.0.md`

- SHA-256: `94D3C11078606E9343FD88F42A90675C9A56C1D3A91BB9C9A7E8164E4A4E7C79`
- Tamanho: `9739 bytes`
- Registo da ratificação: `docs/REPORTS/REPORT-020-RATIFICACAO-ADENDA-ADR-020-MISSION-009A-INTENCAO-9B3-V1.0.md`
- Commit documental: `71cbc71cd45d592d661d8292b07413ee68842818`

A invariável canónica ratificada é exclusivamente:

`ActivationGeneration.activation_decision_id = ActivationExecution.activation_decision_id`

e:

`ActivationGeneration.activation_decision_record_hash = ActivationExecution.activation_decision_record_hash`

O par ID/hash é cumulativo e indivisível. A coincidência de apenas uma componente não satisfaz a invariável.

## 5. Objectivo único

Após auditoria independente dos bytes e ratificação humana expressa futura desta missão, a autoridade concedida ficará limitada a:

1. criação de exactamente um teste RED 9B3;
2. fixture mínima indispensável, no mesmo ficheiro de teste;
3. execução isolada do RED;
4. demonstração física de que PostgreSQL aceita actualmente a geração incoerente;
5. diagnóstico read-only da causa física;
6. preservação de um controlo positivo.

Esta missão não autoriza GREEN.

## 6. Teste exacto e ficheiro técnico permitido

O único teste que poderá ser criado após ratificação expressa desta missão é:

`test_activation_generation_rejects_execution_from_different_exact_decision_via_core`

O único ficheiro técnico que poderá ser modificado é:

`tests/test_adr020_activation_postgresql.py`

A fixture exacta será `postgresql_intention_9b3`, criada no mesmo ficheiro e limitada exclusivamente a este cenário. Nenhum outro ficheiro técnico poderá ser criado ou modificado sob esta missão sem nova decisão expressa.

## 7. Caminho de escrita

O teste deverá usar SQLAlchemy Core sobre `ActivationGeneration`.

É proibido usar `NormativeActivation` como caminho de escrita ou como parte do objecto do teste.

## 8. Cenário RED exacto

O cenário deverá criar:

- `D1` exacta, existente e aprovada;
- `D2` exacta, existente e aprovada;
- `D1` e `D2` materialmente equivalentes, salvo identidade ID/hash e o `idempotency_key` técnico necessariamente distinto;
- `E1` pertencente exactamente a `D1`;
- `E2` pertencente exactamente a `D1`;
- `E1` e `E2` com IDs, `record_hashes` e `idempotency_keys` próprios e distintos;
- `G_control` vinculada a `D1/E1`;
- `G_false` vinculada a `D2/E2`.
- `G_control` e `G_false` com IDs e `record_hashes` próprios e distintos;
- `G_control` e `G_false` com pares `(scope_hash, composition_hash)` distintos, derivados de conteúdo de geração internamente válido e distinto apenas para satisfazer a unicidade física.

`D2` deverá diferir de `D1` cumulativamente no par exacto ID/hash. Não é admissível produzir divergência em somente uma componente.

`E1` e `E2` deverão ser execuções distintas, ambas pertencentes a `D1`, com identidades, `record_hashes` e `idempotency_keys` próprios, porque cada `ActivationGeneration.activation_execution_id` é `UNIQUE`.

As diferenças técnicas obrigatórias de identidade e unicidade entre `D1/D2`, `E1/E2` e `G_control/G_false`, incluindo os pares `(scope_hash, composition_hash)`, servem somente para permitir registos válidos e coexistentes. Não constituem segunda falsidade soberana nem integram o objecto testado.

## 9. Controlo positivo e falsidade única

O controlo positivo `G_control = D1/E1` deverá persistir.

A única falsidade do cenário será:

`G_false.activation_decision_id/hash = D2`

enquanto:

`E2.activation_decision_id/hash = D1`.

Todos os demais campos, relações, estados, hashes e requisitos deverão permanecer internamente válidos. As diferenças técnicas indispensáveis de identidade e unicidade não constituem falsidade soberana e não poderão alterar o objecto testado.

## 10. Comportamento actual esperado

O comportamento actual esperado é que o `INSERT` de `G_false` seja aceite e persista. As garantias físicas actuais validam separadamente:

- a existência exacta de `D2`;
- a existência de `E2`.

Não comparam, porém, a decisão armazenada na geração com a decisão pertencente à execução. O teste que exigir rejeição deverá, portanto, falhar pela ausência da excepção esperada.

## 11. Causa RED vinculante

A falha válida deverá ser equivalente a:

`DID NOT RAISE sqlalchemy.exc.DBAPIError`

A causa vinculante do RED será exclusivamente a aceitação de `D2/E2` por PostgreSQL. Nenhuma falha de fixture, setup, Docker, migration, hash, `UNIQUE` ou outro campo será considerada RED válido.

Se o resultado não demonstrar fisicamente essa causa exclusiva, a execução não satisfaz a missão e não autoriza ampliar, reparar ou reinterpretar o cenário.

## 12. Diagnóstico read-only

Somente após obtenção do RED válido, será permitido diagnóstico read-only para determinar:

- a garantia PostgreSQL ausente;
- os mecanismos físicos tecnicamente possíveis;
- a prospectividade;
- a ordem de triggers;
- a preservação histórica;
- o risco de máscara;
- o impacto em migrations e testes.

O diagnóstico deverá descrever possibilidades e riscos, sem escolher, autorizar ou implementar antecipadamente:

- trigger;
- FK;
- `UNIQUE`;
- constraint;
- função;
- token;
- `SQLSTATE`;
- migration 0039.

O diagnóstico não poderá produzir escrita em schema, dados, migrations ou código, nem converter uma possibilidade técnica em decisão arquitectural ou canónica.

## 13. GREEN separado e proibições técnicas

Qualquer GREEN exigirá instrumento, auditoria e autorização próprios e separados. Esta missão não autoriza:

- alteração de modelo;
- alteração de schema;
- migration 0039;
- função PostgreSQL;
- trigger;
- FK;
- `UNIQUE`;
- constraint;
- token;
- `SQLSTATE`;
- implementação GREEN;
- regressão global posterior ao GREEN;
- commit técnico de implementação.

A eventual confirmação do RED ou conclusão do diagnóstico não concede autoridade implícita para GREEN.

## 14. Exclusões expressas

Permanecem fora do objecto e da autoridade desta missão:

- 9B2;
- 9B4;
- 9C;
- 8B2;
- `NormativeActivation`;
- `target_manifest_hash`;
- `scope_hash`;
- bindings;
- `composition_manifest`;
- subject;
- review;
- gates;
- motor ADR-020;
- scheduler;
- dispatcher;
- endpoints;
- workers;
- publicação;
- deploy;
- Railway;
- produção;
- `MIGRATION-BOOTSTRAP-0000-0001`;
- alteração de migrations históricas;
- `docs/ROADMAP_OPS_AGENTES.md`.

## 15. Sequência institucional obrigatória

1. criar esta minuta;
2. realizar auditoria independente dos bytes;
3. efectuar correcções materiais, caso necessárias;
4. congelar os bytes e calcular SHA-256 externo;
5. obter ratificação expressa da Autoridade Final de Produto;
6. efectuar registo documental posterior;
7. realizar commit e publicação documental;
8. declarar exactamente o RED;
9. criar e executar o único teste;
10. realizar diagnóstico read-only;
11. encerrar a `MISSION-009B`;
12. elaborar instrumento GREEN separado, caso o resultado o justifique.

As etapas 8 a 10 somente poderão ocorrer após conclusão válida das etapas 1 a 7. Esta minuta, isoladamente, não permite antecipá-las.

## 16. Ratificação e autoridade

Esta minuta não concede autoridade. Somente declaração humana expressa de quem exerça a Autoridade Final de Produto — actualmente Miguel — sobre versão e SHA-256 exactos poderá autorizar a missão.

Parecer GPT é auditoria. Codex é redactor subordinado. Commit Git fornece integridade complementar, não ratificação.

Auditoria, congelamento, hash ou commit, isoladamente ou em conjunto, não substituem a declaração humana expressa.

## 17. Integridade documental

O SHA-256 desta futura missão deverá ser externo e calculado somente após revisão e congelamento dos bytes. Este documento não contém self-hash.

Qualquer alteração posterior dos bytes invalida o SHA-256, a auditoria e a ratificação correspondentes. O valor calculado durante a elaboração é meramente provisório e não integra os bytes desta minuta.

Não será criado relatório de ratificação nesta rodada.

## 18. Estado operacional

Enquanto esta proposta não for auditada, congelada e expressamente ratificada, nenhum teste, fixture, execução RED ou diagnóstico está autorizado.

O motor ADR-020 permanece desligado e os gates permanecem bloqueados. Não existe autorização para activation, publicação, deploy, Railway ou produção.

## 19. Registo de elaboração

- Documento: `MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0`
- Versão: `1.0`
- Estado: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`
- Data da proposta: `2026-08-04`
- Baseline Git: `71cbc71cd45d592d661d8292b07413ee68842818`
- Autoridade canónica: adenda 9B3 ratificada
- Registo documental da ratificação: `REPORT-020`
- Redactor subordinado: Codex sob instrução técnica supervisionada
- Auditor independente: PENDENTE
- Autoridade Final de Produto: actualmente exercida por Miguel — decisão expressa pendente
