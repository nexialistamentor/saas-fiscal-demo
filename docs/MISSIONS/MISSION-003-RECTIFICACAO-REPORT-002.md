# MISSION-003 — Rectificação soberana do REPORT-002

**Estado:** PRONTA PARA EXECUÇÃO  
**Data:** 2026-07-22  
**Autoridade arquitectural:** GPT  
**Autoridade de ratificação:** Miguel  
**Executor autorizado:** Codex  
**Missão anterior:** MISSION-002  
**Relatório auditado:** REPORT-002  
**Baseline esperada:** `HEAD = origin/main = 7cdacac5d4af200b4a4f9a0372a88b5bea607fbb`

---

## 1. Natureza da missão

Esta é uma missão documental, mecânica e estritamente limitada.

O Codex actua como Executor Técnico subordinado ao Sistema de Construção Soberana.

O Codex não possui autoridade para:

- decidir arquitectura;
- rever o mérito das rectificações;
- reabrir ADRs ratificadas;
- fechar gates formais;
- alterar código, testes, contratos, migrations ou configurações;
- ampliar a auditoria;
- efectuar stage;
- efectuar commit;
- efectuar push;
- declarar auditoria aprovada;
- declarar ratificação concluída.

As quatro rectificações descritas nesta missão já foram determinadas pela autoridade GPT.

O Codex deve apenas aplicá-las com precisão e produzir as evidências correspondentes.

---

## 2. Objectivo exacto

Rectificar quatro afirmações tecnicamente incorrectas ou ambíguas existentes em:

`docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`

E criar o relatório de execução correspondente:

`docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md`

Nenhuma outra intenção está autorizada.

---

## 3. Artefactos autorizados

### 3.1 Ficheiro que pode ser alterado

```text
docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md
```

### 3.2 Ficheiro que deve ser criado

docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md

### 3.3 Ficheiro da missão

docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md

Este ficheiro já foi criado pela autoridade arquitectural.

O Codex pode lê-lo, mas não pode alterá-lo.

### 3.4 Proibição absoluta

Nenhum outro ficheiro pode ser:

criado;

alterado;

apagado;

renomeado;

movido;

formatado;

restaurado;

adicionado ao stage.

## 4. Alterações locais protegidas

Os seguintes ficheiros contêm trabalho preexistente pertencente a outro fluxo:

app/agents/adapters/ag_encerramento.py

app/agents/engines/ag_encerramento.py

docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md

tests/test_ag_encerramento_mission_adapter.py

Regras obrigatórias:

não abrir para edição;

não formatar;

não restaurar;

não descartar alterações;

não adicionar ao stage;

não alterar line endings;

não usar git checkout;

não usar git restore;

não usar git reset;

não usar git add;

não usar stash;

não tentar limpar o working tree.

Apenas o estado Git desses ficheiros pode ser registado como evidência de preservação.

## 5. Pré-condições obrigatórias

Antes de qualquer edição, executar e registar no REPORT-003:

git branch --show-current

git rev-parse HEAD

git rev-parse origin/main

git status --short

git diff --name-only

git diff --cached --name-only

Confirmar também:

docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md existe

docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md não existe

docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md existe

Estado inicial esperado:

branch = main

HEAD = origin/main = 7cdacac5d4af200b4a4f9a0372a88b5bea607fbb

M app/agents/adapters/ag_encerramento.py

M app/agents/engines/ag_encerramento.py

M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md

M tests/test_ag_encerramento_mission_adapter.py

?? docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md

?? docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md

stage vazio

Caso exista qualquer alteração adicional não autorizada:

não corrigir;

não apagar;

não restaurar;

não iniciar a edição;

criar apenas o REPORT-003 com estado INTERROMPIDA, se for possível fazê-lo sem ampliar o desvio;

terminar a missão.

Caso o REPORT-003 já exista, interromper sem o sobrescrever.

## 6. Preservação da versão anterior

O REPORT-002 ainda não está versionado pelo Git.

Por isso, antes de editar:

calcular e registar o SHA-256 inicial do REPORT-002;

criar uma cópia temporária fora do repositório;

utilizar essa cópia apenas para comparar antes e depois;

não criar backup dentro do repositório;

apagar a cópia temporária antes de terminar.

O REPORT-003 deve registar:

SHA-256 antes:

SHA-256 depois:

Caminho temporário utilizado:

Cópia temporária removida: SIM | NÃO

A edição deve ser mínima.

É proibido reescrever, reformatar ou normalizar o documento inteiro.

Preservar:

codificação UTF-8;

títulos;

estrutura;

espaçamento não relacionado;

restantes evidências;

restantes conclusões;

line endings existentes, quando tecnicamente possível.

## RECTIFICAÇÃO 1 — DATASANITIZATIONAGENT

### 7. Problema factual

O REPORT-002 afirma actualmente, na secção do DataSanitizationAgent, que a conversão de ausência em zero implica que:

o agente L3 não recebe diagnóstico de ausência

Essa formulação está incorrecta.

O agente L3 possui o diagnóstico canónico:

CONTEXTO_SEM_CAMPOS_FISCAIS

O problema real acontece antes do agente:

a fonte candidata utiliza coalesce(sum(...), 0) or 0;

a ausência é transformada em zero;

o contexto chega numericamente preenchido;

o diagnóstico canónico de ausência deixa de poder ser activado.

### 8. Alteração obrigatória

Na secção correspondente, remover qualquer afirmação de que o agente não possui diagnóstico de ausência.

A evidência e a implicação devem expressar obrigatoriamente esta semântica:

Evidência: a fonte candidata converte agregados ausentes em zero antes
da fronteira L3. O agente possui o diagnóstico canónico
CONTEXTO_SEM_CAMPOS_FISCAIS para contexto sem campos fiscais, mas a
transformação anterior apaga a ausência antes de o contexto chegar ao agente.

Implicação: a proveniência de ausência é perdida na fonte ou projector
anterior ao agente, impedindo a activação do diagnóstico canónico.
O problema não é falta de capacidade diagnóstica do DataSanitizationAgent.

Não alterar o estado do gate:

ADR-011-PROVENIENCIA-001

Gate produtivo: ABERTO

Integração produtiva: BLOQUEADA

## RECTIFICAÇÃO 2 — PROVENIÊNCIA DE ICMS

### 9. Problema factual

As linhas relativas a:

icms_pago

icms_devido

afirmam actualmente:

fonte independente por tipo

Essa formulação é excessiva.

Ambos os campos derivam da mesma família declarada:

ItemFiscal.valor_st

A separação actual ocorre apenas pelo tipo de documento:

entrada

saída

Isso produz agregados distintos, mas não comprova proveniência independente.

### 10. Alteração obrigatória

Nas duas linhas da tabela, remover:

fonte independente por tipo

E inserir uma formulação equivalente a:

agregado distinto por tipo de documento; deriva da mesma família
de dados declarados ItemFiscal.valor_st; sem proveniência independente
comprovada; sem cutoff temporal e sem actor autorizado

A conclusão da secção deve permanecer coerente com:

Os valores são agregados distintos por tipo de documento,
mas não constituem pares de proveniência independente comprovada.

Não modificar fórmulas, unidades ou referências de linhas que não estejam relacionadas com esta rectificação.

## RECTIFICAÇÃO 3 — FALLBACK NORMATIVO DO PDF

### 11. Problema factual

O REPORT-002 afirma actualmente que, quando o PDF não encontra referência correspondente no ref_map, ele:

apenas omite a linha de fundamento

Essa afirmação está incorrecta.

O comportamento real é continuar a geração e apresentar:

Fundamento: base normativa em actualização.

### 12. Alteração obrigatória

Substituir a evidência actual por uma formulação factual equivalente a:

Evidência: quando ref_map.get(tipo) não encontra correspondência,
o PDF não bloqueia e não gera alerta. A geração continua e apresenta
o fallback textual: "Fundamento: base normativa em actualização."

A implicação deve declarar:

Implicação: a ausência de referência aplicável é substituída por um
fallback textual com aparência de fundamento normativo, sem bloqueio
e sem alerta explícito.

Preservar as conclusões já existentes sobre:

ausência de foreign key;

convenção Insight.tipo == ReferenciaLegal.codigo;

falta de vigência aplicada;

falta de snapshot normativo;

impossibilidade de o agente provar cobertura por insight.

## RECTIFICAÇÃO 4 — REGISTRY LEGADO E ADAPTERS L3

### 13. Problema de ambiguidade

O relatório deve distinguir inequivocamente:

Agentes legados

de:

Adapters L3

Estado técnico correcto:

Agentes legados:

presentes no registry genérico.

Adapters L3:

não registados, não chamados e sem integração produtiva.

Nenhuma frase pode sugerir que os adapters L3 estão registados no registry legado.

### 14. Alteração obrigatória na secção Scheduler e registry

Onde o relatório afirma que “os três agentes estão no registry genérico”, corrigir para uma formulação equivalente a:

As três classes legadas correspondentes aos agentes estão presentes
no registry genérico e seriam chamadas por run_all com contexto genérico.

Os três adapters L3 não estão registados, não possuem chamador produtivo
e permanecem isolados do scheduler legado.

A implicação deve distinguir:

A presença das classes legadas cria risco de activação acidental
caso o scheduler genérico seja ligado.

O isolamento actual dos adapters L3 está preservado.

### 15. Alteração obrigatória na matriz de evidências

Remover a linha ambígua:

| Ausência de integração no scheduler legado | NÃO | registry 25,30-31 | SIM |

Inserir exactamente duas linhas separadas:

| Adapters L3 isolados do scheduler legado | SIM | adapters sem registo e sem chamador produtivo | NÃO |

| Agentes legados presentes no registry genérico | SIM | `app/agents/agent_registry.py` | SIM |

Semântica da última coluna:

NÃO para isolamento dos adapters: o isolamento actual não é um bloqueio;

SIM para agentes legados no registry: a presença permanece risco e matéria pendente.

Não remover da secção de riscos:

Activação acidental dos agentes legados por run_all se o scheduler for ligado.

### 16. Limites obrigatórios das rectificações

Não alterar:

os estados de ADR-011-PROVENIENCIA-001;

os estados de ADR-012-GRANULARIDADE-001;

os estados de ADR-013-FRONTEIRA-001;

a conclusão de que a integração produtiva permanece bloqueada;

a ausência de executor L3;

a ausência de persistência de missões;

a ausência de persistência de resultados;

a ausência de idempotência concorrente;

a ausência de política transaccional L3;

o estado EXECUTADA COM PENDÊNCIAS da MISSION-002;

a declaração de que não houve commit ou push;

evidências não relacionadas com estas quatro rectificações;

estrutura geral do REPORT-002.

Não adicionar:

propostas de implementação;

patches;

modelos ORM;

migrations;

novos contratos;

novas ADRs;

decisões de produto;

encerramento de gates;

afirmações de prontidão produtiva.

### 17. Validação textual obrigatória

Depois da edição, comprovar que as formulações incorrectas já não existem.

Pesquisar exactamente:

o agente L3 não recebe diagnóstico de ausência

fonte independente por tipo

apenas omite a linha de fundamento

Ausência de integração no scheduler legado | NÃO

Resultado obrigatório para cada uma:

0 ocorrências

Comprovar a presença das formulações correctas:

CONTEXTO_SEM_CAMPOS_FISCAIS

sem proveniência independente comprovada

Fundamento: base normativa em actualização.

Adapters L3 isolados do scheduler legado

Agentes legados presentes no registry genérico

Resultado obrigatório:

pelo menos 1 ocorrência de cada formulação

Confirmar ainda:

ADR-011-PROVENIENCIA-001 continua ABERTO

ADR-012-GRANULARIDADE-001 continua ABERTO

ADR-013-FRONTEIRA-001 continua ABERTO

Integração produtiva continua bloqueada

Não executar testes de aplicação.

Esta é uma missão exclusivamente documental.

### 18. Comparação antes e depois

Utilizando a cópia temporária criada antes da edição:

comparar o REPORT-002 anterior com o rectificado;

confirmar que apenas os quatro grupos autorizados foram alterados;

registar no REPORT-003 um resumo dos hunks modificados;

não copiar o relatório completo;

não incluir conteúdo irrelevante;

apagar a cópia temporária depois da comparação.

Se a comparação mostrar alteração fora dos quatro grupos:

não tentar corrigir por restauração ampla;

interromper;

declarar o desvio no REPORT-003;

não efectuar commit ou push.

## REPORT-003

### 19. Relatório obrigatório da missão

Criar:

docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md

Com a seguinte estrutura exacta:

# REPORT-003 — Rectificação soberana do REPORT-002

## 1. Identificação da missão

## 2. Estado inicial do repositório

## 3. Artefactos autorizados

## 4. Hash inicial do REPORT-002

## 5. Rectificação DataSanitizationAgent

## 6. Rectificação da proveniência de ICMS

## 7. Rectificação do fallback normativo

## 8. Rectificação registry legado versus adapters L3

## 9. Validação textual

## 10. Comparação antes e depois

## 11. Hash final do REPORT-002

## 12. Estado final do repositório

## 13. Declaração de preservação

## 14. Estado da execução

Para cada rectificação, utilizar:

Estado: APLICADA | NÃO APLICADA | INTERROMPIDA

Local alterado:

Formulação anterior:

Formulação rectificada:

Evidência de validação:

O REPORT-003 não pode declarar:

auditoria aprovada;

ratificação concluída;

gate fechado;

integração autorizada;

prontidão produtiva;

commit autorizado.

### 20. Estado final obrigatório

Depois de concluir a edição e criar o REPORT-003, executar:

git branch --show-current

git rev-parse HEAD

git rev-parse origin/main

git status --short

git diff --name-only

git diff --cached --name-only

Calcular novamente o SHA-256 do REPORT-002.

Confirmar que a cópia temporária foi apagada.

Estado final permitido:

M app/agents/adapters/ag_encerramento.py

M app/agents/engines/ag_encerramento.py

M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md

M tests/test_ag_encerramento_mission_adapter.py

?? docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md

?? docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md

?? docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md

stage vazio

HEAD = origin/main

nenhum commit

nenhum push

nenhum outro ficheiro alterado

Caso o estado final seja diferente:

Estado da execução: INTERROMPIDA POR DESVIO DE ESCOPO

Não limpar nem restaurar o repositório.

### 21. Critério de conclusão

A missão pode ser declarada EXECUTADA apenas quando:

as quatro rectificações forem aplicadas;

nenhuma rectificação adicional for introduzida;

os quatro textos incorrectos tiverem zero ocorrências;

os cinco textos correctos estiverem presentes;

os três gates continuarem abertos;

o REPORT-003 estiver criado;

o SHA-256 anterior e posterior estiverem registados;

a comparação confirmar apenas alterações autorizadas;

a cópia temporária tiver sido removida;

as quatro alterações protegidas permanecerem intactas;

o stage estiver vazio;

nenhum commit tiver sido efectuado;

nenhum push tiver sido efectuado.

### 22. Conclusão permitida

O Codex deve terminar apresentando exactamente:

Estado da execução:

EXECUTADA | EXECUTADA COM PENDÊNCIAS | INTERROMPIDA

Ficheiro rectificado:

docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md

Relatório criado:

docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md

Outros ficheiros alterados:

NENHUM

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

### 23. Regra final

Perante qualquer dúvida, ambiguidade, conflito de escopo ou alteração inesperada:

PARAR

REGISTAR

NÃO CORRIGIR

NÃO AMPLIAR

NÃO COMMITAR

NÃO FAZER PUSH