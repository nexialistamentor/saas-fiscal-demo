# MISSION-006 — B14-SVC-02 — Redação do ADR-016 de proveniência soberana

## 1. Identificação

**Missão:** `MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA`  
**Bloco:** `B14-SVC-02`  
**Baseline obrigatória:** `b1775217cbdbb9490aab442bc705f54081f9dc73`  
**Executor:** Codex  
**Autoridade arquitectural:** GPT  
**Autoridade de ratificação:** Miguel  
**Natureza:** documental, com leitura estática limitada e sem implementação  
**Versão da missão:** v1.1 — rectificada após auditoria GPT  
**Estado esperado do repositório:** `main`, `HEAD == origin/main == baseline`

---

## 2. Objectivo

Redigir uma proposta autónoma de ADR para a futura fronteira produtiva de proveniência do `DataSanitizationAgent`.

O novo ADR deve:

1. preservar integralmente o `ADR-011-MIGRACAO-L3-DATA-SANITIZATION.md`;
2. manter válida a decisão de B14.3C segundo a qual o adapter em sombra não possui reader e recebe contexto previamente autorizado;
3. separar formalmente o modo sombra da futura integração produtiva;
4. transformar a auditoria ratificada do `B14-SVC-01` numa decisão arquitectural explícita;
5. impedir qualquer ligação produtiva directa entre `_montar_contexto_engines` e o adapter L3;
6. definir uma fronteira read-only, autorizada, temporal, reproduzível e fail-closed;
7. mapear o gate histórico `ADR-011-PROVENIENCIA-001` para o novo ADR;
8. não implementar reader, projector, contratos, migrations, scheduler, registry, executor ou persistência.

---

## 3. Origem e enquadramento fornecidos pelo GPT

A investigação já concluída e ratificada provou que:

- `ADR-011` regula a migração B14.3C em `shadow/dry_run`;
- a afirmação “não haverá reader” é correcta apenas nesse escopo;
- o contexto de B14.3C é recebido como contexto previamente autorizado;
- a futura integração produtiva constitui uma fronteira distinta;
- `_montar_contexto_engines`, em `app/services/insights_engine.py`, é somente fonte candidata;
- essa função agrega histórico sem cutoff efectivo;
- ausência é colapsada em zero;
- negativos são truncados em campos de lucro;
- `regime` actual e default silencioso influenciam `base_calculo`;
- autorização é feita apenas por `empresa_id`;
- Session e campos extras impedem entrega directa ao contrato `extra="forbid"`;
- não existe snapshot produtivo reprodutível;
- o gate operacional `ADR-011-PROVENIENCIA-001` permanece aberto;
- `ADR-016` não está utilizado nem reservado no repositório;
- `ADR-012` e `ADR-013` já pertencem às migrações dos agentes seguintes.

O Codex não deve repetir a exploração ampla já executada nem procurar nova numeração.

---

## 4. Decisão arquitectural que deve ser redigida

O novo ADR deve materializar, sem reinterpretar, as decisões seguintes.

### 4.1 ADR autónomo e aditivo

Criar:

`docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md`

O ADR-016 será autónomo e aditivo.

Não:

- substitui;
- renumera;
- reescreve;
- rectifica;
- ou invalida

o ADR-011.

O ADR-011 continua canónico para B14.3C em sombra.

### 4.2 Identidade do gate histórico

O identificador histórico:

`ADR-011-PROVENIENCIA-001`

não deve ser apagado nem reescrito em missões e relatórios anteriores.

O ADR-016 deve declarar que esse identificador passa a ser o **gate histórico resolvido arquitecturalmente pelo ADR-016 somente após auditoria GPT e ratificação Miguel**.

Enquanto o ADR-016 estiver apenas proposto:

- o gate continua `ABERTO`;
- integração produtiva continua bloqueada.

Após ratificação, distinguir obrigatoriamente dois estados:

- **gate de decisão arquitectural** `ADR-011-PROVENIENCIA-001`: `RESOLVIDO POR ADR-016`;
- **gate de implementação produtiva**: `PENDENTE E BLOQUEADO`;
- integração produtiva continua bloqueada até implementação, testes, auditoria GPT e ratificação Miguel próprios.

É proibido usar a expressão genérica “gate fechado” sem indicar qual dos dois estados está a ser referido.

### 4.3 Separação entre sombra e produção

#### B14.3C — sombra

Permanece:

- missão explícita;
- contexto previamente autorizado;
- sem reader;
- sem BD;
- sem scheduler genérico;
- sem registry genérico;
- sem escrita;
- sem publicação autónoma;
- `dry_run`;
- read-only;
- motor-first;
- sem autoridade fiscal ou canónica.

#### Fronteira produtiva futura

Exigirá componentes externos ao agente:

1. pedido explícito de proveniência;
2. verificação de autoridade;
3. leitura soberana read-only;
4. snapshot temporal;
5. manifestação de proveniência;
6. projecção estrita;
7. criação da missão L3;
8. execução do adapter em sombra controlada ou modo futuro ratificado.

O agente e o adapter não devem consultar BD directamente.

### 4.4 Reader e projector dedicados

A futura integração produtiva deve possuir componentes dedicados, com nomes finais reservados à implementação, equivalentes semanticamente a:

- **reader soberano de proveniência**;
- **projector soberano do contexto**.

O reader:

- recebe Session por injecção;
- usa `no_autoflush`;
- é estritamente read-only;
- não cria, altera, elimina ou faz flush;
- não devolve ORM;
- não devolve Session;
- não devolve query;
- não executa fórmulas fiscais inventadas;
- não chama LLM;
- não chama agentes;
- não cria missão.

O projector:

- recebe somente snapshot imutável e manifestação de proveniência;
- selecciona exclusivamente os campos aceites pelo contrato;
- não transporta campos auxiliares;
- não usa defaults fiscais silenciosos;
- não converte ausência em zero;
- não trunca negativos;
- não recebe Session;
- não lê BD;
- produz estrutura serializável;
- antecede `context_hash` e criação de `AgentMission`.

### 4.5 Identidades e autorização

O pedido produtivo deve conter explicitamente:

- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `vínculo soberano`;
- identificador único do pedido;
- janela temporal;
- instante de referência do snapshot.

Invariantes mínimas:

- identificadores inteiros positivos e não booleanos;
- no fluxo do proprietário, `actor_id == tenant_id`;
- `actor_id != tenant_id` não é rejeitado por igualdade mecânica: só é permitido quando existir vínculo soberano, delegação ou representação já ratificada, válida, activa e compatível com a Empresa e o escopo solicitado;
- no fluxo do proprietário, Empresa comprovada por `(empresa_id, user_id=tenant_id)`;
- no fluxo delegado, comprovar cumulativamente o proprietário da Empresa e a autoridade do actor segundo ADR-003, ADR-004 e ADR-005, sem ampliar permissões por inferência;
- vínculo ausente, expirado, revogado, suspenso ou fora do escopo produz bloqueio fail-closed;
- predicado de autoridade aplicado às consultas;
- reconfirmação de autoridade antes do retorno;
- falha de autorização produz bloqueio sem leitura transversal;
- acesso negado não produz missão nem mutação.

Nenhuma função que receba apenas `empresa_id` satisfaz esta fronteira.

### 4.6 Temporalidade obrigatória

A fronteira produtiva não pode usar “todo o histórico disponível”.

O pedido deve fornecer:

- `period_start`;
- `period_end`;
- `reference_at`.

Regras:

- `period_start <= period_end <= reference_at`;
- todos os valores devem resultar da mesma janela;
- documentos posteriores a `period_end` são excluídos;
- dados alterados depois de `reference_at` não podem alterar o snapshot já materializado;
- datas nulas ou inválidas devem seguir política explícita fail-closed;
- `MAX(data_emissao)` não equivale a cutoff;
- estado actual de Empresa não pode ser aplicado retroactivamente sem vigência provada.

O ADR não deve escolher granularidade mensal, trimestral ou anual como regra fiscal universal. A janela é explícita no pedido.

### 4.7 Manifestação soberana de proveniência

Antes da projecção, deve existir manifestação imutável contendo, no mínimo:

- versão do esquema;
- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `period_start`;
- `period_end`;
- `reference_at`;
- identificador da fonte;
- versão da regra de selecção;
- identificadores ou hashes dos documentos considerados;
- identificadores ou hashes dos documentos excluídos, com motivo;
- contagens;
- política de duplicidade aplicada;
- política de validade aplicada;
- política de cancelamento/devolução aplicada;
- unidade monetária;
- produtor canónico de cada campo;
- estado de disponibilidade de cada campo;
- hash do snapshot;
- instante de criação.

A manifestação não deve atravessar integralmente o `DataSanitizationContext`.

Pode ser associada à missão por identificador/hash, segundo contrato futuro.

Identificadores documentais na manifestação devem ser IDs internos opacos ou hashes criptográficos. É proibido persistir ou expor como identificador de proveniência CPF, CNPJ, chave de NF-e integral ou conteúdo documental bruto.

Logs não devem expor valores fiscais integrais, CPF, CNPJ, chave de NF-e ou conteúdo documental.

### 4.8 Oito campos fiscais

O contrato observado contém exactamente:

1. `faturamento`;
2. `custos`;
3. `lucro_contabil`;
4. `lucro`;
5. `base_calculo`;
6. `icms_pago`;
7. `icms_devido`;
8. `custo_fiscal_entradas`.

`regime` não integra esse contrato.

Para cada campo, o ADR deve impor uma destas situações:

- `PRODUZIDO_POR_FONTE_CANONICA`;
- `AUSENTE_COM_PROVENIENCIA`;
- `INDISPONIVEL_POR_REGRA_NAO_RATIFICADA`.

É proibido:

- preencher com zero por ausência;
- inventar fórmula;
- usar alias semântico não ratificado;
- tratar valor de produto como custo contabilístico sem decisão;
- tratar `valor_st` declarado como ICMS pago/devido sem decisão;
- duplicar `custos` em `custo_fiscal_entradas` sem decisão;
- usar `0.08` hardcoded como autoridade normativa;
- aplicar regime actual a período histórico sem vigência.

### 4.9 Campos derivados

O reader não deve calcular:

- `lucro`;
- `lucro_contabil`;
- `base_calculo`;
- ou qualquer obrigação fiscal.

Um campo derivado só pode ser projectado quando houver produtor canónico ratificado e identificável.

Na ausência desse produtor:

- o campo permanece ausente ou indisponível;
- a manifestação explica o motivo;
- a fronteira não usa fallback;
- a missão não recebe valor fabricado.

### 4.10 Ausência, null, zero e negativos

A fronteira deve preservar quatro estados distintos:

1. campo omitido;
2. campo presente com `null`;
3. campo presente com zero numérico;
4. campo presente com valor negativo.

Regras:

- ausência não vira zero;
- `null` não vira zero;
- zero real permanece zero;
- negativo permanece negativo;
- o sanitizador pode sinalizar o negativo, mas a fronteira não o trunca;
- `coalesce(..., 0)` não pode ser usado para esconder ausência na projecção produtiva.

### 4.11 Regime tributário

`regime` é dependência auxiliar potencial e não campo do contexto.

Se um produtor canónico futuro necessitar de regime:

- a leitura deve ser autorizada;
- o domínio deve ser validado;
- a vigência deve cobrir a janela;
- a fonte deve ser identificada;
- ausência, vazio, nulo e Empresa inexistente não podem virar `presumido`;
- não deve atravessar o `DataSanitizationContext`;
- deve constar apenas da manifestação ou do input do produtor canónico, conforme contrato futuro.

### 4.12 Documentos válidos e duplicidade

O ADR deve decidir fail-closed:

- somente documentos que satisfaçam predicado canónico de validade podem alimentar o snapshot;
- cancelamento, devolução, substituição, inutilização e duplicidade exigem política explícita;
- ausência de política ratificada bloqueia o campo afectado;
- hash documental deve ser usado quando existente;
- ausência de hash não autoriza deduplicação presumida;
- a fronteira deve registar inclusões e exclusões.

O ADR não deve inventar statuses ou colunas que não existam.

Deve distinguir:

- requisito arquitectural;
- disponibilidade actual do schema;
- implementação futura necessária.

### 4.13 Compatibilidade contratual

É proibido entregar directamente ao adapter o dicionário de `_montar_contexto_engines`.

Motivos obrigatórios no ADR:

- contém Session;
- contém campos extras;
- contém `regime`;
- contém `atividade`;
- contém `data_referencia`;
- contém `context_flags`;
- usa defaults e fórmulas não ratificados;
- não comprova autorização;
- não produz snapshot temporal.

O projector deve produzir exactamente:

- `empresa_id`;
- e os oito campos contratuais permitidos, quando disponíveis.

Nenhum campo auxiliar cru atravessa `extra="forbid"`.

### 4.14 Reprodutibilidade e hashes

Ordem obrigatória:

1. autorizar;
2. ler;
3. materializar snapshot;
4. criar manifestação;
5. projectar contexto;
6. serializar canonicamente;
7. calcular `context_hash`;
8. criar missão;
9. reconfirmar hashes antes da execução.

O mesmo snapshot e a mesma versão de regras devem produzir o mesmo contexto e hash.

O ADR deve exigir representação numérica canónica e política explícita de precisão. `1`, `1.0` e `"1.00"` não podem ser considerados equivalentes por inferência silenciosa; arredondamento, escala e conversão devem pertencer ao produtor canónico ratificado. Na ausência dessa decisão, o campo permanece indisponível.

Mudança de BD posterior não altera missão já criada.

### 4.15 Falha segura

A fronteira deve falhar fechada quando ocorrer:

- identidade ausente ou inválida;
- actor/tenant incoerentes;
- Empresa não autorizada;
- janela temporal inválida;
- fonte sem política ratificada;
- documento sem classificação necessária;
- duplicidade ambígua;
- regime sem vigência;
- produtor canónico inexistente;
- campo extra;
- Session/ORM no payload;
- hash divergente;
- snapshot não reproduzível.

Falha segura significa:

- nenhuma missão produtiva;
- nenhuma escrita;
- nenhuma publicação;
- nenhum fallback silencioso;
- resultado operacional auditável e sanitizado.

### 4.16 Scheduler, registry e executor

A fronteira não será ligada a:

- `agent_scheduler.py`;
- registry genérico;
- `run_all`;
- executor legado genérico;
- contexto genérico.

A activação produtiva futura continuará dependente de missão/evento explícito e adapter L3 independente.

### 4.17 LLM e orçamento

Esta fronteira é determinística.

Não usa LLM.

BudgetGuard e fallback de modelos não participam da leitura, autorização, projecção ou cálculo de proveniência.

### 4.18 Estados do ADR

O ADR-016 deve nascer com:

`Estado: PROPOSTO — aguarda auditoria GPT e ratificação Miguel`

Deve declarar:

- `ADR-011-PROVENIENCIA-001: ABERTO` enquanto proposto;
- nenhuma autorização produtiva;
- nenhuma implementação ratificada;
- nenhum fechamento automático do gate.

---

## 5. Fontes autorizadas para leitura

Ler apenas o necessário nos seguintes ficheiros:

### Governação, autorização, LGPD e contratos

- `docs/ADR-001-GOVERNACAO_CANONICIDADE.md`
- `docs/ADR-003-ACESSO-CONTADOR-EMPRESA-DOCUMENTO.md`
- `docs/ADR-004-VINCULO-SOBERANO-CONTADOR-DT-CONTADOR-01.md`
- `docs/ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md`
- `docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md`
- `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md`
- `docs/ADR-011-MIGRACAO-L3-DATA-SANITIZATION.md`

### Auditoria ratificada

- `docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`
- `docs/MISSIONS/MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA.md`
- `docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`
- `docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md`

### Código estritamente necessário para confirmação factual

- `app/agents/contracts/data_sanitization.py`
- `app/agents/adapters/data_sanitization.py`
- `app/agents/engines/data_sanitization.py`
- `app/agents/contracts/mission.py`
- `app/agents/mission_factory.py`
- `app/services/insights_engine.py`
- `app/models.py`
- `app/agents/readers/ag_encerramento.py`

### Migrations estritamente relacionadas

Somente as migrations citadas pelo REPORT-004, caso seja necessário confirmar nome de coluna ou constraint.

Não fazer pesquisa ampla no repositório.

Não ler `node_modules`, `.git`, caches, venv, build ou artefactos externos.

---

## 6. Ficheiros autorizados

### Entrada preexistente

Esta missão, depois de copiada para:

`docs/MISSIONS/MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA.md`

### Criar exclusivamente

1. `docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md`
2. `docs/REPORTS/REPORT-006-REDACAO-ADR-016-PROVENIENCIA-DATASANITIZATION.md`

### Não alterar

Todos os demais ficheiros, incluindo:

- ADR-001 a ADR-015;
- MISSION-003, MISSION-004 e MISSION-005;
- REPORT-002 a REPORT-005;
- código;
- testes;
- migrations;
- configurações;
- quatro ficheiros protegidos preexistentes.

---

## 7. Quatro ficheiros protegidos

Preservar integralmente:

- `app/agents/adapters/ag_encerramento.py`
- `app/agents/engines/ag_encerramento.py`
- `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md`
- `tests/test_ag_encerramento_mission_adapter.py`

Antes e depois:

- recolher hash do índice;
- recolher hash normalizado da working tree;
- confirmar igualdade com o estado inicial;
- não fazer checkout;
- não fazer reset;
- não normalizar;
- não adicionar ao stage.

O facto de aparecerem como `M` é estado preexistente protegido.

---

## 8. Estrutura mínima do ADR-016

O ADR deve possuir, no mínimo:

1. Título e identificação;
2. Estado;
3. Contexto;
4. Problema;
5. Relação com ADR-011;
6. Gate histórico;
7. Decisão;
8. Escopo;
9. Não escopo;
10. Invariantes de identidade;
11. Autorização;
12. Temporalidade;
13. Reader soberano;
14. Snapshot;
15. Manifestação de proveniência;
16. Projector;
17. Oito campos;
18. Campos derivados;
19. Regime;
20. Ausência, null, zero e negativos;
21. Validade documental;
22. Duplicidade;
23. Compatibilidade contratual;
24. Reprodutibilidade;
25. Falha segura;
26. Scheduler/registry/executor;
27. Segurança e LGPD;
28. Observabilidade;
29. Consequências;
30. Implementação futura;
31. Testes futuros obrigatórios;
32. Critérios para fechamento de implementação;
33. Exclusões;
34. Matriz de rastreabilidade com REPORT-004;
35. Ratificação pendente.

Pode adaptar numeração e títulos ao padrão real dos ADRs, sem omitir matéria.

---

## 9. Testes futuros obrigatórios a documentar

O ADR deve exigir, para futura implementação:

- actor inválido;
- tenant inválido;
- actor diferente de tenant sem vínculo soberano válido — bloqueado;
- actor diferente de tenant com vínculo soberano válido e dentro do escopo — autorizado apenas no limite ratificado;
- vínculo expirado, revogado, suspenso ou fora do escopo — bloqueado;
- Empresa inexistente;
- Empresa de outro utilizador;
- acesso negado sem mutação;
- predicado de autoridade nas consultas;
- reconfirmação final;
- janela temporal inválida;
- documento posterior ao cutoff;
- data nula;
- data inválida;
- ausência de documentos;
- zero real;
- null;
- campo omitido;
- negativo preservado;
- cancelamento;
- devolução;
- duplicidade com hash;
- duplicidade sem hash;
- regime ausente;
- regime inválido;
- regime sem vigência;
- produtor canónico ausente;
- `base_calculo` não fabricada;
- `icms_pago` não inferido de `valor_st`;
- extras rejeitados;
- Session rejeitada;
- ORM rejeitado;
- snapshot imutável;
- `context_hash` reproduzível;
- alteração posterior da BD sem alteração da missão;
- nenhum scheduler/registry genérico;
- nenhuma escrita;
- nenhum LLM;
- logs sem dados sensíveis.

Não criar os testes nesta missão.

---

## 10. Preflight obrigatório

Executar e registar no REPORT-006:

```powershell
Get-Location
git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --name-only
git diff --cached --name-only
```

Critérios:

- localização: `C:\dev\saas-fiscal-demo`;
- branch: `main`;
- `HEAD == origin/main == b1775217cbdbb9490aab442bc705f54081f9dc73`;
- stage vazio;
- somente os quatro ficheiros protegidos podem aparecer como modificados;
- a própria MISSION-006 pode aparecer como untracked;
- ADR-016 e REPORT-006 não podem preexistir.

Se houver qualquer outro desvio:

- parar;
- não criar ficheiros;
- apresentar estado `BLOQUEADA POR DESVIO DE BASELINE`.

---

## 11. Verificações factuais limitadas

Confirmar apenas:

1. ADR-016 não existe;
2. ADR-011 contém a decisão de B14.3C sem reader;
3. REPORT-004 contém a matriz dos oito campos;
4. REPORT-004 mantém o gate aberto;
5. REPORT-005 prova a rectificação;
6. `_montar_contexto_engines` contém os extras já auditados;
7. o contrato usa `extra="forbid"`;
8. o reader de `ag_encerramento` demonstra o padrão comparativo de autorização/read-only.

Não reauditar o projecto.

Não procurar alternativas de arquitectura.

---

## 12. Conteúdo do REPORT-006

Criar:

`docs/REPORTS/REPORT-006-REDACAO-ADR-016-PROVENIENCIA-DATASANITIZATION.md`

Deve conter:

1. identificação da missão;
2. baseline;
3. estado inicial;
4. hashes dos quatro protegidos;
5. confirmação de ADR-016 livre;
6. fontes efectivamente lidas;
7. resumo factual das decisões incorporadas;
8. relação ADR-011 ↔ ADR-016;
9. tratamento do gate histórico;
10. confirmação de que `_montar_contexto_engines` foi rejeitado como fonte directa;
11. confirmação dos oito campos exactos;
12. confirmação de que `regime` não integra o contrato;
13. confirmação de ausência de implementação;
14. hashes finais da MISSION-006 e do ADR-016;
15. declaração de que o SHA-256 do próprio REPORT-006 será apresentado apenas na saída final do Codex, depois de o ficheiro estar fechado, não dentro do próprio REPORT-006;
16. estado final Git;
17. stage vazio;
18. commit não efectuado;
19. push não efectuado;
20. auditoria pendente GPT;
21. ratificação pendente Miguel.

---

## 13. Validação textual obrigatória

Antes de concluir, verificar no ADR-016 presença de:

- `ADR-011-PROVENIENCIA-001`;
- `ADR-011-MIGRACAO-L3-DATA-SANITIZATION`;
- `B14.3C`;
- `ADR-016`;
- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `period_start`;
- `period_end`;
- `reference_at`;
- `extra="forbid"`;
- `faturamento`;
- `custos`;
- `lucro_contabil`;
- `lucro`;
- `base_calculo`;
- `icms_pago`;
- `icms_devido`;
- `custo_fiscal_entradas`;
- `regime não integra`;
- `ausência não vira zero`;
- `negativo`;
- `snapshot`;
- `manifestação de proveniência`;
- `context_hash`;
- `_montar_contexto_engines`;
- `fail-closed`;
- `scheduler`;
- `registry`;
- `LLM`;
- `PROPOSTO`;
- `aguarda auditoria GPT e ratificação Miguel`;
- `gate de decisão arquitectural`;
- `gate de implementação produtiva`;
- `representação numérica canónica`.

Verificar ausência de afirmações equivalentes a:

- ADR-011 revogado;
- ADR-011 substituído;
- gate fechado antes da ratificação;
- integração produtiva autorizada;
- reader implementado;
- projector implementado;
- código alterado;
- teste executado;
- `regime` como nono campo;
- default `presumido` autorizado;
- `0.08` ratificado;
- zero como ausência;
- negativos truncados;
- `_montar_contexto_engines` autorizado directamente.

---

## 14. Estado final permitido

`git status --short` deve mostrar apenas:

- os quatro ficheiros protegidos como modificados preexistentes;
- MISSION-006 untracked;
- ADR-016 untracked;
- REPORT-006 untracked.

`git diff --cached --name-only` deve permanecer vazio.

Nenhum outro ficheiro pode aparecer.

---

## 15. Proibições

Não:

- alterar código;
- alterar testes;
- alterar ADR-011;
- alterar ADR-008;
- actualizar referências históricas;
- fechar o gate;
- executar pytest;
- criar reader;
- criar projector;
- criar migration;
- criar contrato;
- integrar scheduler;
- integrar registry;
- integrar executor;
- criar commit;
- fazer push;
- fazer stage;
- usar `git add`;
- usar `git checkout`;
- usar `git reset`;
- usar `git clean`;
- usar pesquisa recursiva ampla;
- ler `node_modules`;
- decidir fora da arquitectura fornecida.

---

## 16. Resultado esperado

Ao terminar, apresentar de forma concisa:

- estado da execução;
- SHA-256 do REPORT-006 calculado e apresentado somente na saída final, após o ficheiro estar fechado;
- ADR criado;
- REPORT criado;
- MISSION-006 preservada;
- ADR-011 preservado;
- quatro ficheiros protegidos preservados;
- gate `ADR-011-PROVENIENCIA-001`: `ABERTO`;
- integração produtiva: `BLOQUEADA`;
- código/testes alterados: `NENHUM`;
- stage: `VAZIO`;
- commit: `NÃO EFECTUADO`;
- push: `NÃO EFECTUADO`;
- auditoria: `PENDENTE — GPT`;
- ratificação: `PENDENTE — Miguel`.

---

## 17. Regra final

Esta missão redige uma proposta arquitectural.

Ela não implementa a fronteira, não fecha o gate e não autoriza produção.

Perante dúvida factual, divergência de baseline ou necessidade de ampliar escopo:

**PARAR E REGISTAR. NÃO IMPROVISAR.**
