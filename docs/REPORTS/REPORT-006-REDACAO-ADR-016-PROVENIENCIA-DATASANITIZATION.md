# REPORT-006 — Redação do ADR-016 de proveniência soberana

## 1. Identificação da missão

Missão: `MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA`, versão v1.1. Natureza documental, sem implementação. Artefacto proposto: `ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION`.

## 2. Baseline

Branch `main`; `HEAD == origin/main == b1775217cbdbb9490aab442bc705f54081f9dc73`.

## 3. Estado inicial

```text
Get-Location: C:\dev\saas-fiscal-demo
git branch --show-current: main
git rev-parse HEAD: b1775217cbdbb9490aab442bc705f54081f9dc73
git rev-parse origin/main: b1775217cbdbb9490aab442bc705f54081f9dc73
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
ADR-016 preexistente: não
REPORT-006 preexistente: não
```

O preflight satisfez todos os critérios da missão.

## 4. Hashes dos quatro protegidos

| Ficheiro | Hash índice inicial/final | Hash normalizado working tree inicial/final |
|---|---|---|
| `app/agents/adapters/ag_encerramento.py` | `f1880088018a0760d57e09d1866a882fa9898460` | `f1880088018a0760d57e09d1866a882fa9898460` |
| `app/agents/engines/ag_encerramento.py` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` |
| `tests/test_ag_encerramento_mission_adapter.py` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` |

## 5. Confirmação de ADR-016 livre

Antes da criação, `Test-Path docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md` devolveu `False`. A numeração fornecida pela missão foi usada sem pesquisa adicional.

## 6. Fontes efectivamente lidas

- MISSION-006 v1.1;
- ADR-001, ADR-003, ADR-004, ADR-005, ADR-006, ADR-008 e ADR-011, apenas por padrões factuais relevantes;
- REPORT-004 e REPORT-005, apenas nas evidências de inventário, gate e rectificação;
- `app/agents/contracts/data_sanitization.py`;
- `app/services/insights_engine.py`;
- `app/agents/readers/ag_encerramento.py`.

Não houve pesquisa recursiva ampla, leitura de artefactos externos ou pytest.

## 7. Resumo factual das decisões incorporadas

O ADR propõe fronteira externa ao agente com pedido explícito, autorização, reader read-only, snapshot temporal, manifestação imutável, projector estrito, serialização/hash e missão. Distingue estritamente o fluxo próprio (`actor_id == tenant_id`, sem vínculo delegado exigido) do fluxo delegado (`actor_id != tenant_id`, com identificador/prova de vínculo soberano obrigatório e limitado ao escopo ratificado). Impõe fail-closed, preservação de ausência/null/zero/negativo, produtor canónico por campo, segurança/LGPD, reprodutibilidade e separação de gates. Não escolhe regra fiscal nem implementa componentes.

Rectificação residual ordenada pela auditoria GPT: as secções 10, 11 e 31 do ADR-016 foram clarificadas para tornar a ausência de vínculo no fluxo próprio um estado contratual legítimo, exigir vínculo comprovado no fluxo delegado e acrescentar os quatro cenários de teste correspondentes.

## 8. Relação ADR-011 ↔ ADR-016

ADR-016 é autónomo e aditivo. ADR-011 permanece canónico para B14.3C em sombra, sem reader e com contexto previamente autorizado. A futura proveniência produtiva é fronteira distinta e externa ao agente/adapter.

## 9. Tratamento do gate histórico

Enquanto o ADR-016 estiver proposto, `ADR-011-PROVENIENCIA-001: ABERTO` e integração produtiva `BLOQUEADA`. Após auditoria GPT e ratificação Miguel, o gate de decisão arquitectural poderá ser `RESOLVIDO POR ADR-016`; o gate de implementação produtiva continuará `PENDENTE E BLOQUEADO` até bloco próprio, testes, auditoria e ratificação.

## 10. Rejeição de `_montar_contexto_engines`

Confirmada como fonte directa proibida: contém Session e extras (`data_referencia`, `regime`, `atividade`, `context_flags`), usa defaults/fórmulas não ratificados, não comprova autorização e não produz snapshot temporal.

## 11. Oito campos exactos

Confirmados: `faturamento`, `custos`, `lucro_contabil`, `lucro`, `base_calculo`, `icms_pago`, `icms_devido`, `custo_fiscal_entradas`, além da identidade `empresa_id`.

## 12. Regime

Confirmado: `regime` não integra o contrato; é dependência auxiliar potencial, sujeita a autorização, domínio e vigência futuros, e não atravessa `extra="forbid"`.

## 13. Ausência de implementação

Nenhum código, teste, migration, contrato, reader, projector, scheduler, registry, executor ou configuração foi criado ou alterado. Nenhum teste foi executado.

## 14. Hashes finais

- SHA-256 MISSION-006: `8B8D2F991A6E89983A4A0A3DD35CE311B6DAE6D4BFF5FA79307B85FAFFEECE87`
- SHA-256 ADR-016: `5CB8CFE7530B3C59F1E4942AD24F2B7A38CB17B1404A5ECE386E7F196BBD576F`

## 15. Hash do REPORT-006

O SHA-256 do próprio REPORT-006 será apresentado apenas na saída final do Codex, depois de o ficheiro estar fechado, e não dentro do próprio REPORT-006.

## 16. Estado final Git

```text
branch: main
HEAD: b1775217cbdbb9490aab442bc705f54081f9dc73
origin/main: b1775217cbdbb9490aab442bc705f54081f9dc73
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md
?? docs/MISSIONS/MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA.md
?? docs/REPORTS/REPORT-006-REDACAO-ADR-016-PROVENIENCIA-DATASANITIZATION.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
```

## 17. Stage

VAZIO.

## 18. Commit

NÃO EFECTUADO.

## 19. Push

NÃO EFECTUADO.

## 20. Auditoria

PENDENTE — GPT.

## 21. Ratificação

PENDENTE — Miguel.
