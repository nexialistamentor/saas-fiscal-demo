# REPORT-012 — Redacção Controlada do ROADMAP_OPS_AGENTES

**Estado:** RATIFICADO — FECHO DOCUMENTAL AUTORIZADO POR MIGUEL
**Classificação técnica:** REDACÇÃO DOCUMENTAL CONCLUÍDA — AUDITADA E RATIFICADA
**Parecer GPT:** APROVADO APÓS AUDITORIA INTEGRAL.
**Ratificação de Miguel:** RATIFICO O ROADMAP_OPS_AGENTES V2.0 E O REPORT-012, AUTORIZANDO O SEU FECHO DOCUMENTAL, SEM AUTORIZAR A ACTIVAÇÃO DE AGENTES, LLM REAL, SCHEDULER, EXECUTOR, PERSISTÊNCIA OU QUALQUER OUTRA FRONTEIRA PRODUTIVA.
**Data:** 2026-07-23
**Branch:** `main`
**Baseline:** `HEAD = origin/main = a7e16f0ffa5a90189166d4f968eb62b23c69da89`
**Natureza:** execução documental controlada; não activa componentes.

## 1. Preflight literal

Antes de qualquer escrita, foi provado:

```text
BRANCH=main
HEAD=a7e16f0ffa5a90189166d4f968eb62b23c69da89
origin/main=a7e16f0ffa5a90189166d4f968eb62b23c69da89
STAGE=VAZIO
```

Working tree inicial:

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
```

| Ficheiro | SHA-256 inicial |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |
| `docs/ROADMAP_OPS_AGENTES.md` | `16B24C2CDD718AEB6E4AF1A59B74689E0EEB036FFFDEFFDA5C939EAC6FB8CE70` |
| `docs/REPORTS/REPORT-011-AUDITORIA-RECONCILIACAO-ROADMAP-OPS-AGENTES.md` | `D743D8A64C55FDBAC98337AC7CC0063D5B2754C1BCC6787B6AAD68FFFDC1969E` |

Não houve divergência; a escrita documental pôde prosseguir.

## 2. Escopo autorizado

Foram alterados exclusivamente:

- `docs/ROADMAP_OPS_AGENTES.md`;
- `docs/REPORTS/REPORT-012-REDACCAO-CONTROLADA-ROADMAP-OPS-AGENTES.md`.

MISSION-012 não foi gravada. Não foram criados, removidos, renomeados ou
alterados outros ficheiros. As quatro modificações locais protegidas foram
preservadas.

## 3. Fontes consultadas

Sem internet, foram consultados:

- `AGENTS.md` e `docs/CCS/CCS-001-CONSTITUICAO-DE-EXECUCAO.md`;
- roadmap v1.1 e `REPORT-011`, fonte principal da reconciliação;
- `docs/B13_OPS_12_DEPENDENCIAS_NORMATIVAS.md`;
- ADR-008 a ADR-018;
- MISSION-001 e MISSION-003 a MISSION-007;
- REPORT-001 a REPORT-010;
- inventário estático de `app/agents/**`, `app/main.py` e
  `app/services/llm_router.py`;
- testes arquitecturais e contratuais B14 identificados no REPORT-011.

O histórico Git foi usado somente pela reconciliação cronológica já
documentada no REPORT-011. Mensagens de commit não foram elevadas acima do
estado interno dos documentos institucionais.

## 4. Síntese das alterações por secção

| Secção da v2.0 | Alteração |
|---|---|
| Identidade e versão | Nova identidade 2.0, baseline e estado não canónico em auditoria |
| Autoridade e fontes | Papéis de Miguel, GPT e Codex; conflito institucional preservado |
| Princípios vigentes | Motor-first, missão tipada, escritor único e limites de prova |
| Estado actual | Fundação B14, sombra, canário, SCS, ADR-016/017/018 e B14-SVC-06 |
| Inventário | Visão por grupos com remissão ao inventário exacto do REPORT-011 |
| Activação | Separação entre legado, sombra, canário e produção |
| Gates | Blockers documentais, normativos e produtivos mantidos |
| Dependências normativas | Valores e vigências não provados retirados |
| Factos externos | Providers abstractos e manifesto temporal próprio exigido |
| Criptografia | Limites de SHA-256 e agilidade criptográfica declarados |
| Futuro | Categorias sem prioridade estratégica nem autorização implícita |
| Critérios de saída | Evidência, teste, auditoria, ratificação e efeitos controlados |
| Dívida histórica | B13, Pilot 0, T1–T8 e fases antigas deslocados para histórico |
| Histórico de versões | v1.1 superada e v2.0 em auditoria |

## 5. Rastreabilidade das 28 conclusões do REPORT-011

| # | Conclusão auditada | Destino na v2.0 |
|---:|---|---|
| 1 | Identidade v1.1/B13 superada | Secções 1, 13 e 14 |
| 2 | Humano aprova; autoridade limitada | Secções 2 e 3 |
| 3 | Sem commit/deploy/BD/decisão fiscal autónomos | Secções 3 e 12 |
| 4 | Flags globais conflitam com missão explícita | Secção 6 |
| 5 | Kill switch de provider superado | Secções 6 e 9 |
| 6 | Inventário de oito agentes incorrecto | Secção 5 e remissão ao REPORT-011 |
| 7 | “Existe, desligado” não provado | Secções 3 e 5 |
| 8 | Scheduler legado auditado | Secções 5, 6 e 7 |
| 9 | Serviços B13 fora do foco actual | Secção 13 |
| 10 | Valor e diploma normativos incorrectos | Secção 8, sem reproduzir alternativa |
| 11 | Demais fontes/vigências não provadas | Secção 8 |
| 12 | Pilot 0 é histórico | Secção 13 |
| 13 | Fase 0 e T1–T8 superados/não reconciliados | Secção 13 |
| 14 | Prova de fontes “a criar” superada | Secções 8 e 13 |
| 15 | Exemplo normativo “verificado” conflitante | Secção 8 |
| 16 | Testes/manifest/sentinela propostos superados | Secção 13 |
| 17 | Router/providers já existem, uso real não autorizado | Secções 5, 6 e 9 |
| 18 | Modelos/endpoints/depreciação não provados | Secção 9 |
| 19 | Schemas/testes LLM propostos superados | Secções 4 e 13 |
| 20 | Invariantes do router permanecem como princípios | Secções 3 e 9 |
| 21 | `EventoOperacional` já existe | Secção 13 |
| 22 | Sanitização rasa incorrecta | Secção 4 |
| 23 | Prioridade de agentes cabe a Miguel | Secção 11 |
| 24 | Prompt universal superado por motor-first | Secções 3 e 13 |
| 25 | Circuito automático conflita com governação | Secções 3, 6 e 12 |
| 26 | SLA não provado | Removido; nenhum SLA declarado |
| 27 | Fases 0–4 superadas | Secções 11, 13 e 14 |
| 28 | Proibições vigentes preservadas; facto temporal removido | Secções 3, 6 e 9 |

As 28 conclusões possuem destino explícito. Nenhuma foi usada para reabrir ADR
ratificado ou conceder autorização operacional.

## 6. Itens removidos e preservados

Foram removidos do estado corrente:

- percentagens, metas e SLA sem prova;
- valores, diplomas e vigências externas apresentados como verdade;
- nomes temporais de modelos, endpoints, disponibilidade e depreciação;
- propostas de artefactos já existentes;
- activação global por flags;
- prioridades estratégicas e prompt universal;
- circuito automático de prompt, patch, commit e deploy;
- qualquer aparência de produção activa sem evidência.

Foram preservados:

- decisão fiscal não delegada a LLM;
- aprovação humana;
- motor-first/LLM-last;
- missão explícita e tipada, um agente por missão e ausência de chamadas
  directas entre agentes;
- escritor único, ausência de efeitos L3 examinados e separação de estados;
- agilidade criptográfica sem alegação pós-quântica;
- divergências institucionais e dívida histórica sem resolução indevida.

## 7. Gates mantidos

Permanecem `BLOQUEADO`: divergências documentais; proveniência produtiva de
DataSanitization; granularidade/fronteira produtiva de ConsistencyAudit;
memorial além do read-only; integração, executor, persistência e scheduler L3
produtivos; dependências normativas em revisão; chamada real a LLM; conflito
`AGENTS.md` versus CCS-001.

## 8. Ausência de alteração operacional

Não foram alterados código, testes, banco, configuração, contratos, ADRs ou
invariantes. Nenhum agente foi activado ou executado. Não houve chamada real a
LLM, integração, persistência, projecção, scheduler L3 ou escrita operacional.

Internet: não usada.
Testes globais: não executados.
Instalação de dependências: nenhuma.
Commit/push/deploy: nenhum.

## 9. Validações documentais

Foram autorizadas e executadas apenas verificações read-only/documentais:

- `git diff --check`;
- nomes alterados, stage e estado Git;
- whitespace final;
- SHA-256;
- presença das secções obrigatórias;
- rastreabilidade das 28 conclusões;
- procura contextual de termos proibidos e afirmações temporais não provadas;
- encoding UTF-8 sem BOM, LF e exactamente uma newline final.

## 10. Hashes finais

| Ficheiro | SHA-256 final |
|---|---|
| `docs/ROADMAP_OPS_AGENTES.md` | `AFD4ED3A85672CC7492E83D4BE4D6FE9A150D8C9F90D4C2184E4D1B79902D31D` |
| `docs/REPORTS/REPORT-011-AUDITORIA-RECONCILIACAO-ROADMAP-OPS-AGENTES.md` | `D743D8A64C55FDBAC98337AC7CC0063D5B2754C1BCC6787B6AAD68FFFDC1969E` |
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

O hash final deste REPORT-012 é evidência externa: deve ser medido após o
fecho e apresentado no handoff, pois inseri-lo no próprio ficheiro alteraria
os bytes medidos.

## 11. Estado Git final

Stage esperado e confirmado no fecho: vazio.

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M docs/ROADMAP_OPS_AGENTES.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/REPORTS/REPORT-012-REDACCAO-CONTROLADA-ROADMAP-OPS-AGENTES.md
```

`git diff --name-only` literal no fecho:

```text
docs/ROADMAP_OPS_AGENTES.md
```

Os quatro caminhos protegidos permanecem visíveis em `git status --short` e
mantêm os hashes exigidos; não foram tocados nesta missão.

Commit: nenhum.
Push: nenhum.
Deploy: nenhum.

## 12. Fecho documental

A auditoria GPT e a ratificação de Miguel foram concluídas. Nenhuma fronteira
produtiva foi autorizada.
