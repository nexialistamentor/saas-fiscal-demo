# SOLVERIS B02 — R5/R6: procedimento operacional condicionado e interface R7

**Estado:** preparação técnica, sem autorização de DDL, DML, assinatura, COMMIT, GRANT ou B02 CLOSED. Não repetir G4, A2, ORIGIN histórico, 6 CAS, 149 provas ou os 11 testes R7 aceites. Prerequisito da execução: G5 V3/R1 efetivamente aprovado, raiz nativa válida e atos próprios do titular/custodiante.

## R5 — contratos de fonte já preparados

- `migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py` — blob Git `968c092e70e91b6be3d55bfab7a2dd4fc5256669`.
- `migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py` — blob `7f3fbf53217aecfe045280f343982ece5a72d60c`.
- `app/services/enterprise_b02_g5_two_unit_stage.py` — blob `f538cb5665f86e455d1ff57e24174947384602e7`, com `stage_two_real_c3_units` e callbacks reais.
- `app/services/enterprise_b02_noncredential_acquisition.py` — blob `29a2ac01c22ae6c53d86d4b9cb2c07f786d92702`, com `stage_completion`, sem COMMIT.
- `tools/b02_g5_native_pg1710_isolated_build.py` — blob `84c0d93ce1cee9dca663b1e3e28288c294359bf8`. O ELF PG17.10 requer header e hash de raiz G5 V3 independente, não a ROOT documental V2 expirada.
- **Preservar** `tools/b02_g5_v5_atomic_transaction_harness.py` (blob `2b195ee3fd3de0040f813af03e10733953f84b7d`). O CLI possui `LIVE_COMMIT_DISABLED_PENDING_INDEPENDENT_EVIDENCE_GATES` e trabalha com a revisão 0063; não é runner COMMIT da V3 e a guarda não pode ser desativada.

As duas migrações estão em `migrations/candidates/`, fora de `migrations/versions/`; portanto **`alembic upgrade head` não as instala**. A instalação definitiva, se especificamente autorizada, requer um procedimento do instalador competente que fixe blobs, caminho, identidade DB/role, propriedade/ACL de SQL/ELF, cópia imutável, recibo e readback exatos, passando 0063→0064→0065 sem reescrita de histórico ou downgrade.

**Unidades reais exigidas por R5, identificadores apenas PROPOSTOS no corpo V3:**

| Documento | SHA-256 dos bytes CAS | Tamanho | `acquisition_execution_id` | `normative_artifact_id` candidato |
| --- | --- | ---: | --- | --- |
| 1245/2025 (`101202501245`) | `e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832` | 258302 | `B02-G5-101202501245-V3-execution` | `B02-G5-101202501245-V3-artifact` |
| 571/2019 (`101201900571`) | `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d` | 1944929 | `B02-G5-101201900571-V3-execution` | `B02-G5-101201900571-V3-artifact` |

**Entradas de autoridade ainda ausentes:** política G5 V3 final com hash e ratificação próprios, parecer elegível, raízes/mandatos/não revogação/FOUNDER_ORIGIN e sanitização atuais, header/ELF aprovados e hashes, decisão específica de instalação, e para a única transação `approval_id`, `release_id`, `operator_sha256`, `decision_document_sha256`, `key_id` e assinatura Ed25519 do **manifesto calculado pela BD**. Os dois callbacks `build_evidence` e `stage_authenticity` devem usar provas atuais e legitimamente autorizadas, não constantes sintéticas.

**Execução exata, SOMENTE após a autoridade anterior:**

1. Inspeção read-only do mesmo DB `solveris_b02_r4g_test`, role restrita `solveris_b02_writer`, PostgreSQL 17.10, versão Alembic, raiz/ELF, política e cadeia de atos; verificar previamente eventuais `0064/0065` instaladas e one-shot já consumida. Se houver divergência, execução anterior parcial ou COMMIT incerto → **STOP**, readback independente, nunca retry cego.
2. Instalador autorizado aplica as duas migrações com o mecanismo aprovado e verifica `0065_b02_g5_one_shot_real`, as funções e o perfil `REAL_PROFILE_COMPILED_APPROVED_ROOTS`. Não executar a partir do harness V5.
3. Em **uma única transação** `READ COMMITTED`, o chamador real restrito fornece duas estruturas `units` com `document_id`, `binding` (modo `LOCAL_CAS_INCORPORATION`, `synthetic_only=false`), `start`, `read_cas`, `build_evidence` e `stage_authenticity`. Chamar `stage_two_real_c3_units(connection,units=...)`; cada unidade valida SHA/tamanho, faz a cadeia de inserção e autentica FOUNDER_ORIGIN sem fabricar uma nova origem. Erro a qualquer altura → ROLLBACK total.
4. **Após as duas unidades** e na **mesma transação**, chamar a função autorizada `public.b02_g5_reserve_operational_decision(approval_id,release_id,operator_sha256,decision_document_sha256)`, cujo valor retornado vincula `assigned_txid`. Nunca inserir diretamente na tabela, fazer UPSERT ou reservar fora desta transação.
5. Obter `public.b02g5_capability_manifest()` dos **dados reais do servidor**, agora incluindo reserva, documentos e autoridade. O assinador competente fornece `{key_id,signed_message_base64,signature_base64}` apenas como transporte da assinatura matemática desses bytes. A GUC **local à transação** `solveris.g5_signed_capability` não concede autoridade: `b02g5_assert_transaction_capability()` compara os bytes recomputados e a raiz Ed25519 compilada; o callback nativo `PRE_COMMIT` deve validar novamente. Somente após todas as guardas o COMMIT poderá ocorrer. Nenhum campo é preenchido por presunção.
6. Readback em sessão independente: Alembic e identidade, aprovação one-shot/`assigned_txid`, exatamente 2 execuções e seus vínculos `binding`→`receipt`→`verification`→`terminal`→`normative_artifacts`→`artifact_verification_records`, hashes canónicos, bytes originais e estado do COMMIT. Em caso de ACK incerto: reconciliar **antes** de qualquer ação e jamais repetir automaticamente. A existência do objeto não dispensa o hash.

**Contrato físico R5→R6/R7:** uma prova assinável de `policy_hash`, raiz/ELF, autorização, `approval_id`, `release_id`, `assigned_txid`, DB/role/revisão, COMMIT/readback e, por documento, `document_id`, `acquisition_execution_id`, `normative_artifact_id` **persistido**, `normative_artifacts.record_hash`, `artifact_hash` e byte_size, e os IDs/hashes de `binding`, `receipt`, `verification`, `terminal` e `authenticity`. **Lacuna comprovada:** `stage_completion` retorna somente `receipt_id`, `receipt_hash`, `verification_id`, `artifact_hash`; não retorna `normative_artifact_id` nem o `record_hash` do artefacto. Consumi-los por SELECT exato do registro físico durante o staging e novamente no readback, nunca por promoção do ID de minuta. Nenhuma linha R5 foi emitida nesta preparação.

## R6 — persistência real e cotejo fiscal

Fontes pré-existentes: PDFs custodiados da Res. SEFA/PR 571/2019 e 1245/2025 e a matriz `B02_R6_V29_VINCULOS_CANDIDATOS_20261031.json` (blob `2cbf05b6b91386025524009a70c3bf44835cfc04`). Foco C3 comprovado: **henna até 200 g**, NCM `12119090`, CEST `2000100`, janelas documentais 31/03/2026 e 01/04/2026; não inferir vigência posterior. Vaselina e amoníaco estão na matriz como exemplos, mas sem nova comprovação semântica de item real.

Após receber o recibo R5, um executor autorizado produz pelo mecanismo governado `ExtractionRun` e `ExtractionResult` **conclusivo**, com `normative_artifact_id`, PDF SHA, `extraction_result_id` e `record_hash`. Só depois uma `RuleVersion` imutável com `rule_version_record_id`, `rule_hash`, `record_hash`, `extraction_result_id` e `extraction_result_record_hash`, conteúdo estruturado, vigências, exceções, precedência e revisão/ativação pertinentes. Nenhum INSERT manual de origem ou regra sem ato competente, e não inventar relacionamento canónico de `TabelaMVA` para `RuleVersion` (essa FK não existe). Prover leitura autorizada das tabelas exigidas, sem GRANT improvisado.

Associar um **item NF-e real do caso SEFA/PR** ao PDF/excerto/regra, com XML original e SHA-256 mantidos em custódia privada, chave/ID e nItem, NCM, CEST, CFOP, CST/CSOSN, regime, UF, tipo da operação, data e produto/embalagem; autenticação e exceções devem ser atestadas por quem tem competência. Um XML modelo 55 real foi localizado em fonte privada, mas pertence a operação no PA/NCM não contemplado nos excertos C3; portanto **não é elegível** para este vínculo. Nem o XML nem dados pessoais devem ser publicados no GitHub. Ainda falta XML original real do caso pertinente: solicitar pelo nome completo **efetivamente existente**, não inventado.

**Cotejo já implementado:** `tools/b02_r6_normative_linkage_readonly.py` blob `f303b0c47fe708c07392ad410b6eebae639c0ebd` (último resultado: zero fontes/extracções, SELECT em três tabelas negado); e `app/services/enterprise_b02_normative_binding.py` blob `4b65f6c914d462e9404fc3b85268da5f6cd97f5f`. Este último exige C1/C3/C4/C5/C6/G14/G16/G18 mais `RuleVersion` e `ExtractionResult` reais e devolve **`CANDIDATO_DOCUMENTAL_COTEJADO`**, que não equivale a aplicabilidade legal ou validação fiscal. A decisão fiscal é independente, no âmbito estrito do objeto/UF/data e provas efetivas.

**Recibo R6→R7:** por linha de origem PDF, referência de excerto e hash, artefacto/extracção/regra (IDs e hashes), item real (XML e nItem), base legal, período/alterações, resultado do cotejo e parecer fiscal próprio. Sem item legítimo ou parecer, estado `R6_PENDING`.

## R7 — consumo dos recibos

`tools/b02_r7_v2_readonly.py` é apenas projeção documental: aceita os predecessores G4/A2 e mantém B02 OPEN. A correção **focal** da última aceitação Claude fixou a nova candidata V3 no blob `04df1906f6a463f591bd7b8e38010fe2130aba3d` e preservou o histórico: código atualizado, dois novos testes focais adicionados, **ainda não executados nesta sessão**; não repetir os 11 testes antigos. R7 final exige três recibos independentes G5 V3/R1 + R5 + R6 e decisão própria da autoridade. Não interpretar `B02_R7_V2_READONLY_RECONCILED_NO_RELEASE` como B02 CLOSED.

**Próximos atos reais:** G5 V3/R1 final, aprovação específica de instalação e COMMIT R5, XML NF-e aplicável e aprovação para persistência/revisão fiscal R6; depois decisão R7. Nenhum SQL protegido realizado.
