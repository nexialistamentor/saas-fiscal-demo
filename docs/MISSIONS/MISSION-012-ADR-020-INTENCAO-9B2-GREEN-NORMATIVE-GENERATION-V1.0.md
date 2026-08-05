# MISSION-012 — ADR-020 — Intenção 9B2 — GREEN da Coerência entre NormativeActivation e ActivationGeneration — Versão 1.0

## 1. Identificação

- Documento: `MISSION-012-ADR-020-INTENCAO-9B2-GREEN-NORMATIVE-GENERATION-V1.0`
- Versão: `1.0`
- Estado: **PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL — GREEN TÉCNICO NÃO AUTORIZADO**
- Natureza: definição vinculada de uma futura execução GREEN local e de teste, sem autoridade executável presente
- Baseline publicado de elaboração: `ef2e9e708480b9d3460ed29e26e84108bfe67d05`

Este documento não contém auto-hash. O seu tamanho e SHA-256 devem ser calculados externamente depois da fixação dos bytes.

## 2. Estado e cadeia de autoridade

Esta MISSION define a futura execução GREEN, mas permanece não executável até ao cumprimento cumulativo de todas as condições seguintes:

1. auditoria independente;
2. congelamento dos seus bytes;
3. ratificação da cadeia actual;
4. criação de relatório próprio de ratificação;
5. publicação desta MISSION-012 e desse relatório;
6. confirmação futura de `HEAD` igual a `origin/main`;
7. confirmação da integridade do RED congelado.

A futura alteração do regime geral de ratificações humanas não altera retroactivamente esta cadeia. Nenhuma condição isolada, documento anterior ou alteração futura de regime concede autoridade executável a esta MISSION.

## 3. Autoridade publicada

O mecanismo aqui vinculado decorre exclusivamente da proposta soberanamente seleccionada e publicada e do respectivo relatório publicado:

- `docs/PROPOSTA-ADR-020-SELECAO-MECANISMO-GREEN-INTENCAO-9B2-V1.0.md`, tamanho `13362 bytes`, SHA-256 `38A3F5E7C6D0D9FB7A9862D61818193ADCA0701B902B012CFFFB42ABA51391F2`;
- `docs/REPORTS/REPORT-028-RATIFICACAO-PROPOSTA-GREEN-ADR-020-INTENCAO-9B2-V1.0.md`, tamanho `4432 bytes`, SHA-256 `F4699A4FD9486C1D1797783FA3EF4CFC962103701C29BD3F483A16E1139C7C43`.

O RED congelado local possui a seguinte identidade:

- ficheiro: `tests/test_adr020_activation_postgresql.py`;
- tamanho: `254789 bytes`;
- SHA-256: `B32DB5CE6DB7C3B5FA1350691C03D0FEE73E5A4D5B77CBC3C4871264723D52C7`;
- teste exacto: `test_normative_activation_rejects_generation_from_different_exact_decision_via_core`.

## 4. Objectivo técnico futuro único

A futura execução deverá fechar exclusivamente a lacuna 9B2. A tripla declarada por:

```text
NormativeActivation(
    activation_generation_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

deverá corresponder exactamente à tripla de:

```text
ActivationGeneration(
    activation_generation_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

`activation_execution_id` não integra esta garantia. Esta MISSION não implementa nem autoriza 9B4.

## 5. Mecanismo vinculado

A futura execução deverá implementar exactamente, e apenas:

1. uma constraint `UNIQUE` em `activation_generations`, nesta ordem exacta:
   1. `activation_generation_id`;
   2. `activation_decision_id`;
   3. `activation_decision_record_hash`;
2. uma `FOREIGN KEY` composta em `normative_activations`, nesta ordem exacta:
   1. `activation_generation_id`;
   2. `activation_decision_id`;
   3. `activation_decision_record_hash`;
3. a FK composta deverá referenciar a mesma tripla, na mesma ordem, em `activation_generations`.

Nenhum mecanismo alternativo, trigger, função, validação de aplicação ou extensão material é autorizado.

## 6. Identidades físicas vinculadas

A futura implementação possuirá as identidades exactas seguintes:

- migration: `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
- revision: `0040_adr020_norm_gen_decision_fk`;
- down revision: `0039_adr020_gen_exec_decision_fk`;
- `UNIQUE`: `uq_activation_generations_generation_exact_decision`;
- FK composta: `fk_normative_activations_generation_exact_decision`.

## 7. FK simples preservada

A futura execução não poderá remover, renomear, substituir ou enfraquecer a FK simples existente:

`fk_normative_activations_activation_generation`

A sua preservação deverá ser confirmada por introspecção física.

## 8. Contrato exacto da FK composta

A futura FK composta deverá possuir cumulativamente:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID`.

Neste contrato, `NOT VALID` protege novas escritas imediatamente e não valida retroactivamente dados existentes. Não autoriza validação posterior sem autoridade própria e não elimina a necessidade da `UNIQUE` referenciada.

## 9. Contrato e risco da UNIQUE

A `UNIQUE` tripla é pré-requisito PostgreSQL da FK composta. Não existe variante `NOT VALID` equivalente para uma constraint `UNIQUE`.

Antes da futura alteração, a execução deverá efectuar preflight exclusivamente read-only de nomes, revision anterior e integridade local. Não deverá consultar, alterar ou migrar produção. Os riscos operacionais de lock e duração da criação da `UNIQUE` ficam registados; deploy e aplicação em produção permanecem proibidos.

Esta MISSION não selecciona estratégia de índice concorrente, manutenção operacional ou tratamento de dados reais.

## 10. Escopo técnico futuro exacto

Depois de ratificada e publicada, a futura execução poderá modificar somente:

1. `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
2. `tests/test_adr020_activation_postgresql.py`.

Nenhum terceiro ficheiro técnico poderá ser criado ou alterado.

No ficheiro de teste será obrigatório:

- preservar integralmente o teste RED congelado;
- não remover, reescrever, enfraquecer ou substituir a função exacta;
- tornar o RED GREEN exclusivamente pela migration;
- limitar alterações adicionais a conteúdo aditivo;
- não modificar testes 9B3 existentes.

Poderão ser adicionados no mesmo ficheiro, e apenas nele:

- constante da revision `0040`;
- fixture PostgreSQL específica da revision `0040`;
- teste de introspecção física da `UNIQUE`;
- teste de introspecção física da FK composta;
- teste de preservação da FK simples;
- prova prospectiva de `NOT VALID`.

## 11. Ficheiros e matérias excluídos

Ficam expressamente fora do escopo:

- `app/models.py`;
- migrations `0024`–`0039`;
- qualquer segundo ficheiro técnico além dos dois autorizados;
- código de aplicação;
- schemas;
- listeners;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- motor ADR-020;
- gates;
- metadata;
- documentação não autorizada;
- `docs/ROADMAP_OPS_AGENTES.md`;
- 9B4;
- 9C;
- 8B2;
- `MIGRATION-BOOTSTRAP-0000-0001`.

## 12. Ordem obrigatória do upgrade futuro

Sem executar agora, a ordem futura obrigatória será:

1. verificar baseline e down revision;
2. confirmar ausência de colisão dos nomes físicos;
3. criar a `UNIQUE` tripla;
4. criar a FK composta com o contrato exacto;
5. preservar e confirmar a FK simples;
6. inspeccionar fisicamente a `UNIQUE`;
7. inspeccionar fisicamente a FK composta;
8. executar o teste RED exacto;
9. executar regressões PostgreSQL específicas;
10. executar a suíte ADR-020 completa;
11. executar regressão global somente após as anteriores.

Esta ordem não constitui autorização presente para executar qualquer passo.

## 13. Downgrade

A migration futura deverá seguir a irreversibilidade da cadeia ADR-020 e bloquear explicitamente downgrade destrutivo. Não fica autorizada a remoção da FK composta ou da `UNIQUE` por downgrade.

## 14. Testes e evidências futuras obrigatórias

A execução futura deverá produzir evidência verificável de todos os pontos seguintes:

1. teste RED exacto passando sem alteração dos seus bytes;
2. controlo positivo coerente aceite;
3. inserção divergente rejeitada com `DBAPIError`;
4. nome e ordem exacta das colunas da `UNIQUE`;
5. nome e ordem exacta das colunas locais da FK;
6. nome e ordem exacta das colunas referenciadas;
7. `convalidated = false`;
8. `confmatchtype` correspondente a `MATCH SIMPLE`;
9. `confupdtype` correspondente a `RESTRICT`;
10. `confdeltype` correspondente a `RESTRICT`;
11. constraint não deferrable;
12. constraint initially immediate;
13. preservação da FK simples;
14. ausência de `activation_execution_id` na nova FK;
15. nenhuma alteração física ou lógica de 9B4;
16. migrations `0024`–`0039` intactas;
17. `app/models.py` intacto;
18. `git diff --check` sem erros;
19. codificação e integridade dos ficheiros;
20. regressões PostgreSQL ADR-020;
21. suíte ADR-020 completa;
22. regressão global final.

## 15. Separação expressa de 9B4

`activation_execution_id` não integra a `UNIQUE` nem a nova FK. O teste RED 9B2 utiliza a mesma execução na activação e na geração, isolando a divergência da decisão exacta.

9B4 continua posterior, separada e sem autoridade neste instrumento. Nenhum teste ou mecanismo 9B2 poderá introduzir garantia autónoma de igualdade de execução.

## 16. Fronteira de produção

Depois da ratificação e publicação exigidas, esta MISSION autorizará somente implementação e validação local ou de teste no escopo técnico exacto.

Não autoriza:

- deploy;
- Railway;
- execução em base de produção;
- consulta de produção para preflight;
- validação retroactiva de dados existentes;
- estratégia de índice concorrente;
- manutenção operacional;
- alteração de dados reais.

## 17. Proibições presentes

Durante a elaboração e enquanto esta MISSION permanecer não ratificada e não publicada, é proibido:

- modificar qualquer ficheiro existente;
- criar a migration `0040`;
- alterar o RED;
- implementar a `UNIQUE` ou a FK;
- executar `pytest`;
- executar Alembic;
- iniciar containers;
- fazer staging, commit ou push;
- alterar `app/models.py` ou migrations históricas;
- tratar metadata, 9B4, 9C, 8B2 ou `MIGRATION-BOOTSTRAP-0000-0001`;
- alterar endpoints, workers, scheduler, dispatcher, motor ADR-020 ou gates;
- executar deploy, Railway ou qualquer operação em produção;
- alterar `docs/ROADMAP_OPS_AGENTES.md`.

## 18. Critérios de execução futura

Uma execução futura somente poderá começar quando a cadeia do ponto 2 estiver integralmente cumprida e quando o seu baseline confirmar simultaneamente:

- `HEAD` igual a `origin/main`;
- integridade exacta do RED congelado;
- presença e integridade das autoridades publicadas;
- escopo limitado aos dois ficheiros técnicos autorizados;
- ausência de colisão dos nomes físicos e down revision exacta.

Qualquer divergência deverá bloquear a execução e ser reportada à autoridade competente.

## 19. Estado final

Esta MISSION fixa exclusivamente a futura execução GREEN da intenção 9B2 pelo mecanismo soberanamente seleccionado. Não cria migration, não altera o RED, não implementa GREEN e não concede autoridade executável presente.

Permanece vigente o estado exacto:

**PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL — GREEN TÉCNICO NÃO AUTORIZADO**

## 20. Veredicto documental

`MISSION_012_CRIADA_AGUARDA_AUDITORIA_E_RATIFICACAO`
