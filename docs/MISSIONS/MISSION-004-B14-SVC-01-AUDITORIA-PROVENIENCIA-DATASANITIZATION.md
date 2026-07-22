# MISSION-004 — B14-SVC-01 — Auditoria da fronteira de proveniência do DataSanitizationAgent

Estado: PRONTA PARA EXECUÇÃO
Autoridade arquitectural: GPT
Autoridade de ratificação: Miguel
Executor técnico: Codex
Gate auditado: ADR-011-PROVENIENCIA-001
Baseline esperada: HEAD = origin/main = 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f

---

## 1. Natureza da missão

Esta é uma missão técnica, read-only, documental e estritamente delimitada.

O Codex deve auditar as fontes produtivas candidatas para os oito campos fiscais aceites pelo DataSanitizationAgent e produzir um dossiê factual para decisão arquitectural posterior.

O Codex não possui autoridade para:

- escolher a fonte canónica;
- decidir fórmulas fiscais;
- fechar o gate ADR-011-PROVENIENCIA-001;
- alterar ADRs;
- implementar reader, projector, service, endpoint ou job;
- integrar o agente produtivamente;
- alterar contratos, agentes, motores, modelos ou migrations;
- efectuar stage, commit ou push;
- declarar prontidão produtiva.

O resultado permitido é exclusivamente o relatório desta missão.

---

## 2. Objectivo exacto

Determinar, com evidência de código e schema, o estado real da proveniência dos seguintes campos:

1. faturamento
2. custos
3. lucro_contabil
4. lucro
5. regime
6. icms_pago
7. icms_devido
8. custo_fiscal_entradas

Para cada campo, o relatório deve responder:

- de qual tabela, coluna, relação ou resultado deriva;
- qual fórmula é aplicada;
- qual unidade representa;
- qual período temporal abrange;
- quais filtros são aplicados;
- se existe cutoff ou reference_at;
- como ausência é representada;
- se zero real é distinguido de ausência;
- se valores negativos são preservados;
- se existe default silencioso;
- qual actor, tenant e empresa autorizam a leitura;
- se a origem pode ser reproduzida e auditada;
- se a proveniência é independente ou apenas derivada da mesma família declarada;
- se o campo já pode atravessar a fronteira L3 com segurança.

---

## 3. Artefacto autorizado

Criar exclusivamente:

docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md

A missão pode apenas ser lida:

docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md

Nenhum outro ficheiro pode ser criado, alterado, apagado, renomeado, movido, formatado ou restaurado.

---

## 4. Alterações locais protegidas

Preservar integralmente:

- app/agents/adapters/ag_encerramento.py
- app/agents/engines/ag_encerramento.py
- docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
- tests/test_ag_encerramento_mission_adapter.py

É proibido utilizar:

- git restore
- git checkout
- git reset
- git add
- git stash

As marcações locais desses quatro ficheiros não devem ser corrigidas.

O Codex deve registar separadamente:

- estado apresentado por git status;
- resultado de git diff --name-only;
- hash do índice;
- hash normalizado do working tree.

Não concluir que existe alteração real de conteúdo apenas com base em “M” no git status.

---

## 5. Estado inicial obrigatório

Antes da auditoria, executar e registar:

git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --name-only
git diff --cached --name-only

Para os quatro ficheiros protegidos, comparar:

git rev-parse ":CAMINHO"
git hash-object --path="CAMINHO" "CAMINHO"

Estado esperado:

- branch main;
- HEAD igual a origin/main;
- baseline 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f;
- stage vazio;
- nenhum REPORT-004 preexistente.

Se REPORT-004 já existir, interromper sem sobrescrever.

Se existir alteração adicional não autorizada, não corrigir e interromper.

---

## 6. Escopo de leitura obrigatório

Auditar, no mínimo:

- app/services/insights_engine.py
- app/agents/contracts/data_sanitization.py
- app/agents/adapters/data_sanitization.py
- app/agents/engines/data_sanitization.py, caso exista
- app/agents/data_sanitization_agent.py, caso exista
- app/models.py
- app/database.py
- app/agents/readers/ag_encerramento.py
- app/agents/contracts/mission.py
- app/agents/mission_factory.py
- tests/test_data_sanitization_mission_adapter.py
- documentos que contenham ADR-011-PROVENIENCIA-001
- migrations relacionadas com Empresa, DocumentoFiscal, ItemFiscal, NotaFiscalItem e campos utilizados nas fórmulas

A pesquisa adicional deve permanecer limitada aos símbolos, tabelas, colunas e chamadas directamente relacionados com os oito campos e com a autorização da leitura.

Não reauditar:

- executor L3;
- persistência geral de AgentMission;
- scheduler;
- registry;
- ConsistencyAuditAgent;
- MemorialValidatorAgent;
- ADR-012;
- ADR-013.

Essas matérias já foram registadas no REPORT-002.

---

## 7. Matriz obrigatória dos oito campos

Criar uma matriz com estas colunas:

| Campo | Fonte exacta | Fórmula exacta | Filtros e relações | Unidade | Período/cutoff | Ausência versus zero | Negativos | Default | Autorização | Reprodutibilidade | Estado |

Estados permitidos:

- PROVADO
- PARCIAL
- NÃO PROVADO
- INCOMPATÍVEL COM A FRONTEIRA L3

Não preencher lacunas por inferência.

Quando a evidência não existir, declarar NÃO PROVADO.

---

## 8. Questões obrigatórias por campo

### 8.1 faturamento

Comprovar:

- qual modelo e coluna são somados;
- como documento de saída é identificado;
- se cancelamentos, duplicatas ou documentos inválidos entram;
- se o valor é produto, total da nota ou outro agregado;
- se existe delimitação temporal;
- se ausência vira zero.

### 8.2 custos

Comprovar:

- qual modelo e coluna são somados;
- como documento de entrada é identificado;
- se custo contabilístico, custo de aquisição e valor de produto estão a ser tratados como equivalentes;
- se devoluções, cancelamentos e duplicatas entram;
- se existe período.

### 8.3 lucro_contabil

Comprovar:

- fórmula real;
- origem de faturamento e custos;
- existência de max(0, valor);
- perda de prejuízo contabilístico;
- diferença real ou ausência de diferença relativamente a lucro.

### 8.4 lucro

Comprovar:

- fórmula real;
- se é lucro fiscal, operacional, contabilístico ou apenas diferença entre agregados;
- se negativos são truncados;
- se duplica lucro_contabil.

### 8.5 regime

Comprovar:

- coluna de origem;
- valores permitidos;
- comportamento quando Empresa não existe;
- comportamento quando regime está nulo ou vazio;
- existência de default silencioso;
- instante temporal representado pelo regime actual.

### 8.6 icms_pago

Comprovar:

- coluna exacta;
- documentos considerados;
- se representa ICMS próprio, ICMS-ST ou outro valor;
- se “pago” é comprovado ou apenas declarado no XML;
- se deriva de ItemFiscal.valor_st;
- se existe vínculo a pagamento efectivo;
- período e autorização.

### 8.7 icms_devido

Comprovar:

- coluna exacta;
- documentos considerados;
- se representa valor calculado, declarado ou apenas valor_st de saída;
- se possui proveniência independente de icms_pago;
- se deriva da mesma família declarada;
- período e autorização.

### 8.8 custo_fiscal_entradas

Comprovar:

- origem exacta;
- fórmula;
- se está apenas igualado a custos;
- se existe evidência semântica para chamar o valor de custo fiscal;
- impostos incluídos ou excluídos;
- risco de nomenclatura enganadora.

---

## 9. Fronteira temporal obrigatória

Auditar se existe actualmente:

- reference_at;
- data inicial;
- data final;
- competência fiscal;
- período contabilístico;
- filtro por data de emissão;
- regra para documentos posteriores ao instante da missão;
- tratamento de documentos sem data válida.

Distinguir:

- data_referencia apenas informativa;
- data_referencia utilizada como cutoff real.

Se as consultas lerem todo o histórico e apenas calcularem max(data_emissao), declarar expressamente que não existe fronteira temporal efectiva.

---

## 10. Fronteira de autorização obrigatória

Auditar se a fonte candidata comprova, antes de ler ou agregar:

- actor_id;
- tenant_id;
- empresa_id;
- propriedade ou autorização sobre a Empresa;
- coerência actor-tenant-empresa;
- reconfirmação antes da projecção final.

Verificar se as consultas filtram apenas empresa_id.

Comparar, apenas como padrão técnico e sem copiar mecanicamente, com:

app/agents/readers/ag_encerramento.py

Identificar quais elementos daquele padrão seriam necessários para um futuro reader autorizado:

- Session injectada;
- no_autoflush;
- actor igual ao tenant, quando aplicável;
- Empresa filtrada por id e proprietário;
- ausência de ORM ou Session no retorno;
- ausência de escrita;
- reconfirmação final da autoridade.

Não implementar o reader.

---

## 11. Compatibilidade com o contrato L3

Comprovar se o contexto actualmente produzido:

- contém apenas campos aceites;
- transporta db ou Session;
- contém campos extras;
- satisfaz extra="forbid";
- preserva ausência;
- permite CONTEXTO_SEM_CAMPOS_FISCAIS;
- distingue ausência de zero;
- preserva negativos;
- possui identidade coerente;
- pode ser serializado deterministicamente;
- pode gerar context_hash reprodutível.

Identificar exactamente por que o resultado actual de InsightEngine._montar_contexto_engines pode ou não ser entregue directamente ao adapter L3.

Não alterar o contrato.

---

## 12. Reader/projector futuro — requisitos mínimos

Sem implementar ou escolher arquitectura definitiva, listar os requisitos comprovadamente necessários para um futuro componente autorizado.

O relatório deve separar:

### Requisitos obrigatórios comprovados

Exemplos:

- entrada com actor_id, tenant_id, empresa_id e período;
- autorização antes de qualquer agregação;
- consultas read-only;
- ausência preservada como ausência;
- zero somente quando comprovadamente real;
- negativos preservados;
- nenhuma Session ou ORM no contexto;
- apenas campos aceites pelo contrato;
- ordenação e agregação determinísticas;
- referência temporal efectiva;
- reconfirmação de autoridade antes do retorno.

### Decisões ainda dependentes de ratificação

Exemplos:

- fórmula canónica de faturamento;
- significado de custos;
- lucro versus lucro_contabil;
- semântica de ICMS pago e devido;
- significado de custo_fiscal_entradas;
- período fiscal escolhido;
- comportamento para regime ausente.

O Codex não deve seleccionar opções.

---

## 13. Teste autorizado

Pode executar exclusivamente:

pytest -q tests/test_data_sanitization_mission_adapter.py

Não executar a suite completa.

Não modificar testes.

Se o teste falhar:

- registar a falha;
- não corrigir;
- não ampliar o escopo;
- continuar apenas se a auditoria documental permanecer possível.

---

## 14. Estrutura obrigatória do REPORT-004

O relatório deve conter:

# REPORT-004 — Auditoria da proveniência do DataSanitizationAgent

## 1. Identificação da missão
## 2. Estado inicial do repositório
## 3. Metodologia e limites
## 4. Contrato L3 observado
## 5. Fonte produtiva candidata
## 6. Matriz dos oito campos
## 7. Fronteira temporal
## 8. Ausência, zero, negativos e defaults
## 9. Fronteira de autorização
## 10. Compatibilidade com extra="forbid"
## 11. Reprodutibilidade e context_hash
## 12. Requisitos mínimos do futuro reader/projector
## 13. Decisões ainda não ratificadas
## 14. Teste autorizado
## 15. Matriz do gate ADR-011-PROVENIENCIA-001
## 16. Riscos não resolvidos
## 17. Estado final do repositório
## 18. Declaração de não alteração
## 19. Estado da execução

Para cada conclusão, utilizar:

Estado:
Ficheiro:
Linhas:
Evidência:
Implicação:

---

## 15. Matriz final do gate

A matriz final deve conter, no mínimo:

- fonte canónica dos oito campos;
- fórmula e unidade;
- período/cutoff;
- ausência versus zero;
- preservação de negativos;
- regime ausente;
- semântica de ICMS;
- semântica de custo_fiscal_entradas;
- autorização actor/tenant/empresa;
- projector mínimo;
- compatibilidade com contrato;
- reprodutibilidade;
- testes existentes.

Para cada item, declarar:

PROVADO | PARCIAL | NÃO PROVADO

E:

BLOQUEIA INTEGRAÇÃO PRODUTIVA: SIM | NÃO

O Codex não pode declarar o gate fechado.

---

## 16. Estado final obrigatório

Executar e registar:

git branch --show-current
git rev-parse HEAD
git rev-parse origin/main
git status --short
git diff --name-only
git diff --cached --name-only

Confirmar:

- apenas REPORT-004 foi criado;
- MISSION-004 não foi alterada;
- quatro ficheiros protegidos preservados;
- stage vazio;
- nenhum commit;
- nenhum push;
- HEAD e origin/main inalterados.

Se ocorrer qualquer desvio, não limpar o repositório.

---

## 17. Critério de conclusão

A missão será EXECUTADA apenas se:

- os oito campos forem auditados individualmente;
- fontes, fórmulas e lacunas forem documentadas;
- período e cutoff forem comprovados ou declarados ausentes;
- ausência, zero, negativos e defaults forem diferenciados;
- autorização actor/tenant/empresa for auditada;
- compatibilidade com o contrato L3 for comprovada;
- requisitos mínimos do futuro reader/projector forem separados das decisões pendentes;
- nenhum código ou ADR for alterado;
- REPORT-004 for o único ficheiro criado;
- stage permanecer vazio;
- nenhum commit ou push for efectuado.

---

## 18. Conclusão permitida

O Codex deve terminar apresentando:

Estado da execução:
EXECUTADA | EXECUTADA COM PENDÊNCIAS | INTERROMPIDA

Relatório criado:
docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md

Outros ficheiros alterados:
NENHUM

Gate ADR-011-PROVENIENCIA-001:
ABERTO — decisão GPT e ratificação Miguel pendentes

Stage:
VAZIO

Commit:
NÃO EFECTUADO

Push:
NÃO EFECTUADO

Auditoria:
PENDENTE — autoridade GPT

Ratificação:
PENDENTE — autoridade Miguel

---

## 19. Regra final

Perante qualquer dúvida, ambiguidade, conflito ou alteração inesperada:

PARAR
REGISTAR
NÃO CORRIGIR
NÃO IMPLEMENTAR
NÃO AMPLIAR
NÃO COMMITAR
NÃO FAZER PUSH