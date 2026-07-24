# ROADMAP_OPS_AGENTES — Circuito Operacional e Agentes L3

## 1. Identidade e versão

| Campo | Valor |
|---|---|
| Nome | ROADMAP_OPS_AGENTES |
| Versão | 2.0 |
| Data | 2026-07-23 |
| Estado | RATIFICADO — CANÓNICO DOCUMENTAL, SEM AUTORIZAÇÃO OPERACIONAL |
| Baseline | `a7e16f0ffa5a90189166d4f968eb62b23c69da89` |
| Estado documental | Redacção controlada; não constitui autorização operacional |
| Fonte principal de reconciliação | `REPORT-011` |

Este documento separa estado comprovado, histórico, gates e futuro. A sua
existência não activa componentes, não escolhe prioridade estratégica e não
altera contratos, ADRs ou invariantes.

## 2. Autoridade e fontes de verdade

| Item | Estado | Evidência e fronteira | Responsável pela próxima decisão |
|---|---|---|---|
| Autoridade humana final | CONCLUÍDO | `AGENTS.md` identifica Miguel; nenhuma decisão deste roadmap o substitui | Miguel |
| Auditoria e supervisão | CONCLUÍDO | GPT audita e formula missões dentro da hierarquia declarada | GPT |
| Execução técnica limitada | CONCLUÍDO | Codex executa somente missão, escopo e comandos autorizados | Codex |
| Conflito `AGENTS.md` versus CCS-001 | BLOQUEADO | As cadeias de autoridade divergem; CCS-001 está `EM CONSTRUÇÃO`; este roadmap não resolve precedência | Miguel, após auditoria GPT |
| Commits | CONCLUÍDO | Evidência cronológica auxiliar; mensagens não substituem o estado interno dos documentos institucionais | Não aplicável |

ADRs, contratos canónicos e invariantes ratificados são fontes de verdade no
seu âmbito. Quando o estado textual de um documento diverge do histórico Git,
a divergência é preservada até decisão da autoridade competente.

## 3. Princípios vigentes

- **CONCLUÍDO — Decisão fiscal não delegada a LLM.** Motores e fontes
  autorizadas fundamentam cálculo; LLM pode, quando futuramente autorizado,
  analisar ou enriquecer sem produzir decisão fiscal canónica.
- **CONCLUÍDO — motor-first, LLM-last.** A camada determinística precede
  qualquer fallback ou enriquecimento.
- **CONCLUÍDO — missão explícita e tipada.** Um agente por missão, sem chamadas
  directas entre agentes; missão declara fronteira, modo, tenant, autoridade e
  orçamento, mas não cria autoridade por si.
- **CONCLUÍDO — escritor único.** Leitura, análise e proposta não concedem
  escrita; mutação depende de fronteira e autoridade próprias.
- **CONCLUÍDO — ausência de efeitos nos caminhos L3 examinados.**
  `actions_executed=[]`; existência deste campo não autoriza execução futura.
- **CONCLUÍDO — sem `run_all()` produtivo L3.** O executor e o scheduler que
  possuem essa superfície são legados e não integram a brigada L3.
- **CONCLUÍDO — sem auto-commit, auto-push ou auto-deploy.** Cada efeito exige
  autorização explícita e escopo próprio.
- **CONCLUÍDO — prova limitada.** Existência, teste ou instanciação não provam
  activação nem execução. Ausência de prova de activação não deve ser
  convertida em afirmação de inactividade.

## 4. Estado actual comprovado

### 4.1 Fundação contratual

| Marco | Estado | Evidência | Vigência e fronteira |
|---|---|---|---|
| B14.0+B14.1 — fundação contratual | CONCLUÍDO | ADR-008 e fecho documental B14.0+B14.1 | Contratos vigentes; não autoriza produção geral |
| Serialização canónica | CONCLUÍDO | `contracts/canonical.py` e testes contratuais | Determinismo e integridade do contrato |
| `ContextSanitizationGuard` | CONCLUÍDO | ADR-008, `contracts/sanitization.py` e testes | Varrimento profundo; não prova proveniência produtiva |
| Contratos partilhados | CONCLUÍDO | `SourceRef`, `BudgetPolicy`, `AgentEvidence`, `AgentAlert`, `AgentAction` | Limitam e descrevem autoridade; não a ampliam |
| `AgentMission` e `MissionFactory` | CONCLUÍDO | contratos, factory e testes | Missão explícita; disponibilidade não activa agente |
| `AgentExecutionResult` | CONCLUÍDO | contrato e testes | Regista resultado; não executa acções |
| Validação cruzada e invariantes arquitecturais | CONCLUÍDO | `contracts/validation.py` e testes B14 | Restringem combinações inválidas; testes não provam activação |

### 4.2 Sombra, canário e fronteiras

| Marco | Estado | Evidência | Vigência e fronteira |
|---|---|---|---|
| B14.3A–F | CONCLUÍDO | ADR-009 a ADR-014, adapters, engines e testes | Migrações em sombra; estados textuais divergentes de ADR-009/011 permanecem registados |
| B14.3G | CONCLUÍDO | ADR-015 e adapter/engine de pré-execução | Canário; `llm_used=false`; sem chamada real ao router/provider |
| Sistema de Construção Soberana | CONCLUÍDO | `AGENTS.md`, MISSION-001/REPORT-001 e ciclo MISSION/REPORT | Governa execução; não activa produto |
| ADR-016 | EM AUDITORIA | Documento define fronteira de proveniência; o próprio estado textual diz `PROPOSTO` | Implementação produtiva permanece bloqueada |
| ADR-017 | CONCLUÍDO | Estado textual ratificado por GPT e Miguel | Decisão arquitectural sem implementação produtiva |
| ADR-018 | EM AUDITORIA | Estado textual ratificado, ainda declara aguardar commit/push documentais | Não autoriza projecção ou mutação além da fronteira decidida |
| B14-SVC-06 | CONCLUÍDO | REPORT-010 e fronteira HTTP do memorial | Apenas leitura HTTP; não activa integração, projecção ou mutação L3 |

Nenhum destes marcos constitui autorização produtiva geral.

## 5. Inventário arquitectural

O inventário exacto, ficheiro a ficheiro, permanece na secção 7 do
`REPORT-011`. Esta visão por grupos não o substitui.

| Grupo | Natureza | Estado | Escrita | Autoridade fiscal | LLM | Prova de activação |
|---|---|---|---|---|---|---|
| Agentes legados | Agentes anteriores aos contratos L3 | ABERTO | Alguns contêm leitura, efeitos ou acesso potencial; sem autorização L3 | Não provada ou não canónica | Possível em caminho legado específico | Não provada em produção |
| Registry/scheduler/executor legados | Orquestração e persistência legadas | BLOQUEADO | Executor pode gravar e scheduler abre sessões | Nenhuma autoridade L3 | Indirecto/não provado | Instanciação em `app/main.py` não é execução; lifespan não inicia scheduler |
| Adapters L3 | Fronteira `AgentMission` → `AgentExecutionResult` | CONCLUÍDO | Nenhuma nos caminhos examinados | Orientação/validação, nunca decisão canónica | Não; canário mantém `llm_used=false` | Sombra ou canário, não produção |
| Engines L3 | Processamento determinístico | CONCLUÍDO | Nenhuma | Limitada pelo contrato de cada missão | Não chamam provider | Existência e teste não provam execução |
| Reader L3 | Leitura para snapshot de encerramento | CONCLUÍDO | Leitura apenas; sem commit | Nenhuma | Não | Sombra; não prova publicação |
| Contratos L3 | Tipos, guardas e validação | CONCLUÍDO | Descrevem/limitam; não executam | Autoridade tipada e limitada | Apenas metadados contratuais | Vigência contratual não equivale a activação |
| Router/providers LLM | Stack substituível já existente | ABERTO | Sem autoridade de escrita L3 | Não pode decidir fiscalmente | Capacidade abstracta | Existência não prova uso; chamada real L3 não autorizada |
| Fronteiras HTTP read-only | Exposição de leitura do memorial | CONCLUÍDO | Sem mutação no escopo B14-SVC-06 | Nenhuma decisão fiscal | Não | Prova apenas a rota read-only implementada |

## 6. Fronteiras de activação

- **CONCLUÍDO:** nenhuma flag global activa a brigada L3.
- **CONCLUÍDO:** adapters exigem missão explícita, tipada e uma fronteira
  própria; flags de configuração não concedem autoridade.
- **CONCLUÍDO:** scheduler, registry e executor legados não constituem
  integração nem autorização L3.
- **CONCLUÍDO:** B14.3G não chama `LLMRouter` nem provider e mantém
  `llm_used=false`.
- **BLOQUEADO:** chamada real a LLM permanece não autorizada.
- **FUTURO NÃO AUTORIZADO:** produção L3 depende de missão posterior,
  evidência apropriada, auditoria GPT e decisão de Miguel.

Legado, sombra, canário e produção são estados distintos. Código legado pode
conter efeitos sem estar autorizado para L3; sombra executa apenas na
fronteira explícita de validação; canário testa pré-condições sem chamada
real; produção exige autorização e evidência próprias.

## 7. Gates e blockers

| Gate | Estado | Evidência/fronteira | Responsável pela próxima decisão |
|---|---|---|---|
| Divergências de estado documental | BLOQUEADO | REPORT-011, secção 10 | Miguel, após auditoria GPT |
| Proveniência produtiva de DataSanitization | BLOQUEADO | ADR-016 e REPORT-004/005/006 | Miguel, após auditoria GPT e missão própria |
| Granularidade/fronteira produtiva de ConsistencyAudit | BLOQUEADO | ADR-017 decide arquitectura, sem implementação | Miguel, por missão posterior |
| Memorial além de HTTP read-only | BLOQUEADO | ADR-018, REPORT-009/010 | Miguel, por missão posterior |
| Integração, executor, persistência e scheduler L3 produtivos | BLOQUEADO | REPORT-002/003 | Miguel, após proposta e auditoria |
| Dependências normativas em revisão | BLOQUEADO | B13-OPS-12; fontes incapazes de fundamentar decisão enquanto assim marcadas | Autoridade normativa e Miguel |
| Conflito `AGENTS.md` versus CCS-001 | BLOQUEADO | REPORT-011, secção 10 | Miguel, após auditoria GPT |

Estes gates são preservados, não resolvidos por este roadmap.

## 8. Dependências normativas

**BLOQUEADO.** O roadmap não reproduz valores, diplomas ou vigências externas
como verdade. Uma dependência normativa só pode ser apresentada no seu
manifesto versionado, com pelo menos:

- `fonte_id`;
- fonte e data de verificação;
- início e fim de vigência, quando provados;
- estado da autoridade;
- capacidade explícita de fundamentar decisão;
- risco e comportamento quando estiver em revisão.

O manifesto e B13-OPS-12 contêm dependências em revisão ou pendentes. Este
documento não valida fontes externas nem ratifica qualquer valor alternativo.

## 9. Factos externos e providers

**ABERTO.** Modelos, preços, endpoints, disponibilidade e depreciação são
factos temporais externos e não são declarados aqui. A arquitectura deve usar
capacidades abstractas e provider substituível. Qualquer uso futuro exige
manifesto próprio, versionado, com fonte, data de verificação, vigência,
autoridade, limites e política de substituição.

## 10. Fronteira criptográfica

**CONCLUÍDO — limite da evidência actual.** SHA-256 prova somente integridade
byte a byte no momento da medição. Não prova autoria, proveniência, não
repúdio, timestamp confiável ou resistência pós-quântica.

**FUTURO NÃO AUTORIZADO.** Uma assinatura institucional exige ADR próprio.
Qualquer desenho futuro deve preservar versionamento, substituibilidade,
agilidade criptográfica e independência de algoritmo. Este roadmap não escolhe
algoritmo nem alega segurança pós-quântica.

## 11. Sequência futura autorizável

Esta secção não ordena prioridade. Recomendação não equivale a autorização.

### ABERTO

- Reconciliar estados documentais divergentes por decisão humana.
- Manter inventário e manifestos versionados à medida que missões autorizadas
  produzam evidência.
- Definir evidência mínima para cada fronteira produtiva, sem a implementar
  por este roadmap.

### BLOQUEADO

- Proveniência produtiva de DataSanitization.
- Implementação produtiva da granularidade/fronteira de ConsistencyAudit.
- Memorial além da leitura HTTP já implementada.
- Integração, execução, persistência e scheduler soberanos L3.
- Dependências normativas ainda em revisão.
- Chamada real a LLM no caminho L3.

### FUTURO NÃO AUTORIZADO

- Activação produtiva de qualquer adapter ou brigada L3.
- Projector, reader adicional, scheduler, executor ou persistência L3.
- Mutação do memorial e efeitos transaccionais.
- Integração real com provider LLM.
- Assinatura institucional e evolução criptográfica.

Miguel escolhe prioridade e emite autorização; GPT audita; Codex executa
somente a missão delimitada.

## 12. Critérios de saída

Uma categoria futura só pode sair do seu estado quando possuir, conforme o
risco e a missão:

1. evidência documental rastreável;
2. teste apropriado, sem confundir cobertura com activação;
3. auditoria GPT;
4. ratificação de Miguel;
5. commit de escopo único;
6. push confirmado;
7. deploy apenas com autorização explícita.

O cumprimento de um critério não presume os seguintes.

## 13. Dívida histórica

| Item histórico | Estado | Registo |
|---|---|---|
| B13 | CONCLUÍDO | Transição operacional para B14 comprovada; dependências normativas pendentes permanecem gates próprios |
| Pilot 0 e correcção de race condition | CONCLUÍDO | Marco histórico anterior a B14 |
| P0-07, T1–T8 e feedback do Pilot 0 | ABERTO | Fecho documental individual não provado; não são fase corrente |
| Fases 0–4 da v1.1 | CONCLUÍDO | Sequência histórica superada pela arquitectura B14 e pelo ciclo MISSION/REPORT |
| Propostas de criação de router, schemas, evento e testes | CONCLUÍDO | Artefactos passaram a existir; existência não prova activação |
| Prompt universal e prioridades antigas | FUTURO NÃO AUTORIZADO | Removidos da arquitectura corrente; eventual artefacto exige missão e decisão próprias |

## 14. Histórico de versões

| Versão | Data | Estado | Evidência |
|---|---|---|---|
| 1.1 | 2026-06-28 | CONCLUÍDO — histórica e superada | SHA-256 `16B24C2CDD718AEB6E4AF1A59B74689E0EEB036FFFDEFFDA5C939EAC6FB8CE70` |
| 2.0 | 2026-07-23 | RATIFICADO — CANÓNICO DOCUMENTAL, SEM AUTORIZAÇÃO OPERACIONAL | Baseline `a7e16f0ffa5a90189166d4f968eb62b23c69da89`; reconciliação `REPORT-011` |

A auditoria GPT e a ratificação de Miguel foram concluídas. A versão 2.0 é
canónica documental, sem autorização para activar agentes, LLM real, scheduler,
executor, persistência ou qualquer fronteira produtiva.
