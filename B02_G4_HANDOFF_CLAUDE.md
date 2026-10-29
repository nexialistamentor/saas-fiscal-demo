# SOLVERIS B02 — Handoff G4 ao Claude (preparação; não operação)

## Baseline e artefactos
- Branch: `candidate/g5-successor-window-prep`.
- Baseline auditado: `f8be751f9c3f851ae658ec02332098664bc1583a`.
- Procedimento: `executar_ativacao_g4_real.py` (dry-run por omissão; execução explícita e ainda não autorizada).
- Serviço reutilizado, não alterado: `app/services/enterprise_b02_policy_activation_atomicity.py::stage_policy_activation()`.
- Modelos consultados: `app/models.py` e `app/models_policy_activation_atomicity.py`.
- `preflight_scope_hash.sql` eliminado: não era uma entrada do serviço e a sua descrição como valor em falta induzia em erro.
- G5 V3 imutável: `POLICY_G5_CANDIDATO_V3_COMPLETO.json`, SHA-256 institucional esperado `8b3b0cc0a880156b5659166b6878de580b1ddafcf245d811545a0f1ba60500d4`. Não alterar este ficheiro.

## Contrato efetivo
O escritor exige `connection` em transação externa e exatamente `execution`, `activation`, `generation_id`, `outbox_id`, `provenance`. Calcula no servidor o manifesto `structured_result`, incluindo `scope_hash = sha256(canonical_bytes(policy.scope))`; o chamador NÃO fornece `scope_hash`, `record_hash`, `assigned_txid`, `payload_hash` nem `structured_result`. Produz os quatro registos, devolve hashes disponíveis e nunca faz COMMIT. O chamador gere COMMIT/ROLLBACK.

O novo script confere role/base, permissões, política/decisão/bootstrap exatos, funções SQL e ausência de colisões; em modo real abre transação externa, usa timestamp de servidor, chama o escritor existente e só considera sucesso após leitura independente `READ ONLY` e reconciliação dos quatro registos, dos seus vínculos, hashes, manifesto, conteúdo, payload e identidade transacional. Perda de ACK nunca desencadeia nova escrita; três leituras independentes inconclusivas terminam em STOP.

Os IDs literais aprováveis (ainda não executados) estão no script: `B02-05ede-execution-v2`, `B02-05ede-activation-v2`, `B02-05ede-generation-v2`, `B02-05ede-outbox-v2`; idempotência `B02-05ede-execution-v2-20261103T120000Z`. Janela proposta: 03/11/2026 12:00 UTC a 04/11/2026 07:56:30.910737 UTC.

## Preflight G4 físico concluído — 29/10/2026 (evidência terminal Windows)

- Diagnóstico administrativo local, exclusivamente leitura: `SERVER|solveris_b02_r4g_test|solveris_test|solveris_test`; writer `LOGIN=true`, password configurada e validade ilimitada; `HBA_ERRORS|0`. A via TCP publicada exige SCRAM; as entradas locais do servidor para socket e loopback são `trust`, tal como observadas. Não houve edição do HBA.
- Ligação direta pelo socket do container **sem SET ROLE**: `DIRECT_WRITER|solveris_b02_r4g_test|solveris_b02_policy_writer|solveris_b02_policy_writer`.
- SQL sob o writer, `BEGIN READ ONLY`: nove verificações `PASS` — `IDENTITY`, `ROLE`, `TABLE_PERMISSIONS`, `PREDECESSOR_READ`, `SQL_FUNCTIONS`, `POLICY`, `DECISION`, `BOOTSTRAP`, `IDS_AVAILABLE`. `CONTAINER|RESTORED_STOPPED`.
- Preflight **Python final**: executado na `.venv-release` do checkout Windows; código `executar_ativacao_g4_real.py` lido de `FETCH_HEAD` com verificação do blob Git `1729e6d62c77510ef4dd7db0af56a6cbe985c168`; identidade PostgreSQL via ponte TCP de loopback efémera `docker exec` para o loopback interno já autorizado, sem password e sem alteração do servidor. Execução por stdin para preservar aspas (`python -`), **sem `--execute`**.
- Resultado final recebido do terminal de Miguel: `mode=DRY_RUN`; `DRY_RUN_DB_READ_ONLY_PASS: exact predecessors, IDs available`; `PYTHON_EXIT|0`; `CONTAINER|RESTORED_STOPPED`. A função `independent_read()` impõe `SET TRANSACTION READ ONLY` e executa `preflight()`. Portanto, esta é uma confirmação física do preflight **read-only**, não mera ligação SQL nem apenas `DRY_RUN_STATIC_ONLY`.
- Primeiro ensaio Python falhou por perda das aspas em `python -c` (`SyntaxError` antes da ligação); corrigido executando o mesmo código via stdin, sem alterar o procedimento versionado. Não repetir esse ensaio.
- **Não é necessária redefinição de password** para este percurso comprovado. Não criar, divulgar ou custodiar credenciais adicionais; não instalar dependências no container.
- Nenhum INSERT, UPDATE, DELETE, DDL, GRANT, ALTER ROLE, ativação G4/G5, COMMIT de escrita, migração, assinatura ou ensaio normativo. O `scope_hash` é derivado pelo código do serviço a partir da política real; não é parâmetro de entrada e não se inventa.
- O G5 V3, MEI, serviço de escrita, regras de autenticação e PASS anteriores permanecem inalterados. **Preflight G4 fechado; ativação G4 NÃO realizada.**

## Passos posteriores (não iniciar)
1. **Não repetir o preflight físico concluído.** Miguel decide expressamente se autoriza **esta unidade G4 de quatro registos**, com IDs, janela e papel exatos. O preflight PASS não constitui autorização operacional.
2. Apenas com autorização específica e acesso legítimo à mesma identidade, operador autorizado poderá usar `--execute --approval-reference` com referência verdadeira do ato. Validar novamente o contexto no instante da futura operação. Não executar antecipadamente.
3. Custodiar exclusivamente o resultado `FOUR_RECORDS_RECONCILED` (IDs, `execution_hash`, `activation_hash`, `generation_hash`, `outbox_hash`, `outbox_payload_hash`, `scope_hash`, `policy_hash`). Não inferir sucesso por um INSERT isolado ou ACK.
4. Apenas depois, preparar **novo candidato G5 sucessor**, atualizando as duas vinculações documentais `g4.policy_binding.policy_activation_id` e `policy_activation_record_hash` com os valores observados, e referenciar execução/geração/outbox conforme contrato G5 efetivo. Preservar V3, obter revisão segregada e nova decisão institucional antes de o considerar final.
5. Os três testes integrados G5, instalação 0064/0065, assinatura real e operação continuam pendentes. B02 não fechado.
