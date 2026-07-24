# ADR-016 — Fronteira soberana de proveniência do DataSanitizationAgent

## 1. Identificação

**ADR:** ADR-016
**Bloco:** B14-SVC-02
**Autoridade arquitectural:** GPT
**Autoridade de ratificação:** Miguel
**Relação:** aditivo a `ADR-011-MIGRACAO-L3-DATA-SANITIZATION`

## 2. Estado

**Estado: RATIFICADO POR GPT E MIGUEL — DECISÃO ARQUITECTURAL AUTÓNOMA E ADITIVA; SEM AUTORIZAÇÃO PRODUTIVA**

`ADR-011-PROVENIENCIA-001: RESOLVIDO POR ADR-016`. O gate de implementação produtiva permanece `PENDENTE E BLOQUEADO`. Não há autorização produtiva, implementação produtiva ratificada nem fechamento automático do gate produtivo.

Registo histórico preservado: antes da auditoria GPT e da ratificação literal de Miguel, o ADR-016 encontrava-se `PROPOSTO`, com GPT `PENDENTE`, Miguel `PENDENTE` e o gate arquitectural `ADR-011-PROVENIENCIA-001` ainda `ABERTO`. Este registo descreve o estado anterior e não altera o estado normativo vigente.

## 3. Contexto

O ADR-011 governa B14.3C em `shadow/dry_run`: missão explícita, contexto previamente autorizado, sem reader, BD, escrita, scheduler ou registry genéricos, publicação autónoma ou autoridade fiscal/canónica. A auditoria de B14-SVC-01 provou que a futura proveniência produtiva é fronteira distinta.

## 4. Problema

`_montar_contexto_engines` é fonte candidata, não fronteira soberana: lê todo o histórico sem cutoff efectivo, colapsa ausência em zero, trunca negativos nos lucros, usa regime actual/default e fórmulas não ratificadas, autoriza apenas por `empresa_id`, inclui Session e extras e não materializa snapshot reproduzível.

## 5. Relação com ADR-011

O ADR-016 é autónomo e aditivo. Não substitui, renumera, reescreve, rectifica ou invalida o ADR-011. O `ADR-011-MIGRACAO-L3-DATA-SANITIZATION` permanece canónico para B14.3C em sombra, motor-first, read-only, `dry_run`, sem reader e com contexto previamente autorizado.

## 6. Gate histórico

`ADR-011-PROVENIENCIA-001` é o gate histórico resolvido arquitecturalmente pelo ADR-016 após auditoria GPT aprovada e ratificação literal de Miguel. Os estados são explicitamente distintos:

- gate de decisão arquitectural `ADR-011-PROVENIENCIA-001`: `RESOLVIDO POR ADR-016`;
- gate de implementação produtiva: `PENDENTE E BLOQUEADO`.

A integração continuará bloqueada até implementação, testes, auditoria GPT e ratificação Miguel próprios.

## 7. Decisão

A futura integração terá componentes externos ao agente nesta ordem funcional: pedido explícito de proveniência; verificação de autoridade; leitura soberana read-only; snapshot temporal; manifestação de proveniência; projecção estrita; criação da missão L3; execução controlada do adapter. Agente e adapter não consultam BD directamente.

## 8. Escopo

Definir identidade, autorização, temporalidade, leitura, manifestação, projecção, reprodutibilidade, segurança, falha e gates da futura fronteira produtiva.

## 9. Não escopo

Não implementar reader, projector, produtor fiscal, contrato, migration, scheduler, registry, executor, persistência, endpoint ou job; não escolher regra fiscal, granularidade universal ou nome final dos componentes.

## 10. Invariantes de identidade

Todo pedido inclui `actor_id`, `tenant_id`, `empresa_id`, identificador único, `period_start`, `period_end` e `reference_at`. No fluxo do proprietário, `actor_id == tenant_id` e nenhum vínculo delegado é exigido; a ausência do vínculo nesse fluxo é estado contratual legítimo, não default fictício. No fluxo delegado, `actor_id != tenant_id` e o identificador/prova do vínculo soberano é obrigatório. O contrato futuro deverá distinguir estritamente fluxo próprio e fluxo delegado. Identificadores são inteiros positivos e não booleanos. Nenhuma função que receba somente `empresa_id` satisfaz a fronteira.

## 11. Autorização

No fluxo do proprietário, `actor_id == tenant_id`, nenhum vínculo delegado é exigido e a Empresa é comprovada por `(empresa_id, user_id=tenant_id)`. No fluxo delegado, `actor_id != tenant_id`; o identificador/prova do vínculo soberano é obrigatório e comprovam-se cumulativamente o proprietário da Empresa e a autoridade do actor conforme ADR-003, ADR-004 e ADR-005, sem inferir permissões. `actor_id != tenant_id` sem vínculo válido, activo e compatível com Empresa e escopo bloqueia fail-closed.

Vínculo ausente, expirado, revogado, suspenso ou fora do escopo bloqueia fail-closed. O predicado de autoridade integra as consultas e é reconfirmado antes do retorno. Negação não produz leitura transversal, missão ou mutação.

## 12. Temporalidade

Exige-se `period_start <= period_end <= reference_at`. Todos os valores pertencem à mesma janela; documentos posteriores a `period_end` são excluídos; alterações após `reference_at` não mudam snapshot materializado. Datas nulas ou inválidas seguem política explícita fail-closed. `MAX(data_emissao)` não é cutoff. Estado actual de Empresa não se aplica retroactivamente sem vigência provada. A janela é explícita, sem impor periodicidade fiscal universal.

## 13. Reader soberano

O futuro reader soberano de proveniência recebe Session por injecção, usa `no_autoflush`, é estritamente read-only e não cria, altera, elimina, faz flush, chama LLM/agente ou cria missão. Não devolve ORM, Session ou query e não inventa fórmulas fiscais.

## 14. Snapshot

A leitura autorizada materializa snapshot imutável da janela e do instante de referência. O snapshot separa dados lidos, classificações e estados de disponibilidade, e não muda por alteração posterior da BD.

## 15. Manifestação de proveniência

Antes da projecção existe manifestação de proveniência imutável com: versão do esquema; identidades; janela; `reference_at`; fonte; versão da selecção; IDs internos opacos ou hashes dos documentos incluídos e excluídos com motivo; contagens; políticas de duplicidade, validade, cancelamento/devolução; unidade monetária; produtor canónico e disponibilidade por campo; hash do snapshot; instante de criação.

A manifestação não atravessa integralmente o contexto; poderá associar-se à missão por identificador/hash em contrato futuro. É proibido usar CPF, CNPJ, chave integral de NF-e ou conteúdo bruto como identificador de proveniência.

## 16. Projector soberano

O futuro projector soberano recebe somente snapshot imutável e manifestação. Selecciona exclusivamente campos contratuais, não transporta auxiliares, não usa defaults fiscais silenciosos, não converte ausência em zero, não trunca negativos, não recebe Session nem lê BD. Produz estrutura serializável antes de `context_hash` e `AgentMission`.

## 17. Oito campos fiscais

O contexto contém `empresa_id` e exactamente: `faturamento`, `custos`, `lucro_contabil`, `lucro`, `base_calculo`, `icms_pago`, `icms_devido`, `custo_fiscal_entradas`.

Cada campo assume `PRODUZIDO_POR_FONTE_CANONICA`, `AUSENTE_COM_PROVENIENCIA` ou `INDISPONIVEL_POR_REGRA_NAO_RATIFICADA`. Proíbe-se zero por ausência, fórmula inventada, alias não ratificado, valor de produto como custo contabilístico, `valor_st` como ICMS pago/devido, duplicação de custos, `0.08` como autoridade normativa e regime actual sobre histórico sem vigência.

## 18. Campos derivados

O reader não calcula `lucro`, `lucro_contabil`, `base_calculo` ou obrigação fiscal. Campo derivado exige produtor canónico ratificado e identificável; sem ele permanece ausente/indisponível, com motivo na manifestação, sem fallback ou valor fabricado.

## 19. Regime tributário

regime não integra o contrato: é dependência auxiliar potencial. Se produtor futuro o exigir, a leitura será autorizada, domínio validado, vigência compatível e fonte identificada. Ausência, vazio, nulo ou Empresa inexistente não viram `presumido`. Regime não atravessa o contexto e fica na manifestação ou input do produtor, conforme contrato futuro.

## 20. Ausência, null, zero e negativos

Preservam-se campo omitido, presente com `null`, zero numérico e valor negativo. **ausência não vira zero**; `null` não vira zero; zero real permanece zero; negativo permanece negativo. O sanitizador pode sinalizar negativo, mas a fronteira não o trunca. `coalesce(..., 0)` não esconderá ausência na projecção.

## 21. Validade documental

Só documentos que satisfaçam predicado canónico de validade alimentam o snapshot. Cancelamento, devolução, substituição e inutilização exigem política explícita; sem política ratificada, o campo afectado fica bloqueado. O ADR define requisito arquitectural, reconhece disponibilidade actual limitada do schema e remete a implementação futura, sem inventar status ou coluna.

## 22. Duplicidade

Usa-se hash documental quando existente. Ausência de hash não autoriza deduplicação presumida. Ambiguidade bloqueia o campo; manifestação regista inclusões, exclusões e política aplicada.

## 23. Compatibilidade contratual

É proibido entregar directamente `_montar_contexto_engines` ao adapter: contém Session, `regime`, `atividade`, `data_referencia`, `context_flags` e outros campos extras; usa defaults/fórmulas não ratificados; não comprova autorização; não produz snapshot temporal.

O projector produz exactamente `empresa_id` e os oito campos permitidos quando disponíveis. Nenhum auxiliar cru atravessa `extra="forbid"`.

## 24. Reprodutibilidade

Ordem obrigatória: autorizar; ler; materializar snapshot; criar manifestação; projectar; serializar canonicamente; calcular `context_hash`; criar missão; reconfirmar hashes antes da execução. Mesmo snapshot e versão de regras produzem o mesmo contexto/hash.

Exige-se representação numérica canónica e política explícita de precisão. `1`, `1.0` e `"1.00"` não são equivalentes por inferência silenciosa; escala, arredondamento e conversão pertencem ao produtor ratificado. Sem decisão, o campo fica indisponível.

## 25. Falha segura

A fronteira falha fail-closed perante identidade inválida, actor/tenant incoerentes, Empresa não autorizada, janela inválida, política ausente, classificação documental insuficiente, duplicidade ambígua, regime sem vigência, produtor inexistente, extra, Session/ORM no payload, hash divergente ou snapshot irreproduzível.

Falha significa nenhuma missão produtiva, escrita, publicação ou fallback; o resultado operacional é auditável e sanitizado.

## 26. Scheduler, registry e executor

Não há ligação a `agent_scheduler.py`, scheduler, registry genérico, `run_all`, executor legado ou contexto genérico. Activação futura depende de missão/evento explícito e adapter L3 independente.

## 27. Segurança e LGPD

Identificadores documentais são IDs internos opacos ou hashes criptográficos. Logs não expõem valores fiscais integrais, CPF, CNPJ, chave de NF-e ou conteúdo documental. Princípios de minimização, autorização e escopo dos ADR-006 e ADR-008 permanecem aplicáveis.

## 28. Observabilidade

Registam-se identificador do pedido, estados sanitizados, versões de regras, hashes, contagens e motivos codificados de inclusão, exclusão ou bloqueio. Não se registam payloads integrais nem dados protegidos.

## 29. Consequências

A fronteira fica separada do agente, reproduzível e auditável, ao custo de componentes e contratos futuros, políticas canónicas por campo e gates independentes de decisão e implementação.

## 30. Implementação futura

Nomes finais são reservados ao bloco de implementação. Esse bloco deverá criar componentes dedicados, contratos de snapshot/manifestação, produtores ratificados e integração explícita, sem alterar esta decisão por implementação implícita.

## 31. Testes futuros obrigatórios

Devem cobrir: actor/tenant inválidos; proprietário sem vínculo delegado autorizado; proprietário com vínculo delegado indevido ou incoerente rejeitado conforme contrato futuro; actor diferente de tenant sem vínculo bloqueado; actor diferente de tenant com vínculo válido limitado ao escopo ratificado; vínculo expirado, revogado, suspenso ou fora do escopo; Empresa inexistente ou de outro utilizador; acesso negado sem mutação; predicado e reconfirmação de autoridade; janela inválida; documento posterior ao cutoff; data nula/inválida; ausência documental; zero, `null`, omissão e negativo preservado; cancelamento, devolução e duplicidade com/sem hash; regime ausente, inválido ou sem vigência; produtor ausente; `base_calculo` não fabricada; `icms_pago` não inferido de `valor_st`; extras, Session e ORM rejeitados; snapshot imutável; `context_hash` reproduzível; BD posterior sem mudar missão; nenhum scheduler/registry genérico, escrita ou LLM; logs sem dados sensíveis.

## 32. Critérios para fechamento de implementação

Exigem implementação explicitamente autorizada, testes futuros aprovados, manifestação e hashes auditáveis, auditoria GPT e ratificação Miguel. Só então o gate de implementação produtiva poderá mudar; a decisão arquitectural ratificada não autoriza produção por si.

## 33. Exclusões

BudgetGuard e fallback de modelos não participam da fronteira determinística. Não se decide regra fiscal, produtor, precisão, schema, endpoint, scheduler, registry, executor ou LLM.

## 34. Matriz de rastreabilidade com REPORT-004

| Evidência do REPORT-004 | Decisão ADR-016 |
|---|---|
| histórico sem cutoff | janela e snapshot temporal obrigatórios |
| autorização só por empresa | identidades, vínculo, predicado e reconfirmação |
| ausência colapsada e perda observada de valores negativos | quatro estados preservados |
| fórmula/regime não ratificados | produtor canónico e vigência obrigatórios |
| Session e extras | reader/projector externos e `extra="forbid"` |
| fonte mutável sem snapshot | manifestação, serialização e hashes |
| oito campos exactos | disponibilidade explícita por campo |
| gate aberto | gates de decisão e implementação separados |

## 35. Ratificação concluída

| Papel | Autoridade | Estado |
|---|---|---|
| Auditor arquitectural | GPT | APROVADO |
| Ratificador de produto | Miguel | RATIFICADO |

Evidência: REPORT-013 auditado e declaração literal de Miguel reproduzida no REPORT-014.

A ratificação decide arquitectura; não implementa componentes, não autoriza produção e não fecha o gate de implementação produtiva. Também não escolhe regras fiscais, produtores, precisão, schema, endpoint, scheduler, registry, executor, LLM ou algoritmo criptográfico.

`ADR-011-PROVENIENCIA-001: RESOLVIDO POR ADR-016`.

Gate de implementação produtiva: `PENDENTE E BLOQUEADO`. A integração produtiva continua bloqueada e não autorizada.
