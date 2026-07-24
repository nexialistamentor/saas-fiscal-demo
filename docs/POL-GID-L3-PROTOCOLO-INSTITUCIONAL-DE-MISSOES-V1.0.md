# POL-GID-L3 — Protocolo Institucional de Missões Documentais Ordinárias — Versão 1.0

## 1. Estado

**PROPOSTA DOCUMENTAL — INACTIVO — NÃO IMPLEMENTADO.**

O gate de activação permanece pendente e bloqueado.

## 2. Identificação

Identificador: `PROTOCOLO-MISSOES-GID-L3-V1.0`.

Classificação: **INSTRUMENTO PROCEDIMENTAL SUBORDINADO À POL-GID-L3 v1.0.**

## 3. Autoridade de origem

A autoridade deriva exclusivamente da POL-GID-L3 v1.0 ratificada, materializada no ADR-019 e registada no REPORT-017. Este protocolo não cria autoridade.

## 4. Hierarquia e subordinação

ADR-001 permanece regra geral de canonicidade. ADR-019 e POL-GID-L3 v1.0 são regra especial somente para matérias documentais ordinárias no escopo exacto. REPORT-017 regista a ratificação constitucional. Este protocolo e o modelo ACTO-GID-L3 são subordinados.

Não alteram ADR-001, ADR-019 ou a política; não reduzem matérias reservadas; não modificam critérios, estados, transições ou fail-closed; não autorizam operação nem interpretam conflito constitucional. Conflito ou ambiguidade bloqueiam.

## 5. Objectivo

Especificar, sem implementar, como uma missão documental ordinária futura poderá iniciar recolha, execução mecânica, produção de evidência, auditoria e eventual materialização de ACTO-GID-L3.

## 6. Escopo permitido

Somente matéria exclusivamente documental, reversível, inicialmente potencialmente ordinária, sem indicador reservado ou efeito operacional, sem criação de autoridade, dentro da POL-GID-L3 v1.0, com artefacto, versão, caminho, hash e baseline Git identificados e fail-closed activo.

Exemplos possíveis, sem autorização automática: correcção formal sem mudança semântica; reconciliação que reproduza decisão existente; inventário factual de fonte identificada; consolidação de hash com causa provada; versionamento documental de roadmap sem matéria reservada. Nenhum exemplo dispensa classificação, evidência, auditoria ou 24 critérios.

## 7. Escopo proibido

São proibidos matéria reservada, primeiro utilizador real externo, Go/No-Go, produção, deploy, pagamentos, abertura pública, expansão, alteração de política, autoridade, gates ou regra fiscal, normativa ou de negócio, migration, RBAC, código, testes, configuração, activação de agente ou LLM, escrita em base de dados, publicação, promoção canónica operacional, assinatura institucional, selecção criptográfica ou operação irreversível.

Ao detectar matéria proibida: interromper, preservar evidência, classificar como bloqueada ou revisão humana reservada e não produzir resultado aplicado.

## 8. Papéis institucionais

**Autoridade Constitucional Final**, actualmente Miguel: decide matérias reservadas e não participa por ocorrência em missões documentais ordinárias conformes.

**Auditor Arquitectural Independente**, actualmente GPT: audita, verifica, emite parecer e bloqueia; não executa, ratifica ou controla o acto.

**Executor técnico**, actualmente Codex: executa missão fechada e produz evidência; não audita institucionalmente, ratifica ou decide conflito.

**Materializador do ACTO-GID-L3:** função futura separada, sem interpretação, dispensa de critério ou autoridade própria.

Cada aplicação futura identifica `MATERIALIZADOR_FUNCAO`, `MATERIALIZADOR_ID`, `MATERIALIZADOR_EXECUCAO_ID` e `PROVA_SEPARACAO_MATERIALIZADOR`. O materializador não pode ser o Auditor Arquitectural Independente, produzir ou alterar o parecer, interpretar critérios, dispensar falhas ou alterar artefacto ou evidência congelados. Apenas executa a regra determinística final. A identidade não constitui assinatura institucional e nenhum fornecedor, modelo ou ferramenta fica permanentemente nomeado.

Cada execução identifica também `MATERIALIZADOR_CONTRATO_ID`, `MATERIALIZADOR_CONTRATO_VERSAO` e `MATERIALIZADOR_CONTRATO_HASH`. O contrato descreve exclusivamente a regra determinística, sem discricionariedade; não altera critérios, dispensa falha ou modifica política, protocolo, modelo, artefacto, evidência ou parecer. Contrato divergente ou não aprovado bloqueia. Nenhum contrato real é criado nesta missão.

## 9. Separação de funções

Nenhuma função isolada completa o processo. Executor, auditor, materializador e Autoridade Constitucional Final permanecem funções distintas. O parecer usa contexto separado e o materializador apenas aplica regra determinística.

A separação funcional do materializador exige evidência verificável. Ausência de prova bloqueia.

## 10. Condições para iniciar missão

Exigem-se cumulativamente POL-GID-L3 v1.0 vigente, protocolo aplicável e activo, escopo permitido, classificação inicial potencialmente ordinária, ausência inicial de indicador reservado, ausência de autorização operacional e fail-closed.

Iniciar não ratifica, não garante classificação, não dispensa critérios e não autoriza mutação Git ou operação.

## 11. Identidade da missão

Formato lógico proposto: `MISSAO-GID-L3-AAAA-MM-DD-NNN`, em que a data é declarativa e `NNN` é sequência de três dígitos. Cada identidade é única; reutilização é proibida e correcção exige nova missão. O identificador não é assinatura ou autoridade.

Nenhum identificador real é criado nesta especificação.

## 12. Conteúdo obrigatório da missão

Cada missão futura contém identificador, título, data declarativa, política, protocolo, missão, artefacto, manifesto de evidência, relatório do executor, parecer, materializador e registo externo, todos pelas identidades, versões e hashes aplicáveis; baseline Git; classificação inicial; prova inicial de ausência de matéria reservada; objectivo fechado; escopos exactos de leitura e escrita; ficheiros e comandos permitidos e proibidos; critérios de aborto; formato esperado; evidências; estados Git esperados e declaração de ausência de autorização operacional.

A cadeia mínima obrigatória é:

- `POLITICA_ID`, `POLITICA_VERSAO`, `POLITICA_HASH`;
- `PROTOCOLO_ID`, `PROTOCOLO_VERSAO`, `PROTOCOLO_HASH`;
- `MODELO_ACTO_ID`, `MODELO_ACTO_VERSAO`, `MODELO_ACTO_HASH`;
- `MISSAO_ID`, `MISSAO_HASH`;
- `ARTEFACTO_ID`, `ARTEFACTO_VERSAO`, `ARTEFACTO_CAMINHO`, `ARTEFACTO_HASH_INICIAL`, `ARTEFACTO_HASH_FINAL`;
- `EVIDENCIA_MANIFESTO_ID`, `EVIDENCIA_MANIFESTO_HASH`;
- `RELATORIO_EXECUTOR_ID`, `RELATORIO_EXECUTOR_HASH`;
- `PARECER_AUDITOR_ID`, `PARECER_AUDITOR_HASH`;
- `MATERIALIZADOR_FUNCAO`, `MATERIALIZADOR_ID`, `MATERIALIZADOR_EXECUCAO_ID`, `PROVA_SEPARACAO_MATERIALIZADOR`;
- `MATERIALIZADOR_CONTRATO_ID`, `MATERIALIZADOR_CONTRATO_VERSAO`, `MATERIALIZADOR_CONTRATO_HASH`;
- `SELAGEM_EXECUCAO_ID`, `PROVA_ATOMICIDADE_SELAGEM`;
- `REGISTO_HASH_EXTERNO_ACTO_ID`, `REGISTO_HASH_EXTERNO_ACTO_CAMINHO`, `HASH_FINAL_ACTO`.

`MODELO_ACTO_ID` identifica o modelo documental exacto aprovado; `MODELO_ACTO_VERSAO`, a versão exacta; `MODELO_ACTO_HASH`, os bytes exactos aprovados. Divergência, modelo não aprovado ou hash divergente impede acto válido. O modelo não cria autoridade e a sua aprovação documental não activa o protocolo.

## 13. Preflight

Antes de escrever, confirmar identidade, política, versão e hashes; baseline local e remota quando exigida; working tree e stage; caminhos permitidos; colisões; fontes; formato e condições de aborto. Divergência aborta antes da mutação.

## 14. Classificação inicial

A triagem apenas classifica como potencialmente ordinária. Não é conclusão final. Qualquer indicador reservado, conflito, ambiguidade ou falta de prova interrompe a via delegada.

## 15. Execução mecânica

O executor cumpre literalmente objectivo e escopo, sem decisão arquitectural, expansão oportunista ou interpretação constitucional. Somente mutações expressamente autorizadas pela missão são admissíveis.

As etapas procedimentais, que não criam ou substituem estados institucionais, são:

1. identificação;
2. preflight;
3. triagem inicial;
4. execução mecânica;
5. produção de evidência;
6. verificação de formato;
7. congelamento por hash;
8. auditoria independente;
9. avaliação dos 24 critérios;
10. materialização do ACTO-GID-L3;
11. resultado aplicado ou bloqueado;
12. preservação histórica.

## 16. Produção de evidência

A evidência inclui comandos autorizados, resultados relevantes, caminhos, versões, hashes, baseline, verificações de formato, divergências, bloqueios e estado Git, sem contaminar o artefacto.

O manifesto de evidência é futuro artefacto individual e imutável, contendo referências e hashes de todas as evidências consideradas. Não é criado nesta missão. Alteração da evidência invalida manifesto e parecer; nova execução exige novo manifesto e hash. Referência textual sem hash não satisfaz o congelamento.

## 17. Congelamento do artefacto e da evidência

Antes do parecer, artefacto e evidência finais são congelados, hashes calculados e baseline registada. O executor deixa de possuir autorização de escrita sobre o artefacto. Alteração posterior invalida o parecer e exige nova missão, hashes e parecer.

SHA-256 limita-se à integridade byte a byte; não prova autoria, assinatura, identidade ou timestamp confiável.

## 18. Auditoria independente

Exige contexto ou sessão separados da execução, artefacto e evidência congelados, ausência de escrita no repositório durante o parecer e correspondência exacta de caminhos, versões e hashes.

O parecer incide sobre artefacto final congelado, manifesto, relatório do executor, classificação, ausência de matéria reservada, hashes disponíveis e critérios materiais verificáveis antes da emissão. Não declara antecipadamente o critério 23 `CONFORME`, certifica acto inexistente, materializa acto, controla selagem ou substitui validação determinística final.

O materializador verifica existência, literalidade, identidade e hash do parecer para os critérios 16 e 17. Um parecer estruturalmente válido, identificável e correspondente é obrigatório para iniciar a selagem. Parecer FAVORÁVEL é obrigatório apenas para resultado APLICADO. Os pareceres de bloqueio admitidos na secção 21 podem produzir acto válido com resultado BLOQUEADO. A matriz integral só é validada durante a emissão atómica.

Parecer literal possível: `FAVORÁVEL`, `NÃO FAVORÁVEL`, `BLOQUEADO POR AUSÊNCIA DE EVIDÊNCIA`, `BLOQUEADO POR CONFLITO` ou `REVISÃO HUMANA RESERVADA`. Parecer favorável é condição, não ratificação.

## 19. Correspondência por hashes

Política, protocolo, missão, artefacto, relatório e parecer devem corresponder às identidades e hashes exactos. Divergência, reutilização ou causa não provada produzem bloqueio.

A correspondência abrange também manifesto de evidência, materializador, execução de materialização e registo externo do hash final.

## 20. Gate dos 24 critérios

Os critérios materiais preservados da POL-GID-L3 v1.0 são:

1. POL-GID-L3 identificada;
2. versão exacta 1.0;
3. hash da política verificado;
4. política constitucionalmente ratificada;
5. missão documental ordinária iniciada pela POL-GID-L3 v1.0 vigente e por protocolo institucional de missões aplicável, em escopo permitido, com classificação inicial potencialmente ordinária, ausência inicial de indicador reservado, ausência de autorização operacional e fail-closed;
6. artefacto e versão identificados;
7. caminho ou referência exacta;
8. hash do artefacto verificado;
9. baseline Git verificada;
10. matéria classificada como ordinária;
11. demonstração de ausência de matéria reservada;
12. ausência de conflito com ADR-001;
13. precedência normativa respeitada;
14. evidência integral e rastreável;
15. relatório de execução Codex identificado;
16. parecer literal favorável do Auditor Arquitectural Independente;
17. parecer correspondente ao artefacto e hash exactos;
18. independência entre executor e auditor controlada;
19. ausência de alteração da evidência após parecer;
20. ausência de alteração do artefacto após hashes;
21. divergências e bloqueios preservados;
22. estado e transição permitidos;
23. ACTO-GID-L3 individual completo e imutável;
24. ausência de autorização operacional.

Todos são cumulativos; nenhuma dispensa é permitida.

## 21. ACTO-GID-L3

A transacção pode iniciar somente depois de existir parecer identificável e de estar concluída a avaliação pré-emissão dos critérios 1 a 22 e 24. Não se exige conformidade integral antes da transacção.

- parecer `FAVORÁVEL`, com todos os critérios conformes, permite resultado possível `APLICADO`;
- parecer `NÃO FAVORÁVEL`, `BLOQUEADO POR AUSÊNCIA DE EVIDÊNCIA` ou `BLOQUEADO POR CONFLITO`, estruturalmente válido e correspondente, sem matéria reservada, produz ACTO-GID-L3 válido com resultado `BLOQUEADO`;
- parecer `REVISÃO HUMANA RESERVADA` interrompe a via delegada, não produz ACTO-GID-L3 válido e encaminha a matéria para `REVISÃO HUMANA RESERVADA`;
- parecer ausente, inválido ou sem correspondência impede ACTO-GID-L3 válido.

O materializador não decide nem interpreta. O critério 23 permanece pós-condição da emissão atómica. Matéria reservada permanece fora da aplicação delegada. O acto não substitui política ou parecer, altera artefacto ou cria autoridade.

A finalização possui duas fases procedimentais, sem criar estado institucional.

**Fase A — avaliação e preparação:**

1. avaliar individualmente os critérios 1 a 22 e 24;
2. preservar resultados, evidências e bloqueios;
3. preparar candidato de ACTO-GID-L3;
4. preencher identidades, hashes, matriz, divergências, estado anterior e transição pretendida;
5. não declarar `APLICADO`;
6. não alterar o estado do artefacto.

**Fase B — validação e selagem:** executa uma única operação lógica denominada `TRANSACCAO-DE-EMISSAO-ACTO-GID-L3`, identificada por `SELAGEM_EXECUCAO_ID` e demonstrada por `PROVA_ATOMICIDADE_SELAGEM`.

A transacção indivisível:

1. recebe todos os inputs congelados;
2. verifica política, protocolo, modelo e hashes;
3. verifica missão, artefacto, manifesto, relatório e parecer;
4. verifica materializador e contrato exactos;
5. avalia deterministicamente os critérios 1 a 22 e 24;
6. constrói em memória os bytes finais;
7. define `APLICADO` ou `BLOQUEADO`;
8. define estado resultante ou preserva estado anterior;
9. completa a matriz, incluindo o critério 23;
10. calcula o hash dos bytes finais;
11. constrói o registo externo;
12. publica acto e registo como um único conjunto reconhecido;
13. somente após sucesso integral reconhece o acto como válido.

O critério 23 é pós-condição da emissão atómica. Não pode ser definitivamente conforme num candidato isolado; a marcação final `CONFORME` só é reconhecida se toda a selagem terminar com sucesso. Antes disso, qualquer valor é candidato interno. Transacção falhada não produz acto válido nem altera estado.

Critério 23 `CONFORME` e todos os restantes `CONFORME` produzem acto final `APLICADO`. Critério 23 `CONFORME` com qualquer outro `NÃO CONFORME` ou `NÃO PROVADO` produz acto final `BLOQUEADO`. Critério 23 não conforme ou não provado impede emissão de acto válido; a tentativa fica no relatório como `BLOQUEADO POR ACTO INVÁLIDO`, sem mudar o artefacto. Este é resultado procedimental da tentativa, não estado institucional nem resultado de acto válido. Matéria reservada produz `REVISÃO HUMANA RESERVADA`. Todo bloqueio preserva evidência e estado anterior.

Nenhum acto válido existe antes do passo 13. Acto ou registo isolado, ficheiro temporário, candidato ou escrita parcial não é acto. Falha em qualquer passo invalida toda a emissão; nenhuma aplicação ou transição ocorre e tentativa e evidência ficam no relatório.

Falha técnica da operação produz `BLOQUEADO POR SELAGEM INCOMPLETA`: resultado procedimental, não estado institucional ou resultado de acto válido; não altera artefacto, não admite conversão retroactiva, exige nova missão e execução, preserva candidatos, evidência e erro conforme retenção futura e não autoriza repetição automática ilimitada.

`BLOQUEADO POR ACTO INVÁLIDO` permanece para falha estrutural anterior à publicação. Distingue-se de selagem tecnicamente incompleta e de acto válido cujo resultado determinístico seja `BLOQUEADO`.

O valor `HASH_FINAL_ACTO` nunca integra os bytes que representa. Primeiro congelam-se os bytes; depois calcula-se SHA-256 e regista-se externamente. O acto contém somente `REGISTO_HASH_EXTERNO_ACTO_ID`.

O registo externo individual e imutável contém `REGISTO_HASH_EXTERNO_ACTO_ID`, caminho do registo, `ID_ACTO`, caminho e hash final do acto, política, protocolo e modelo por IDs, versões e hashes, missão, manifesto, relatório e parecer por IDs e hashes, materializador, contrato e execução, `SELAGEM_EXECUCAO_ID`, baseline, data e resultado. Não é acto, parecer, autoridade, assinatura, timestamp confiável ou prova de autoria. A completude abrange acto congelado, registo externo, manifesto, relatório e parecer. Nenhum registo real é criado.

## 22. Resultados possíveis

Resultado do ACTO-GID-L3: `APLICADO` ou `BLOQUEADO`.

Quando aplicado, o estado exacto do artefacto é `RATIFICADO POR POL-GID-L3 v1.0 — CANÓNICO DOCUMENTAL NO SEU ESCOPO, SEM AUTORIZAÇÃO OPERACIONAL.`

Quando bloqueado, o estado anterior permanece inalterado, a evidência é preservada e nenhuma aplicação ocorre.

## 23. Estados institucionais preservados

Este protocolo não cria estados. Preserva os três planos, estados e transições definidos no ADR-019. As etapas procedimentais não são estados institucionais.

## 24. Fail-closed

Dúvida, conflito, ambiguidade, fonte ausente, hash divergente, evidência incompleta ou matéria potencialmente reservada bloqueiam. Nenhuma interpretação por GPT, Codex ou automação resolve conflito constitucional.

## 25. Matéria reservada

Matéria reservada interrompe imediatamente a aplicação delegada e segue para `REVISÃO HUMANA RESERVADA`, sem presumir decisão ou autorização.

## 26. Ausência de autorização operacional

Missão, evidência, parecer, acto e estado documental não autorizam código, produção, deploy, utilizadores, pagamentos, publicação, agentes, LLMs ou qualquer operação.

## 27. Git e mutações proibidas

Missão documental não autoriza automaticamente `git add`, commit, push, deploy, merge, rebase, reset, restore, stash ou tag. Cada acção exige bloco posterior separado e evidência própria.

São proibidos `git add .`, `git add -A`, `git add --all`, force push, amend não autorizado e alteração fora do escopo.

## 28. Imutabilidade histórica

Artefactos, evidências, pareceres e actos anteriores permanecem preservados. Nenhuma correcção pode reescrever retroactivamente história ou converter bloqueio em aplicação.

## 29. Correcções posteriores

Erro ou alteração posterior exige nova identidade de missão, novos hashes, nova execução, novo parecer e novo acto. A relação com a identidade anterior deve ser explícita.

## 30. Auditoria e rastreabilidade

Preservam-se identidades, versões, caminhos, hashes, baseline, classificação, critérios, evidências, relatório, parecer, divergências, estados, transição, resultado e ausência de autorização operacional.

## 31. Gate de activação do protocolo

Estado: **PENDENTE E BLOQUEADO.**

Exige cumulativamente parecer material favorável do Auditor Arquitectural Independente, decisão institucional sobre esta versão exacta, hash final, modelo ACTO-GID-L3 aprovado, independência operacionalizada, congelamento de evidência, validação por hashes, contrato de materialização, missão específica de activação e prova de ausência de autorização operacional.

Esta missão não satisfaz ou fecha o gate.

A ratificação documental do protocolo e modelo é MATÉRIA RESERVADA da AUTORIDADE CONSTITUCIONAL FINAL, actualmente Miguel. Exige versões e hashes exactos, parecer material favorável, declaração constitucional própria, ausência de defeito bloqueante e de autorização operacional.

Após essa decisão, o estado futuro do protocolo seria `RATIFICADO — VIGENTE DOCUMENTALMENTE — INACTIVO — NÃO IMPLEMENTADO`; o modelo seria `APROVADO DOCUMENTALMENTE — NÃO EXECUTÁVEL — NENHUM ACTO REAL CRIADO`. Ratificação não activa, implementa, cria missão ou acto, nem autoriza operação.

A primeira activação técnica também é MATÉRIA RESERVADA da Autoridade Constitucional Final. Exige ratificação documental, implementação, testes, independência, congelamento, manifesto, materializador, registo externo, auditoria técnica, missão específica e Go/No-Go próprio. O estado actual permanece pendente e bloqueado.

Exige ainda modelo exacto por ID, versão e hash, contrato exacto do materializador, implementação comprovada da transacção atómica, prova de que escritas parciais não produzem acto válido e testes de falha em cada etapa da selagem.

## 32. Não decide

Este protocolo não é ratificado ou activo, não implementa processo, avaliador ou automação, não cria acto real, não aplica política, não altera estado, não fecha gate e não autoriza operação.

## 33. Classificação final

**PROTOCOLO DOCUMENTAL SUBORDINADO, PROPOSTO, INACTIVO, NÃO IMPLEMENTADO E APTO SOMENTE PARA AUDITORIA MATERIAL FUTURA.**

Sem parecer favorável, ratificação, activação, implementação ou autorização.
