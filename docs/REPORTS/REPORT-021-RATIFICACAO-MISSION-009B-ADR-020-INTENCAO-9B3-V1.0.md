# REPORT-021 — Registo da Ratificação da MISSION-009B — ADR-020 — Intenção 9B3 — RED e Diagnóstico — Versão 1.0

## Estado

RATIFICAÇÃO HUMANA REGISTADA — AGUARDA PUBLICAÇÃO DOCUMENTAL — NÃO EXECUTÁVEL

## Registo documental

- Documento: REPORT-021-RATIFICACAO-MISSION-009B-ADR-020-INTENCAO-9B3-V1.0
- Versão: 1.0
- Estado: RATIFICAÇÃO HUMANA REGISTADA — AGUARDA PUBLICAÇÃO DOCUMENTAL — NÃO EXECUTÁVEL
- Data: 2026-08-04
- Autoridade Final de Produto: Miguel
- Missão vinculada: MISSION-009B V1.0
- SHA-256 da missão: 1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50
- Tamanho da missão: 10888 bytes
- Baseline: 71cbc71cd45d592d661d8292b07413ee68842818
- Estado de publicação: PENDENTE

## Missão ratificada

- Caminho: `docs/MISSIONS/MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0.md`
- Documento: MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0
- Versão: 1.0
- SHA-256 exacto dos bytes congelados: 1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50
- Tamanho exacto: 10888 bytes
- Baseline Git da elaboração e ratificação: 71cbc71cd45d592d661d8292b07413ee68842818

Estado físico confirmado:

- bytes congelados;
- ficheiro read-only;
- sem self-hash;
- missão não modificada após congelamento.

## Autoridade humana

A ratificação foi emitida directamente por Miguel, Autoridade Final de Produto, em 2026-08-04.

## Declaração principal — registo literal

EU, MIGUEL, NO EXERCÍCIO DA AUTORIDADE FINAL DE PRODUTO, RATIFICO
EXPRESSAMENTE A MISSION-009B — ADR-020 — INTENÇÃO 9B3 — RED E
DIAGNÓSTICO DA COERÊNCIA DA DECISÃO SOBERANA ENTRE
ACTIVATIONGENERATION E ACTIVATIONEXECUTION — VERSÃO 1.0, SOBRE OS
BYTES CONGELADOS DE SHA-256
1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50
E TAMANHO EXACTO DE 10888 BYTES.

ESTA RATIFICAÇÃO AUTORIZA EXCLUSIVAMENTE, APÓS O REGISTO E A
PUBLICAÇÃO DOCUMENTAL:

1. A CRIAÇÃO DO ÚNICO TESTE RED 9B3:
test_activation_generation_rejects_execution_from_different_exact_decision_via_core;

2. A CRIAÇÃO DA FIXTURE postgresql_intention_9b3, LIMITADA AO MESMO
FICHEIRO DE TESTE;

3. A EXECUÇÃO ISOLADA DESSE RED;

4. A DEMONSTRAÇÃO FÍSICA DE QUE O INSERT INCOERENTE É ACTUALMENTE
ACEITE;

5. O DIAGNÓSTICO POSTERIOR E ESTRITAMENTE READ-ONLY;

6. A PRESERVAÇÃO DO CONTROLO POSITIVO.

ESTA RATIFICAÇÃO NÃO AUTORIZA GREEN, MIGRATION 0039, MODELOS,
SCHEMAS, FUNÇÕES, TRIGGERS, FK, UNIQUE, CONSTRAINTS, TOKENS,
SQLSTATE, REGRESSÃO DE IMPLEMENTAÇÃO, 9B2, 9B4, 9C, 8B2, MOTOR
ADR-020, GATES, ENDPOINTS, WORKERS, SCHEDULER, DISPATCHER, DEPLOY,
RAILWAY OU PRODUÇÃO.

A MISSION-009B É AUTÓNOMA E NÃO AMPLIA RETROACTIVAMENTE A
MISSION-009A V0.2.

QUALQUER GREEN OU MECANISMO FÍSICO EXIGIRÁ INSTRUMENTO, AUDITORIA E
AUTORIZAÇÃO PRÓPRIOS E SEPARADOS.

## Declaração correctiva — registo literal

EU, MIGUEL, NO EXERCÍCIO DA AUTORIDADE FINAL DE PRODUTO, CORRIJO
EXCLUSIVAMENTE O NOME DA FIXTURE INDICADO NA MINHA RATIFICAÇÃO DA
MISSION-009B VERSÃO 1.0.

ONDE CONSTA:

postgresqL_intention_9b3

DEVE CONSTAR EXACTAMENTE:

postgresql_intention_9b3

ESTA CORRECÇÃO NOMINAL NÃO ALTERA OS BYTES RATIFICADOS, O SHA-256
1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50,
O TAMANHO DE 10888 BYTES, O ESCOPO, AS EXCLUSÕES OU QUALQUER OUTRA
PARTE DA RATIFICAÇÃO.

PERMANECEM PROIBIDOS GREEN, MIGRATION 0039, QUALQUER MECANISMO
FÍSICO, MOTOR ADR-020, GATES, DEPLOY E PRODUÇÃO.

## Função deste REPORT

O REPORT-021 apenas regista a declaração emitida directamente por Miguel. Não cria, substitui ou amplia a ratificação. A correcção nominal integra a interpretação exacta da declaração, e o identificador técnico autorizado é somente `postgresql_intention_9b3`. A grafia incorrecta `postgresqL_intention_9b3` não está autorizada e aparece apenas na reprodução literal da declaração correctiva.

O commit futuro fornecerá somente inclusão, cronologia e integridade Git complementar. A publicação documental é condição anterior à execução do RED. A criação isolada deste REPORT não torna a missão executável.

## Escopo técnico após publicação

Somente:

- um teste RED;
- uma fixture: `postgresql_intention_9b3`;
- um ficheiro técnico: `tests/test_adr020_activation_postgresql.py`;
- execução isolada do RED;
- controlo positivo;
- demonstração física da lacuna;
- diagnóstico posterior read-only.

## Proibições preservadas

- GREEN;
- migration 0039;
- escolha de mecanismo físico;
- função PostgreSQL;
- trigger;
- FK;
- UNIQUE;
- constraint;
- token;
- SQLSTATE;
- modelos;
- schemas;
- outros ficheiros técnicos;
- regressão de implementação;
- 9B2;
- 9B4;
- 9C;
- 8B2;
- motor ADR-020;
- gates;
- endpoints;
- workers;
- scheduler;
- dispatcher;
- deploy;
- Railway;
- produção;
- MIGRATION-BOOTSTRAP-0000-0001;
- alteração de migrations históricas;
- `docs/ROADMAP_OPS_AGENTES.md`.

## Estado operacional

- MISSION-009B ratificada humanamente;
- registo documental criado, mas ainda não publicado;
- RED bloqueado até commit e push documentais;
- motor desligado;
- gates bloqueados;
- migration 0039 inexistente;
- nenhuma implementação autorizada.

## Integridade

Este REPORT não inclui self-hash. O SHA-256 do REPORT será calculado externamente após auditoria. O documento deve permanecer em UTF-8 sem BOM, com LF, zero CRLF, uma newline final e zero trailing whitespace.
