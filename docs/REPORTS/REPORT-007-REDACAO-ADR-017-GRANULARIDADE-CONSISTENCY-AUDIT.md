# REPORT-007 — Redacção do ADR-017 de granularidade do ConsistencyAuditAgent

## 1. Identificação

**Missão:** `MISSION-007-B14-SVC-03-DECISAO-GRANULARIDADE-SOBERANA-CONSISTENCY-AUDIT`
**Natureza:** documental, com leitura estática limitada e sem implementação
**Executor:** Codex
**Autoridade arquitectural/auditoria:** GPT
**Autoridade de ratificação:** Miguel

## 2. Baseline

Branch `main`; `HEAD == origin/main == e5cfd5ef989eb5920d479b29880746a93ba1afaa`.

## 3. Estado inicial e preflight

```text
Get-Location:
C:\dev\saas-fiscal-demo

git branch --show-current:
main

git rev-parse HEAD:
e5cfd5ef989eb5920d479b29880746a93ba1afaa

git rev-parse origin/main:
e5cfd5ef989eb5920d479b29880746a93ba1afaa

git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-007-B14-SVC-03-DECISAO-GRANULARIDADE-SOBERANA-CONSISTENCY-AUDIT.md

git diff --name-only:
app/agents/adapters/ag_encerramento.py
app/agents/engines/ag_encerramento.py
docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
tests/test_ag_encerramento_mission_adapter.py

git diff --cached --name-only:
vazio
```

ADR-017 preexistente: NÃO. REPORT-007 preexistente: NÃO. O preflight satisfez a baseline e o estado permitido.

## 4. Hashes iniciais e finais dos quatro ficheiros protegidos

| Ficheiro | Hash do índice inicial/final | Hash normalizado da working tree inicial/final |
|---|---|---|
| `app/agents/adapters/ag_encerramento.py` | `f1880088018a0760d57e09d1866a882fa9898460` | `f1880088018a0760d57e09d1866a882fa9898460` |
| `app/agents/engines/ag_encerramento.py` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` |
| `tests/test_ag_encerramento_mission_adapter.py` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` |

Os hashes finais repetidos após a criação dos documentos foram exactamente iguais aos hashes iniciais acima. Os estados `M` eram preexistentes. A igualdade entre hash do índice e hash normalizado da working tree confirma preservação do conteúdo Git; os avisos observados referem-se a CRLF/LF. Nenhum protegido foi editado, formatado, restaurado ou adicionado ao stage.

## 5. Fontes efectivamente lidas

- `AGENTS.md`;
- `docs/CCS/CCS-001-CONSTITUICAO-DE-EXECUCAO.md`;
- `docs/ADR-001-GOVERNACAO_CANONICIDADE.md`;
- `docs/ADR-003-ACESSO-CONTADOR-EMPRESA-DOCUMENTO.md`;
- `docs/ADR-004-VINCULO-SOBERANO-CONTADOR-DT-CONTADOR-01.md`;
- `docs/ADR-005-CARTEIRA-CONTADOR-ANTI-CAPTURA.md`;
- `docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md`;
- `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md`;
- `docs/ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT.md`;
- `docs/ADR-016-FRONTEIRA-SOBERANA-PROVENIENCIA-DATASANITIZATION.md`;
- `docs/MISSIONS/MISSION-003-RECTIFICACAO-REPORT-002.md`;
- `docs/MISSIONS/MISSION-006-B14-SVC-02-REDACAO-ADR-016-PROVENIENCIA-SOBERANA.md`;
- `docs/REPORTS/REPORT-002-AUDITORIA-FRONTEIRAS-BRIGADA-L3.md`;
- `docs/REPORTS/REPORT-003-RECTIFICACAO-REPORT-002.md`;
- `docs/REPORTS/REPORT-006-REDACAO-ADR-016-PROVENIENCIA-DATASANITIZATION.md`;
- `app/agents/contracts/consistency_audit.py`;
- `app/agents/engines/consistency_audit.py`;
- `app/agents/adapters/consistency_audit.py`;
- `app/agents/consistency_audit_agent.py`;
- `app/services/tax_consistency/tax_consistency_engine.py`;
- `tests/test_consistency_audit_mission_adapter.py`;
- `app/models.py`;
- `app/services/registro_analise_service.py`.

Não foi necessário ler migrations ou qualquer fonte adicional.

## 6. Verificações factuais limitadas

### 6.1 ADR-012 v1.3 e B14.3D

Confirmado: `docs/ADR-012-MIGRACAO-L3-CONSISTENCY-AUDIT.md` declara `RATIFICADA v1.3 — Miguel e GPT`. A ADR fixa missão documental, contexto previamente fornecido e ausência de reader produtivo.

Confirmado: o commit B14.3D existe como `d4c506c598a9a1f1c430266cc10aacef3375e99e`, com assunto `feat: migrar ConsistencyAuditAgent para contrato L3 em sombra`.

Confirmados os quatro ficheiros previstos:

- contrato `app/agents/contracts/consistency_audit.py`;
- motor `app/agents/engines/consistency_audit.py`;
- adapter `app/agents/adapters/consistency_audit.py`;
- testes `tests/test_consistency_audit_mission_adapter.py`.

O adapter mantém `scope = "documento"`, `entity_type = "documento_fiscal"`, vínculo entre `entity_id` e `context.documento_id`, execução apenas em `sombra`/`dry_run` e bloqueio de `activo`.

### 6.2 Gate produtivo

Como registo histórico anterior à ADR-017, REPORT-002 declarou `ADR-012-GRANULARIDADE-001` aberto e integração produtiva bloqueada, e REPORT-003 confirmou que o gate continuava `ABERTO`.

`ItemFiscal` possui identidade interna `id`, vínculo `documento_id` e campos declarados por item, incluindo `base_st` e `valor_st`. As fontes examinadas não comprovam persistência de cada resultado calculado do motor com identidade de execução e vínculo ao mesmo item. `EngineResultado` liga resultados a Empresa/relatório, sem vínculo produtivo comprovado ao item fiscal. Logo, o gate de implementação produtiva permanece `PENDENTE E BLOQUEADO`, e a integração produtiva permanece `BLOQUEADA`.

## 7. Decisões materializadas no ADR-017

O ADR distingue expressamente:

- escopo da missão: documento fiscal;
- unidade canónica de auditoria: `item_documento_fiscal`.

Fixa item como unidade de comparação; documento como contentor/snapshot/execução; e relatório, período e agregado como estruturas derivadas que não substituem itens.

Proíbe compensação entre itens: diferenças positivas e negativas em itens distintos não podem produzir coerência documental por soma. O estado documental deriva da conjunção dos resultados item a item.

Exige proveniência independente para o lado declarado e o lado calculado, além de vínculo verificável documento–item–motor–resultado e execução identificada. Sem vínculo, o estado é `INDISPONIVEL_POR_VINCULO_NAO_COMPROVADO`, sem fallback documental.

Dados incompletos são distintos de divergência e coerência; produzem bloqueio ou auditoria inconclusiva, nunca `dados_coerentes=True`. Ausência e `null` não viram zero.

O ADR declara que consistência interna não equivale a verdade fiscal, validade normativa, pagamento, direito, ilicitude, conformidade ou autorização de publicação.

## 8. Estado actual dos gates

- gate de decisão arquitectural `ADR-012-GRANULARIDADE-001`: `RESOLVIDO POR ADR-017`;
- gate de implementação produtiva: `PENDENTE E BLOQUEADO`;
- integração produtiva: `BLOQUEADA`;
- nenhuma implementação autorizada.

A auditoria foi aprovada por GPT e a ADR-017 foi ratificada por Miguel em 2026-07-23. A resolução do gate de decisão arquitectural não resolve o gate de implementação, que continua pendente e bloqueado até missão própria.

## 9. Ausência de implementação e preservação

Nenhum código, teste, migration, contrato, reader, projector, endpoint, scheduler, registry, executor, persistência ou configuração foi criado ou alterado.

ADR-012 e ADR-016 não foram alteradas. O canário B14.3D, o serviço protegido, o agente legado e os quatro ficheiros protegidos permanecem inalterados. Não foram executados pytest, migrations ou testes de aplicação; apenas validações textuais e Git autorizadas.

## 10. Ficheiros

Criados originalmente pelo Codex:

1. `docs/ADR-017-FRONTEIRA-SOBERANA-GRANULARIDADE-CONSISTENCY-AUDIT.md`;
2. `docs/REPORTS/REPORT-007-REDACAO-ADR-017-GRANULARIDADE-CONSISTENCY-AUDIT.md`.

Ficheiros preexistentes alterados nesta rectificação pós-ratificação: ADR-017 e REPORT-007, exclusivamente.
Ficheiros removidos: NENHUM.

Os quatro `M` protegidos e a MISSION-007 untracked já integravam o estado inicial.

## 11. Hashes finais dos artefactos fechados antes deste relatório

- SHA-256 MISSION-007: `4F6C22B31EBFA0006EDC139B35963388E19F4C08AAC7EA818232F207EBB8F322`;
- SHA-256 ADR-017: `01EA79D34EEB6A3026D95B7A9CDE7C618C469C98B313E2B9C833A50FDDBB3E0E`.

O SHA-256 do próprio REPORT-007 será apresentado somente na saída final do Codex, após o fechamento deste ficheiro.

## 12. Validação textual

Todos os termos obrigatórios da MISSION-007 foram encontrados no ADR-017. As formulações proibidas foram verificadas como ausentes, incluindo qualquer afirmação de revogação/substituição da ADR-012, invalidação do B14.3D, autorização produtiva, implementação de componentes, uso de ausência como zero ou agregação compensatória. A rectificação regista a resolução pós-ratificação apenas do gate de decisão arquitectural e preserva o bloqueio produtivo.

## 13. Estado Git confirmado na execução original

O bloco seguinte preserva o registo histórico da execução original do REPORT-007 e não representa o estado Git da rectificação pós-ratificação:

```text
branch:
main

HEAD:
e5cfd5ef989eb5920d479b29880746a93ba1afaa

origin/main:
e5cfd5ef989eb5920d479b29880746a93ba1afaa

git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/ADR-017-FRONTEIRA-SOBERANA-GRANULARIDADE-CONSISTENCY-AUDIT.md
?? docs/MISSIONS/MISSION-007-B14-SVC-03-DECISAO-GRANULARIDADE-SOBERANA-CONSISTENCY-AUDIT.md
?? docs/REPORTS/REPORT-007-REDACAO-ADR-017-GRANULARIDADE-CONSISTENCY-AUDIT.md

git diff --cached --name-only:
vazio
```

## 14. Declarações finais

Stage nesta rectificação: NÃO ALTERADO; nenhum `git add` executado.
Commit: NÃO EFECTUADO.
Push: NÃO EFECTUADO.
Auditoria: APROVADA — GPT.
Ratificação: RATIFICADA — Miguel.

## 15. Estado final da missão

`CONCLUÍDA`. A rectificação pós-ratificação B14-SVC-03 actualizou os estados e os hashes efectivos da MISSION-007 e da ADR-017; o SHA-256 definitivo deste relatório é calculado após o seu fechamento e apresentado somente na saída final do Codex.
