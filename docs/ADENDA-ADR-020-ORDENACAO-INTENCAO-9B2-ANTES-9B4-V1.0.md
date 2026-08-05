# ADENDA ADR-020 — Ordenação Soberana da Intenção 9B2 antes da Intenção 9B4 — Versão 1.0

## 1. Identificação

- Documento: `ADENDA-ADR-020-ORDENACAO-INTENCAO-9B2-ANTES-9B4-V1.0`
- Versão: `1.0`
- Data: `2026-08-04`
- Baseline publicada: `9f568b4605f2e0a41de196a4d2072f333e40f086`
- Objecto: ordenação documental soberana das intenções `ADR-020 9B2` e `ADR-020 9B4`

## 2. Estado

**DECISÃO HUMANA RATIFICADA — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO — NÃO AUTORIZA EXECUÇÃO TÉCNICA**

Esta Adenda regista e delimita uma decisão humana já emitida. Não substitui, não amplia e não cria nova autoridade técnica.

## 3. Baseline publicada

No início desta elaboração documental, `HEAD` e `origin/main` correspondiam exactamente a:

`9f568b4605f2e0a41de196a4d2072f333e40f086`

A branch era `main`, a árvore de trabalho estava limpa e nada estava staged.

## 4. Origem humana da decisão

A decisão soberana foi ratificada humana e expressamente pela Autoridade Final de Produto. A decisão humana é a fonte da ratificação.

Esta Adenda apenas regista e delimita essa decisão. O documento não constitui a sua fonte, não a substitui, não a amplia e não transforma inferência anterior do Codex em autoridade.

## 5. Contexto deixado pela intenção 9B3

A intenção 9B3 foi encerrada e publicada antes desta Adenda. O seu encerramento tratou da coerência exacta entre `ActivationGeneration` e `ActivationExecution` e preservou expressamente 9B2, 9B4, 9C e 8B2 fora do respectivo escopo.

O motor ADR-020 permanece desligado e os gates permanecem desligados. O encerramento de 9B3 não decidiu a ordenação entre 9B2 e 9B4 e não concedeu autoridade documental ou técnica a qualquer delas.

## 6. Problema de ordenação anteriormente indeterminado

Após o encerramento de 9B3, a ordem documental entre 9B2 e 9B4 permanecia indeterminada. Nenhuma inferência operacional, designação anterior ou proximidade temática podia resolver essa ordem sem decisão humana soberana.

Esta Adenda regista exclusivamente a decisão humana que remove essa indeterminação documental.

## 7. Decisão soberana de ordem

A intenção 9B2 será diagnosticada e formalizada antes da intenção 9B4.

**Ordem soberana ratificada: 9B2 antes de 9B4.**

Esta ordenação é documental. Não diagnostica definitivamente uma lacuna física, não escolhe mecanismo e não autoriza execução técnica.

## 8. Definição exclusiva da intenção 9B2

A intenção 9B2 deverá tratar exclusivamente da coerência entre a decisão declarada por `NormativeActivation`, por meio de:

- `activation_decision_id`;
- `activation_decision_record_hash`;

e a decisão soberana vinculada à `ActivationGeneration` associada.

Esta definição não confunde a decisão da geração com a execução da geração. Não define ainda o mecanismo físico, não escolhe migration, constraint, trigger, listener ou teste e não declara definitivamente diagnosticada qualquer lacuna física.

## 9. Separação e postergação da intenção 9B4

A intenção 9B4 permanece:

- separada;
- posterior à 9B2;
- não canónica enquanto não possuir autoridade própria;
- dependente de diagnóstico e missão próprios;
- destinada, em termos ainda sujeitos a ratificação própria, à coerência entre `NormativeActivation` e `ActivationExecution`.

Nenhum mecanismo físico é formulado para 9B4. Esta Adenda não autoriza diagnóstico, missão, implementação ou execução de 9B4.

## 10. Exclusão de 9C e 8B2

- 9C permanece fora do escopo.
- 8B2 permanece fora do escopo.
- Nenhuma definição técnica ou regra de negócio de 9C ou 8B2 é criada por esta Adenda.

## 11. Limites da autoridade

A autoridade desta Adenda limita-se à ordenação documental de 9B2 antes de 9B4 e à delimitação exclusiva dos seus objectos nos termos aqui registados.

Não cria, altera, reinterpreta ou ratifica mecanismo técnico, arquitectura, política fiscal, regra de negócio, contrato canónico ou invariável além da exacta decisão humana de ordenação. Não autoriza a execução do motor ADR-020, a abertura de gates nem qualquer efeito operacional.

## 12. Actos autorizados

Somente ficam autorizados:

1. auditoria documental;
2. congelamento;
3. publicação desta Adenda e do `REPORT-025`;
4. após a publicação, diagnóstico read-only da intenção 9B2;
5. posterior criação, auditoria, congelamento e publicação de missão própria para 9B2.

A futura missão 9B2 não deve ser criada nesta rodada.

## 13. Actos não autorizados

Não estão autorizados:

- código;
- models;
- migrations;
- testes;
- banco de dados;
- containers;
- pytest;
- motor ADR-020;
- gates;
- `NormativeActivation` em produção;
- endpoints;
- workers;
- schedulers;
- dispatcher;
- staging;
- commit;
- push;
- deploy;
- Railway;
- produção;
- 9B4;
- 9C;
- 8B2;
- `MIGRATION-BOOTSTRAP-0000-0001`;
- `docs/ROADMAP_OPS_AGENTES.md`.

## 14. Sequência documental seguinte

A sequência seguinte é:

1. auditar documentalmente esta Adenda e o `REPORT-025`;
2. congelar os bytes dos dois documentos;
3. publicar o bundle documental;
4. somente após a publicação, iniciar diagnóstico read-only próprio da intenção 9B2;
5. posteriormente, criar, auditar, congelar e publicar missão própria para 9B2 sob autoridade separada.

Nenhuma etapa desta sequência autoriza antecipar 9B4, 9C ou 8B2.

## 15. Estado final

A decisão humana de ordenação está ratificada e registada. A Adenda aguarda auditoria, congelamento e publicação. Não existe autorização para execução técnica e a futura missão 9B2 não foi criada nesta rodada.

Este documento não inclui hash próprio.

## 16. Veredicto documental

`ORDENACAO_9B2_ANTES_9B4_RATIFICADA_AGUARDA_PUBLICACAO`
