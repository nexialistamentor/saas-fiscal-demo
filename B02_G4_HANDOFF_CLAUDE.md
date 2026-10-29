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

## Autorização e execução Windows — preparação em 29/10/2026

- A autorização institucional **já existe**, no ficheiro \`AUTORIZACAO_G4_MIGUEL_20261029.json\`, commit \`a78cc8ec152d45846f226df1de2784be131c5544\`, referência \`B02-G4-AUTH-MIGUEL-20261029-01\`. Procedimento expressamente abrangido: \`executar_ativacao_g4_real.py\`, blob Git \`1729e6d62c77510ef4dd7db0af56a6cbe985c168\`. Não solicitar nova autorização para a mesma unidade.
- Pacote de revisão histórico: \`a91bd50b130cd6529ed2abe35bf21fae2718039a\`. Reutilizado sem reabrir exames fechados.
- Runner GitHub preparado: \`tools/b02_g4_authorized_runner.py\`. Requer o checkout Windows \`candidate/g5-successor-window-prep\` atualizado exclusivamente por \`git fetch\` e \`git merge --ff-only\`. Não apaga nem modifica untracked.
- Reusa o caminho fisicamente aprovado, **Python Windows → listener efémero 127.0.0.1 → docker exec → TCP loopback interno 127.0.0.1:5432**. O pacote de revisão descreve este transporte de forma imprecisa como «socket»; socket administrativo e ponte TCP do Python são percursos distintos. Não usar a porta publicada 55432.
- O runner fixa autorização, procedimento e blob, base, writer, política, IDs, janela, código do serviço e SHA-256 do V3; verifica container/volume, executa exatamente uma invocação aprovada \`--execute --approval-reference B02-G4-AUTH-MIGUEL-20261029-01\`, e **não faz INSERT adicional**. Mesmo que o COMMIT fique incerto, abre uma segunda ponte da mesma tipologia, numa nova sessão SQLAlchemy \`NullPool\`, exclusivamente \`READ ONLY\`, para reconciliar os quatro registos. Sem \`FOUR_RECORDS_RECONCILED\` na sessão independente, STOP sem nova escrita.
- Após sucesso verificado, grava localmente \`B02_G4_RESULTADO_RECONCILIADO_20261029.json\` e \`POLICY_G5_CANDIDATO_SUCESSOR_G4_PARA_REVISAO.json\` (não ratificado), este último atualizado apenas nos dois vínculos \`g4.policy_binding\` dos documentos existentes. Imprime diff. G5 V3 é imutável.
- \`finally\`: fecha listener/conexões/subprocessos, remove \`SOLVERIS_B02_POLICY_WRITER_DSN\`, e restaura container se tiver sido iniciado pelo runner e não houver outro cliente ativo.
- Verificação realizada nesta sessão antes de disponibilizar a execução: revisão estática do código do runner, compilação Python e exercício offline da guarda de hashes e da geração das duas vinculações G5, sem Docker/BD.
- **Estado nesta entrega: execução Windows não observada neste chat; não afirmar G4 ativo, não inventar record hashes, não criar G5 final.** A próxima evidência deve ser o resultado terminal verdadeiro da execução autorizada.

## STOP Windows corrigido — integridade V3 (29/10/2026)

- Miguel executou git fetch e git merge --ff-only até b9adc4b47531c994decef4ebb1e5fe64f05429c4, ambos bem-sucedidos.
- O runner terminou em STOP_G5_V3_BYTES_DIVERGENT antes de iniciar o container, estabelecer ligação ou realizar INSERT. Não houve COMMIT nem hashes G4 novos nessa tentativa.
- Causa limitada: divergência entre os bytes do V3 na árvore Windows e os bytes institucionais do Git. Sem prova de que se trate especificamente de CRLF; podem existir mudanças ou filtros locais.
- Correção: verificar o SHA-256 sobre os bytes imutáveis de git show HEAD:POLICY_G5_CANDIDATO_V3_COMPLETO.json, sem tocar no ficheiro Windows. Esperado: 8b3b0cc0a880156b5659166b6878de580b1ddafcf245d811545a0f1ba60500d4.
- O candidato G5 sucessor é preparado a partir dos mesmos bytes Git e somente quatro valores em dois vínculos G4 são substituídos; nenhuma reindentação global.
- O volume passa a ser reconhecido pelo prefixo único confirmado nos diagnósticos do Windows, com paragem obrigatória perante zero ou múltiplos matches.
- Autorização B02-G4-AUTH-MIGUEL-20261029-01 e procedimento aprovado blob 1729e6d62c77510ef4dd7db0af56a6cbe985c168 preservados. Sem nova autorização e sem revisão normativa.
- Estado: ativação G4 continua não executada neste chat; correção validada estaticamente no GitHub, execução Windows ainda pendente.

## Falha na primeira entrada de escrita — causa e correção (29/10/2026)

- Evidência Windows observada: `STOP: AttributeError`, `APPROVED_PROCEDURE_EXIT|2`, `STOP|INDEPENDENT_READ_NO_UNIT`, `CONTAINER|RESTORED_STOPPED`. Não há unidade completa reconciliada nem novos hashes, nem prova positiva de COMMIT. Não repetir INSERT automaticamente sem a correção.
- Diagnóstico em sessão posterior exclusivamente de leitura: `DIAG_EXCEPTION|AttributeError`; traceback: `executar_ativacao_g4_real.py:29` (import), `models_policy_activation_atomicity.py:7`, `models.py:25`, `database.py:259` e `database.py:248 ensure_sqlite_schema_compat`. `DIAG_PYTHON_EXIT|0`, `CONTAINER|RESTORED_STOPPED`.
- Causa confirmada no código do repositório: o procedimento usa `SOLVERIS_B02_POLICY_WRITER_DSN` para o writer, mas o import `app.database` depende separadamente de `DATABASE_URL`; quando ausente e em desenvolvimento, cai em `sqlite:///./test.db` e tenta a compatibilização legada durante o import circular. A falha é anterior à escrita do serviço.
- Correção estritamente no wrapper `tools/b02_g4_authorized_runner.py`: durante `execute_exact_bridge`, passar temporariamente `DATABASE_URL` igual ao mesmo DSN efémero do writer. O import de `app.database` passa ao caminho PostgreSQL, que não executa a compatibilização SQLite. Antes de invocar o G4 autorizado, o wrapper importa serviço e modelos reais e valida o destino (PostgreSQL, base, writer e loopback), emitindo `G4_POSTGRESQL_MODEL_IMPORT_PASS`; erro no import provoca STOP sem entrada na escrita. Em `finally` restaura ou remove `DATABASE_URL`, além de remover o DSN efémero.
- O procedimento G4 permanece com blob imutável `1729e6d62c77510ef4dd7db0af56a6cbe985c168`; nenhuma alteração em `app/database.py`, modelos, migrations, credenciais ou pg_hba.conf. O V3 também permanece intocado. A autorização G4 existente continua a mesma.
- **Execução após a correção ainda não observada neste chat.** Só ratificar G4 quando a leitura independente apresentar `FOUR_RECORDS_RECONCILED` com quatro IDs e hashes verificados. Sem sucesso, não produzir G5 sucessor nem repetir tentativas cegas.

## InternalError após import PostgreSQL — evidência Windows (29/10/2026)

- Checkout Windows sincronizado por fast-forward até `31391c4a00561245a97aba4c858370c3f19a54a4`. Wrapper emite `G4_POSTGRESQL_MODEL_IMPORT_PASS`, provando que o problema anterior de import SQLite já não bloqueia o import.
- Execução G4 aprovada emitiu `mode=EXECUTION_REQUESTED`, depois `STOP: InternalError` e `APPROVED_PROCEDURE_EXIT|2`. Sonda independente emitiu `INDEPENDENT_READ_NO_UNIT`; container `RESTORED_STOPPED`; `RUNNER_EXIT|2`. **Não existe `FOUR_RECORDS_RECONCILED`, não custodiar hashes novos nem gerar G5 sucessor.**
- A classe `InternalError` isolada não identifica o SQLSTATE, a função SQL ou a instrução; não afirmar COMMIT nem causa concreta por suposição. A evidência mostra falha e ausência da unidade no instante da leitura independente.
- Diagnóstico não-mutante reforçado em `tools/b02_g4_attribute_diagnostic.py`: reutiliza a ponte aprovada em ligação única, com `default_transaction_read_only=on` validado antes das consultas. Produz `DIAG_SQLSTATE` e eventuais códigos `B02` delimitados, sem DSNs ou SQL completo. Não constitui execução G4, não autoriza tentativa de escrita nem altera o blob aprovado.
- **Regra imediata:** não repetir `tools/b02_g4_authorized_runner.py` até causa concreta esclarecida e correção cirúrgica avaliada. Preservar autorização G4 já existente.

## Passos posteriores (não iniciar)
1. **Não repetir o preflight físico nem solicitar nova autorização.** Executar o runner autorizado no Windows pelo percurso de loopback anteriormente validado. Só aceitar resultado da reconciliação independente da unidade completa.
2. O runner utiliza a autorização existente e executa o procedimento aprovado uma única vez; em resultado incerto, apenas leituras independentes. Não repetir INSERT automaticamente.
3. Custodiar exclusivamente o resultado `FOUR_RECORDS_RECONCILED` (IDs, `execution_hash`, `activation_hash`, `generation_hash`, `outbox_hash`, `outbox_payload_hash`, `scope_hash`, `policy_hash`). Não inferir sucesso por um INSERT isolado ou ACK.
4. Apenas depois, preparar **novo candidato G5 sucessor**, atualizando as duas vinculações documentais `g4.policy_binding.policy_activation_id` e `policy_activation_record_hash` com os valores observados, e referenciar execução/geração/outbox conforme contrato G5 efetivo. Preservar V3, obter revisão segregada e nova decisão institucional antes de o considerar final.
5. Os três testes integrados G5, instalação 0064/0065, assinatura real e operação continuam pendentes. B02 não fechado.
