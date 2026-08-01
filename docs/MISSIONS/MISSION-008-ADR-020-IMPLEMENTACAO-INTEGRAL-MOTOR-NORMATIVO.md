# MISSION-008 — Implementação Integral do Motor Normativo ADR-020

**Estado:** AUTORIZADA
**Sistema:** Sistema de Construção Soberana
**Documento superior:** CCS-001 — Constituição de Execução do Executor Técnico

---

# 1. Identificação

- ID: MISSION-008
- Título: Implementação Integral do Motor Normativo ADR-020
- Estado: AUTORIZADA
- Data declarativa: 2026-08-01T16:06-03:00
- Autoridade emissora: Miguel — AUTORIDADE CONSTITUCIONAL FINAL
- Executor: Codex, exclusivamente como executor técnico
- Missão relacionada: implementação local restante da ADR-020 v0.3 R2
- Declaração ratificada: “RATIFICO AS QUATRO DECISÕES FÍSICAS DA IMPLEMENTAÇÃO ADR-020.”
- Baseline operacional: `35d32c9d44ab1a4e39c2101c1d18b83327204078`

---

# 2. Objetivo

Implementar localmente, de forma verificável, append-only, fail-closed e sem efeito operacional, os blocos restantes BC-1, BC-2A, BC-2C, BC-3A, BC-3B e BC-3C da ADR-020 ratificada. A conclusão exige as entidades, migrations, validadores e serviços determinísticos autorizados, testes isolados, cumulativos, integrados e globais verdes, cadeia Alembic única e exacta e relatório institucional final.

Implementação local não equivale a activação normativa, autorização operacional, publicação, deploy ou produção.

---

# 3. Escopo

## 3.1 Decisões físicas ratificadas

1. **Contrato de cobertura:** `CoverageContract` é entidade própria, versionada, imutável, content-addressed e append-only. Não especializa `PolicyVersion`, não concede autoridade e é a entidade canónica; `SourceAcquisitionProfile` é somente denominação histórica equivalente. `ActivationAuthorityPolicy` é materializada por `PolicyVersion(policy_type = activation_authority)` e pela cadeia institucional e activação exactas.
2. **Ledger e checkpoints:** `CoverageLedgerEntry` preserva uma entrada append-only por unidade observada ou processada, com contrato exacto, unidade, ordem determinística, resultado, evidência, fencing token, proveniência, timestamp e `record_hash`. `CoverageCheckpointRecord` preserva fotografias append-only de `observed_through`, `completed_through`, `covered_through` e `pending_gap_from`, vinculadas ao contrato e último ledger entry exactos, sem projecção destrutiva, salto de lacuna ou promoção presumida de falha.
3. **Agrupamento atómico:** o núcleo operacional BC-2A/BC-2C integra o mesmo Commit 7: `PolicyActivationExecution`, `PolicyActivation`, `ActivationDecision`, `ActivationExecution`, `NormativeActivation`, `ActivationGeneration`, atomicidade, proveniência e outbox. `AutomationEnvelope` é `PolicyVersion(policy_type = automation_envelope)` com `PolicyActivation` exacta e activa; não existe autoridade mutável paralela.
4. **Outbox:** `OutboxEventRecord` é entidade própria, imutável e append-only, com `outbox_event_id`, `event_type`, `activation_execution_id`, `activation_generation_id`, `activation_decision_id`, `scope_hash`, `composition_hash`, `payload`, `payload_hash`, `provenance`, `created_at` e `record_hash`. Não possui `published`, update, delete, dispatcher, worker, scheduler, endpoint, rede ou publicação real. Payload não contém segredo ou credencial. Execução concluída, geração integral e outbox nascem na mesma transacção lógica; qualquer falha impede todos os efeitos parciais. Futura tentativa de entrega exigirá registo append-only separado.

## 3.2 Sequência de commits autorizada

- Commit 5: fundação institucional de políticas — `PolicyVersion`, `PolicyDecision`, `BootstrapAuthorityRecord`; migration `0022_adr020_policy_foundation.py`; teste principal `test_adr020_policy_foundation.py`; mensagem `feat(adr-020): establish policy authority foundation`.
- Commit 6: contrato e ledger de cobertura — `CoverageContract`, `CoverageLedgerEntry`, `CoverageCheckpointRecord`; migration `0023_adr020_coverage_foundation.py`; teste principal `test_adr020_coverage_foundation.py`; mensagem `feat(adr-020): establish coverage contract and ledger`.
- Commit 7: núcleo atómico de activação — entidades e contratos BC-2A/BC-2C e `OutboxEventRecord`; migration `0024_adr020_activation_foundation.py`; teste principal `test_adr020_activation_foundation.py`; mensagem `feat(adr-020): establish atomic policy and normative activation`.
- Commit 8: credenciais e sanitização — seis entidades BC-3C e enforcement prospectivo; migration `0025_adr020_credentials_foundation.py`; teste principal `test_adr020_credential_sanitization.py`; mensagem `feat(adr-020): establish credential and sanitization chain`.
- Commit 9: publicação, consumo e réplicas — quatro entidades BC-3A; migration `0026_adr020_consumption_foundation.py`; teste principal `test_adr020_consumption_foundation.py`; mensagem `feat(adr-020): establish generation consumption and replica fences`.
- Commit 10: cálculo determinístico e replay — cinco entidades BC-3B; migration `0027_adr020_calculation_replay.py`; teste principal `test_adr020_calculation_replay.py`; mensagem `feat(adr-020): establish deterministic calculation and replay`.
- Commit 11: fecho contratual integrado — teste `test_adr020_integrated_pipeline.py` e REPORT-008; sem entidades ou migration; mensagem `test(adr-020): verify sovereign pipeline contracts end to end`.

## 3.3 Ficheiros autorizados

- `docs/MISSIONS/MISSION-008-ADR-020-IMPLEMENTACAO-INTEGRAL-MOTOR-NORMATIVO.md`
- `docs/REPORTS/REPORT-008-ADR-020-IMPLEMENTACAO-INTEGRAL-MOTOR-NORMATIVO.md`
- `app/models.py`
- `app/services/adr020/**`
- `migrations/versions/0022_adr020_policy_foundation.py`
- `migrations/versions/0023_adr020_coverage_foundation.py`
- `migrations/versions/0024_adr020_activation_foundation.py`
- `migrations/versions/0025_adr020_credentials_foundation.py`
- `migrations/versions/0026_adr020_consumption_foundation.py`
- `migrations/versions/0027_adr020_calculation_replay.py`
- `tests/test_adr020_policy_foundation.py`
- `tests/test_adr020_coverage_foundation.py`
- `tests/test_adr020_activation_foundation.py`
- `tests/test_adr020_credential_sanitization.py`
- `tests/test_adr020_consumption_foundation.py`
- `tests/test_adr020_calculation_replay.py`
- `tests/test_adr020_integrated_pipeline.py`

Teste ADR-020 anterior só pode ser alterado no commit da entidade futura que invalide uma asserção expressa de ausência, sem remoção ou enfraquecimento do contrato histórico, e com justificação no REPORT-008.

---

# 4. Restrições

- Proibidos push, pull, fetch, deploy, Railway, Vercel, produção e rede.
- Proibidos scheduler activo, worker activo, endpoint público e publicação real.
- Proibidos secrets manager real, credencial real, aquisição externa, segredo persistido, regra fiscal inventada e conteúdo jurídico novo.
- Proibidas alterações a ADRs, documentos constitucionais, contratos canónicos, invariantes e commits 1–4.
- Proibidos `git add .`, `git add -A`, reset, restore, checkout destrutivo, clean, stash, rebase, amend e force.
- Não remover testes nem enfraquecer constraints para obter verde.
- Cada retry usa nova identidade; entidades e estados terminais nunca são reabertos.
- Nenhuma versão actual, corrente ou mais recente pode ser inferida.
- Todos os ficheiros tocados devem ser UTF-8 sem BOM, LF, CR = 0 e zero-width = 0.

## 4.1 Ficheiros protegidos

- `migrations/versions/0018_adr020_acquisition_foundation.py`
- `migrations/versions/0019_adr020_extraction_foundation.py`
- `migrations/versions/0020_adr020_rule_foundation.py`
- `migrations/versions/0021_adr020_relation_foundation.py`
- `docs/ROADMAP_OPS_AGENTES.md` — absolutamente proibido

---

# 5. Entradas

- Bundle `C:\Users\Oem\AppData\Local\Temp\BUNDLE-CONSTITUCIONAL-FINAL-ADR-020-V0.3-R2-R1.zip`, SHA-256 `8f5b6f2de56acaf087d1577b997c09025a6820fff12b8fb3fcc6bd5053f6adaf`.
- ADR-020 v0.3 R2, SHA-256 `b57c4c20cb8976940e35b91469cd998dd9a6367e96c4e12c096a3f02a31135ad`.
- Auditoria Independente, SHA-256 `029f6c76f93eb916a536e5927d60034119c008c857c6f7d5952a3d143cd83ed9`.
- Acto de Ratificação, SHA-256 `1e7a64adc80fecb46705b77f8e376e53801b180a9a89c5050b31fe97a7a7882e`.
- Encerramento Constitucional, SHA-256 `4f4c9e766d35fb4645deab7dace70249eab6fc49c8e9755be55111fbaf5bbf14`.
- Auditoria técnica read-only `AUDITORIA-TECNICA-ADR020-20260801-154832.txt`, SHA-256 `b162fc6647446207644b990e5da825176007abdf28a386794b28272c07483fb8`.
- AGENTS.md, CCS aplicável, MISSION-TEMPLATE, código e testes do baseline.

---

# 6. Saídas esperadas

- Commits locais isolados 5–11, todos verdes.
- Seis migrations numa única lineage de `0022_adr020_policy` a `0027_adr020_calc_replay`.
- Modelos, validators e serviços determinísticos estritamente autorizados.
- Testes isolados, cumulativos, integrados e suite global verdes.
- REPORT-008 com evidência integral, limitações, riscos, pendências e estado final.
- Árvore limpa, stage vazio e ficheiros protegidos intactos.

---

# 7. Evidências obrigatórias

Antes de cada commit: listar alterações; validar escopo e ficheiros protegidos; validar encoding; executar `git diff --check`; testes isolados e ADR-020 cumulativos; verificar única Alembic head e lineage; stagear individualmente; confirmar stage exacto; criar commit; confirmar árvore limpa.

Após o Commit 11: executar todos os testes ADR-020, suite global, `git diff --check`, Alembic heads, validação de encoding, integridade do roadmap e migrations protegidas, ausência de push/deploy/rede/produção e estado final de stage/worktree.

---

# 8. Critérios de aceitação

- Todos os contratos positivos e negativos determinados pela autorização e ADR estão implementados e verdes.
- `ActivationExecution(completed)`, `ActivationGeneration` integral e `OutboxEventRecord` são atómicos.
- Sanitização `verified_sanitized` é obrigatória prospectivamente para aquisição e extracção.
- Consumo é contíguo, fenced, idempotente, monotónico e fail-closed.
- Cálculo e replay são determinísticos, sem rede, estado mutável ou relógio corrente.
- Nenhuma autoridade é implícita, derivada de cobertura ou réplica, nem resolvida por “mais recente”.
- A implementação permanece local e inactiva.

---

# 9. Critérios de interrupção

Qualquer divergência, erro de teste, necessidade de ficheiro não autorizado, alteração protegida, múltipla head, quebra de lineage, erro de encoding ou impossibilidade de produzir evidência interrompe imediatamente a execução. Preservam-se commits verdes; não se cria commit vermelho; reportam-se último commit verde, teste exacto, ficheiros alterados e estado da árvore. Se o limite de execução se aproximar, a paragem ocorre somente após commit integralmente verde e árvore limpa, sem iniciar o seguinte.

---

# 10. Relatório obrigatório

O `REPORT-008-ADR-020-IMPLEMENTACAO-INTEGRAL-MOTOR-NORMATIVO.md` registará preflight, hashes, commits completos, ficheiros, migrations e lineage, testes, warnings, HEAD, stage, worktree, integridade protegida, ausências operacionais, limitações, pendências e estado institucional exacto.

O relatório não declarará Auditoria Independente pós-implementação concluída. A implementação local concluída, se alcançada, continuará sem equivaler a activação normativa, autorização de deploy ou efeito produtivo.
