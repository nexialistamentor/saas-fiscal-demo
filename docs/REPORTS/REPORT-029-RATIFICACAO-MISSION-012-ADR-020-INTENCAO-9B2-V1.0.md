# REPORT-029 — Ratificação da MISSION-012 — ADR-020 — Intenção 9B2 — GREEN — Versão 1.0

## 1. Identificação

- Documento: `REPORT-029-RATIFICACAO-MISSION-012-ADR-020-INTENCAO-9B2-V1.0`
- Versão: `1.0`
- Estado: **RATIFICAÇÃO HUMANA REGISTADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — EXECUÇÃO GREEN AINDA NÃO AUTORIZADA**
- Natureza: registo documental de ratificação humana, sem autoridade executável

Este relatório não contém auto-hash e não é uma missão executável.

## 2. Baseline publicado

O baseline publicado declarado para este registo é:

- `HEAD`: `ef2e9e708480b9d3460ed29e26e84108bfe67d05`;
- `origin/main`: `ef2e9e708480b9d3460ed29e26e84108bfe67d05`.

## 3. Identidade exacta da MISSION-012

A MISSION-012 ratificada possui a identidade exacta seguinte:

- Caminho: `docs/MISSIONS/MISSION-012-ADR-020-INTENCAO-9B2-GREEN-NORMATIVE-GENERATION-V1.0.md`;
- Título: **MISSION-012 — ADR-020 — Intenção 9B2 — GREEN da Coerência entre NormativeActivation e ActivationGeneration — Versão 1.0**;
- Tamanho: `11040 bytes`;
- SHA-256: `322564154C6D556916213BF231F4124129DCA5341CBB6D20279CCA556FA412F8`.

A MISSION-012 permanece sem autoridade executável até à publicação dela e deste relatório. A publicação ainda não ocorreu.

## 4. Auditoria independente

A auditoria independente emitiu o veredicto exacto:

`APTO_PARA_CONGELAMENTO_E_RATIFICACAO_MISSION_012`

## 5. Ratificação humana exacta

Regista-se integralmente a ratificação humana:

> RATIFICO A MISSION-012 — ADR-020 — INTENÇÃO 9B2 — GREEN DA COERÊNCIA ENTRE NORMATIVEACTIVATION E ACTIVATIONGENERATION — VERSÃO 1.0, COM 11040 BYTES E SHA-256 322564154C6D556916213BF231F4124129DCA5341CBB6D20279CCA556FA412F8, AUTORIZANDO FUTURAMENTE, APÓS PUBLICAÇÃO DA MISSION E DO SEU RELATÓRIO DE RATIFICAÇÃO, A IMPLEMENTAÇÃO LOCAL E DE TESTE DA UNIQUE TRIPLA E DA FOREIGN KEY COMPOSTA EXACTAMENTE DEFINIDAS, PRESERVANDO O RED CONGELADO, A FK SIMPLES EXISTENTE E A SEPARAÇÃO INTEGRAL DA INTENÇÃO 9B4. ESTA RATIFICAÇÃO NÃO AUTORIZA DEPLOY, RAILWAY, PRODUÇÃO, DADOS REAIS, VALIDAÇÃO RETROACTIVA OU QUALQUER ALTERAÇÃO FORA DOS DOIS FICHEIROS TÉCNICOS FIXADOS.

A decisão humana é a fonte da ratificação. Este relatório somente a regista e delimita, sem a ampliar e sem conceder autoridade de execução presente.

## 6. Mecanismo e ordem vinculados

O mecanismo vinculado é constituído, nesta sequência exacta, por:

1. `UNIQUE` tripla em `activation_generations`;
2. seguida de FK composta em `normative_activations`.

A ordem exacta e vinculada das colunas é:

1. `activation_generation_id`;
2. `activation_decision_id`;
3. `activation_decision_record_hash`.

Esta ordem aplica-se à `UNIQUE`, às colunas locais da FK composta e às colunas referenciadas em `activation_generations`.

As identidades físicas vinculadas são:

- migration: `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
- revision: `0040_adr020_norm_gen_decision_fk`;
- down revision: `0039_adr020_gen_exec_decision_fk`;
- `UNIQUE`: `uq_activation_generations_generation_exact_decision`;
- FK composta: `fk_normative_activations_generation_exact_decision`.

A nova FK será `MATCH SIMPLE`, `ON UPDATE RESTRICT`, `ON DELETE RESTRICT`, `NOT DEFERRABLE`, `INITIALLY IMMEDIATE` e `NOT VALID`.

A FK simples `fk_normative_activations_activation_generation` será preservada. Não poderá ser removida, renomeada, substituída ou enfraquecida.

`activation_execution_id` não integra a `UNIQUE` nem a FK composta.

## 7. RED congelado

O RED exacto permanece congelado com a identidade seguinte:

- Ficheiro: `tests/test_adr020_activation_postgresql.py`;
- Tamanho: `254789 bytes`;
- SHA-256: `B32DB5CE6DB7C3B5FA1350691C03D0FEE73E5A4D5B77CBC3C4871264723D52C7`.

A futura execução exige a integridade exacta deste RED e `HEAD` igual a `origin/main`. O teste RED congelado deverá ser preservado integralmente.

## 8. Escopo técnico futuro exacto

Somente após a publicação da MISSION-012 e deste relatório, e cumpridas todas as restantes condições vinculadas, a futura execução poderá modificar exclusivamente:

1. `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
2. `tests/test_adr020_activation_postgresql.py`.

Nenhum terceiro ficheiro técnico poderá ser criado ou alterado. `app/models.py` e as migrations `0024`–`0039` permanecem excluídos e intocados.

Nenhuma migration `0040` foi criada por este relatório. Nenhuma `UNIQUE` ou FK composta foi implementada. Nenhum GREEN foi implementado e a lacuna não é declarada corrigida. A intenção 9B2 não é declarada tecnicamente encerrada.

## 9. Separação integral da intenção 9B4

A intenção 9B4 permanece separada, posterior, fora do escopo e sem autoridade. Não foi incluída nesta ratificação, neste relatório ou no mecanismo 9B2.

Em particular, `activation_execution_id` permanece fora da `UNIQUE` e da nova FK composta, sem criação de garantia autónoma própria de 9B4.

## 10. Fronteiras locais e de produção

A autoridade futura, depois da publicação e das demais condições, ficará limitada à implementação e validação local ou de teste nos dois ficheiros técnicos fixados.

Permanecem proibidos:

- deploy;
- Railway;
- produção;
- consulta, alteração ou migração de dados reais;
- validação retroactiva de dados existentes;
- qualquer alteração fora dos dois ficheiros técnicos fixados.

Produção não está autorizada por esta ratificação ou por este relatório.

## 11. Condição de publicação e cadeia temporal

A MISSION-012 permanece sem autoridade executável enquanto não forem publicadas a própria MISSION-012 e este REPORT-029. A publicação de ambos ainda não ocorreu. Até essa publicação, a execução GREEN, a criação da migration `0040` e qualquer alteração técnica permanecem não autorizadas.

Depois da publicação, a futura execução ainda exigirá cumulativamente `HEAD` igual a `origin/main`, integridade exacta do RED congelado e observância integral do escopo e das condições da MISSION-012.

A futura alteração do regime geral de ratificações humanas não altera retroactivamente esta cadeia.

## 12. Estado final

**RATIFICAÇÃO HUMANA REGISTADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — EXECUÇÃO GREEN AINDA NÃO AUTORIZADA**

`REPORT_029_CRIADO_AGUARDA_AUDITORIA_E_PUBLICACAO`
