# REPORT-028 — Ratificação da Proposta do Mecanismo GREEN — ADR-020 — Intenção 9B2 — Versão 1.0

## 1. Identificação

- Documento: `REPORT-028-RATIFICACAO-PROPOSTA-GREEN-ADR-020-INTENCAO-9B2-V1.0`
- Versão: `1.0`
- Estado: **RATIFICAÇÃO HUMANA REGISTADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — GREEN TÉCNICO AINDA NÃO AUTORIZADO**
- Natureza: registo documental de ratificação humana, sem autoridade executável

## 2. Baseline publicado

O baseline publicado registado para esta ratificação é:

- `HEAD`: `bf474dbdb2ee92fb65d54c0c2befca584a4b7d42`;
- `origin/main`: `bf474dbdb2ee92fb65d54c0c2befca584a4b7d42`.

## 3. Proposta ratificada

A proposta soberanamente seleccionada possui a seguinte identidade exacta:

- Caminho: `docs/PROPOSTA-ADR-020-SELECAO-MECANISMO-GREEN-INTENCAO-9B2-V1.0.md`;
- Título: **PROPOSTA ADR-020 — Selecção do Mecanismo GREEN da Intenção 9B2 — Versão 1.0**;
- Tamanho: `13362 bytes`;
- SHA-256: `38A3F5E7C6D0D9FB7A9862D61818193ADCA0701B902B012CFFFB42ABA51391F2`.

A proposta foi objecto de auditoria independente, que produziu o veredicto:

`APTO_PARA_CONGELAMENTO_E_RATIFICACAO_PROPOSTA_GREEN_9B2`

## 4. Ratificação humana exacta

Regista-se integralmente a ratificação humana:

> RATIFICO A PROPOSTA ADR-020 — SELECÇÃO DO MECANISMO GREEN DA INTENÇÃO 9B2 — VERSÃO 1.0, COM 13362 BYTES E SHA-256 38A3F5E7C6D0D9FB7A9862D61818193ADCA0701B902B012CFFFB42ABA51391F2, SELECCIONANDO SOBERANAMENTE PARA FUTURA MISSION GREEN O MECANISMO POSTGRESQL CONSTITUÍDO POR UNIQUE TRIPLA EM ACTIVATION_GENERATIONS SEGUIDA DE FOREIGN KEY COMPOSTA EM NORMATIVE_ACTIVATIONS, PRESERVANDO A FK SIMPLES EXISTENTE E MANTENDO ACTIVATION_EXECUTION_ID E A INTENÇÃO 9B4 FORA DO ESCOPO. ESTA RATIFICAÇÃO NÃO AUTORIZA IMPLEMENTAÇÃO, NÃO AUTORIZA A CRIAÇÃO DA MIGRATION 0040 E NÃO SUBSTITUI A FUTURA MISSION GREEN SEPARADA, AUDITADA, RATIFICADA E PUBLICADA.

## 5. Mecanismo soberanamente seleccionado

Foi seleccionado soberanamente, para futura MISSION GREEN, o mecanismo PostgreSQL constituído por:

1. `UNIQUE` tripla em `activation_generations`;
2. seguida de FK composta em `normative_activations`.

A ordem exacta e vinculada da tripla é:

1. `activation_generation_id`;
2. `activation_decision_id`;
3. `activation_decision_record_hash`.

A FK simples `fk_normative_activations_activation_generation` será preservada. O campo `activation_execution_id` não integra o mecanismo seleccionado.

## 6. Fronteiras da selecção

A selecção soberana está estritamente limitada à intenção 9B2 e ao mecanismo descrito neste relatório. Em particular:

- a intenção 9B4 permanece separada e fora do escopo;
- `app/models.py` permanece fora do menor escopo;
- as migrations `0024`–`0039` permanecem intocadas;
- nenhuma migration `0040` foi criada;
- nenhum GREEN técnico foi implementado.

A ratificação selecciona a proposta, mas não concede autoridade de execução. Não declara a lacuna corrigida, não encerra tecnicamente a intenção 9B2 e não autoriza implementação de `UNIQUE`, FK composta ou qualquer migration.

## 7. RED congelado

O teste RED permanece congelado com a identidade exacta:

- Ficheiro: `tests/test_adr020_activation_postgresql.py`;
- Tamanho: `254789 bytes`;
- SHA-256: `B32DB5CE6DB7C3B5FA1350691C03D0FEE73E5A4D5B77CBC3C4871264723D52C7`.

## 8. MISSION GREEN posterior

Uma MISSION GREEN separada deverá ser criada, auditada, congelada, ratificada e publicada antes de qualquer execução técnica. Essa futura MISSION deverá confirmar, no seu próprio baseline de execução:

- `HEAD` igual a `origin/main`;
- a integridade do RED congelado;
- o escopo técnico exacto do mecanismo seleccionado.

A futura MISSION GREEN ainda não existe por efeito desta ratificação, e este relatório não a substitui.

## 9. Ausência de autoridade executável

Este relatório não é missão executável. Não autoriza o GREEN técnico, não autoriza a criação da migration `0040` e não concede autoridade para alterar código, modelos, migrations ou testes.

A publicação da proposta ratificada e deste relatório ainda será necessária. Nenhuma publicação é declarada como já ocorrida por este instrumento.

## 10. Estado final

**RATIFICAÇÃO HUMANA REGISTADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — GREEN TÉCNICO AINDA NÃO AUTORIZADO**

`REPORT_028_CRIADO_AGUARDA_AUDITORIA_E_PUBLICACAO`
