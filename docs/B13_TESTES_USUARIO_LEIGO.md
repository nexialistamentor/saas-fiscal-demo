# B13-02 — Bateria de Testes de Utilizador Leigo

**Versão:** 1.0  
**Data:** 2026-06-26  
**Plataforma:** Fisco Soberano (https://www.fiscosoberano.com.br / https://saas-fiscal-demo.vercel.app)  
**Executor:** Miguel (Piloto 0)  
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
| T1 | Entrada básica | ⬜ Passa / ⬜ Falha | | |
| T2 | Criar conta | ⬜ Passa / ⬜ Falha | | |
| T3 | Sem CNPJ | ⬜ Passa / ⬜ Falha | | |
| T4 | Simular abertura | ⬜ Passa / ⬜ Falha | | |
| T5 | CNAE para leigo | ⬜ Passa / ⬜ Falha | | |
| T6 | Erros controlados | ⬜ Passa / ⬜ Falha | | |
| T7a | Assistente — contador | ⬜ Passa / ⬜ Falha | | |
| T7b | Assistente — MEI | ⬜ Passa / ⬜ Falha | | |
| T7c | Assistente — CNPJ | ⬜ Passa / ⬜ Falha | | |
| T7d | Assistente — CNAE | ⬜ Passa / ⬜ Falha | | |
| T8 | Mobile | ⬜ Passa / ⬜ Falha | | |

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
| | | | | |

---

## Próximo passo após execução

1. Preencher a tabela de resultados
2. Registar problemas com prioridade P0/P1/P2
3. Correcções P0 → antes de abertura a outros utilizadores
4. Criar `docs/PILOTO_0_FEEDBACK.md` com síntese
5. Fechar Bloco 13 formalmente
