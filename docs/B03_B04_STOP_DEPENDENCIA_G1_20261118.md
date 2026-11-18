# SOLVERIS Enterprise — STOP: G1 omitido na recuperação B03/B04

**Data:** 18/11/2026. **Natureza:** relatório de investigação read-only do primeiro ensaio dirigido em Windows; não aprova alteração de código, commit de produto, merge ou deploy.

**Estado obrigatório:** `ENTERPRISE_RECOVERY_STATUS=BLOCKED`, `GLOBAL_GREEN=false`. A catraca estrutural de 29 controlos passou; os testes de integração **não passaram**. As 13 falhas da baseline `main@a6a2da6c` continuam aceites **apenas** como exceções diferenciais anteriores, nunca como GREEN global.

## 1. Recibo do ensaio recebido de Miguel

- Worktree isolado: `C:\dev\saas-fiscal-demo-b06-green-20261118`, montado sobre a `main` fixa `a6a2da6cbf07c7b9922f8571bf2e6016376304d5`, com restauro de 36 blobs originários de `c9a17fd1` e aplicação dos dois patches documentais de candidato (`669bb9bd`).
- Comando: `python -m pytest -q --tb=short --disable-warnings tests/test_enterprise_b03_item_reconciliation.py tests/test_enterprise_b04_icms_st_integral_bridge.py tests/test_solveris_b01_circuit.py tests/test_enterprise_b01_atomic_rollback_contract.py`.
- Resultado **observado**, não inferido: **43 collected; 23 passed; 20 failed; 54 warnings; 4.62 s**. A execução dirigida é RED; não foi executada uma nova suite global após esta falha.
- Transcrição integral da saída fornecida na conversa em `Texto colado(20261118-133643).txt`; SHA-256 do ficheiro recebido `3eb6a4055d1b499364e24068ab3aa5e0affd06935f289c030593b97ef5c4fbcd` (recibo externo da análise; não é JUnit nem substitui comprovativo de execução independente).
- Pré-gate executado por Miguel: `python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q` → **29 tests OK**. Isso verifica preparativos, **não** a admissibilidade de integrar.

## 2. Causa material comum — versão G1 ausente

| Verificação Git/contrato | `main@a6a2da6c` | Origem Enterprise `c9a17fd1` |
| --- | --- | --- |
| `app/services/tax_consistency/tax_consistency_engine.py` | blob `9f7a5ddf144293fe3591989c784c8ec6d875cd07` | blob `543f19b4b777ecaaa107d699dd13c002b378e8a2` |
| `verificar_consistencia` | resposta `{'consistente': bool, 'divergencias': [...]}`; pode indicar `True` sem pares por item | resposta com `estado`, `consistente=None`, identidade documental/itens e `autoridade_fiscal=False`, `credito_confirmado=False`, `checkout_autorizado=False` |
| Teste causal G1 | ausente do pacote seletivo atual | `tests/test_enterprise_g1_consistencia_causal_item.py`, blob `45a2080a8adead467aa4b00275e3a33616b0966c`, **22 contratos** |
| Proveniência | implementação de base na `main` | commit `ee100756` (`fix(enterprise): fail closed on unproven fiscal consistency`), **não ancestral** da `main` |

As duas versões foram confirmadas via `git ls-tree`, `git show`, `git diff c9a17fd1..a6a2da6c` e `git merge-base --is-ancestor ee100756 a6a2da6c` (saída 1). O G1 é uma **dependência necessária de G12, G13 e do scaffold B03** e não entrou na lista de 36 ficheiros restaurados, nem na allowlist de caminhos do manifesto V2. Portanto, a recolha de blobs B03/B04 preservou o código original, mas **não reconstruiu a dependência de contrato G1**.

## 3. Decomposição exata dos 20 RED dirigidos

| Grupo | Falhas | Causa demonstrada |
| --- | ---: | --- |
| `test_enterprise_b03_item_reconciliation.py` | 5 | `enterprise_b03_item_reconciliation.py:222` lê `bruto['estado']`; G1 da `main` não devolve `estado` → `KeyError`. |
| `test_solveris_b01_circuit.py` | 6 | G12 recebeu do G1 `consistente=True`, sem `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`; G13 recusou em `G13_G1_CONFRONTO_NAO_FALHA_FECHADO` (proteção **correta**). |
| `test_enterprise_b01_atomic_rollback_contract.py` — testes novos | 3 | Chegam ao mesmo G13 incompatível antes de testar commit final/G17/Insights. Outros 3 passaram. |
| `test_enterprise_b01_atomic_rollback_contract.py` — recolha duplicada | 6 | O ficheiro novo importa a subclasse `unittest.TestCase` original como `_B01Fixture` no namespace: `pytest` recolheu e repetiu os mesmos 12 testes B01, incluindo os 6 RED. **Defeito de recolha**, não seis regressões independentes. |
| **Total** | **20** | **1 contrato G1 ausente + 1 defeito de recolha**. |

Os 6 testes de B04 ficaram GREEN nesta seleção, mas isso não autoriza caracterizar a **cadeia integral B01/B03/B04** como recuperada. Não alterar as asserções originais B01/B03/B04, nem o gate G13; ele está corretamente a bloquear uma falsa atribuição de autoridade.

## 4. Risco e fronteira de autorização

`TaxConsistencyEngine` é **compartilhado**, não exclusivamente Enterprise: há importações no `app/xml_service.py`, `app/agents/consistency_audit_agent.py` e no adaptador `app/agents/engines/consistency_audit.py`; scanners de alcance MEI também o reconhecem. Substituir silenciosamente a versão da `main` pelo blob histórico mudaria o formato de saída para consumidores legados e poderia afetar os fluxos que Miguel mandou preservar. Fazer o G13 aceitar `consistente=True` ou fabricar campos em G12 para mascarar a divergência seria um **falso GREEN** e violaria fail-closed.

**STOP_SCOPE_EXPANSION_REQUIRED:** este ficheiro não pertence ao conjunto autorizado de alterações V2. A sua modificação, a importação alternativa por consumidor ou a criação de um módulo segregado são decisões de arquitetura com impacto de contrato. Não editar motor, MEI, G12/G13, teste canónico ou manifesto V2 por conveniência. Não mexer em produção/Railway, Alembic, pagamentos, SERPRO ou MVA.

## 5. Próxima decisão de Miguel (sem execução antecipada)

**Proposta técnica preferida para avaliação, não ratificada:** recuperar o **blob G1 original**, byte a byte, numa **dependência privada de Enterprise**, destinada exclusivamente a B03 e G12/G13. Deixar intacto o módulo compartilhado da `main` e os seus consumidores (incluindo MEI), rastreando a proveniência `543f19b4...` e reexecutando os 22 contratos G1 originais imutáveis (`45a2080a...`) mais os 25 obrigatórios B01/B03/B04 e os 6 novos atómicos. Essa via requer autorização explícita para novo caminho, alteração dirigida de imports Enterprise e atualização versionada do manifesto/gate; não pressupor que passa os testes.

**Alternativa de maior risco, não recomendada sem missão independente:** substituir o motor G1 compartilhado da `main`, revalidando todos os consumidores. Não a executar no âmbito atual.

**Higiene separável:** num novo patch versionado, corrigir somente a dupla recolha usando importação de **módulo** do fixture B01 em vez de expor a classe `TestCase` com outro nome. Os 12 contratos B01 originais ficam imutáveis. A alteração também requer atualizar o hash do candidato e os controlos, sem reescrever silenciosamente o patch V2 já publicado.

Até ratificação específica: preservar exatamente os candidatos, parar mudanças de produto, manter `ENTERPRISE_RECOVERY_STATUS=BLOCKED` / `GLOBAL_GREEN=false`; B06 Fase 0 ainda **não iniciada** e nenhum PDF gerado.
