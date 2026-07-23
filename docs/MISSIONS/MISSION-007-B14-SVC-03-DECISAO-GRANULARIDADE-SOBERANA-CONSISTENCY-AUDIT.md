# MISSION-007 — B14-SVC-03 — DECISÃO DA GRANULARIDADE SOBERANA DO CONSISTENCYAUDITAGENT

## 1. Identificação

**Missão:** `MISSION-007-B14-SVC-03-DECISAO-GRANULARIDADE-SOBERANA-CONSISTENCY-AUDIT`
**Bloco:** `B14-SVC-03`
**Data:** `2026-07-23`
**Baseline obrigatória:** `e5cfd5ef989eb5920d479b29880746a93ba1afaa`
**Executor:** Codex
**Autoridade arquitectural:** GPT
**Autoridade de ratificação:** Miguel
**Natureza:** documental, com leitura estática limitada e sem implementação
**Versão da missão:** `v1.0`
**Estado esperado do repositório:** `main`, com `HEAD == origin/main == baseline`

---

## 2. Objectivo

Redigir uma proposta autónoma de ADR para resolver arquitecturalmente o gate produtivo:

`ADR-012-GRANULARIDADE-001`

relativo à futura fronteira produtiva do `ConsistencyAuditAgent`.

A missão deve:

1. preservar integralmente a ADR-012 v1.3 e a implementação B14.3D em sombra;
2. distinguir a granularidade operacional já ratificada para o canário da granularidade canónica necessária para dados produtivos reais;
3. definir a unidade canónica de comparação dos pares fiscais;
4. definir a relação entre item, documento, relatório, período e agregado;
5. definir proveniência independente para cada lado de cada par comparado;
6. definir autorização, snapshot, projecção, vínculo com o motor e falha segura;
7. impedir coerência falsa por agregação, compensação entre itens, ausência convertida em zero ou falta de vínculo entre valores;
8. delimitar que consistência interna não equivale a verdade fiscal, validade normativa ou autorização de publicação;
9. mapear o gate histórico para um novo ADR autónomo;
10. não implementar reader, projector, contratos, migrations, executor, scheduler, registry, persistência, endpoint ou modo activo.

Resultado esperado:

- criação de proposta de `ADR-017`;
- criação de `REPORT-007`;
- nenhuma alteração em código, testes, ADR-012 ou ficheiros protegidos;
- stage vazio;
- commit e push não efectuados;
- auditoria GPT e ratificação Miguel pendentes.

---

## 3. Estado institucional já provado

A missão não deve reabrir decisões já ratificadas.

### 3.1 ADR-012 v1.3 e B14.3D

A ADR-012 v1.3 permanece canónica para o canário L3 em sombra.

Já foi decidido e implementado:

- `mission_type = "auditar_consistencia_fiscal"`;
- `target_agent = "consistency_audit_agent"`;
- `scope = "documento"`;
- `entity_type = "documento_fiscal"`;
- `entity_id == context.documento_id`;
- execução somente em `sombra` ou `dry_run`;
- modo `activo` bloqueado;
- contexto previamente fornecido;
- sem reader;
- sem BD;
- sem LLM;
- sem HTTP;
- sem filesystem;
- sem persistência;
- sem scheduler, registry ou executor activos;
- comparação determinística via `TaxConsistencyEngine`;
- serviço protegido preservado;
- valores fiscais brutos descartados antes do payload público.

Commits históricos conhecidos:

- `f30b971` — ratificação documental inicial da ADR-012;
- `9c71782` — rectificação da ADR-012 para v1.3;
- `d4c506c` — contrato, motor, adapter e testes B14.3D em sombra.

A presente missão não deve alterar, substituir, renumerar, rectificar ou invalidar a ADR-012.

### 3.2 Gate produtivo posterior

A auditoria de fronteiras posterior a B14.3D comprovou que:

- valores declarados do XML existem por item;
- resultados calculados não estão comprovadamente persistidos como pares independentes ligados ao mesmo item ou documento;
- a unidade canónica produtiva ainda não estava decidida;
- faltava decidir item, documento, relatório ou agregado;
- faltava proveniência independente de cada lado do par;
- faltava vínculo canónico documento–item–execução do motor–resultado;
- faltava política para múltiplos itens e duplicatas;
- a integração produtiva permanecia bloqueada.

O novo ADR deve resolver a decisão arquitectural, não declarar implementação produtiva concluída.

---

## 4. Decisão arquitectural que deve ser redigida

O Codex deve materializar no ADR-017, sem ampliar ou reinterpretar, as decisões abaixo.

### 4.1 ADR autónomo e aditivo

Criar exclusivamente:

`docs/ADR-017-FRONTEIRA-SOBERANA-GRANULARIDADE-CONSISTENCY-AUDIT.md`

O ADR-017 será autónomo e aditivo.

Não:

- substitui;
- revoga;
- renumera;
- reescreve;
- rectifica;
- invalida

a ADR-012.

A ADR-012 continua canónica para B14.3D em sombra.

### 4.2 Tratamento do gate histórico

O identificador:

`ADR-012-GRANULARIDADE-001`

deve permanecer intacto em missões e relatórios históricos.

Enquanto o ADR-017 estiver apenas proposto:

- `ADR-012-GRANULARIDADE-001`: `ABERTO`;
- integração produtiva: `BLOQUEADA`;
- nenhuma implementação autorizada.

Após auditoria GPT e ratificação explícita de Miguel, distinguir obrigatoriamente:

- **gate de decisão arquitectural** `ADR-012-GRANULARIDADE-001`: `RESOLVIDO POR ADR-017`;
- **gate de implementação produtiva**: `PENDENTE E BLOQUEADO`;
- integração produtiva continua bloqueada até implementação, testes, auditoria e ratificação próprios.

É proibido escrever apenas “gate fechado” sem indicar qual gate foi resolvido.

### 4.3 Duas granularidades distintas

O ADR-017 deve distinguir:

#### Escopo da missão

Permanece:

- `scope = "documento"`;
- `entity_type = "documento_fiscal"`;
- uma missão identifica um documento fiscal.

Esta decisão preserva compatibilidade institucional com a ADR-012.

#### Unidade canónica de auditoria

A unidade produtiva de comparação deve ser:

`item_documento_fiscal`

Cada comparação fiscal deve pertencer a exactamente um item identificável dentro de exactamente um documento.

A missão continua documental, mas a auditoria produtiva ocorre item a item.

É proibido tratar “escopo da missão” e “unidade de comparação” como sinónimos.

### 4.4 Hierarquia de granularidades

O ADR deve fixar:

1. **item** — unidade canónica de comparação;
2. **documento** — contentor autorizado, snapshot e unidade de execução da missão;
3. **relatório** — consumidor posterior de resultados já auditados, sem recalcular ou redefinir pares;
4. **período** — filtro explícito ou contentor de múltiplas missões documentais, nunca unidade automática de compensação;
5. **agregado** — visão derivada posterior, não unidade de prova de coerência de pares.

Relatório, período ou agregado não podem substituir a auditoria item a item.

Qualquer futura auditoria cujo objecto canónico seja relatório, período ou agregado exige ADR e contrato próprios.

### 4.5 Proibição de compensação entre itens

Valores divergentes de itens diferentes não podem compensensar-se.

Exemplo arquitectural obrigatório:

- item A: diferença positiva;
- item B: diferença negativa;
- soma documental aparentemente igual.

O documento não pode ser declarado coerente pela soma.

A coerência documental é derivada exclusivamente da conjunção dos resultados item a item:

- documento coerente somente se todos os pares aplicáveis de todos os itens auditáveis forem coerentes;
- qualquer divergência item a item torna o documento não coerente;
- ausência de pares comparáveis não produz coerência;
- item incompleto não desaparece por agregação.

### 4.6 Identidade canónica do item

Cada item deve possuir identidade estável e reproduzível dentro do snapshot.

Ordem de preferência:

1. identificador interno persistente e imutável do item;
2. identificador documental canónico já existente;
3. fingerprint determinístico do item, acrescido de ordinal estável quando itens materialmente idênticos puderem repetir-se.

É proibido:

- usar apenas descrição livre do produto;
- usar apenas NCM;
- usar apenas posição actual de uma lista mutável;
- deduplicar itens iguais por presunção;
- colapsar itens legítimos repetidos;
- usar CPF, CNPJ, chave integral de NF-e ou conteúdo bruto como identificador público.

O ADR deve distinguir requisito arquitectural de disponibilidade actual do schema.

Se o schema actual não fornecer identidade estável suficiente, a integração produtiva permanece bloqueada até implementação ratificada.

### 4.7 Pares canónicos por item

Para cada `item_documento_fiscal`, a fronteira poderá produzir somente os pares já reconhecidos pela ADR-012:

1. `icms_st_xml` ↔ `icms_st_motor`;
2. `mva_xml` ↔ `mva_motor`;
3. `base_st_xml` ↔ `base_st_motor`.

Cada lado deve manter proveniência independente.

Nenhum par pode ser construído com valores pertencentes a itens diferentes.

Nenhum valor documental ou agregado pode ser apresentado como valor do item sem produtor canónico ratificado.

Novos pares exigem ADR e contrato próprios.

### 4.8 Proveniência independente de cada lado

Para cada par aplicável, o snapshot deve manifestar separadamente:

#### Lado declarado

- documento;
- item;
- campo exacto de origem;
- valor canónico;
- unidade;
- escala/precisão;
- parser e versão;
- hash ou identificador opaco da fonte;
- estado de validade;
- instante de materialização.

#### Lado calculado

- documento;
- item correspondente;
- campo exacto produzido;
- valor canónico;
- unidade;
- escala/precisão;
- motor;
- versão do motor;
- versão da regra;
- hash dos inputs;
- identificador da execução;
- instante de cálculo;
- estado da execução.

O vínculo entre os dois lados deve ser explícito e verificável.

É proibido inferir correspondência apenas por:

- mesma empresa;
- mesmo documento;
- mesma ordem aparente;
- mesmo NCM;
- mesmo valor;
- proximidade temporal;
- posição em listas independentes.

### 4.9 Vínculo documento–item–motor–resultado

A fronteira produtiva deve provar cumulativamente:

- o documento pertence ao tenant autorizado;
- o item pertence ao documento;
- o input do motor pertence ao mesmo item;
- o resultado pertence à execução identificada;
- a execução usou o snapshot e a versão declarados;
- o resultado não foi substituído por valor actual posterior;
- o par foi montado somente depois dessas provas.

Resultado calculado sem vínculo item a item é `INDISPONIVEL_POR_VINCULO_NAO_COMPROVADO`.

Não usar fallback documental.

### 4.10 Pedido e autorização

A futura fronteira deve receber explicitamente:

- `request_id`;
- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `documento_id`;
- vínculo soberano, quando aplicável;
- `reference_at`;
- versão da política;
- finalidade da missão.

Invariantes mínimas:

- IDs inteiros positivos e não booleanos;
- proprietário: `actor_id == tenant_id`;
- delegado: `actor_id != tenant_id` somente com vínculo soberano válido, activo, não expirado, não revogado, dentro do escopo e compatível com a Empresa e o documento;
- Empresa comprovada por predicado autorizado;
- documento comprovado como pertencente à Empresa;
- autorização aplicada nas queries;
- reconfirmação antes do retorno;
- acesso negado sem leitura transversal, missão, escrita ou publicação.

A autorização deve preceder materialização de valores fiscais.

### 4.11 Reader soberano

A futura implementação exigirá reader dedicado, externo ao adapter e ao motor L3.

O reader:

- recebe Session por injecção;
- usa `no_autoflush`;
- é read-only;
- não faz `add`, `flush`, `commit`, `delete` ou mutação;
- não devolve ORM, Session ou query;
- aplica autorização nas consultas;
- lê somente documento, itens e resultados necessários;
- não agrega valores para esconder divergências;
- não inventa correspondência;
- não chama LLM;
- não cria missão;
- não publica;
- materializa estruturas imutáveis.

O ADR-017 não deve escolher nomes finais de módulos como autorização de implementação.

### 4.12 Snapshot produtivo

O snapshot documental deve ser imutável e conter, no mínimo:

- versão do esquema;
- `request_id`;
- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `documento_id`;
- `reference_at`;
- identidade e hash do documento;
- itens incluídos;
- itens excluídos e motivo;
- identidade estável de cada item;
- ordem canónica dos itens;
- pares disponíveis por item;
- proveniência independente de cada lado;
- motor e versão;
- execução e versão da regra;
- unidade, escala e precisão;
- políticas de validade, cancelamento, substituição e duplicidade;
- contagens;
- lacunas;
- hash do snapshot;
- instante de criação.

Mudanças posteriores no banco não alteram o snapshot nem a missão criada.

### 4.13 Temporalidade

O pedido deve conter `reference_at`.

Quando o documento ou o resultado do motor possuírem vigência ou instante próprio:

- devem ser anteriores ou iguais a `reference_at`;
- a execução do motor usada deve ser identificada;
- resultado posterior não substitui silenciosamente resultado do snapshot;
- reprocessamento cria nova identidade de execução e novo snapshot;
- não usar automaticamente “último resultado” sem política explícita.

Auditoria de período múltiplo não pertence a esta missão.

### 4.14 Projecção estrita

Um projector dedicado deve receber somente snapshot imutável e manifestação de proveniência.

O projector:

- não recebe Session;
- não consulta BD;
- não recebe ORM;
- não agrega itens;
- não altera valores;
- não converte ausência em zero;
- não trunca negativos;
- não arredonda sem política;
- não fabrica pares;
- não usa aliases não ratificados;
- produz estrutura serializável e `extra="forbid"`;
- antecede `context_hash` e criação da missão.

A futura projecção produtiva poderá exigir nova versão contratual.

O ADR-017 não deve alterar nesta missão o contrato v1.0 da ADR-012.

### 4.15 Estados de disponibilidade

Cada lado de cada par deve possuir estado explícito:

- `PRODUZIDO_POR_FONTE_CANONICA`;
- `AUSENTE_COM_PROVENIENCIA`;
- `INDISPONIVEL_POR_REGRA_NAO_RATIFICADA`;
- `INDISPONIVEL_POR_VINCULO_NAO_COMPROVADO`;
- `INVALIDO_POR_FONTE`;
- `EXCLUIDO_POR_POLITICA_DOCUMENTAL`.

Somente um par cujos dois lados estejam em `PRODUZIDO_POR_FONTE_CANONICA` pode ser comparado.

É proibido:

- ausência virar zero;
- `null` virar zero;
- item incompleto ser omitido silenciosamente;
- resultado ausente ser recalculado implicitamente;
- valor actual substituir valor do snapshot;
- inferir coerência quando nenhum par é comparável.

### 4.16 Dados incompletos

O ADR deve distinguir:

- item sem qualquer par aplicável;
- par com um lado ausente;
- par com valor inválido;
- resultado do motor ausente;
- vínculo não comprovado;
- documento sem itens auditáveis;
- snapshot incompleto.

Esses estados não equivalem a divergência fiscal e não equivalem a coerência.

Devem produzir bloqueio ou resultado explícito de auditoria inconclusiva, sanitizado e sujeito a revisão humana.

A nomenclatura operacional final fica para o contrato futuro, mas o ADR deve proibir `dados_coerentes=True` nesses casos.

### 4.17 Duplicidade e repetição legítima

A política deve distinguir:

- documento duplicado;
- item duplicado por erro;
- item materialmente igual mas legitimamente repetido;
- reprocessamento do mesmo documento;
- múltiplas execuções do motor.

Regras mínimas:

- hash documental pode detectar duplicidade documental quando existente;
- itens iguais não são colapsados sem identidade canónica;
- ordinal estável pode distinguir repetições legítimas;
- reprocessamento produz nova execução identificada;
- escolha da execução usada deve ser explícita;
- ausência de política ratificada bloqueia a comparação afectada.

### 4.18 Ordem canónica

O snapshot deve ordenar itens por identidade canónica estável.

Dentro de cada item, os pares devem seguir:

1. ICMS-ST;
2. MVA;
3. Base ST.

A ordem não pode depender de ordem acidental de query, mapping ou lista externa.

O mesmo snapshot e a mesma versão de regras devem produzir a mesma serialização e o mesmo hash.

### 4.19 Consistência interna não é verdade fiscal

O ADR deve declarar explicitamente:

O `ConsistencyAuditAgent` verifica somente coerência interna entre:

- valor declarado por fonte identificada;
- valor calculado por motor identificado;
- para o mesmo item, documento, snapshot e regra.

O agente não prova:

- que o XML é verdadeiro;
- que o motor está normativamente correcto;
- que a regra fiscal está vigente;
- que o tributo foi pago;
- que existe crédito ou restituição;
- que o documento é juridicamente válido;
- que a empresa pode publicar ou usar o resultado;
- que uma divergência constitui ilícito;
- que ausência de divergência constitui conformidade fiscal.

Nenhuma saída pode usar linguagem de decisão fiscal definitiva.

### 4.20 Resultado documental derivado

O resultado do documento deve ser derivado dos resultados item a item.

Pode conter somente metadados sanitizados, como:

- documento auditado;
- total de itens;
- total de itens auditáveis;
- total de pares comparados;
- total de divergências;
- total de itens inconclusivos;
- códigos canónicos;
- estado geral derivado;
- `publication_allowed=False`;
- `requires_human_review=True`.

Não deve conter valores fiscais brutos, diferenças, percentagens, XML bruto ou mensagens do legado.

### 4.21 Falha segura

A fronteira deve falhar fechada perante:

- identidade inválida;
- autorização ausente;
- documento fora do tenant;
- item sem identidade estável;
- item não ligado ao documento;
- resultado não ligado ao item;
- execução do motor não identificada;
- versão da regra ausente;
- proveniência incompleta;
- snapshot mutável;
- hash divergente;
- duplicidade ambígua;
- ordem não determinística;
- unidade ou escala incompatível;
- par parcialmente disponível;
- tentativa de agregação compensatória;
- Session, ORM ou extras na projecção;
- modo activo não ratificado.

Falha segura significa:

- nenhuma missão produtiva;
- nenhuma escrita;
- nenhuma publicação;
- nenhum fallback;
- nenhum LLM;
- resultado operacional sanitizado;
- revisão humana quando aplicável.

### 4.22 Scheduler, registry e executor

A futura fronteira não será ligada a:

- `agent_scheduler.py`;
- `agent_registry.py` genérico;
- `agent_executor.py` legado;
- `run_all`;
- contexto genérico.

A activação futura dependerá de:

- pedido ou evento explícito;
- autorização;
- snapshot;
- criação de `AgentMission`;
- executor L3 independente e previamente ratificado.

O ADR-017 não autoriza esse executor.

### 4.23 Persistência e transacção

A decisão arquitectural deve exigir, para implementação futura:

- persistência idempotente do snapshot e da missão;
- identidade única de execução;
- política explícita de retry;
- protecção contra concorrência;
- fronteira transaccional própria;
- nenhuma confirmação parcial;
- nenhuma escrita pelo reader, adapter ou motor;
- publicação separada da auditoria;
- revogação e rastreabilidade.

Esses componentes permanecem bloqueados por gates transversais próprios.

### 4.24 LLM

Esta fronteira é determinística e não usa LLM.

LLM não participa de:

- autorização;
- identificação de item;
- formação dos pares;
- proveniência;
- cálculo;
- comparação;
- hash;
- decisão de coerência;
- publicação.

BudgetGuard não substitui qualquer regra ausente.

### 4.25 Segurança e LGPD

Não expor em payload ou logs:

- CPF;
- CNPJ;
- chave integral de NF-e;
- XML bruto;
- descrição integral sensível;
- valores fiscais brutos;
- diferenças;
- traceback;
- segredo;
- Session ou representação ORM.

Usar IDs internos opacos ou hashes quando a identidade documental precisar atravessar fronteiras.

### 4.26 Estados do ADR-017

O ADR-017 deve nascer com:

`Estado: PROPOSTO — aguarda auditoria GPT e ratificação Miguel`

Deve declarar:

- `ADR-012-GRANULARIDADE-001`: `ABERTO`;
- integração produtiva: `BLOQUEADA`;
- nenhuma implementação autorizada;
- nenhuma alteração ao canário B14.3D;
- nenhum fechamento automático do gate;
- gate de decisão e gate de implementação são distintos.

---

## 5. Fontes autorizadas para leitura

Ler apenas o necessário.

### 5.1 Governação e contratos

- `AGENTS.md`
- `docs/CCS/CCS-001-CONSTITUICAO-DE-EXECUCAO.md`, se existir
- `docs/ADR-001-GOVERNACAO_CANONICIDADE.md`
- `docs/ADR-003-ACESSO-CONTADOR-EMPRESA-DOCUMENTO.md`
- `docs/ADR-004-VINCULO-SOBERANO-CONTADOR-DT-CONTADOR-01.md`
- `docs/ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md`
- `docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md`
- `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md`
- `docs/ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT.md`
- `docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md`

### 5.2 Missões e relatórios ratificados

- `docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md`
- `docs/MISSIONS/MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA.md`
- `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`
- `docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md`
- `docs/REPORTS/REPORT-006-REDACAO-ADR-016-PROVENIENCIA-DATASANITIZATION.md`

### 5.3 Código estritamente necessário

- `app/agents/contracts/consistency_audit.py`
- `app/agents/engines/consistency_audit.py`
- `app/agents/adapters/consistency_audit.py`
- `app/agents/consistency_audit_agent.py`
- `app/services/tax_consistency/tax_consistency_engine.py`
- `tests/test_consistency_audit_mission_adapter.py`
- `app/models.py`
- `app/services/registro_analise_service.py`

### 5.4 Migrations

Ler somente migrations directamente relacionadas às tabelas e colunas citadas pelas fontes autorizadas, caso seja necessário confirmar:

- identidade do documento;
- identidade do item;
- vínculo item–documento;
- vínculo de resultado;
- timestamps;
- hashes;
- constraints.

Não pesquisar migrations por exploração ampla.

### 5.5 Proibições de leitura

Não:

- executar “Explain this codebase”;
- explorar todo o repositório;
- ler `node_modules`;
- ler `.git`;
- ler venv;
- ler caches;
- ler builds;
- procurar funcionalidades adjacentes;
- abrir ficheiros não listados sem registar necessidade e interromper.

Perante necessidade real de fonte adicional:

- parar;
- registar o ficheiro necessário e o motivo;
- não ampliar autonomamente o escopo.

---

## 6. Ficheiros autorizados

### 6.1 Entrada preexistente

Esta missão, depois de copiada para:

`docs/MISSIONS/MISSION-007-B14-SVC-03-DECISAO-GRANULARIDADE-SOBERANA-CONSISTENCY-AUDIT.md`

### 6.2 Criar exclusivamente

1. `docs/ADR-017-FRONTEIRA-SOBERANA-GRANULARIDADE-CONSISTENCY-AUDIT.md`
2. `docs/REPORTS/REPORT-007-REDACAO-ADR-017-GRANULARIDADE-CONSISTENCY-AUDIT.md`

### 6.3 Não alterar

Todos os demais ficheiros, incluindo:

- ADR-001 a ADR-016;
- MISSION-001 a MISSION-006;
- REPORT-002 a REPORT-006;
- código;
- testes;
- migrations;
- configuração;
- templates;
- ficheiros protegidos.

A própria MISSION-007 é entrada institucional e não deve ser alterada pelo Codex.

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
- não abrir para edição;
- não formatar;
- não normalizar;
- não restaurar;
- não fazer checkout;
- não fazer reset;
- não adicionar ao stage.

O estado `M` é preexistente e protegido.

---

## 8. Estrutura mínima do ADR-017

O ADR deve conter, no mínimo:

1. título e identificação;
2. estado;
3. contexto;
4. problema produtivo;
5. relação com ADR-012;
6. relação com B14.3D;
7. gate histórico;
8. decisão arquitectural;
9. escopo da missão;
10. unidade canónica de auditoria;
11. hierarquia de granularidades;
12. proibição de compensação;
13. identidade do item;
14. pares canónicos;
15. proveniência do lado declarado;
16. proveniência do lado calculado;
17. vínculo documento–item–motor–resultado;
18. pedido e autorização;
19. reader;
20. snapshot;
21. temporalidade;
22. projector;
23. estados de disponibilidade;
24. dados incompletos;
25. duplicidade;
26. ordem canónica;
27. consistência interna versus verdade fiscal;
28. resultado documental;
29. falha segura;
30. scheduler/registry/executor;
31. persistência e transacção;
32. segurança e LGPD;
33. observabilidade;
34. consequências;
35. implementação futura;
36. testes futuros obrigatórios;
37. critérios de fechamento do gate de implementação;
38. exclusões;
39. matriz de rastreabilidade;
40. ratificação pendente.

Pode adaptar numeração ao padrão real dos ADRs sem omitir matéria.

---

## 9. Testes futuros obrigatórios a documentar

O ADR deve exigir, para futura implementação:

### 9.1 Identidade e autorização

- actor inválido;
- tenant inválido;
- Empresa inexistente;
- Empresa de outro tenant;
- documento inexistente;
- documento de outra Empresa;
- actor delegado sem vínculo;
- vínculo expirado;
- vínculo revogado;
- vínculo fora do escopo;
- acesso autorizado;
- predicado de autorização nas queries;
- reconfirmação antes do retorno;
- acesso negado sem leitura transversal;
- acesso negado sem missão;
- acesso negado sem mutação.

### 9.2 Identidade de item

- item inexistente;
- item de outro documento;
- ID booleano;
- ID zero ou negativo;
- item sem identidade estável;
- itens materialmente iguais e legitimamente repetidos;
- ordinal estável;
- ordem de query alterada sem mudar hash canónico;
- tentativa de usar NCM ou descrição como identidade única.

### 9.3 Pares e proveniência

- cada par isolado;
- dois pares;
- três pares;
- lados pertencentes ao mesmo item;
- tentativa de cruzar itens diferentes;
- proveniência do lado XML ausente;
- proveniência do lado motor ausente;
- motor sem versão;
- regra sem versão;
- execução sem identidade;
- resultado sem vínculo;
- hash de input divergente;
- unidade incompatível;
- escala incompatível;
- precisão não ratificada.

### 9.4 Granularidade

- documento com um item;
- documento com múltiplos itens;
- divergência num único item;
- divergências em vários itens;
- compensação positiva/negativa entre itens não mascara divergência;
- soma documental igual com itens divergentes;
- relatório não substitui itens;
- agregado não substitui itens;
- período não cria comparação automática.

### 9.5 Dados incompletos

- nenhum par aplicável;
- um lado ausente;
- `null`;
- zero real;
- negativo finito;
- resultado do motor ausente;
- item incompleto;
- documento sem itens auditáveis;
- vínculo não comprovado;
- estado inconclusivo não produz `dados_coerentes=True`;
- ausência não vira zero.

### 9.6 Duplicidade e reprocessamento

- documento duplicado com hash;
- documento sem hash;
- item duplicado por erro;
- repetição legítima;
- duas execuções do motor;
- selecção explícita da execução;
- reprocessamento cria nova identidade;
- resultado posterior não substitui snapshot anterior.

### 9.7 Snapshot e hash

- snapshot imutável;
- serialização canónica;
- mesmo snapshot produz mesmo hash;
- ordem acidental não altera hash;
- alteração posterior da BD não altera missão;
- alteração de versão produz novo hash;
- hash divergente bloqueia;
- Session rejeitada;
- ORM rejeitado;
- extras rejeitados.

### 9.8 Segurança pública

- payload sem valores fiscais brutos;
- payload sem diferenças e percentagens;
- logs sem CPF/CNPJ/chave integral/XML;
- erro sem traceback;
- erro sem `str(exc)`;
- resultado sanitizado;
- `publication_allowed=False`;
- `requires_human_review=True`.

### 9.9 Integridade estrutural

- ADR-012 inalterada;
- B14.3D inalterado;
- serviço protegido inalterado;
- agente legado inalterado;
- scheduler, registry e executor não referenciam a fronteira;
- ausência de reader implementado nesta missão;
- ausência de código alterado;
- quatro ficheiros protegidos preservados.

Não criar testes nesta missão.

---

## 10. Preflight obrigatório

Executar e registar no REPORT-007:

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
- `HEAD == origin/main == e5cfd5ef989eb5920d479b29880746a93ba1afaa`;
- stage vazio;
- somente os quatro ficheiros protegidos podem aparecer como modificados;
- a própria MISSION-007 pode aparecer como untracked;
- ADR-017 e REPORT-007 não podem preexistir.

Se houver qualquer outro desvio:

- parar;
- não criar ADR-017;
- não criar REPORT-007;
- apresentar estado `BLOQUEADA POR DESVIO DE BASELINE`.

---

## 11. Verificações factuais limitadas

Confirmar somente:

1. ADR-012 está ratificada em v1.3;
2. B14.3D existe nos quatro ficheiros previstos;
3. ADR-012 fixa missão documental e não possui reader produtivo;
4. REPORT-002 mantém o gate produtivo aberto;
5. REPORT-003 confirma que o gate continua aberto;
6. valores declarados são observados por item;
7. não existe vínculo produtivo comprovado de pares calculados por item;
8. ADR-017 está livre;
9. REPORT-007 está livre;
10. quatro ficheiros protegidos mantêm hashes iniciais.

Não reauditar o projecto.

Não procurar arquitectura alternativa.

---

## 12. Conteúdo obrigatório do REPORT-007

Criar:

`docs/REPORTS/REPORT-007-REDACAO-ADR-017-GRANULARIDADE-CONSISTENCY-AUDIT.md`

Deve conter:

1. identificação da missão;
2. baseline;
3. estado inicial;
4. hashes iniciais dos quatro ficheiros protegidos;
5. fontes efectivamente lidas;
6. confirmação da ADR-012 v1.3;
7. confirmação do commit B14.3D;
8. confirmação de que o canário permanece inalterado;
9. evidência factual do gate produtivo;
10. confirmação da distinção entre missão documental e unidade de auditoria por item;
11. confirmação da proibição de compensação entre itens;
12. confirmação de proveniência independente dos dois lados;
13. confirmação do vínculo documento–item–motor–resultado;
14. confirmação do tratamento de dados incompletos;
15. confirmação de consistência interna versus verdade fiscal;
16. confirmação de ausência de implementação;
17. lista exacta de ficheiros criados;
18. lista de ficheiros alterados;
19. lista de ficheiros removidos;
20. hashes finais da MISSION-007 e do ADR-017;
21. declaração de que o SHA-256 do próprio REPORT-007 será apresentado somente na saída final do Codex;
22. estado final Git;
23. stage vazio;
24. commit não efectuado;
25. push não efectuado;
26. auditoria pendente GPT;
27. ratificação pendente Miguel;
28. estado final da missão.

---

## 13. Validação textual obrigatória

Antes de concluir, verificar no ADR-017 presença de:

- `ADR-012-GRANULARIDADE-001`;
- `ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT`;
- `B14.3D`;
- `ADR-017`;
- `scope = "documento"`;
- `item_documento_fiscal`;
- `unidade canónica de auditoria`;
- `escopo da missão`;
- `compensação entre itens`;
- `proveniência independente`;
- `documento`;
- `item`;
- `motor`;
- `execução`;
- `snapshot`;
- `reference_at`;
- `context_hash`;
- `actor_id`;
- `tenant_id`;
- `empresa_id`;
- `documento_id`;
- `no_autoflush`;
- `read-only`;
- `ausência não vira zero`;
- `dados incompletos`;
- `inconclusiva`;
- `consistência interna`;
- `não equivale a verdade fiscal`;
- `publication_allowed=False`;
- `requires_human_review=True`;
- `scheduler`;
- `registry`;
- `executor`;
- `LLM`;
- `fail-closed`;
- `PROPOSTO`;
- `aguarda auditoria GPT e ratificação Miguel`;
- `gate de decisão arquitectural`;
- `gate de implementação produtiva`.

Verificar ausência de afirmações equivalentes a:

- ADR-012 revogada;
- ADR-012 substituída;
- B14.3D inválido;
- granularidade do canário reaberta;
- integração produtiva autorizada;
- reader implementado;
- projector implementado;
- contrato v1.0 alterado;
- modo activo autorizado;
- agregação documental prova coerência;
- somas compensadas autorizadas;
- ausência como zero;
- item sem vínculo aceite;
- resultado mais recente usado automaticamente;
- LLM como autoridade;
- gate fechado antes da ratificação;
- código alterado;
- testes executados.

---

## 14. Estado final permitido

`git status --short` deve mostrar somente:

- os quatro ficheiros protegidos como modificados preexistentes;
- MISSION-007 untracked;
- ADR-017 untracked;
- REPORT-007 untracked.

`git diff --cached --name-only` deve permanecer vazio.

Nenhum outro ficheiro pode aparecer.

---

## 15. Proibições

Não:

- alterar código;
- alterar testes;
- alterar ADR-012;
- alterar ADR-016;
- alterar ADR-008;
- alterar missões ou relatórios anteriores;
- alterar ficheiros protegidos;
- criar reader;
- criar projector;
- criar contrato;
- criar migration;
- criar endpoint;
- criar scheduler;
- alterar registry;
- alterar executor;
- criar persistência;
- activar modo activo;
- executar pytest;
- executar migrations;
- criar commit;
- fazer push;
- fazer stage;
- usar `git add`;
- usar `git checkout`;
- usar `git reset`;
- usar `git clean`;
- normalizar ficheiros;
- pesquisar amplamente;
- ler ficheiros não autorizados;
- decidir fora da arquitectura fornecida;
- declarar verdade fiscal;
- declarar abertura produtiva.

---

## 16. Critérios de aceitação

A missão só pode terminar como `CONCLUÍDA` quando:

- baseline estiver exacta;
- ADR-017 e REPORT-007 não preexistirem;
- somente ADR-017 e REPORT-007 forem criados pelo Codex;
- ADR-012 e B14.3D permanecerem inalterados;
- quatro ficheiros protegidos permanecerem inalterados;
- todas as decisões obrigatórias estiverem no ADR-017;
- todas as evidências obrigatórias estiverem no REPORT-007;
- nenhum código, teste ou migration for alterado;
- stage permanecer vazio;
- nenhum commit ou push for efectuado;
- estado final corresponder ao permitido.

A missão deve ser `INTERROMPIDA` quando:

- baseline divergir;
- fonte necessária estiver fora do escopo;
- ADR-017 ou REPORT-007 já existirem;
- surgir conflito institucional;
- for necessária decisão arquitectural não fornecida;
- a execução exigir implementação;
- ficheiro protegido tiver sido tocado;
- não for possível produzir evidência.

---

## 17. Resultado final esperado do Codex

Apresentar concisamente:

- estado da execução;
- ADR criado;
- REPORT criado;
- MISSION-007 preservada;
- ADR-012 preservada;
- B14.3D preservado;
- quatro ficheiros protegidos preservados;
- `ADR-012-GRANULARIDADE-001`: `ABERTO`;
- integração produtiva: `BLOQUEADA`;
- código/testes alterados: `NENHUM`;
- stage: `VAZIO`;
- commit: `NÃO EFECTUADO`;
- push: `NÃO EFECTUADO`;
- SHA-256 do REPORT-007 calculado após fechamento do ficheiro;
- auditoria: `PENDENTE — GPT`;
- ratificação: `PENDENTE — Miguel`.

---

## 18. Regra final

Esta missão redige uma proposta arquitectural.

Ela:

- não implementa a fronteira;
- não altera o canário;
- não fecha automaticamente o gate;
- não autoriza integração produtiva;
- não autoriza abertura da plataforma.

Perante dúvida factual, divergência de baseline, conflito institucional ou necessidade de ampliar escopo:

**PARAR, PRESERVAR, REGISTAR E DEVOLVER AO GPT. NÃO IMPROVISAR.**
