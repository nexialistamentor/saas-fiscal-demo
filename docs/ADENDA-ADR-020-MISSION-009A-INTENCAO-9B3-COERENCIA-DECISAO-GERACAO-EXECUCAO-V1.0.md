# ADENDA-ADR-020 — MISSION-009A — INTENÇÃO 9B3 — Coerência da Decisão Soberana entre ActivationGeneration e ActivationExecution — Versão 1.0

## 1. Identificação documental

- Documento: `ADENDA-ADR-020-MISSION-009A-INTENCAO-9B3-COERENCIA-DECISAO-GERACAO-EXECUCAO-V1.0`
- Versão: `1.0`
- Data da proposta: `2026-08-04`
- Baseline Git: `1825e321211c9390d5c967e1d194aa6223000460`
- ADR subordinante: `ADR-020 v0.3 R2`
- SHA-256 externo da ADR-020 registado na MISSION-008: `b57c4c20cb8976940e35b91469cd998dd9a6367e96c4e12c096a3f02a31135ad`

## 2. Estado documental

**PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL**

Esta minuta não cria autoridade vigente, não declara vigência documental ou técnica e não presume ratificação.

## 3. Natureza e subordinação

Esta adenda é uma proposta normativa estritamente subordinada à `ADR-020 v0.3 R2`. A MISSION-009A constitui a origem operacional da descoberta da lacuna, nunca a fonte originária de canonicidade. Esta proposta não reescreve, substitui, reinterpreta ou ratifica os bytes e as decisões originárias da ADR-020; caso venha a ser expressamente ratificada, acrescentará exclusivamente a invariável definida neste documento, em estrita subordinação à ADR-020.

Nos termos do ADR-001, o percurso institucional aplicável permanece: **Evidência → Auditoria Independente → Ratificação Institucional**. A elaboração desta minuta satisfaz apenas a preparação do objecto documental a submeter a esse percurso.

## 4. Evidência da lacuna

No exame operacional da MISSION-009A foi identificada a necessidade de uma decisão canónica própria sobre a coerência entre a decisão soberana registada numa nova `ActivationGeneration` e a decisão soberana da `ActivationExecution` por ela referenciada.

A existência da descoberta não resolve a matéria. Sem adenda auditada e ratificada, nenhuma invariável nova produz efeitos documentais. Sem implementação técnica posterior separadamente autorizada, não existe enforcement técnico nem efeito operacional.

## 5. Objecto exclusivo

O objecto exclusivo desta proposta é definir a coerência da identidade soberana exacta entre uma nova `ActivationGeneration` e a `ActivationExecution` por ela referenciada, nos limites prospectivos definidos neste documento.

A adenda propõe somente a invariável canónica. Não escolhe nem autoriza qualquer mecanismo técnico para a impor.

## 6. Invariável canónica proposta

Caso esta decisão entre em vigor documentalmente, toda nova `ActivationGeneration` abrangida prospectivamente pela invariável deve pertencer à mesma decisão soberana exacta da `ActivationExecution` por ela referenciada. O enforcement técnico somente poderá ocorrer após implementação posterior separadamente autorizada.

`ActivationGeneration.activation_decision_id` deve ser igual a `ActivationExecution.activation_decision_id`.

`ActivationGeneration.activation_decision_record_hash` deve ser igual a `ActivationExecution.activation_decision_record_hash`.

A coincidência de apenas uma componente não satisfaz a invariável.

A `ActivationDecision` exacta e a `ActivationExecution` exacta referenciadas devem existir fisicamente.

A proposta é prospectiva e não declara conformidade retroactiva.

## 7. Identidade soberana exacta

A identidade soberana exacta da decisão é o par indivisível:

- `activation_decision_id`;
- `activation_decision_record_hash`.

Nenhuma das componentes, considerada isoladamente, identifica de modo suficiente a decisão soberana exacta para efeitos desta proposta. A igualdade exigida abrange cumulativamente ambas as componentes e as entidades exactas fisicamente existentes.

## 8. Prospectividade

A invariável proposta adquire vigência documental caso venha a ser expressamente ratificada. O seu enforcement técnico aplica-se somente a novas `ActivationGeneration` criadas após implementação técnica posterior, própria e separadamente autorizada.

Antes da vigência documental, esta minuta não rege matéria alguma; antes da implementação, não produz escrita, validação, execução ou outro efeito operacional.

## 9. Preservação histórica

O histórico anterior é integralmente preservado. Esta proposta determina:

- sem backfill;
- sem reconstrução;
- sem saneamento retroactivo;
- sem `UPDATE` histórico;
- sem `DELETE` histórico;
- sem validação retroactiva;
- sem alegar que linhas anteriores já cumprem a invariável.

Nenhuma conformidade retroactiva é declarada, inferida ou presumida.

## 10. Exclusões expressas

Ficam literalmente excluídos do objecto e da autoridade desta proposta:

- decisão da `NormativeActivation` contra `ActivationGeneration` — 9B2;
- decisão da `NormativeActivation` contra a sua `ActivationExecution`;
- `scope_hash` — 9C;
- `target_manifest_hash`;
- igualdade ou interpretação de bindings;
- `composition_manifest`;
- `subject`;
- `review`;
- favorabilidade — 8B2;
- gates;
- escolha de norma vencedora;
- scheduler;
- dispatcher;
- endpoints;
- workers;
- publicação;
- deploy;
- Railway;
- produção;
- activação do motor ADR-020;
- `MIGRATION-BOOTSTRAP-0000-0001`.

## 11. Separação entre autoridade e mecanismo técnico

Esta adenda propõe somente a invariável canónica. Permanecem sem autorização:

- teste RED;
- fixture;
- migration 0039;
- FK composta;
- `UNIQUE` adicional;
- trigger;
- constraint trigger;
- função PostgreSQL;
- nome de constraint;
- nome de trigger;
- token;
- `SQLSTATE`;
- diagnóstico;
- ordem nominal;
- implementação GREEN.

Não são autorizados trigger, constraint, função PostgreSQL, migration ou qualquer outro mecanismo de execução. A escolha futura de mecanismo requer autoridade própria e não pode ser inferida desta proposta.

## 12. Relação com 9B2

A futura 9B3, quando ratificada e implementada, poderá tornar mais isolável a comparação entre:

`NormativeActivation.decision`

e:

`ActivationGeneration.decision`.

Esta observação não ratifica a 9B2, não decide o seu conteúdo e não lhe concede autoridade documental ou técnica.

## 13. Relação com a futura coerência NormativeActivation↔ActivationExecution

Regista-se somente como pendência não autorizada:

`NormativeActivation.activation_decision_id/hash` = decisão soberana pertencente à `ActivationExecution` referenciada.

Designação operacional proposta:

**MISSION-009A — INTENÇÃO 9B4 — COERÊNCIA DECISÃO SOBERANA NORMATIVEACTIVATION↔ACTIVATIONEXECUTION**

Esta designação é não canónica, requer auditoria própria, requer autoridade documental própria, não pertence à 9B3 e não está autorizada por esta adenda.

## 14. Integridade documental

- `SHA-256_DA_ADENDA`: `EXTERNO — A REGISTAR NO RELATÓRIO POSTERIOR DE RATIFICAÇÃO APÓS O CONGELAMENTO DOS BYTES; NÃO EMBUTIR O VALOR NOS BYTES DESTA ADENDA.`

O SHA-256 integral desta adenda nunca integra os bytes que representa.
Primeiro congelam-se os bytes; depois calcula-se externamente o
SHA-256. Qualquer alteração posterior invalida o hash, a auditoria e a
ratificação correspondentes.

Este documento não contém hash próprio, placeholder hexadecimal, manifesto adicional ou envelope criptográfico novo.

## 15. Processo de auditoria e ratificação

O parecer do GPT constitui auditoria, não ratificação. Codex é redactor subordinado, não autoridade. Um commit Git prova inclusão e fornece integridade complementar, mas não constitui ratificação.

Somente uma declaração humana expressa de quem exerça a Autoridade Final de Produto — actualmente Miguel — sobre a versão e o SHA-256 exacto pode ratificar esta adenda. Uma ratificação futura deve ser registada no `REPORT-020`. Nenhuma ratificação é presumida, e a palavra `RATIFICADA` não constitui estado vigente desta minuta.

## 16. Condições de vigência documental

A vigência documental depende de bytes finais congelados, cálculo externo do SHA-256, auditoria independente e declaração humana expressa da Autoridade Final de Produto que identifique a versão e o SHA-256 exacto. O registo posterior aplicável apenas documenta essa decisão já emitida e não constitui, substitui ou completa a autoridade ratificadora.

Enquanto essas condições não forem satisfeitas, o estado permanece o definido na secção 2. Mesmo eventual vigência documental não autoriza implementação, RED, migration 0039, trigger, constraint, função PostgreSQL, activação do motor ou abertura de gates.

## 17. Não executabilidade

Esta minuta não cria autoridade vigente; não autoriza RED; não autoriza migration 0039; não autoriza trigger, constraint ou função PostgreSQL; não autoriza activação do motor; não declara implementação concluída; não declara ratificação por Miguel; e não declara vigência técnica.

O motor ADR-020 permanece desligado e os gates permanecem bloqueados. Nenhum código, teste, fixture, migration, SQL, endpoint, worker, publicação, deploy ou operação é autorizado por este documento.

## 18. Registo de elaboração

- Documento: `ADENDA-ADR-020-MISSION-009A-INTENCAO-9B3-COERENCIA-DECISAO-GERACAO-EXECUCAO-V1.0`
- Versão: `1.0`
- Estado: `PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL`
- Data da proposta: `2026-08-04`
- Baseline Git: `1825e321211c9390d5c967e1d194aa6223000460`
- ADR subordinante: `ADR-020 v0.3 R2`
- Redactor subordinado: Codex sob instrução técnica supervisionada
- Auditor independente: PENDENTE
- Autoridade soberana competente: Autoridade Final de Produto — actualmente exercida por Miguel — decisão expressa pendente
- Relatório posterior previsto: `docs/REPORTS/REPORT-020-RATIFICACAO-ADENDA-ADR-020-MISSION-009A-INTENCAO-9B3-V1.0.md`
