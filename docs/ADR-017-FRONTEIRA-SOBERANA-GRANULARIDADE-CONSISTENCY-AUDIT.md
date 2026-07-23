# ADR-017 — Fronteira soberana de granularidade do ConsistencyAuditAgent

**Data:** 2026-07-23
**Estado:** RATIFICADO — GPT e Miguel em 2026-07-23
**Natureza:** decisão arquitectural autónoma, aditiva e sem implementação
**Gate de decisão arquitectural:** `ADR-012-GRANULARIDADE-001`: `RESOLVIDO POR ADR-017`
**Gate de implementação produtiva:** `PENDENTE E BLOQUEADO`
**Integração produtiva:** `BLOQUEADA`

## 1. Contexto e problema produtivo

A `ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT`, ratificada na versão 1.3, e o canário B14.3D estabeleceram uma missão determinística, documental e exclusivamente em sombra ou `dry_run`. Essa fronteira recebe contexto previamente fornecido, não possui reader e compara pares por meio do `TaxConsistencyEngine`, descartando valores fiscais brutos antes do payload público.

Esse canário não prova a fronteira produtiva. Existem valores declarados do XML por item, mas não existe prova de resultados calculados persistidos como pares independentes ligados ao mesmo item e à mesma execução do motor. Sem unidade canónica, proveniência independente e vínculo verificável, uma agregação pode produzir coerência falsa, compensar divergências ou converter ausência em zero.

Este ADR resolve somente a decisão arquitectural da granularidade futura. Não declara que schema, reader, projector, persistência ou executor produtivos já existem.

## 2. Relação com ADR-012 e B14.3D

O ADR-017 é autónomo e aditivo. Não substitui, revoga, renumera, reescreve, rectifica nem invalida a ADR-012. A granularidade operacional do canário não é reaberta: `scope = "documento"`, `entity_type = "documento_fiscal"` e `entity_id == context.documento_id` permanecem canónicos para B14.3D.

Nenhuma alteração é autorizada no contrato v1.0, no adapter, no motor L3, no agente, no serviço protegido ou nos testes de B14.3D. O modo activo continua bloqueado.

## 3. Gate histórico e gates distintos

O identificador histórico `ADR-012-GRANULARIDADE-001` permanece intacto em missões e relatórios. O seu estado actual é `RESOLVIDO POR ADR-017`.

Historicamente, enquanto este ADR esteve apenas proposto:

- `ADR-012-GRANULARIDADE-001`: `ABERTO`;
- gate de implementação produtiva: `PENDENTE E BLOQUEADO`;
- integração produtiva: `BLOQUEADA`;
- nenhuma implementação está autorizada.

Após auditoria GPT e ratificação explícita de Miguel em 2026-07-23, fica registado:

- gate de decisão arquitectural `ADR-012-GRANULARIDADE-001`: `RESOLVIDO POR ADR-017`;
- gate de implementação produtiva: `PENDENTE E BLOQUEADO`;
- integração produtiva: `BLOQUEADA`.

É proibido declarar apenas “gate fechado”. A ratificação da decisão não fecha automaticamente o gate de implementação, que exige bloco próprio, testes, auditoria e ratificação.

## 4. Decisão arquitectural

### 4.1 Escopo da missão

O escopo da missão permanece documental:

- `scope = "documento"`;
- `entity_type = "documento_fiscal"`;
- uma missão identifica exactamente um documento fiscal.

O documento é o contentor autorizado, o objecto do snapshot e a unidade de execução da missão.

### 4.2 Unidade canónica de auditoria

A unidade canónica de auditoria produtiva é `item_documento_fiscal`.

Cada comparação pertence a exactamente um item identificável dentro de exactamente um documento identificável. A missão é documental, mas a comparação é realizada item a item. “Escopo da missão” e “unidade canónica de auditoria” não são sinónimos.

### 4.3 Hierarquia de granularidades

1. **Item:** unidade canónica de comparação.
2. **Documento:** contentor autorizado, snapshot e unidade de execução da missão.
3. **Relatório:** consumidor posterior de resultados já auditados; não recalcula nem redefine pares.
4. **Período:** filtro explícito ou contentor de várias missões documentais; nunca unidade automática de compensação.
5. **Agregado:** visão derivada posterior; não constitui prova de coerência dos pares.

Relatório, período ou agregado não substituem a auditoria item a item. Uma futura auditoria cujo objecto canónico seja qualquer dessas três granularidades exige ADR e contrato próprios.

## 5. Proibição de compensação entre itens

É proibida a compensação entre itens. Exemplo obrigatório: o item A tem diferença positiva e o item B tem diferença negativa; ainda que a soma documental pareça igual, o documento não pode ser declarado coerente.

A coerência documental deriva exclusivamente da conjunção dos resultados item a item:

- o documento somente é coerente se todos os pares aplicáveis de todos os itens auditáveis forem coerentes;
- qualquer divergência item a item torna o documento não coerente;
- ausência de pares comparáveis não produz coerência;
- item incompleto não desaparece por agregação;
- soma documental ou agregada nunca mascara divergência.

## 6. Identidade canónica do item

Cada item deve possuir identidade estável e reproduzível dentro do snapshot, nesta preferência:

1. identificador interno persistente e imutável;
2. identificador documental canónico já existente;
3. fingerprint determinístico acrescido de ordinal estável quando itens materialmente idênticos puderem repetir-se.

É proibido usar isoladamente descrição livre, NCM ou posição actual de lista mutável; deduplicar por presunção; colapsar repetições legítimas; ou expor CPF, CNPJ, chave integral de NF-e ou conteúdo bruto como identificador público.

Esta é uma exigência arquitectural, não uma afirmação sobre disponibilidade actual do schema. Se o schema não assegurar identidade estável suficiente, a comparação afectada e a integração produtiva permanecem bloqueadas até implementação ratificada.

## 7. Pares canónicos por item

Para cada `item_documento_fiscal`, somente são admitidos os pares já reconhecidos pela ADR-012, nesta ordem:

1. `icms_st_xml` ↔ `icms_st_motor`;
2. `mva_xml` ↔ `mva_motor`;
3. `base_st_xml` ↔ `base_st_motor`.

Cada lado conserva proveniência independente. É proibido formar um par com valores de itens diferentes ou apresentar valor documental/agregado como valor do item sem produtor canónico ratificado. Novos pares exigem ADR e contrato próprios.

## 8. Proveniência independente

### 8.1 Lado declarado

Cada lado declarado deve manifestar separadamente:

- documento e item;
- campo exacto de origem e valor canónico;
- unidade, escala e precisão;
- parser e versão;
- hash ou identificador opaco da fonte;
- estado de validade;
- instante de materialização.

### 8.2 Lado calculado

Cada lado calculado deve manifestar separadamente:

- documento e item correspondente;
- campo exacto produzido e valor canónico;
- unidade, escala e precisão;
- motor e versão do motor;
- versão da regra;
- hash dos inputs;
- identificador da execução;
- instante de cálculo;
- estado da execução.

O vínculo entre lados deve ser explícito e verificável. Não pode ser inferido por empresa, documento, ordem aparente, NCM, valor, proximidade temporal ou posição em listas independentes.

## 9. Vínculo documento–item–motor–resultado

Antes de montar um par, a fronteira deve provar cumulativamente:

- o documento pertence ao tenant autorizado;
- o item pertence ao documento;
- o input do motor pertence ao mesmo item;
- o resultado pertence à execução identificada;
- a execução usou o snapshot e a versão declarados;
- um valor actual posterior não substituiu o resultado;
- os dois lados se referem ao mesmo documento, item, snapshot e regra.

Resultado sem vínculo item a item assume `INDISPONIVEL_POR_VINCULO_NAO_COMPROVADO`. Não existe fallback documental.

## 10. Pedido e autorização

O pedido futuro deve fornecer explicitamente `request_id`, `actor_id`, `tenant_id`, `empresa_id`, `documento_id`, vínculo soberano quando aplicável, `reference_at`, versão da política e finalidade da missão.

Os IDs devem ser inteiros positivos e não booleanos. No fluxo proprietário, `actor_id == tenant_id`. No fluxo delegado, `actor_id != tenant_id` somente com vínculo soberano válido, activo, não expirado, não revogado, dentro do escopo e compatível com a Empresa e o documento.

A Empresa deve ser comprovada por predicado autorizado; o documento deve pertencer à Empresa; a autorização deve integrar as queries e ser reconfirmada antes do retorno. A autorização precede a materialização de valores fiscais. Acesso negado não realiza leitura transversal, não cria missão, não escreve e não publica.

## 11. Reader soberano

A futura implementação exige reader dedicado, externo ao adapter e ao motor L3. O reader recebe `Session` por injecção, usa `no_autoflush`, é read-only e:

- não executa `add`, `flush`, `commit`, `delete` ou mutação;
- não devolve ORM, `Session` ou query;
- aplica autorização nas consultas;
- lê apenas documento, itens e resultados necessários;
- não agrega para esconder divergências nem inventa correspondência;
- não chama LLM, não cria missão e não publica;
- materializa estruturas imutáveis.

Este ADR não escolhe nomes finais de módulos nem autoriza a implementação do reader.

## 12. Snapshot produtivo

O snapshot documental é imutável e contém no mínimo:

- versão do esquema;
- `request_id`, `actor_id`, `tenant_id`, `empresa_id`, `documento_id` e `reference_at`;
- identidade e hash do documento;
- itens incluídos; itens excluídos e motivo;
- identidade estável e ordem canónica de cada item;
- pares disponíveis por item;
- proveniência independente dos dois lados;
- motor, versão, execução e versão da regra;
- unidade, escala e precisão;
- políticas de validade, cancelamento, substituição e duplicidade;
- contagens, lacunas, hash do snapshot e instante de criação.

Mudanças posteriores no banco não alteram o snapshot nem a missão criada.

## 13. Temporalidade

O pedido inclui `reference_at`. Documento e resultado com vigência ou instante próprio devem ser anteriores ou iguais a essa referência. A execução usada deve ser identificada; um resultado posterior não substitui silenciosamente o snapshot.

Reprocessamento cria nova identidade de execução e novo snapshot. É proibido seleccionar automaticamente o “último resultado” sem política explícita. Auditoria de múltiplos períodos está excluída.

## 14. Projecção estrita

Um projector dedicado recebe somente snapshot imutável e manifestação de proveniência. Não recebe `Session`, não consulta BD, não recebe ORM, não agrega itens, não altera valores, não converte ausência em zero, não trunca negativos, não arredonda sem política, não fabrica pares e não usa aliases não ratificados.

A projecção produz estrutura serializável com `extra="forbid"`, antecede `context_hash` e a criação da missão. A futura projecção pode exigir nova versão contratual; o contrato v1.0 da ADR-012 permanece inalterado. Este ADR não implementa projector.

## 15. Estados de disponibilidade

Cada lado de cada par possui exactamente um estado explícito:

- `PRODUZIDO_POR_FONTE_CANONICA`;
- `AUSENTE_COM_PROVENIENCIA`;
- `INDISPONIVEL_POR_REGRA_NAO_RATIFICADA`;
- `INDISPONIVEL_POR_VINCULO_NAO_COMPROVADO`;
- `INVALIDO_POR_FONTE`;
- `EXCLUIDO_POR_POLITICA_DOCUMENTAL`.

Somente pares cujos dois lados estejam em `PRODUZIDO_POR_FONTE_CANONICA` podem ser comparados. Ausência não vira zero; `null` não vira zero; item incompleto não é omitido; resultado ausente não é recalculado implicitamente; valor actual não substitui snapshot; nenhum par comparável não implica coerência.

## 16. Dados incompletos

Devem ser distintos: item sem par aplicável, par com um lado ausente, valor inválido, resultado do motor ausente, vínculo não comprovado, documento sem itens auditáveis e snapshot incompleto.

Esses dados incompletos não equivalem a divergência fiscal nem a coerência. Produzem bloqueio ou auditoria inconclusiva explícita, sanitizada e sujeita a revisão humana. O contrato futuro definirá a nomenclatura operacional, mas é proibido `dados_coerentes=True` nesses estados.

## 17. Duplicidade e repetição legítima

A política distingue documento duplicado, item duplicado por erro, item materialmente igual porém legitimamente repetido, reprocessamento e múltiplas execuções do motor.

Hash documental pode detectar duplicidade documental quando disponível. Itens iguais não são colapsados sem identidade canónica; ordinal estável pode distinguir repetições legítimas. Reprocessamento cria nova execução identificada, e a escolha da execução é explícita. Falta de política ratificada bloqueia a comparação afectada.

## 18. Ordem canónica e reprodutibilidade

O snapshot ordena itens por identidade canónica estável. Dentro do item, a ordem é ICMS-ST, MVA e Base ST. Ordem acidental de query, mapping ou lista externa não interfere.

O mesmo snapshot e a mesma versão de regras produzem a mesma serialização, o mesmo `context_hash` e o mesmo hash de snapshot.

## 19. Consistência interna não equivale a verdade fiscal

O `ConsistencyAuditAgent` verifica somente consistência interna entre valor declarado por fonte identificada e valor calculado por motor identificado, para o mesmo item, documento, snapshot e regra.

Consistência interna não equivale a verdade fiscal. O agente não prova que o XML é verdadeiro; que o motor está normativamente correcto; que a regra está vigente; que o tributo foi pago; que existe crédito ou restituição; que o documento é juridicamente válido; que a empresa pode publicar ou usar o resultado; que uma divergência é ilícito; ou que ausência de divergência é conformidade fiscal.

Nenhuma saída utiliza linguagem de decisão fiscal definitiva.

## 20. Resultado documental derivado

O resultado documental deriva dos resultados item a item e contém apenas metadados sanitizados: documento auditado, totais de itens, itens auditáveis, pares comparados, divergências e itens inconclusivos, códigos canónicos e estado geral derivado.

Deve fixar `publication_allowed=False` e `requires_human_review=True`. Não contém valores fiscais brutos, diferenças, percentagens, XML bruto ou mensagens do legado.

## 21. Falha segura

A fronteira opera em `fail-closed` perante identidade ou autorização inválida; documento fora do tenant; identidade de item insuficiente; vínculos ausentes; execução ou versão de regra ausente; proveniência incompleta; snapshot mutável ou hash divergente; duplicidade ambígua; ordem não determinística; unidade/escala incompatível; par parcial; compensação entre itens; `Session`, ORM ou extras na projecção; ou modo activo não ratificado.

Falha segura significa nenhuma missão produtiva, escrita, publicação, fallback ou LLM; somente resultado operacional sanitizado e revisão humana quando aplicável.

## 22. Scheduler, registry e executor

A fronteira futura não será ligada a `agent_scheduler.py`, `agent_registry.py` genérico, `agent_executor.py` legado, `run_all` ou contexto genérico.

Activação futura depende de pedido ou evento explícito, autorização, snapshot, criação de `AgentMission` e executor L3 independente previamente ratificado. O ADR-017 não autoriza scheduler, registry ou executor.

## 23. Persistência e transacção

Implementação futura exigirá persistência idempotente do snapshot e da missão, identidade única de execução, retry explícito, protecção concorrente, fronteira transaccional própria, nenhuma confirmação parcial, nenhuma escrita por reader, adapter ou motor, publicação separada, revogação e rastreabilidade.

Persistência, migrations e componentes transversais continuam bloqueados por gates próprios.

## 24. LLM

A fronteira é determinística e não usa LLM. LLM não participa em autorização, identidade do item, formação de pares, proveniência, cálculo, comparação, hash, decisão de coerência ou publicação. `BudgetGuard` não substitui regra ausente.

## 25. Segurança, LGPD e observabilidade

Payloads e logs não expõem CPF, CNPJ, chave integral de NF-e, XML bruto, descrição integral sensível, valores fiscais brutos, diferenças, traceback, segredo, `Session` ou representação ORM. Identidades que atravessam fronteiras usam IDs internos opacos ou hashes.

Observabilidade futura limita-se a eventos sanitizados e correlacionáveis por identificadores opacos: pedido, autorização, versão de política, snapshot, execução, estado de disponibilidade, código de bloqueio e revisão humana. Não regista valores fiscais nem `str(exc)`.

## 26. Consequências

A unidade item a item impede coerência falsa por agregação e torna explícitos proveniência, temporalidade e vínculo. Em contrapartida, a integração permanece indisponível até existirem identidade estável, fontes independentes, execução ligada, snapshot, contratos e fronteiras transaccionais ratificados.

Relatórios e agregados tornam-se consumidores derivados. Dados incompletos tornam-se visíveis como inconclusivos em vez de coerentes por omissão.

## 27. Implementação futura

Um bloco futuro, posterior à ratificação desta decisão, deverá especificar contratos/versionamento, reader, snapshot, projector, persistência, criação idempotente de missão, executor L3 e observabilidade. Deve preservar ADR-012 e B14.3D e provar todas as autorizações e vínculos antes de materializar pares.

Este ADR não cria reader, projector, contrato, migration, endpoint, scheduler, registry, executor, persistência ou modo activo.

## 28. Testes futuros obrigatórios

### 28.1 Identidade e autorização

Devem cobrir actor e tenant inválidos; Empresa inexistente ou de outro tenant; documento inexistente ou de outra Empresa; delegado sem vínculo, com vínculo expirado, revogado ou fora do escopo; acesso autorizado; predicado nas queries; reconfirmação; e acesso negado sem leitura transversal, missão ou mutação.

### 28.2 Identidade de item

Devem cobrir item inexistente ou de outro documento; ID booleano, zero ou negativo; identidade instável; repetições legítimas; ordinal estável; alteração da ordem da query sem alterar hash; e rejeição de NCM ou descrição como identidade única.

### 28.3 Pares e proveniência

Devem cobrir cada par isolado, dois e três pares; lados do mesmo item; rejeição de cruzamento entre itens; proveniência ausente em cada lado; motor/regra sem versão; execução sem identidade; resultado sem vínculo; hash de input divergente; unidade, escala ou precisão incompatíveis.

### 28.4 Granularidade

Devem cobrir documento com um e múltiplos itens; divergência em um e vários itens; diferenças positivas e negativas sem compensação; soma documental igual com itens divergentes; e incapacidade de relatório, agregado ou período substituírem itens.

### 28.5 Dados incompletos

Devem cobrir nenhum par aplicável; um lado ausente; `null`; zero real; negativo finito; motor ausente; item incompleto; documento sem itens auditáveis; vínculo não comprovado; estado inconclusivo sem `dados_coerentes=True`; e ausência não vira zero.

### 28.6 Duplicidade e reprocessamento

Devem cobrir documento duplicado com e sem hash; item duplicado por erro; repetição legítima; duas execuções; selecção explícita; nova identidade no reprocessamento; e impossibilidade de resultado posterior substituir snapshot anterior.

### 28.7 Snapshot e hash

Devem cobrir imutabilidade, serialização canónica, hash reproduzível, independência da ordem acidental, estabilidade após mudança da BD, novo hash por versão, bloqueio por divergência, rejeição de `Session`, ORM e extras.

### 28.8 Segurança pública

Devem provar payload sem valores, diferenças ou percentagens; logs sem CPF/CNPJ/chave/XML; erro sem traceback ou `str(exc)`; resultado sanitizado; `publication_allowed=False`; e `requires_human_review=True`.

### 28.9 Integridade estrutural

Devem provar ADR-012, B14.3D, serviço protegido e agente legado inalterados; ausência de ligação a scheduler, registry e executor; nenhum reader criado nesta missão; ausência de código alterado; e preservação dos quatro ficheiros protegidos.

## 29. Critérios de fechamento do gate de implementação

O gate de implementação produtiva somente poderá ser resolvido por missão própria após:

1. ADR-017 auditado e ratificado;
2. identidade canónica e schema/migrations ratificados;
3. autorização nas queries e reconfirmação provadas;
4. reader read-only, snapshot imutável e projector estrito implementados;
5. proveniência e vínculo item–execução provados;
6. persistência idempotente e transacção concorrente provadas;
7. todos os testes futuros aprovados;
8. segurança/LGPD e observabilidade auditadas;
9. executor L3 independente ratificado;
10. auditoria GPT e ratificação Miguel específicas da implementação.

Até lá, integração produtiva e modo activo permanecem bloqueados.

## 30. Exclusões

Este ADR não decide regra fiscal, validade normativa, verdade do XML, direito a crédito/restituição, pagamento, ilicitude ou publicação. Não abrange auditoria canónica de relatório, período ou agregado. Não altera ADR-012, ADR-016, B14.3D, contratos, código, testes ou migrations.

## 31. Matriz de rastreabilidade

| Tema | Decisão | Gate/efeito |
|---|---|---|
| Missão | documento fiscal | preserva ADR-012/B14.3D |
| Unidade de auditoria | `item_documento_fiscal` | implementação bloqueada |
| Documento | contentor/snapshot/execução | resultado derivado |
| Relatório/período/agregado | consumidores/contentores derivados | não provam coerência |
| Pares | três pares da ADR-012 por item | novos pares exigem ADR |
| Proveniência | independente por lado | ausência bloqueia |
| Vínculo | documento–item–motor–resultado | sem fallback documental |
| Incompletude | bloqueio ou inconclusiva | nunca coerência |
| Segurança | metadados sanitizados | sem valores fiscais brutos |
| Gate de decisão arquitectural | `ADR-012-GRANULARIDADE-001`: `RESOLVIDO POR ADR-017` | decisão ratificada em 2026-07-23 |
| Implementação | `PENDENTE E BLOQUEADO` | missão futura própria |
| Integração produtiva | `BLOQUEADA` | depende do gate de implementação |

## 32. Ratificação final

**Estado:** `RATIFICADO — GPT e Miguel em 2026-07-23`.

O gate de decisão arquitectural `ADR-012-GRANULARIDADE-001` está `RESOLVIDO POR ADR-017`. O gate de implementação produtiva permanece `PENDENTE E BLOQUEADO`, e a integração produtiva permanece `BLOQUEADA`. A ratificação não autoriza implementação, não altera o canário B14.3D e não abre o modo produtivo.
