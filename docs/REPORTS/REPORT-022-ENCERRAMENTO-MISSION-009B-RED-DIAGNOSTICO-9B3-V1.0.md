# REPORT-022 — Encerramento da MISSION-009B — RED Válido e Diagnóstico Técnico da Coerência Decisão–Execução 9B3 — Versão 1.0

## Estado

EVIDÊNCIA RED E DIAGNÓSTICO REGISTADOS — MISSION-009B ENCERRADA — GREEN NÃO AUTORIZADO

## 1. Registo documental

- Documento: `REPORT-022-ENCERRAMENTO-MISSION-009B-RED-DIAGNOSTICO-9B3-V1.0`
- Versão: `1.0`
- Estado: `EVIDÊNCIA RED E DIAGNÓSTICO REGISTADOS — MISSION-009B ENCERRADA — GREEN NÃO AUTORIZADO`
- Data: `2026-08-04`
- Baseline: `51f53857d304307b595cd1aaf41f05b619de8f32`
- Missão vinculada: `MISSION-009B V1.0`
- Teste RED: `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`
- Fixture: `postgresql_intention_9b3`
- Resultado: `RED_9B3_VALIDO_LACUNA_FISICA_PROVADA`
- Diagnóstico: `DIAGNOSTICO_9B3_CONCLUIDO_AGUARDA_INSTRUMENTO_GREEN`
- Estado GREEN: `NÃO AUTORIZADO`

## 2. Missão encerrada e autoridade documental

A missão encerrada é:

- Caminho: `docs/MISSIONS/MISSION-009B-ADR-020-INTENCAO-9B3-RED-DIAGNOSTICO-V1.0.md`
- Versão: `1.0`
- SHA-256: `1F2B7DCE4C599D76B140F8C13CEAC6157F614D1AB7384BF72E68627C8418CF50`

O registo da ratificação é `docs/REPORTS/REPORT-021-RATIFICACAO-MISSION-009B-ADR-020-INTENCAO-9B3-V1.0.md`, com SHA-256 `42149C981A277AD180F446ED3CD220781CCAEBB5E0911BB6CC5A1B8AC0ABB0BF`.

O objectivo da missão foi cumprido: o RED válido foi obtido, o diagnóstico read-only foi concluído e a `MISSION-009B` está encerrada. O próximo gate documental é um instrumento GREEN próprio e separado. Até que esse instrumento seja auditado, congelado, ratificado e publicado, nenhuma implementação é permitida.

## 3. Baseline técnica e resultado RED

- HEAD da execução: `51f53857d304307b595cd1aaf41f05b619de8f32`
- Ficheiro técnico modificado: `tests/test_adr020_activation_postgresql.py`
- Fixture: `postgresql_intention_9b3`
- Teste: `test_activation_generation_rejects_execution_from_different_exact_decision_via_core`
- Comando executado: `python -m pytest tests/test_adr020_activation_postgresql.py::test_activation_generation_rejects_execution_from_different_exact_decision_via_core -q`
- Resultado exacto: `1 failed in 7.03s`
- Falha vinculante: `Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>`

O teste não foi executado nesta rodada de encerramento documental. Este REPORT regista o resultado exacto da execução RED já realizada sob a `MISSION-009B`.

## 4. Provas alcançadas

A execução RED demonstrou cumulativamente que:

- o PostgreSQL isolado iniciou;
- as migrations até 0038 foram aplicadas;
- `D1` e `D2`, exactas, existentes e aprovadas, persistiram;
- `E1` e `E2`, distintas e ambas pertencentes exactamente a `D1`, persistiram;
- o controlo positivo `G_control = D1/E1` persistiu;
- `G_false = D2/E2` foi aceite;
- nenhuma segunda falsidade foi observada;
- nenhuma falha de fixture, Docker, conexão, migration, `UNIQUE`, campo obrigatório ou controlo positivo causou o RED.

A aceitação de `G_false` e a ausência da excepção esperada constituem a causa vinculante e única do RED.

## 5. Lacuna física provada

A lacuna física provada é cumulativa:

- `G` possui uma decisão exacta `D2` válida;
- `G` possui uma execução `E2` válida;
- `E2` pertence exactamente a `D1`;
- `D1` e `D2` são distintas;
- não existe garantia PostgreSQL que compare cumulativamente:

  `G.activation_decision_id`

  `G.activation_decision_record_hash`

  com:

  `E.activation_decision_id`

  `E.activation_decision_record_hash`.

Assim, o banco aceita separadamente referências válidas que, quando relacionadas pela geração, representam decisões exactas diferentes.

## 6. Garantias físicas existentes

O PostgreSQL garante separadamente:

1. FK exacta `G→D` sobre `(activation_decision_id, activation_decision_record_hash)`;
2. FK simples `G→E` sobre `activation_execution_id`;
3. FK exacta `E→D` sobre `(activation_decision_id, activation_decision_record_hash)`;
4. aprovação, integralidade, unicidades e append-only.

Nenhuma dessas garantias relaciona cumulativamente a decisão de `G` com a decisão exacta pertencente a `E`. A validade individual das três relações não implica a coerência decisão–execução requerida pela intenção 9B3.

## 7. Caminhos afectados e fronteira soberana

A lacuna física alcança:

- ORM normal;
- SQLAlchemy Core;
- SQL cru;
- `COPY`;
- bulk inserts.

Listeners ORM não constituem fronteira soberana e não protegem todos esses caminhos de escrita. O RED usa SQLAlchemy Core e demonstra a ausência da garantia na fronteira PostgreSQL, sem usar `NormativeActivation`.

## 8. Mecanismos diagnosticados, não escolhidos

Foram identificadas apenas como opções técnicas possíveis:

- trigger PostgreSQL prospectivo;
- FK composta `G(execution_id, decision_id, decision_hash) → E`, com chave candidata/`UNIQUE` correspondente;
- constraint trigger diferível;
- alteração ou normalização do modelo;
- listener ORM como defesa em profundidade;
- procedimento ou view de escrita controlada com privilégios restringidos;
- entidade imutável de vínculo.

Nenhuma opção foi seleccionada. Nenhuma recomendação definitiva foi emitida. Nenhum nome de função, trigger, constraint, token ou `SQLSTATE` foi escolhido. Nenhuma migration foi autorizada.

Uma `CHECK` simples não pode consultar outra linha ou tabela de forma suportada para impor a relação 9B3.

## 9. Histórico e prospectividade

- a lacuna existe fisicamente desde a migration 0024;
- existe possibilidade lógica de registos históricos incoerentes;
- esta missão não auditou dados persistentes;
- não se afirma existência nem ausência de incoerências históricas;
- uma garantia futura deverá ser pelo menos prospectiva;
- política histórica, `NOT VALID`, `VALIDATE` ou reparação exigem decisão própria;
- nenhuma correcção destrutiva ou retroactiva está autorizada.

## 10. Ordem e coexistência de triggers

- `trg_activation_generations_validate_insert` é o único trigger `BEFORE INSERT` actual da tabela;
- os triggers append-only actuam em `UPDATE`, `DELETE` ou `TRUNCATE`;
- múltiplos triggers PostgreSQL do mesmo tipo e evento são executados por ordem alfabética;
- qualquer mecanismo futuro deverá decidir coexistência e risco de máscara;
- objectos históricos não poderão ser substituídos silenciosamente.

Este diagnóstico não escolhe a introdução, alteração, substituição ou ordenação de qualquer trigger.

## 11. Auditoria do teste RED

O teste RED:

- é homogéneo;
- usa SQLAlchemy Core;
- não usa `NormativeActivation`;
- contém o controlo positivo `G_control = D1/E1`;
- preserva uma única falsidade soberana em `G_false = D2/E2`, pois `E2` pertence exactamente a `D1`;
- diferencia apenas identidades e unicidades tecnicamente necessárias;
- não apresenta fragilidade conhecida capaz de converter o RED em falso-positivo;
- deve permanecer inalterado até autorização GREEN.

O teste RED permanece modificado e não staged. Não foi alterado nem staged nesta rodada.

## 12. Estado da migration 0039

A migration 0039 é inexistente e não autorizada. O RED não concede autoridade automática. `revision`, `down_revision`, nome, mecanismo, função, trigger, token e `SQLSTATE` permanecem não escolhidos.

## 13. Fronteira de um futuro GREEN

Um instrumento futuro, próprio e separado, deverá decidir expressamente:

- mecanismo físico;
- objectos e nomes exactos;
- migration e lineage;
- carácter prospectivo e política histórica;
- comportamento fail-closed;
- comparação cumulativa ID/hash;
- cardinalidade;
- cobertura ORM/Core/raw/`COPY`/bulk;
- ordem e coexistência de triggers;
- risco de máscara;
- token e `SQLSTATE`, caso utilizados;
- downgrade;
- testes focados;
- bypass matrix;
- regressões;
- ficheiros autorizados e proibidos.

Esse instrumento não é criado nesta rodada. O diagnóstico aqui registado não antecipa as suas decisões.

## 14. Função deste REPORT

O `REPORT-022` apenas regista evidência e diagnóstico. Não cria autoridade GREEN, não escolhe arquitectura, não autoriza migration 0039 e não transforma o RED em implementação.

Commit e publicação futuros fornecem somente inclusão, cronologia e integridade documental. O teste RED permanece modificado e não staged.

## 15. Proibições preservadas

Permanecem expressamente proibidos:

- alteração do teste RED;
- GREEN;
- migration 0039;
- função;
- trigger;
- FK;
- `UNIQUE`;
- constraint;
- token;
- `SQLSTATE`;
- modelos;
- schemas;
- migrations históricas;
- outros testes;
- regressão;
- staging do teste;
- commit técnico;
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
- `MIGRATION-BOOTSTRAP-0000-0001`;
- `docs/ROADMAP_OPS_AGENTES.md`.

O motor ADR-020 permanece desligado e os gates permanecem bloqueados.

## 16. Integridade documental

Este documento não inclui self-hash. O SHA-256 será calculado externamente após auditoria. O ficheiro deve permanecer em UTF-8 sem BOM, com LF, zero CRLF, uma newline final e zero trailing whitespace.

## 17. Estado final da MISSION-009B

- objectivo da missão cumprido;
- RED válido obtido;
- diagnóstico read-only concluído;
- `MISSION-009B` encerrada;
- próximo gate documental: instrumento GREEN separado;
- GREEN não autorizado;
- nenhuma implementação permitida até auditoria, congelamento, ratificação e publicação desse instrumento futuro.

Veredicto: `REPORT_022_CRIADO_MISSION_009B_ENCERRADA_GREEN_NAO_AUTORIZADO`.
