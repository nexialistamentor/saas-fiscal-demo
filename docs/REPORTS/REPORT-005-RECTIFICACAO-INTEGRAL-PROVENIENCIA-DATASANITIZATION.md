# REPORT-005 — Rectificação integral da auditoria de proveniência

## 1. Identificação da missão

Missão: `MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA`. Gate: `ADR-011-PROVENIENCIA-001`. Baseline: `2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f`.

## 2. Origem arquitectural do defeito

O defeito factual teve origem no escopo da MISSION-004, cujo inventário indicava `regime` entre os oito campos e omitia `base_calculo`. O Codex executou correctamente o inventário que lhe foi fornecido. A MISSION-005 substitui apenas a lista factual de campos e a evidência incompleta; nenhuma responsabilidade arquitectural é atribuída ao executor e nenhuma decisão autónoma do Codex originou o defeito.

## 3. Estado inicial do repositório

```text
git branch --show-current: main
git rev-parse HEAD: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git rev-parse origin/main: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/MISSIONS/MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA.md
?? docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
```

Branch, baseline, `HEAD == origin/main`, stage vazio e os três artefactos de entrada existentes foram confirmados. `REPORT-005` não existia.

## 4. Hashes iniciais

SHA-256:

- MISSION-004: `4C6CB5B0039C440EE553433CF2E8F8CB52BD5C19D28B32E5ED4E981FB98D264B`
- REPORT-004: `ECEFD50CC7BDABAB921194A49F6BDFBDC29FB88A4857273053848848190ED31A`
- MISSION-005: `48B5EBAD99C98B748E61E6F2D8D0D2AB8404A72D9CE1EABC82B8440C811C8EAF`

Foi criada cópia temporária do REPORT-004 em `C:\Users\Oem\AppData\Local\Temp\REPORT-004-MISSION-005-before.md`, com SHA-256 idêntico ao original.

## 5. Inventário canónico comprovado

Estado: APLICADA  
Local rectificado: REPORT-004, secções 4, 6 e 10.  
Evidência do código: `DataSanitizationField` e `CAMPOS_FISCAIS_CANONICOS` em `app/agents/contracts/data_sanitization.py:31-40,67-79`; `DataSanitizationContext` em `143-159`.  
Formulação anterior: oito auditados com `regime`, enquanto `base_calculo` era tratado à parte.  
Formulação correcta: `empresa_id` e oito campos fiscais canónicos: `faturamento`, `custos`, `lucro_contabil`, `lucro`, `base_calculo`, `icms_pago`, `icms_devido`, `custo_fiscal_entradas`.  
Validação: matriz com exactamente oito linhas; `regime` não integra o contrato.

## 6. Rectificação de base_calculo

Estado: APLICADA  
Local rectificado: REPORT-004, secções 6, 8, 12, 13, 15 e 16.  
Evidência do código: `app/services/insights_engine.py:98-121`.  
Formulação anterior: campo omitido da matriz contratual.  
Formulação correcta: deriva de faturamento, custos e estado actual de `Empresa.regime_tributario`; `lucro = faturamento - custos`; `base_calculo = lucro` se `regime == "real"`, caso contrário `faturamento * 0.08`. Não há coluna própria persistida.  
Validação: documentadas sem inferência a semântica não ratificada, percentual hardcoded sem fundamento normativo provado, defaults para `presumido`, ausência de vigência, ausência já colapsada em zero, comportamento dos negativos nos dois ramos, unidade não formalizada, histórico sem cutoff, autorização apenas por empresa e reprodução limitada por BD/regime mutáveis e ausência de snapshot. Estado: `INCOMPATÍVEL COM A FRONTEIRA L3`.

## 7. Reclassificação de regime

Estado: APLICADA  
Local rectificado: REPORT-004, subseção separada após a matriz e secções relacionadas.  
Evidência do código: `app/services/insights_engine.py:98-101,108-127` e ausência em `DataSanitizationField`/`DataSanitizationContext`.  
Formulação anterior: linha contratual na matriz dos oito campos.  
Formulação correcta: regime é dependência auxiliar da fonte candidata, não campo fiscal canónico do `DataSanitizationContext`; escolhe a fórmula de `base_calculo` e é extra rejeitado por `extra="forbid"`.  
Validação: origem, domínio não comprovado, default, Empresa inexistente, colapso de ausência/vazio/nulo, estado actual sem validade histórica e rejeição contratual documentados.

## 8. Rectificações aplicadas ao REPORT-004

Estado: APLICADA  
Local rectificado: secções 4, 6, 8, 10, 12, 13, 14, 15, 16 e 19.  
Evidência do código: contrato canónico e fonte candidata citados nas secções anteriores.  
Formulação anterior: inventário incompleto, regime contratual e teste não recolhido.  
Formulação correcta: inventário exacto, auditoria integral de `base_calculo`, regime auxiliar, extras exactos e resultado correcto do teste.  
Validação: alterações restritas aos sete grupos autorizados pela missão.

Rectificação residual ordenada pela auditoria GPT: removida da secção 16 do REPORT-004 a afirmação desactualizada de que o teste autorizado não fora recolhido e substituída pelo resultado factual e pelos limites da prova, sem alteração dos demais conteúdos.

## 9. Preflight do ambiente

Comandos e saída:

```text
Get-Location
C:\dev\saas-fiscal-demo

python --version
Python 3.11.9

python -c "import os,sys; print(os.getcwd()); print(sys.executable); import app; print(app.__file__)"
C:\dev\saas-fiscal-demo
C:\Users\Oem\AppData\Local\Programs\Python\Python311\python.exe
C:\dev\saas-fiscal-demo\app\__init__.py
```

Preflight aprovado antes do pytest; nenhum diagnóstico adicional foi necessário.

## 10. Resultado do teste autorizado

Comando exclusivo:

```text
python -m pytest -q tests/test_data_sanitization_mission_adapter.py
```

Resultado literal:

```text
........................................................................ [ 88%]
.........                                                                [100%]
81 passed in 0.55s
```

Exit code: `0`.

## 11. Limites da prova de teste

O resultado prova apenas contrato, engine e adapter isolados cobertos pelo ficheiro. Não prova a fonte produtiva candidata, não prova reader/projector, não fecha ADR-011 e não autoriza integração produtiva.

## 12. Validação textual

Estado: APLICADA. Presenças confirmadas no REPORT-004: `base_calculo`, `regime é dependência auxiliar`, `regime não integra o contrato`, `faturamento * 0.08`, `regime == "real"`, `extra="forbid"`, `CONTEXTO_SEM_CAMPOS_FISCAIS`, `81 passed in 0.55s` e `gate permanece aberto`. Ausentes as formulações erradas enumeradas na missão. A matriz contém exactamente oito linhas contratuais e nenhuma linha contratual de `regime`.

## 13. Comparação antes e depois

Comparação com a cópia temporária: `1 file changed, 30 insertions(+), 16 deletions(-)`. Hunks restritos a: inventário canónico; matriz e auditoria de `base_calculo`; reclassificação de `regime`; defaults/compatibilidade; requisitos e decisões; teste/matriz do gate; riscos e estado final coerente, incluindo a rectificação residual ordenada pela auditoria GPT. Não houve normalização ou reescrita integral.

## 14. Hashes finais

SHA-256:

- MISSION-004: `4C6CB5B0039C440EE553433CF2E8F8CB52BD5C19D28B32E5ED4E981FB98D264B` — inalterado
- REPORT-004: `854F5CD29A996218DCFA45D60DFE599DF6B1C10CAF51C656BF1B0F4F852A3DA1` — rectificado
- MISSION-005: `48B5EBAD99C98B748E61E6F2D8D0D2AB8404A72D9CE1EABC82B8440C811C8EAF` — inalterada

## 15. Estado do gate

`ADR-011-PROVENIENCIA-001`: ABERTO — decisão GPT e ratificação Miguel pendentes. O teste aprovado não altera o gate.

## 16. Estado final do repositório

```text
git branch --show-current: main
git rev-parse HEAD: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git rev-parse origin/main: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/MISSIONS/MISSION-005-B14-SVC-01-RECTIFICACAO-INTEGRAL-PROVENIENCIA.md
?? docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
```

`HEAD == origin/main`; nenhum commit ou push.

## 17. Declaração de preservação

MISSION-004 e MISSION-005 foram preservadas. Os quatro ficheiros protegidos mantiveram, antes e depois, os pares índice/working tree: `f1880088.../f1880088...`, `ef99aa7e.../ef99aa7e...`, `f78b8c15.../f78b8c15...`, `5dc8d0c6.../5dc8d0c6...`. Nenhum código, teste, ADR, contrato, migration ou configuração foi alterado. Apenas REPORT-004 foi alterado e apenas REPORT-005 foi criado. Stage permaneceu vazio. A cópia temporária foi removida antes do término.

## 18. Estado da execução

Estado da execução: EXECUTADA COM PENDÊNCIAS — rectificação concluída; gate, auditoria e ratificação pendentes.  
Relatório rectificado: `docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`  
Relatório criado: `docs/REPORTS/REPORT-005-RECTIFICACAO-INTEGRAL-PROVENIENCIA-DATASANITIZATION.md`  
MISSION-004: PRESERVADA — hash inalterado  
Teste autorizado: `81 passed in 0.55s`  
Outros ficheiros alterados: NENHUM  
Gate: ABERTO  
Stage: VAZIO  
Commit: NÃO EFECTUADO  
Push: NÃO EFECTUADO  
Auditoria: PENDENTE — autoridade GPT  
Ratificação: PENDENTE — autoridade Miguel
