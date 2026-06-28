# L3_READY_PRINCIPIOS_ABERTURA_EMPRESA.md

**Versão:** 1.0
**Data:** 2026-06-26
**Contexto:** Plataforma Tributária Fisco Soberano — Bloco 13 Piloto

---

## Propósito

Este documento não descreve o que será construído agora.
Descreve os princípios que garantem que o que é construído agora pode evoluir para L3 sem refactor estrutural pesado.

B13 continua focado no Piloto 0. Este documento é arquitectura preventiva.

---

## Princípios L3-Ready

### 1. Não mexer no Cartório Digital Soberano L2 agora
O Cartório existe e opera. A sua integração com a abertura de empresa é futura.
O Cartório pode registar dossiês e intenções — mas não substitui gov.br.

### 2. Não implementar REDESIM/gov.br agora
A submissão oficial de abertura de empresa passa sempre pelo cidadão com o seu login gov.br.
A plataforma prepara, orienta e acompanha — não substitui o acto oficial.

### 3. Não implementar agentes L3 agora
Agentes só entram quando existir evidência estruturada real do piloto.
Sem dados reais, agente é simulação — não inteligência soberana.

### 4. Toda simulação deve poder evoluir para dossiê auditável
O resultado actual de simulação (CNAE + regime) é a semente do dossiê.
Campos futuros do DossieAbertura:

id, user_id, descricao_actividade

cnae_sugerido, regime_sugerido, porte

faturamento_estimado, folha_estimada

requer_contador (enum — ver Princípio 6)

canal_oficial (redesim | portal_mei | outro)

status (simulado | dossie_gerado | submetido | protocolo | activo)

protocolo_externo

versao_motor

created_at, updated_at

Não criar migration agora. Registar o modelo mental.

### 5. Toda recomendação deve ter evidência, justificativa e versão do motor
O resultado de simulação já tem `justificativa_cnae` e `justificativa_regime`.
Futuramente deve incluir:

```json
{
  "tipo_resultado": "recomendacao_preliminar",
  "fonte": "motor_cnae_regime",
  "versao_motor": "B13-P0",
  "decisao_oficial": false,
  "evidencia": "descricao_actividade + porte + faturamento"
}
```

### 6. Contador é gate condicionado — nunca dependência universal
Estados possíveis do contador no fluxo:

nao_necessario         → MEI, CPF sem obrigação específica

opcional               → recomendável mas não obrigatório

recomendado            → risco médio ou regime complexo

obrigatorio_por_regra  → lei/LC exige responsabilidade técnica

obrigatorio_por_risco  → actividade regulada ou risco fiscal alto

escolhido_pelo_utilizador → utilizador opta por contratar contador

Nunca usar "contador obrigatório" como regra universal.

### 7. Gov.br/REDESIM/Receita Federal não são substituídos
A plataforma é soberana nos seus domínios.
Os órgãos oficiais são soberanos nos seus.
A plataforma conduz o utilizador — não substitui o Estado.

### 8. Agentes futuros não terão autoridade fiscal canónica
Agent Entrevistador → recolhe dados
Agent CNAE → sugere candidatos
Agent Regime → explica cenários
Agent Dossiê → organiza documentos
Motor determinístico → valida regras
Auditoria → regista evidência
Utilizador/Estado/Contador → actos oficiais quando aplicável

Agente não decide. Agente alimenta.

### 9. A plataforma deve guardar estado futuro do processo
Cada simulação deve poder evoluir para:

Simulação

→ Dossiê gerado

→ Canal oficial identificado

→ Utilizador conduzido

→ Protocolo externo registado

→ CNPJ consultado via API

→ Empresa activada na plataforma

O `proximo_passo` deve ser explícito em cada resposta relevante.

### 10. B13 continua focado em Piloto 0
Nada neste documento bloqueia o Piloto 0.
Este documento existe para que o Piloto 0 não crie dívida arquitectural.

---

## Sequência de evolução (referência)

B13 → Piloto controlado (actual)

B14 → Matriz autonomia + Wizard abertura

B15 → REDESIM/Portal + API CNPJ + acompanhamento protocolo

B16 → LLMRouter/Agentes com evidência real do piloto

---

## O que NÃO fazer antes de B15

- Prometer abertura automática de CNPJ
- Substituir login gov.br do utilizador
- Activar agentes sem dados reais do piloto
- Tornar contador obrigatório para qualquer fluxo sem base legal
- Criar migration de DossieAbertura sem validar o modelo com dados reais
