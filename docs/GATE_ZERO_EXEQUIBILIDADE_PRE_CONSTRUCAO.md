# Gate Zero — Prova de exequibilidade antes de construir ou ratificar

**Âmbito:** todos os projetos, produtos, verticais, motores, agentes, políticas e integrações governadas da SOLVERIS, segundo risco e criticidade.

**Natureza:** diretriz operacional preventiva proposta para adoção no fluxo de governação. Este texto não é ato de ratificação institucional, autorização de instalação, abertura de base, assinatura ou deploy.

**Regra central:** **não basta provar que o sistema rejeita o inválido; é preciso provar, antes de congelar a política, que existe um caminho legítimo demonstrável para aceitar o válido**.

## 1. Incidente que motivou o controlo — B02 G5 V8 / R5

Em 7 de novembro de 2026, a auditoria física do clone isolado B02 apresentou: PostgreSQL 17.10 e revisão Alembic 0065, política V8 ativa e sucessão 0066 instalada; hashes e contratos documentais coerentes, mas **zero** unidades R5 persistidas. Ambos os manifestos imutáveis de sanitização da V8 careciam de `independence_evidence_binding.hash` válido, embora a guarda de verificação o exigisse e o modo legado pedisse igualdade exata com o manifesto da política. A cadeia G5 mostrava quatro atos, mas a mesma pessoa nos papéis de proponente, auditor e ratificador, sem prova de segregação pessoal efetiva.

**Falha causal:** corrigiram-se versões sucessivas por resposta ao primeiro veto de cada tentativa, sem demonstrar previamente que *todos* os predicados da política, os requisitos de evidência e a cadeia de autoridade eram conjuntamente satisfazíveis. Testes de partes foram confundidos com exequibilidade do fluxo real. O sistema tinha guardas rigorosas, mas permitia preparar políticas cujo conteúdo não podia satisfazê-las.

A observação sobre o clone não é autorização para alterar a V8 histórica, a sucessão 0066 ou o alcance nacional do produto; os dois PDFs SEFA/PR são um caso documental do B02, não a fronteira comercial da SOLVERIS Enterprise.

## 2. O Gate Zero antecede qualquer política e implementação governada

Sequência recomendada:

`Problema e resultado observável → inventário de autoridade e contratos → matriz de exequibilidade → prova de satisfazibilidade e dependências → revisão segregada → ratificação competente → implementação → testes de integração e negativos → commit/deploy controlados → readback → handoff`.

O Gate Zero não substitui a auditoria, os testes nem a ratificação: impede que se entre nessas fases com pré-condições impossíveis, dados presumidos ou provas fictícias.

### A. Fixar o alvo correto (sem misturar gerações)

Registar repositório/branch/commit, ambiente, identificação da BD, revisão de migração, funções/triggers **efetivamente instalados**, política candidata, ativações e intervalos. Distinguir em colunas separadas `código histórico`, `candidato` e `runtime instalado`. Havendo divergência, a implementação não pode presumir que o Git descreve o runtime.

### B. Inventariar TODOS os requisitos antes de corrigir um

Extrair contratos de código e base instalada, incluindo funções auxiliares chamadas pelas guardas, constraint triggers, validação de assinatura, identidade de role, permissões, estados, janelas temporais, predecessores, versões, hashing/canonicidade, bytes físicos, reserva única e COMMIT. Inspecionar todos os ramos aplicáveis, incluindo ambos os documentos/unidades e caminhos de erro.

Para cada requisito, registar:

| Campo obrigatório | Pergunta |
| --- | --- |
| `predicado` | Qual é a condição exata e onde está definida (ficheiro/linha ou função/hash instalada)? |
| `valor_origem` | Política imutável, BD, documento físico, ato de autoridade ou dado produzido em transação? |
| `fase` | Existe antes da política, antes da transação, durante a transação ou só depois do COMMIT? |
| `responsável` | Quem pode atestar/produzir esta prova? Há segregação real comprovada? |
| `evidência` | Identificador e hash verificável, mecanismo de leitura independente e custódia? |
| `resultado` | PASS, FAIL comprovado, BLOQUEADO por pré-condição, ou NÃO VERIFICADO? |
| `conflito` | Dependência temporal, circularidade, privilégio incompatível ou exigência contraditória? |

Nunca transformar `NÃO VERIFICADO` em `PASS` por inferência. Teste sintético deve manter a etiqueta sintética e não autentica o mundo real.

### C. Verificar satisfazibilidade, não apenas validade de campos

Verificar simultaneamente:
- se os mesmos bytes podem satisfazer *todas* as guardas que lhes são aplicáveis;
- se campos congelados pela política são independentes de `txid`, recibos, hashes e inspeções produzidos depois; se não forem, o contrato deve ser redesenhado **antes** de qualquer nova versão;
- se a prova prévia é identificável e verificável no sistema correto, incluindo vínculos não vazios;
- se existe uma autoridade habilitada para cada assinatura e uma revisão efetivamente segregada (duas IAs ou dois papéis não bastam);
- se os requisitos de tempo, unicidade, migrações, ACL, reserva e leitura independente podem coexistir.

Criar uma **prova de exequibilidade** do caminho completo em clone descartável, com `ROLLBACK` e controles negativos proporcionais ao risco, sem contornar triggers, sem mudar fixtures aprovadas e sem executar COMMIT protegido. Se uma prova real depender de pessoa, chave ou ato ainda não disponível, a demonstração permanece `BLOQUEADA` e a dependência deve ser exposta.

### D. Critério para autorização de construir ou propor uma política

Entregável obrigatório: matriz completa, grafo de dependências (incluindo ciclo), evidência de testes de integração pertinentes, atos e segregação, diff proposto, riscos residuais, condição de rollback e resultado `GATE_ZERO_PASS` ou `GATE_ZERO_STOP`.

`PASS` só quando os predicados verificáveis estão satisfeitos em conjunto, o caminho completo foi demonstrado no âmbito adequado e as dependências institucionais foram resolvidas de modo legítimo. A ratificação humana continua separada. `STOP` quando houver contradição, prova inventada, independência fictícia, ausência de autoridade, divergência runtime/candidato ou lacuna de teste relevante.

## 3. Regra de contenção — acabar com a cascata de versões

1. **Não gerar versão sucessora para descobrir o próximo erro.** Levantar numa única passagem as incompatibilidades identificáveis por leitura e análise estática, e distinguir as verificáveis somente em runtime.
2. **Não alterar uma política histórica ou um contrato aceite** para conseguir GREEN. Qualquer sucessão exige base jurídica/técnica própria, prova de compatibilidade integral e autorização distinta.
3. **Não transformar testes de mecanismo em prova real.** Um `PASS_DIAGNOSTIC_POSITIVE` sintético demonstra apenas o que o seu ensaio efetivamente cobriu.
4. **Não inferir independência por multiplicidade de chats/IA.** Exigir ato próprio, ausência de conflitos, evidência de elegibilidade e separação efetiva.
5. **Nunca fechar por contagem de commits, testes ou versões.** Fechar apenas pelo resultado operacional acordado, com recibos físicos, COMMIT autorizado e leitura independente, quando aplicáveis.

## 4. Aplicação ao B02 atual e novos projetos

- **B02:** preservar V8, cadeia 0066 e G4 já demonstrados. Os bloqueios observados são o manifesto da prova de independência e a segregação institucional não demonstrada. Não criar V9 até um Gate Zero específico cobrir o contrato realmente instalado e as fontes de prova; não confundir reconhecimento de um defeito com prova de que é o único.
- **Outras verticais SOLVERIS:** aplicar o mesmo princípio *antes de iniciar a construção*: estabelecer o que significa funcionar, onde a evidência virá, quem poderá legitimamente autorizar, como verificar aceitação e quais contradições tornariam o projeto inexequível. A profundidade do Gate Zero é proporcional ao risco.
- **Integração futura:** acrescentar gates automatizados que rejeitem políticas incompatíveis com o schema e as guardas atuais, mas não fingir que um teste automatizado substitui prova humana de independência ou atos de autoridade.

**Autoridade:** documentação não é ratificação; execução protegida permanece fail-closed. A instrução de registo no Git não autoriza alterar migrações instaladas, dados de produção ou cadeias imutáveis.
