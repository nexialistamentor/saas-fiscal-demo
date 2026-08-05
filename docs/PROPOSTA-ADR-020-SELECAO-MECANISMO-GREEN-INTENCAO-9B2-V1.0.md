# PROPOSTA ADR-020 — Selecção do Mecanismo GREEN da Intenção 9B2 — Versão 1.0

## 1. Identificação

- Documento: `PROPOSTA-ADR-020-SELECAO-MECANISMO-GREEN-INTENCAO-9B2-V1.0`
- Versão: `1.0`
- Intenção: `ADR-020 9B2`
- Natureza: proposta documental soberana para futura seleção de mecanismo físico PostgreSQL
- Baseline publicado: `bf474dbdb2ee92fb65d54c0c2befca584a4b7d42`

## 2. Estado documental

**PROPOSTA SOBERANA — AGUARDA AUDITORIA, CONGELAMENTO E RATIFICAÇÃO HUMANA — NÃO EXECUTÁVEL — GREEN NÃO AUTORIZADO**

Este instrumento propõe formalmente um mecanismo para futura seleção soberana. Não é uma missão executável, não autoriza implementação, não cria migration, não encerra tecnicamente a intenção 9B2 e não autoriza a intenção 9B4.

A proposta ainda não equivale à seleção soberana final. A seleção somente existirá após ratificação humana explícita e publicação. Este documento não contém auto-hash; o seu tamanho e SHA-256 devem ser calculados externamente após a fixação dos bytes.

## 3. Autoridade e evidência publicadas

A presente proposta toma como autoridade e evidência publicadas:

- `docs/MISSIONS/MISSION-011-ADR-020-INTENCAO-9B2-RED-DIAGNOSTICO-V1.0.md`, SHA-256 `88ED6A40C23BF4E5E1BC2BD8764500FFD2A9F02D391518D6947D30E2C3EC361E`;
- `docs/REPORTS/REPORT-026-RATIFICACAO-MISSION-011-ADR-020-INTENCAO-9B2-V1.0.md`, SHA-256 `512BC3EB37EB537CA2D0B06120BB29D001EC69152173E72D07810112826901FB`;
- `docs/REPORTS/REPORT-027-ENCERRAMENTO-RED-MISSION-011-ADR-020-INTENCAO-9B2-V1.0.md`, tamanho `8170 bytes` e SHA-256 `FD799E859658EF7ED1006A1C97673620277F4A1DB7E3D02DA3FC14587F78BAE1`;
- `tests/test_adr020_activation_postgresql.py`, tamanho congelado `254789 bytes` e SHA-256 `B32DB5CE6DB7C3B5FA1350691C03D0FEE73E5A4D5B77CBC3C4871264723D52C7`.

O teste RED exacto congelado é `test_normative_activation_rejects_generation_from_different_exact_decision_via_core`. O resultado provado foi:

```text
Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>
```

O PostgreSQL na revision `0039_adr020_gen_exec_decision_fk` aceitou uma `NormativeActivation` cuja decisão exacta `D2/H2` divergia da decisão exacta `D1/H1` da `ActivationGeneration` referenciada, embora ambas utilizassem a mesma `activation_execution_id`.

## 4. Diagnóstico GREEN read-only

O diagnóstico read-only produziu o veredicto:

`DIAGNOSTICO_GREEN_9B2_CONCLUIDO_AGUARDA_INSTRUMENTO_DOCUMENTAL`

Foi confirmado que a tripla de 9B2 ainda não possui `UNIQUE` física própria; a chave primária simples da geração não serve como alvo da FK composta; `CHECK` não garante relações entre tabelas; e validação de aplicação não constitui garantia física. Trigger ou função PostgreSQL seriam possíveis, mas introduziriam maior complexidade e menor declaratividade. O candidato técnico mínimo é uma `UNIQUE` sobre a tripla, seguida de uma FK composta sobre a mesma tripla e na mesma ordem.

A FK simples actual pode ser preservada. `app/models.py` não é necessário para a garantia física. Migrations históricas não devem ser alteradas.

## 5. Mecanismo físico proposto

Propõe-se, ainda sujeito a auditoria e ratificação humana, exclusivamente o seguinte mecanismo físico PostgreSQL:

1. criar em `activation_generations` uma constraint `UNIQUE` sobre, exactamente nesta ordem:
   - `activation_generation_id`;
   - `activation_decision_id`;
   - `activation_decision_record_hash`;
2. criar em `normative_activations` uma `FOREIGN KEY` composta sobre, exactamente nesta ordem:
   - `activation_generation_id`;
   - `activation_decision_id`;
   - `activation_decision_record_hash`;
3. referenciar a mesma tripla, na mesma ordem, em `activation_generations`;
4. preservar a FK simples existente `fk_normative_activations_activation_generation`;
5. não incluir `activation_execution_id` na nova FK;
6. não implementar 9B4;
7. não depender de ORM, listener, endpoint, worker, scheduler ou validação de aplicação.

Nenhum mecanismo alternativo é seleccionado. A comparação técnica não converte esta proposta numa decisão soberana final.

## 6. Identidades físicas propostas

A migration futura proposta, ainda não criada nem autorizada, é:

`migrations/versions/0040_adr020_norm_gen_decision_fk.py`

- Revision proposta: `0040_adr020_norm_gen_decision_fk`;
- down revision: `0039_adr020_gen_exec_decision_fk`;
- nome proposto da `UNIQUE`: `uq_activation_generations_generation_exact_decision`;
- nome proposto da FK composta: `fk_normative_activations_generation_exact_decision`.

Os nomes das constraints possuem, respectivamente, 51 e 50 bytes ASCII. Ambos respeitam o limite físico de 63 bytes para identificadores PostgreSQL. A pesquisa read-only no baseline não encontrou colisão com nomes físicos existentes conhecidos. Uma futura missão deverá repetir o preflight físico imediatamente antes da execução; esta verificação documental não substitui essa obrigação operacional.

## 7. Contrato físico proposto

Para a FK composta, propõe-se explicitamente:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID`.

`NOT VALID` protege imediatamente novas escritas, sem presumir a inexistência de divergências históricas. A opção não valida retroactivamente linhas antigas. Qualquer futura validação integral exige autoridade separada ou inclusão expressa numa missão ratificada.

O PostgreSQL exige uma chave candidata sobre as colunas referenciadas antes de admitir a FK composta. Por isso, a `UNIQUE` tripla é pré-requisito do mecanismo. Uma constraint `UNIQUE` não possui opção equivalente a `NOT VALID`; a sua criação pode adquirir lock e a construção pode ter duração operacional relevante. Antes de qualquer execução futura será obrigatório um preflight autorizado sobre dados, nomes e condições operacionais. Esta proposta não selecciona agora índice concorrente nem estratégia de produção.

## 8. Capacidade soberana de 9B2

O mecanismo proposto fecha exclusivamente 9B2 ao fazer a decisão exacta declarada pela `NormativeActivation` coincidir com a decisão exacta da `ActivationGeneration` referenciada. A inserção falsa do RED deverá ser rejeitada com `DBAPIError`, enquanto o controlo positivo coerente deverá permanecer aceite.

Por ser uma garantia física PostgreSQL, o mecanismo alcança SQLAlchemy Core, ORM, SQL directo e outros caminhos de escrita no banco. É motor-first, database-enforced e transaccional. Não depende de LLM nem da aplicação como autoridade.

## 9. Separação expressa de 9B4

A nova FK não contém `activation_execution_id`. O RED 9B2 conserva a mesma execução na activação e na geração; portanto, a garantia de igualdade de execução é matéria separada.

Nenhuma decisão sobre 9B4 é tomada por este instrumento. Nenhuma futura missão 9B2 poderá ampliar implicitamente o escopo para 9B4. Qualquer tratamento de 9B4 dependerá de autoridade própria, posterior e independente.

## 10. Preservação da FK simples existente

Propõe-se preservar integralmente:

`fk_normative_activations_activation_generation`

Essa preservação produz o menor delta físico, mantém o contrato histórico, evita uma janela de remoção e conserva explícito o diagnóstico de existência da geração. Eventual remoção ou substituição exigirá instrumento próprio e não poderá ser presumida numa futura execução de 9B2.

## 11. `app/models.py` e metadata

`app/models.py` não é necessário para a garantia física proposta e não deverá integrar o menor escopo técnico futuro. Divergências históricas entre metadata e constraints físicas permanecem fora do escopo.

Este instrumento não corrige `uq_activation_decisions_exact`, `uq_activation_generations_exact` nem qualquer outra divergência de metadata. A existência dessas matérias não autoriza contaminação do escopo 9B2.

## 12. Comparação resumida de alternativas

- `UNIQUE` tripla seguida de FK composta: mecanismo declarativo, motor-first, transaccional e aplicável a todos os caminhos de escrita; é o único candidato proposto para futura ratificação.
- trigger ou função PostgreSQL: poderia impor a relação, mas seria mais complexo e menos declarativo; não é proposto nem seleccionado.
- `CHECK`: não consegue impor a relação entre duas tabelas; não é proposto.
- validação de aplicação: não garante todos os caminhos de escrita no banco e não constitui autoridade física; não é proposta.

## 13. Upgrade futuro proposto

Sem executar qualquer passo, propõe-se a seguinte ordem para uma futura missão ratificada:

1. verificar baseline e revision anterior;
2. verificar dados e nomes físicos dentro da futura missão;
3. criar a `UNIQUE` tripla;
4. criar a FK composta;
5. confirmar a FK simples preservada;
6. inspeccionar fisicamente nomes, colunas, ordem, tipos, `convalidated`, match, update/delete e deferrability;
7. executar o teste RED exacto;
8. executar regressões autorizadas;
9. não validar retroactivamente a FK sem autoridade explícita.

Esta sequência é uma proposta documental, não uma instrução executável presente.

## 14. Downgrade

A cadeia ADR-020 existente é tratada como irreversível. Propõe-se que a futura migration mantenha esse padrão e bloqueie explicitamente downgrade destrutivo.

Esta formulação é apenas uma proposta sujeita a auditoria e ratificação. Nenhum downgrade é implementado ou autorizado por este documento.

## 15. Menor escopo técnico futuro proposto

O menor escopo técnico futuro deverá conter somente:

1. a nova migration `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
2. o teste PostgreSQL existente `tests/test_adr020_activation_postgresql.py`.

A função RED exacta congelada não poderá ser removida, reescrita, enfraquecida ou substituída. Deverá tornar-se GREEN pela garantia física. Testes físicos ou prospectivos adicionais somente poderão ser aditivos e expressamente autorizados pela futura missão. Nenhum segundo ficheiro técnico deverá ser presumido.

Ficam excluídos do menor escopo técnico futuro:

- `app/models.py`;
- migrations 0024–0039;
- código de aplicação;
- schemas;
- listeners;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- documentação não autorizada;
- `docs/ROADMAP_OPS_AGENTES.md`.

## 16. Regressões futuras propostas

Sem executar ou criar testes agora, uma futura missão deverá definir pelo menos:

- execução exacta do RED congelado, que deverá passar;
- controlo positivo coerente;
- introspecção física da `UNIQUE`;
- introspecção física da FK composta;
- ordem exacta das colunas locais e referenciadas;
- nomes físicos;
- `convalidated`;
- `confmatchtype`;
- `confupdtype`;
- `confdeltype`;
- deferrability;
- preservação da FK simples;
- comportamento prospectivo de `NOT VALID`;
- regressões PostgreSQL ADR-020;
- suíte ADR-020 completa;
- regressão global somente depois das regressões específicas.

## 17. Condições cumulativas para autorização futura

Nenhum GREEN poderá começar antes de:

1. auditoria independente desta proposta;
2. congelamento dos bytes;
3. ratificação humana explícita da proposta;
4. criação de relatório de ratificação próprio;
5. publicação da proposta e da ratificação;
6. criação de MISSION GREEN separada;
7. auditoria e congelamento da MISSION GREEN;
8. ratificação humana da MISSION GREEN;
9. publicação da MISSION GREEN e da sua ratificação;
10. confirmação de `HEAD` igual a `origin/main`;
11. confirmação da integridade do RED congelado;
12. confirmação do escopo técnico exacto.

O cumprimento de qualquer condição isolada não cria autoridade executável.

## 18. Riscos obrigatórios

Uma futura decisão e missão deverão controlar expressamente:

- lock durante a criação da `UNIQUE`;
- duração da construção;
- dados históricos eventualmente divergentes;
- colisão de nomes;
- ordem incorrecta de colunas;
- remoção indevida da FK simples;
- alteração indevida do RED;
- expansão acidental para 9B4;
- contaminação por metadata;
- tentativa indevida de validar linhas antigas;
- execução em produção sem missão própria.

Nenhum destes riscos é resolvido por presunção nesta proposta.

## 19. Proibições e fronteiras

Este documento não autoriza alterar qualquer ficheiro existente, alterar o RED, criar a migration 0040, implementar `UNIQUE`, implementar FK, implementar trigger ou função, alterar models, executar pytest, executar Alembic, iniciar containers, fazer staging, commit ou push.

Permanecem fora do escopo 9B4, 9C, 8B2, `MIGRATION-BOOTSTRAP-0000-0001`, divergências de metadata, motor ADR-020, gates, endpoints, workers, scheduler, dispatcher, deploy, Railway, produção e `docs/ROADMAP_OPS_AGENTES.md`.

## 20. Estado final

Esta proposta apresenta exclusivamente o candidato `UNIQUE` tripla mais FK composta para futura seleção soberana. Não cria nem executa o mecanismo, não altera o contrato físico presente e não concede autoridade técnica.

Permanece vigente o estado:

**PROPOSTA SOBERANA — AGUARDA AUDITORIA, CONGELAMENTO E RATIFICAÇÃO HUMANA — NÃO EXECUTÁVEL — GREEN NÃO AUTORIZADO**

## 21. Veredicto documental

`PROPOSTA_GREEN_9B2_CRIADA_AGUARDA_AUDITORIA_E_RATIFICACAO`
