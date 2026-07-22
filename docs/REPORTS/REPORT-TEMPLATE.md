# REPORT — Modelo Institucional

**Estado:** MODELO  
**Sistema:** Sistema de Construção Soberana  
**Documento superior:** CCS-001 — Constituição de Execução do Executor Técnico  
**Documento relacionado:** MISSION — Modelo Institucional

---

# 1. Identificação

- ID do relatório:
- ID da missão:
- Título da missão:
- Estado final da missão:
- Autoridade emissora:
- Executor:
- Data de início:
- Data de conclusão:
- Commit inicial:
- Commit final:

---

# 2. Resumo executivo

Esta secção apresenta uma descrição objetiva e verificável do resultado da execução.

Deve informar:

- o que foi executado;
- qual foi o resultado alcançado;
- se o objetivo foi integralmente cumprido;
- se ocorreram interrupções, limitações, riscos ou pendências;
- qual o estado final atribuído à missão.

Não deve conter opiniões, justificações vagas ou informação não sustentada por evidências.

---

# 3. Objetivo da missão

Registar integralmente o objetivo definido na missão.

O relatório não pode reinterpretar, ampliar ou substituir o objetivo autorizado.

## Resultado alcançado

Descrever objetivamente o resultado produzido em relação ao objetivo.

## Grau de cumprimento

Selecionar exatamente uma opção:

- INTEGRAL
- PARCIAL
- NÃO CUMPRIDO
- NÃO APLICÁVEL POR INTERRUPÇÃO

Apresentar a justificação com referência às evidências produzidas.

---

# 4. Escopo executado

Descrever exatamente o que foi executado dentro do escopo autorizado.

## Componentes abrangidos

- Ficheiros:
- Módulos:
- Testes:
- Documentos:
- Outros componentes autorizados:

## Componentes não alterados

Registar os componentes relevantes que permaneceram fora da execução por não integrarem o escopo autorizado.

## Desvios de escopo

Selecionar exatamente uma opção:

- NÃO OCORRERAM
- OCORRERAM E FORAM AUTORIZADOS
- OCORRERAM SEM AUTORIZAÇÃO

Quando aplicável, descrever cada desvio e a respetiva autorização ou violação.

---

# 5. Alterações produzidas

## Ficheiros criados

Listar cada ficheiro criado.

Quando não existirem:

- NENHUM

## Ficheiros alterados

Listar cada ficheiro alterado e resumir objetivamente a alteração realizada.

Quando não existirem:

- NENHUM

## Ficheiros removidos

Listar cada ficheiro removido e a autorização correspondente.

Quando não existirem:

- NENHUM

## Comportamentos alterados

Descrever qualquer alteração de comportamento observável.

Quando não existirem:

- NENHUM

## Dependências

Listar dependências introduzidas, removidas ou atualizadas.

Quando não existirem:

- NENHUMA

---

# 6. Execução realizada

Descrever, em ordem objetiva, as ações executadas durante a missão.

O registo deve permitir compreender o percurso técnico sem depender da memória do Executor.

Não devem ser incluídos raciocínios privados, hipóteses descartadas sem relevância ou informação não verificável.

## Ferramentas utilizadas

Listar todas as ferramentas relevantes utilizadas durante a execução.

## Comandos executados

Registar os comandos necessários para reproduzir ou auditar a execução.

Operações que exponham credenciais, dados pessoais, segredos ou informação protegida devem ser sanitizadas.

---

# 7. Evidências

Toda afirmação relevante do relatório deve ser sustentada por evidência verificável.

## Estado inicial do repositório

Registar:

- branch;
- commit;
- resultado de `git status`;
- alterações preexistentes;
- ficheiros não rastreados;
- outras condições relevantes.

## Diferenças produzidas

Apresentar ou referenciar:

- `git diff`;
- `git diff --stat`;
- lista final dos ficheiros afetados;
- outras evidências equivalentes.

## Estado final do repositório

Registar:

- branch;
- commit;
- resultado de `git status`;
- alterações remanescentes;
- ficheiros não rastreados;
- outras condições relevantes.

## Evidências adicionais

Incluir logs, saídas, resultados, capturas ou referências necessárias para auditoria independente.

---

# 8. Testes e validações

## Testes previstos na missão

Listar todos os testes e validações obrigatórios definidos na missão.

## Testes executados

Para cada teste, registar:

- comando;
- escopo;
- resultado;
- quantidade de testes aprovados;
- quantidade de testes falhados;
- quantidade de testes ignorados;
- avisos relevantes.

## Testes não executados

Listar cada teste não executado e a justificação objetiva.

Quando não existirem:

- NENHUM

## Regressões

Selecionar exatamente uma opção:

- NÃO IDENTIFICADAS
- IDENTIFICADAS E RESOLVIDAS
- IDENTIFICADAS E NÃO RESOLVIDAS
- NÃO FOI POSSÍVEL DETERMINAR

Descrever as evidências que sustentam a classificação.

---

# 9. Restrições e conformidade

Avaliar o cumprimento das restrições definidas na missão.

## Restrições cumpridas

Listar as restrições verificadas e as respetivas evidências.

## Violações

Selecionar exatamente uma opção:

- NÃO IDENTIFICADAS
- IDENTIFICADAS

Quando existirem, descrever cada violação, o momento em que ocorreu e o impacto produzido.

## Conformidade institucional

Registar a conformidade com:

- CCS aplicável;
- `AGENTS.md`;
- ADRs referenciados;
- contratos institucionais;
- missão formal;
- outras normas superiores aplicáveis.

Qualquer conflito deve ser explicitamente declarado.

---

# 10. Limitações

Registar todas as limitações técnicas, operacionais ou probatórias encontradas durante a execução.

Quando não existirem:

- NENHUMA

Uma limitação não pode ser ocultada nem convertida em conclusão positiva sem evidência suficiente.

---

# 11. Riscos identificados

Para cada risco, registar:

- descrição;
- origem;
- impacto possível;
- probabilidade estimada, quando verificável;
- mitigação existente;
- ação futura recomendada;
- necessidade ou não de nova decisão institucional.

Quando não existirem:

- NENHUM

O Executor não deve resolver unilateralmente riscos que exijam decisão arquitetural ou institucional.

---

# 12. Pendências

Listar todas as ações não concluídas, questões abertas ou trabalhos que exijam missão futura.

Para cada pendência, registar:

- descrição;
- motivo;
- impacto;
- bloqueio associado;
- documento ou decisão necessária;
- proposta de tratamento futuro, sem execução não autorizada.

Quando não existirem:

- NENHUMA

---

# 13. Interrupções

Selecionar exatamente uma opção:

- NÃO OCORRERAM
- OCORRERAM

Quando ocorrerem, registar:

- momento da interrupção;
- critério acionado;
- motivo;
- evidências preservadas;
- estado do repositório;
- decisão necessária para eventual continuidade.

O Executor não deve declarar resolvido um motivo de interrupção sem autorização institucional.

---

# 14. Estado final da missão

Selecionar exatamente um estado:

- CONCLUÍDA
- CONCLUÍDA COM PENDÊNCIAS
- INTERROMPIDA
- REJEITADA

## Justificação

A justificação deve demonstrar objetivamente a relação entre:

- objetivo;
- escopo;
- alterações;
- testes;
- evidências;
- restrições;
- limitações;
- riscos;
- pendências;
- estado final atribuído.

O Executor declara o resultado técnico, mas não ratifica institucionalmente a missão.

---

# 15. Declaração do Executor

O Executor declara que:

- executou apenas o escopo autorizado;
- não ocultou alterações, falhas, limitações, riscos ou pendências;
- produziu as evidências disponíveis;
- não tomou decisões arquiteturais ou institucionais fora da sua autoridade;
- o conteúdo deste relatório corresponde ao estado efetivamente observado.

- Executor:
- Data:
- Referência técnica:

---

# 16. Auditoria

Esta secção deve ser preenchida pela função de auditoria competente.

## Resultado da auditoria

Selecionar exatamente uma opção:

- APROVADO
- APROVADO COM RESSALVAS
- DEVOLVIDO PARA CORREÇÃO
- REJEITADO

## Verificações

- Objetivo verificado:
- Escopo verificado:
- Evidências verificadas:
- Testes verificados:
- Conformidade institucional verificada:
- Riscos e pendências verificados:
- Estado final considerado adequado:

## Observações da auditoria

Registar apenas constatações verificáveis, ressalvas e inconformidades.

- Auditor:
- Data:
- Referência da auditoria:

---

# 17. Ratificação

Esta secção deve ser preenchida exclusivamente pela autoridade competente.

## Decisão

Selecionar exatamente uma opção:

- RATIFICADA
- RATIFICADA COM CONDICIONANTES
- NÃO RATIFICADA
- NOVA MISSÃO NECESSÁRIA

## Fundamentação

Registar a decisão institucional e as condições aplicáveis.

A ratificação não altera retroativamente as evidências nem o resultado técnico declarado pelo Executor.

- Autoridade de ratificação:
- Data:
- Referência da decisão: