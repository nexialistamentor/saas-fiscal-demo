# REPORT-008 — Redacção e verificação documental da ADR-018

**Estado:** AUDITORIA GPT APROVADA E RATIFICAÇÃO DE MIGUEL REGISTADA — AGUARDA COMMIT E PUSH
**Data:** 2026-07-23
**Missão:** MISSION-008 / B14-SVC-04
**Repositório:** nexialistamentor/saas-fiscal-demo
**Branch:** `main`
**Baseline:** `HEAD = origin/main = c0b6337887b7313bcc3168ff8d654d43fe15e9e2`

---

## 1. Objecto

Este relatório regista a execução exclusivamente documental da
MISSION-008. A execução limitou-se à redacção da proposta ADR-018 e
deste relatório.

Registam-se a auditoria GPT aprovada e a ratificação de Miguel, ambas em
2026-07-23. Não se declara a implementação autorizada, testes verdes,
suite verde, commit, push, deploy ou integração produtiva concluídos.

## 2. Estado Git inicial

Verificação inicial:

```text
branch: main
HEAD: c0b6337887b7313bcc3168ff8d654d43fe15e9e2
origin/main: c0b6337887b7313bcc3168ff8d654d43fe15e9e2
stage: vazio
```

Alterações locais protegidas observadas:

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
```

Os quatro ficheiros foram preservados sem edição, formatação,
normalização, restauro, descarte, stage ou alteração de encoding e line
endings.

## 3. Fontes consultadas

- `docs/ADR-013-MIGRACAO-L3-MEMORIAL-VALIDATOR.md`;
- `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`;
- `app/routes/relatorio_router.py`;
- `app/services/memorial_service.py`;
- `app/security.py`;
- `app/routers/dashboard_router.py`;
- `app/services/pdf_report_service.py`;
- `app/models.py`;
- `tests/test_ops12_f6_memorial_contract.py`;
- `tests/test_e2e_bloco2_memorial.py`.

## 4. Decisões transcritas

A ADR-018 estabelece, por decisão arquitectural ratificada:

- D1 — autorização pelo criador directo ou pelo proprietário da empresa
  associada;
- D2 — ordem canónica 401/404/403/402/200;
- D3 — preflight limitado a `id`, `user_id`, `empresa_id` e `pago`,
  com prova mínima de empresa quando aplicável;
- D4 — materialização rica somente depois de existência, autorização e
  pagamento;
- D5 — separação estrita entre contexto rico e projecção mínima
  `MemorialValidatorContext` v1;
- D6 — GET semanticamente read-only e `memorial_gerado` sem valor de
  prova soberana;
- D7 — escrita futura somente por comando explícito, definido em ADR
  própria;
- D8 — autoridade transaccional na unidade de aplicação, sem
  `commit`, `rollback` ou `flush` em serviço read-only;
- D9 — integração produtiva do agente continua bloqueada.

Também foram registadas a matriz de testes futura, as provas de ordem e
projecção, as exclusões normativas, os riscos de schema e as questões
não resolvidas de entrega e publicação.

## 5. Artefactos criados

Foram criados exactamente:

```text
docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md
docs/REPORTS/REPORT-008-REDACAO-ADR-018-FRONTEIRA-MEMORIAL.md
```

Nenhum código, teste, migration, ADR anterior ou relatório anterior foi
alterado. Nenhum outro ficheiro foi criado, apagado, movido, renomeado
ou formatado.

## 6. Execução e proibições observadas

- nenhum teste foi executado;
- nenhum formatter, linter com autofix, `pytest` ou `alembic` foi
  executado;
- nenhum ficheiro foi stageado;
- nenhum commit foi criado;
- nenhum push foi efectuado;
- nenhum deploy foi efectuado.

## 7. Verificação documental

`git diff --check` é permitido apenas para os dois artefactos e o seu
resultado é registado após a redacção.

Os SHA-256 são obtidos por `Get-FileHash`. O hash final da ADR pode ser
embutido neste relatório. O hash final deste REPORT-008 é registado no
handoff mecânico externo, porque incorporar o próprio hash alteraria os
bytes do artefacto e invalidaria o valor.

```text
ADR-018 SHA-256: 747ADFA9A93CA786F1A76B1176AD879B7A9518C0E3427EC1A1BFA3AE9A6A79AD
REPORT-008 SHA-256 final: REGISTADO NO HANDOFF MECÂNICO
git diff --check: CONFORME — sem saída, exit code 0
```

## 8. Estado Git final

O estado final autorizado deve permanecer:

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md
?? docs/REPORTS/REPORT-008-REDACAO-ADR-018-FRONTEIRA-MEMORIAL.md
```

O estado foi confirmado exactamente como acima. `git diff --name-only`
não revelou qualquer ficheiro tracked adicional e
`git diff --cached --name-only` confirmou stage vazio.

## 9. Pendências institucionais

```text
Auditoria GPT: APROVADA em 2026-07-23
Ratificação de Miguel: APROVADA em 2026-07-23
ADR-013-FRONTEIRA-001: decisão arquitectural RESOLVIDA pela ADR-018
Implementação produtiva: BLOQUEADA
```

A próxima autoridade é a verificação final, seguida de stage e commit
documental controlado. O push permanece posterior ao commit.
