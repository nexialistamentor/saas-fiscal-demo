# B13-02 — Bateria de Testes de Utilizador Leigo

**Versão:** 1.0  
**Data:** 2026-06-26  
**Plataforma:** Fisco Soberano (https://www.fiscosoberano.com.br / https://saas-fiscal-demo.vercel.app)  
**Executor:** Miguel (Piloto 0) + execução automatizada Cursor (2026-06-26)  
**URL usada na execução:** `https://saas-fiscal-demo.vercel.app` + API `https://saas-fiscal-demo-production.up.railway.app`  
**DNS `www.fiscosoberano.com.br`:** ainda não resolve (2026-06-26) — T8 mobile pendente reteste no domínio final  
**Objectivo:** Simular uma pessoa comum que nunca viu a plataforma, sem conhecer CNPJ, CNAE, regime tributário, XML ou contador.

---

## Princípio de avaliação

A plataforma deve ser compreensível e utilizável por alguém que:

- Nunca ouviu falar de CNAE, regime tributário ou Simples Nacional
- Não tem CNPJ ainda
- Não sabe se precisa de contador
- Usa o telemóvel como dispositivo principal
- Esperaria uma experiência semelhante a uma app do governo digital

---

## Tabela de resultados

| Teste | Cenário | Resultado | Problema encontrado | Prioridade |
|-------|---------|-----------|---------------------|------------|
| T1 | Entrada básica | ⬜ Passa / ✅ Falha | Ecrã inicial é só Login — sem explicação do propósito da plataforma em 5 s | P1 |
| T2 | Criar conta | ⬜ Passa / ✅ Falha | Registo CPF funciona; tipo default MEI expõe CNPJ; erros 422 da API são técnicos; termos só após login | P1 |
| T3 | Sem CNPJ | ✅ Passa / ⬜ Falha | Conta CPF sem documento acede ao dashboard; card simulação diz explicitamente que CNPJ não é obrigatório | — |
| T4 | Simular abertura | ⬜ Passa / ✅ Falha | CNAE errado para software (ex.: 5811-5/00 ou 6110-8/01 vs 6201-5/01 esperado); regime devolvido como sigla `lp` sem explicação | P0 |
| T5 | CNAE para leigo | ⬜ Passa / ✅ Falha | Mostra código + descrição, mas descrição incorrecta; sem tooltip/explicação do que é CNAE | P1 |
| T6 | Erros controlados | ⬜ Passa / ✅ Falha | T6a/T6b OK; T6c expõe validação técnica (`greater than 0`); T6d MEI + R$ 500k não alerta limite MEI | P0 |
| T7a | Assistente — contador | ⬜ Passa / ✅ Falha | **Sem UI de assistente no dashboard**; API responde linguagem soberana (contador não universal) | P1 |
| T7b | Assistente — MEI | ⬜ Passa / ✅ Falha | Sem UI; API devolve checklist de abertura MEI em vez de “depende da actividade/faturamento” | P1 |
| T7c | Assistente — CNPJ | ⬜ Passa / ✅ Falha | Sem UI; API orienta Portal do Empreendedor (MEI) — parcialmente correcto | P1 |
| T7d | Assistente — CNAE | ⬜ Passa / ✅ Falha | Sem UI; API responde mensagem genérica — não explica o que é CNAE | P1 |
| T8 | Mobile | ⬜ Passa / ⬜ Falha / ⏳ Pendente | DNS do domínio final inactivo; teste físico em telemóvel não executado nesta sessão | P1 |

**Prioridade:** P0 = bloqueia piloto | P1 = corrigir antes de abertura ampla | P2 = melhoria futura

---

## T1 — Entrada básica na plataforma

**Perfil simulado:** pessoa comum, primeira visita, sem contexto técnico.

**Passos:**

1. Abrir https://www.fiscosoberano.com.br (ou URL actual)
2. Observar o ecrã inicial sem qualquer ajuda

**Perguntas a responder:**

- [ ] Em 5 segundos percebo o que esta plataforma faz?
- [ ] Existe chamada à acção clara ("Criar conta", "Entrar", "Começar")?
- [ ] O design transmite confiança para uma plataforma fiscal?
- [ ] Existe explicação do que a plataforma oferece antes de pedir dados?

**Critério de aprovação:** utilizador leigo percebe o propósito e sabe onde clicar sem ajuda.

---

## T2 — Criar conta

**Perfil simulado:** pessoa quer experimentar a plataforma.

**Passos:**

1. Clicar em "Criar conta" ou equivalente
2. Preencher dados mínimos
3. Tentar avançar com campo em falta
4. Completar o registo

**Perguntas a responder:**

- [ ] O formulário é simples e claro?
- [ ] Os labels explicam o que é pedido (ex: "CPF" sem explicação vs "CPF (documento fiscal brasileiro)")?
- [ ] O erro por campo em falta é claro ou técnico (ex: "422 Unprocessable Entity")?
- [ ] Após o registo, fica claro o que fazer a seguir?
- [ ] Os termos aparecem de forma compreensível?

**Critério de aprovação:** utilizador consegue criar conta sem ajuda externa e entende os erros se errar.

---

## T3 — Utilizador sem CNPJ

**Perfil simulado:** pessoa que quer abrir empresa mas ainda não tem CNPJ.

**Passos:**

1. Criar conta sem fornecer CNPJ
2. Tentar aceder ao dashboard
3. Tentar usar o card de simulação de abertura

**Perguntas a responder:**

- [ ] O sistema permite avançar sem CNPJ?
- [ ] Existe mensagem clara explicando que CNPJ não é obrigatório para simular?
- [ ] O utilizador não fica bloqueado ou confuso?
- [ ] A plataforma orienta o próximo passo ("simula primeiro, depois abre empresa")?

**Critério de aprovação:** utilizador sem CNPJ consegue usar a plataforma e entende que pode simular antes de ter CNPJ.

---

## T4 — Simular abertura de empresa

**Perfil simulado:** pessoa que quer abrir empresa de tecnologia/software.

**Passos:**

1. Localizar o card "Simular abertura de empresa" no dashboard
2. Preencher com linguagem natural:
   - Descrição: *"quero abrir uma plataforma de software para ajudar empresas com impostos"*
   - Actividade: Serviços
   - Porte: ME
   - Faturamento: 120000
3. Clicar "Simular abertura"
4. Ler o resultado

**Perguntas a responder:**

- [ ] O card é fácil de encontrar no dashboard?
- [ ] Os campos são autoexplicativos?
- [ ] O resultado aparece em linguagem compreensível?
- [ ] O resultado diz claramente se pode ou não ser MEI e porquê?
- [ ] O regime recomendado é explicado ou é só uma sigla?
- [ ] O resultado menciona contador como obrigatório universal? (deve ser NÃO)

**Resultado esperado:**

```
CNAE: 6201-5/01 ou similar (desenvolvimento de software)
Permite MEI: Não (actividade/porte/faturamento excede limite)
Regime recomendado: Simples Nacional
Justificativa: compreensível para não especialista
```

**Critério de aprovação:** utilizador leigo percebe o resultado e sabe o próximo passo sem precisar de contador.

---

## T5 — CNAE para leigo

**Perfil simulado:** pessoa que nunca ouviu falar de CNAE.

**Passos:**

1. Após a simulação, observar o resultado do CNAE
2. Verificar se existe explicação do que é CNAE

**Perguntas a responder:**

- [ ] O resultado mostra só o código (ex: "6201-5/01") ou também a descrição?
- [ ] Existe alguma explicação do que significa CNAE?
- [ ] O utilizador percebe porque aquele CNAE foi sugerido?

**Resultado actual esperado:** o resultado mostra `codigo` e `descricao` — verificar se a descrição é legível.

**Critério de aprovação:** utilizador percebe o CNAE sugerido sem precisar pesquisar noutra fonte.  
**Se falhar → P1:** adicionar tooltip ou explicação mínima de CNAE no card de resultado.

---

## T6 — Erros controlados

**Perfil simulado:** utilizador que comete erros comuns.

**Sub-cenários:**

### T6a — Campo de descrição vazio

- Clicar "Simular abertura" sem preencher descrição
- Esperado: botão desactivado ou mensagem clara, não erro técnico

### T6b — Descrição demasiado vaga

- Descrição: *"quero vender coisas"*
- Esperado: sistema tenta recomendar CNAE; se não conseguir, mensagem clara

### T6c — Faturamento inválido ou zero

- Faturamento: 0 ou texto em vez de número
- Esperado: campo numérico não aceita texto; zero pode gerar alerta

### T6d — Actividade incompatível com porte

- Porte: MEI + faturamento 500000
- Esperado: sistema indica que faturamento excede limite MEI

**Critério de aprovação:** nenhum erro técnico visível ao utilizador em nenhum sub-cenário.

---

## T7 — Assistente fiscal

**Perfil simulado:** utilizador com dúvidas comuns, usando linguagem natural.

**Localizar o assistente** no dashboard (campo de pergunta).

### T7a — Pergunta: "preciso de contador para abrir empresa?"

**Resposta esperada:**

- Para MEI: não é obrigatório
- Para ME/EPP: pode ser recomendado; obrigatório apenas quando regime, actividade ou escrituração exigir
- Não deve dizer "sim, obrigatório" como regra universal

**Critério:** resposta soberana, não dependência universal de contador.

### T7b — Pergunta: "posso ser MEI?"

**Resposta esperada:**

- Depende da actividade, faturamento e condições
- Plataforma pode ajudar a verificar
- Não deve dizer só "sim" ou "não" sem contexto

### T7c — Pergunta: "como abrir CNPJ?"

**Resposta esperada:**

- Orientação clara sobre Portal do Empreendedor (MEI) ou REDESIM
- Plataforma conduz o que puder automaticamente
- Sem contador como etapa universal

### T7d — Pergunta: "o que é CNAE?"

**Resposta esperada:**

- Explicação simples: classificação da actividade económica
- Exemplo concreto
- Não deve devolver só definição técnica

**Critério de aprovação T7:** respostas compreensíveis, soberanas e sem contador como dependência universal.

---

## T8 — Teste mobile

**Dispositivo:** telemóvel (Android/iOS, browser nativo)

**URL:** https://www.fiscosoberano.com.br (quando activo) ou URL actual

**Passos:**

1. Abrir a plataforma no telemóvel
2. Fazer login
3. Localizar o card de simulação
4. Preencher e submeter
5. Ler o resultado

**Perguntas a responder:**

- [ ] O ecrã de login é legível e fácil de usar?
- [ ] O dashboard não fica cortado em ecrã pequeno?
- [ ] O card "Simular abertura" aparece e é acessível?
- [ ] Os campos de input têm tamanho adequado para toque?
- [ ] O resultado é legível sem scroll horizontal?
- [ ] O botão "Simular abertura" é fácil de carregar?

**Critério de aprovação:** utilizador consegue completar o fluxo completo no telemóvel sem frustração.

---

## Critérios globais de aprovação do Piloto 0

| Condição | Obrigatório? |
|----------|-------------|
| Utilizador cria conta sem ajuda | P0 |
| Utilizador sem CNPJ não fica bloqueado | P0 |
| Simulação de abertura funciona e retorna resultado | P0 |
| Resultado não menciona contador como obrigatório universal | P0 |
| Nenhum erro técnico visível ao utilizador | P0 |
| CNAE explicado com descrição legível | P1 |
| Assistente responde com linguagem soberana | P1 |
| Experiência mobile funcional | P1 |
| Explicação de CNAE para leigo no resultado | P2 |

---

## Registo de problemas encontrados

| ID | Teste | Descrição do problema | Prioridade | Estado |
|----|-------|-----------------------|------------|--------|
| B13-P0-01 | T4 | Motor CNAE recomenda códigos incorrectos para actividade de software/SaaS (ex.: 5811-5/00, 6110-8/01 em vez de 6201-5/01) | P0 | Aberto |
| B13-P0-02 | T6d | Simulação MEI com faturamento R$ 500.000 devolve `permite_mei: true` sem alerta de limite | P0 | Aberto |
| B13-P0-03 | T6c | Faturamento zero/inválido expõe mensagem técnica Pydantic ao utilizador (`Input should be greater than 0`) | P0 | Aberto |
| B13-P1-01 | T1 | Landing page sem hero/explicação — utilizador leigo não percebe o propósito antes do login | P1 | Aberto |
| B13-P1-02 | T2 | Formulário de registo default MEI sugere CNPJ obrigatório; erros de validação pouco amigáveis | P1 | Aberto |
| B13-P1-03 | T4/T5 | Regime recomendado aparece como sigla (`lp`, `simples`) sem tradução para leigo | P1 | Aberto |
| B13-P1-04 | T5 | Falta explicação mínima de CNAE no card de resultado (tooltip ou texto) | P1 | Aberto |
| B13-P1-05 | T7 | Assistente fiscal existe na API (`POST /perguntar`) mas **não há campo de pergunta no frontend** | P1 | Aberto |
| B13-P1-06 | T7b/T7d | Intenções “posso ser MEI?” e “o que é CNAE?” não têm respostas dedicadas — fallback genérico ou checklist errado | P1 | Aberto |
| B13-P1-07 | T8 | Teste mobile pendente — aguardar DNS `www.fiscosoberano.com.br` e validação em dispositivo real | P1 | Pendente |
| B13-P2-01 | T7c | Resposta “como abrir CNPJ?” não distingue claramente MEI vs ME/EPP (REDESIM) | P2 | Aberto |

---

## Próximo passo após execução

1. ~~Preencher a tabela de resultados~~ ✅ (2026-06-26 — URL fallback Vercel/Railway)
2. ~~Registar problemas com prioridade P0/P1/P2~~ ✅
3. Correcções P0 → antes de abertura a outros utilizadores (**3 bloqueadores abertos**)
4. Criar `docs/PILOTO_0_FEEDBACK.md` com síntese
5. Retestar T8 quando `www.fiscosoberano.com.br` estiver activo
6. Fechar Bloco 13 formalmente após correcções P0 e reteste T8

### Síntese Piloto 0 (pré-feedback formal)

| Critério global P0 | Estado |
|--------------------|--------|
| Criar conta sem ajuda | ⚠️ Parcial (funciona, UX confusa) |
| Sem CNPJ não bloqueado | ✅ |
| Simulação retorna resultado | ⚠️ Retorna, mas CNAE/regime incorrectos para caso software |
| Sem contador universal | ✅ |
| Sem erro técnico visível | ❌ T6c |

---

## Anexo L3 — Preparação para Plataforma Soberana Autónoma

> Este anexo não bloqueia o Piloto 0. Serve como camada futura de maturidade para garantir que a plataforma evolui de uma interface funcional para um sistema soberano, auditável, explicável e operacionalmente confiável.

### Objectivo L3

Validar se a plataforma consegue conduzir um utilizador leigo com mínima intervenção humana, mantendo: autonomia operacional, linguagem compreensível, decisões justificadas, rastreabilidade, respeito aos limites legais, contador apenas como gate condicionado, e preparação para agentes especializados.

### Princípios L3

1. Fazer automaticamente tudo o que puder ser feito com regras públicas, dados oficiais e fluxos governamentais
2. Não depender do fundador para explicar o fluxo
3. Não depender de contador para etapas em que a lei não exige contador
4. Não esconder incerteza: quando não souber, deve dizer o que falta
5. Não devolver decisão fiscal sem evidência
6. Não usar linguagem técnica sem tradução para o utilizador comum
7. Registar por que uma recomendação foi feita

### T9 — Explicabilidade da recomendação

- [ ] O sistema explica por que sugeriu aquele CNAE?
- [ ] O sistema explica por que indicou ou rejeitou MEI?
- [ ] O sistema explica por que sugeriu determinado regime?
- [ ] O utilizador entende o próximo passo?
- [ ] A explicação separa recomendação automática de decisão oficial?

**Critério L3:** nenhuma recomendação relevante pode aparecer sem justificativa compreensível.

### T10 — Rastreabilidade da decisão

| Campo | Presente? |
|-------|-----------|
| Descrição informada pelo utilizador | ⬜ |
| CNAE sugerido + justificativa | ⬜ |
| Regime recomendado + motivo | ⬜ |
| Motivo de exclusão de regimes | ⬜ |
| Data/hora da simulação | ⬜ |
| Versão do motor | ⬜ |
| Intervenção de agente/LLM | ⬜ |

**Critério L3:** cada simulação relevante deve poder gerar um registo auditável.

### T11 — Autonomia sem fundador

- [ ] O utilizador entende o que fazer primeiro?
- [ ] O utilizador entende o resultado?
- [ ] O utilizador sabe o próximo passo?
- [ ] O utilizador não precisa chamar suporte para interpretar CNAE/regime?
- [ ] O utilizador não fica dependente de explicação externa?

**Critério L3:** a plataforma deve orientar sozinha o utilizador comum até uma próxima acção clara.

### T12 — Contador como gate condicionado

| Frase | Resposta soberana? |
|-------|--------------------|
| "preciso de contador?" | ⬜ |
| "sou MEI, preciso de contador?" | ⬜ |
| "quero abrir ME" | ⬜ |
| "quero emitir nota" | ⬜ |
| "vou ter funcionário" | ⬜ |
| "vou prestar serviço digital" | ⬜ |

**Critério L3:** nunca transformar contador em etapa padrão para todos os casos.

### T13 — Linguagem para leigo

| Termo | Explicação presente? |
|-------|---------------------|
| CNAE | ⬜ |
| CNPJ | ⬜ |
| MEI / ME / EPP | ⬜ |
| Simples Nacional | ⬜ |
| Regime tributário | ⬜ |
| DAS | ⬜ |
| Inscrição estadual/municipal | ⬜ |
| Obrigação acessória | ⬜ |

**Critério L3:** qualquer termo técnico exibido ao utilizador deve ter explicação curta ou contexto.

### T14 — Métrica de fricção

| Métrica | Valor |
|---------|-------|
| Tempo até criar conta | |
| Tempo até encontrar simulação | |
| Tempo até concluir simulação | |
| Número de dúvidas durante o fluxo | |
| Número de erros visíveis | |
| Vezes que precisou de ajuda externa | |
| Dispositivo usado | |
| Browser usado | |

**Critério L3:** reduzir progressivamente tempo, dúvidas e necessidade de suporte.

### T15 — Preparação para agentes

| Campo | Disponível? |
|-------|------------|
| Actividade descrita pelo utilizador | ⬜ |
| Intenção do utilizador | ⬜ |
| Porte pretendido | ⬜ |
| Faturamento estimado | ⬜ |
| Resultado CNAE | ⬜ |
| Resultado regime | ⬜ |
| Motivo de não MEI | ⬜ |
| Próximos passos sugeridos | ⬜ |

**Critério L3:** agente só pode actuar sobre evidência estruturada — não deve inventar dados ausentes.

### T16 — Erro honesto

**Resposta esperada:** dizer o que entendeu, o que não conseguiu determinar, que informação falta, e qual o próximo passo seguro. Nunca inventar CNAE/regime, nunca devolver erro técnico cru.

**Critério L3:** incerteza deve ser explícita e útil.

### Critérios L3 de maturidade

| Critério | Estado |
|----------|--------|
| Simulação explicável | ⬜ |
| Resultado auditável | ⬜ |
| Contador condicionado | ⬜ |
| Linguagem leiga | ⬜ |
| Métricas de fricção registadas | ⬜ |
| Agentes só com evidência estruturada | ⬜ |
| Erros honestos e compreensíveis | ⬜ |
| Fluxo utilizável sem fundador | ⬜ |

> **Nota:** O Piloto 0 fecha B13 com critérios P0. O Anexo L3 não bloqueia B13 — orienta a evolução futura para autonomia, soberania operacional, explicabilidade e agentes confiáveis.
