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

## Evidência e limites
- GitHub: commit inicial e serviço/modelos lidos; sem alteração em serviço, migrations, papéis, G5 V3 ou MEI.
- Preparação local: `py_compile` e dry-run de um protótipo do procedimento concluídos; a versão final do GitHub recebeu inspeção estática da assinatura, campos, transação e reconciliação. **Não afirmar que a versão final foi importada com todo o checkout nem que o PostgreSQL local foi observado nesta sessão.**
- Nenhuma ativação, INSERT/UPDATE/DELETE/DDL, assinatura ou ensaio Docker nesta missão. Não existe novo hash G4 observado.
- A evidência anterior sobre o escritor restrito, a decisão ratificada e o bootstrap é aproveitada, mas o preflight atual foi codificado para **confirmá-los novamente apenas na futura invocação**. Não converter observações históricas em provas operacionais atuais.

## Passos posteriores (não iniciar)
1. Miguel decide expressamente se autoriza **esta unidade G4 de quatro registos**, com IDs, janela e papel exatos. Sem essa decisão, apenas dry-run.
2. No ambiente Windows real, após disponibilização segura da variável `SOLVERIS_B02_POLICY_WRITER_DSN`, executar o script por omissão para o preflight `READ ONLY`; avaliar qualquer STOP. Não expor DSN.
3. Só com autorização específica, operador autorizado poderá usar `--execute --approval-reference` com a referência verdadeira do ato. Não executar antecipadamente.
4. Custodiar exclusivamente o resultado `FOUR_RECORDS_RECONCILED` (IDs, `execution_hash`, `activation_hash`, `generation_hash`, `outbox_hash`, `outbox_payload_hash`, `scope_hash`, `policy_hash`). Não inferir sucesso por um INSERT isolado ou ACK.
5. Apenas depois, preparar **novo candidato G5 sucessor**, atualizando as duas vinculações documentais `g4.policy_binding.policy_activation_id` e `policy_activation_record_hash` com os valores observados, e referenciar execução/geração/outbox conforme contrato G5 efetivo. Preservar V3, obter revisão segregada e nova decisão institucional antes de o considerar final.
6. Os três testes integrados G5, instalação 0064/0065, assinatura real e operação continuam pendentes. B02 não fechado.
