# SOLVERIS B02 G5 V5 — Parecer causal integrado: R2 versus ativação G5

**Corte:** 30/10/2026. **Objeto:** política `SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE` v2, hash `007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf`. **Ponto de partida:** commit `f9734a9a0fdc4aac7a0fb2f94dded9fce5be1e48`. Diagnóstico estático de código e dos pareceres; **nenhuma leitura/escrita nova na base local**.

## 1. Conclusão de aplicabilidade

**Classificação C1 corrigida:** incompatibilidade da evidência da submissão com o contrato do verificador **R2 identificada**; **não demonstrada como requisito de ativação G5**. O caminho de ativação e o SQL específico G5 **não chamam** o verificador R2 nem exigem as suas quatro chaves `policy_subject`, `actor_identity`, `record_evidence`, `technical_author`. Não alterar a decisão `submetida` append-only, não repetir INSERT nem fabricar evidências criptográficas.

O que G5 exige de facto é **cadeia institucional válida**, papéis distintos, hashes de predecessores e decisão **`ratificada`**, mais bootstrap ou superior autorizado, quatro registos atómicos coerentes e, para persistência documental real, os gates próprios das candidatas `0064`/`0065`. A prova do proponente **não substitui** a auditoria ou ratificação ainda não emitidas.

## 2. Matriz causal — chamador real, gate, estado

| Percurso | Chamador / verificador | Requisito confirmado | Classificação |
|---|---|---|---|
| Inserção da submissão | `tools/b02_g5_v5_submission_runner.py` → `public.policy_decisions` → trigger `adr020_validate_policy_decision_chain()` em `migrations/versions/0022_adr020_policy_foundation.py` | `submetida`, `proponente_institucional`, predecessor `NULL`, sujeito exato e hash de registo íntegro | **COMMITTED/reconciliado** conforme log físico do operador |
| Ativação — estágio Python | `app/services/enterprise_b02_policy_activation_atomicity.py::stage_policy_activation()` → `app.models` e SQL `b02p_require_complete()` | writer restrito, policy id/version/hash, `policy_decision_record_hash`, unidade execução/ativação/geração/outbox, atomicidade; sem chamada a R2 | **R2 não é gate direto** |
| Ativação — SQL 0063 aplicada | `migrations/versions/0063_adr020_policy_activation_atomicity.py::b02p_check_authority()` | **`ratificada`**, autoridade constitucional, writer segregado, cronologia, bootstrap manual válido **ou** cadeia superior ativa | **Auditoria + ratificação ainda pendentes** |
| Persistência documental G5 real — SQL 0064 | `migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py::b02g5_require_real_release()` | Quatro eventos em cadeia `submetida→auditoria_iniciada→auditada_favoravelmente→ratificada`, atores segregados, hash predecessor, sem ramos/terminais ambíguos, intervalo, prova G4 atual, sanitização, perfil nativo real | **Candidata não instalada; sem R2 obrigatório neste SQL** |
| Reserva/assinatura operacional — SQL 0065 | `migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py` | Reserva one-shot, vínculos da política, emissão/custódia e perfil `REAL_PROFILE_COMPILED_APPROVED_ROOTS`; prova efetiva de duas unidades | **Candidata não instalada; não autorizada por esta análise** |
| Admissão documental G4 (R2) | `app/services/sefa_pr_documentary_admission.py::admit_documentary_verification()` → `sefa_pr_policy_projection.py::require_current_authority()` → `validate_institutional_chain()` → adaptador `enterprise_b02_institutional_verifier.py` ou `enterprise_b02_founder_runtime.py` | Chaves R2 nas evidências e verificação institucional; a admissão exige `domain='SEFA_PR_B02_DOCUMENTAL'` | **R2 é efetivamente obrigatório para este percurso G4**, não para a ativação G5 |
| Autenticidade de origem SEFA/PR | `enterprise_b02_sefa_pr_authenticity.py::verify_document_authenticity()` → `admit_with_preserved_institutional_proofs()` → G4/R2 | Prova independente autenticada da origem documental | **Permanece como percurso específico de G4** |

**Prova negativa delimitada:** procuradas chamadas a `validate_institutional_chain`, `require_current_authority`, `verify_exact_chain` nos caminhos de ativação acima e nas SQL 0064/0065. A ausência de chamada direta **não significa ausência de gates de autoridade**; as funções SQL fazem validações próprias. Não se afirma análise de funções futuras não publicadas.

### 2-A. Exigências R2 individualizadas

| Campo R2 | Verificador e linha | Chamador que o torna necessário | Aplicabilidade ao G5 |
|---|---|---|---|
| `policy_subject` | `sefa_pr_policy_projection.py::validate_institutional_chain` linha 67 | `require_current_authority` (chamado pela admissão documental G4) | Nenhum chamador demonstrado no `stage_policy_activation`, 0063, 0064 ou 0065 |
| `actor_identity` | mesmo verificador, linha 69 | mesmo percurso G4/R2; adaptador `verify_exact_chain` | Não transportar automaticamente ao G5 |
| `record_evidence` | mesmo verificador, linhas 69 e 81 | mesmo percurso G4/R2 e verificação externa dos pins | Não transportar automaticamente ao G5 |
| `technical_author` | mesmo verificador, linhas 73–74 | mesmo percurso G4/R2, segregação do autor e auditor | Não transportar automaticamente ao G5 |

**Sobre o revisor real:** o JSON imutável V5 ainda nomeia `roles.functional_reviewer=/root/canonical_executor_technical_review`, ao passo que a manifestação nova se identifica `GPT-6/revisor-documental-chat-b02-g5-v5-20261030`. O SQL G5 0063/0064 não exige literalmente que o `actor` da decisão coincida com o campo histórico `roles.functional_reviewer`; exige papel `auditor_independente`, diferença de ator, sequência e hashes. **Isso não autoriza atribuição automática de mandato:** a correspondência de designação entre execução e âmbito deve continuar sustentada pela manifestação emitida e verificada institucionalmente, sem alterar os bytes da política V5.

## 3. Comparação literal da evidência persistida

A submissão física real já reconciliada tem:
- `decision_id=B02-G5-V5-GPT6-submetida-v1`
- `decision_record_hash=dfa49ca6a05fae13e649a04ba795f6bf9f0576151a0b3751a582b903d4599f2a`
- `actor=GPT-6/executor-tecnico-chat-b02-g5-v5-20261029`
- `previous_decision_id=NULL`, `evidence.previous_decision_record_hash=null`
- `policy_record_hash=fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9`

A validação R2 em `sefa_pr_policy_projection.py:61–81` exigiria adicionalmente `policy_subject`, `actor_identity`, `record_evidence`, `technical_author` dentro do JSON `evidence`; **isso não é cláusula da trigger 0022, de `stage_policy_activation`, de `b02p_check_authority` ou da cadeia SQL 0064**. A 0064 exige, para o primeiro evento, precisamente `previous_decision_id IS NULL` e `evidence.previous_decision_record_hash` JSON `null`. Os eventos seguintes devem apontar para ID e `record_hash` de antecessor verdadeiros.

**Decisão de correção:** nenhuma alteração à linha append-only da submissão, ao conteúdo/hashes da política ou aos campos R2 (não exigíveis neste percurso). Proteger a distinção em sete testes focais: `tests/test_b02_g5_v5_r2_applicability_delta.py`. A suite original encerrada **não foi repetida**.

## 4. Segregação do revisor — avaliação de mandato, não de assinatura

Fontes recebidas: `B02_G5_V5_MANIFESTACAO_PROPRIA_INICIO_REVISAO_20261030.json` e `B02_G5_V5_PARECER_DOCUMENTAL_REVISOR_20261030.json`. O revisor identificou-se `GPT-6/revisor-documental-chat-b02-g5-v5-20261030`, aceitou documentalmente o mandato de exame crítico e declarou participação/contexto compartilhados, ausência de credencial criptográfica independente e ausência de acesso direto ao PostgreSQL. Declara não ter redigido V5, o runner ou a submissão.

O V5 fixa `segregation_of_duties.reviewer_not_author_or_integrator=true`, `shared_context_infrastructure_limit_acknowledged=true`, `no_internal_model_identity_or_material_independence_asserted=true`. A **segregação funcional declarada** é compatível em desenho com esse enunciado, mas **não equivale a comprovação independente do facto ou à emissão de `PolicyDecision`**. A trigger 0022 exige `auditoria_iniciada` por `auditor_independente`, ator distinto do proponente; `auditada_favoravelmente` pelo **mesmo auditor**, seguida de `ratificada` por autoridade constitucional final distinta. Os pareceres atuais declaram explicitamente **zero eventos SQL de auditoria emitidos**, portanto não podem ser promovidos automaticamente.

**C2 reclassificada:** o R2 não impõe aqui, por si, uma chave segregada ao auditor G5. A condição que permanece é a **atribuição legítima, exame próprio e eventos institucionais emitidos pelo auditor**; não inferir competência apenas de etiqueta funcional, nem inventar auditoria positiva/negativa.

## 5. Gates que efetivamente permanecem abertos

1. Aceitação/documentação própria do revisor já recebida **para revisão documental**; falta seu ato próprio `auditoria_iniciada` no SQL e exame institucional/decisão subsequente. Não substituir a decisão do revisor.
2. **Ratificação SQL `ratificada`** de Miguel: a ratificação documental já recebida não autoriza emissão artificial nem retroativa do evento antes de auditoria favorável.
3. Bootstrap/superior válido, evidência física segregada e integrações de autoridade; `stage_policy_activation` não cria esses registos, e o harness atual proíbe `--commit` vivo enquanto os gates faltarem.
4. Candidatas 0064/0065, binário/raízes/header, custódia Ed25519, backup/restauro, ACL, sanitização real e one-shot: **sem homologação/instalação por este parecer**.
5. A janela material imutável V5 `2026-10-29T13:00:00Z` → `2026-10-30T13:00:00Z` é distinta do mandato até 08/11. Nenhuma ação posterior ao prazo pode invocar a política como vigente; sem extensão silenciosa.

## 6. Fecho técnico

**C1 = incompatibilidade R2 real, mas bloqueio de G5 indevidamente transportado e removido do diagnóstico.** **C2 = identidade/aceitação documental de revisor registadas, sem evento institucional SQL próprio ainda.** **C3 = gates operacionais independentes preservados.**

Trabalho executado: rastreio de chamadas Python/SQL, separação do domínio G4/R2, testes estáticos focais e reconciliação documental. **Sem DML, DDL, assinatura, new root, deploy, alterações G4 ou MEI.** Política e `submetida` permanecem COMMITTED. **B02 OPEN; B03 BLOCKED.**

## 7. Proveniência e continuidade do auditor após COMMIT do início

**Rastreio executado em 30/10/2026:** o emissor documental original da declaração e do aditamento é uma **outra conversa**, a instância funcional `GPT-6/revisor-documental-chat-b02-g5-v5-20261030`. Esta conversa, de execução técnica proponente, **não é a emissora revisora** e não pode produzir o resultado com o seu identificador.

**Originais pinados no Git:**
- `B02_G5_V5_MANIFESTACAO_PROPRIA_INICIO_REVISAO_20261030.json`: identificação, aceitação, conflitos e participação anterior declarados pela execução revisora, preservado na Biblioteca do utilizador.
- `B02_G5_V5_ADITAMENTO_PROPRIO_G5_REAPRECIACAO_20261030.json`: commit `061daa7c3af1c496bbcd06bc7519b6035af1b640`, Git blob `93cead223b473998d816ba8e6a09e58b56a5c94f`; explicita contribuição anterior limitada a ferramenta read-only e não reivindica identidade material permanente.
- `B02_G5_V5_AUDITORIA_INICIADA_DECLARACAO_PROPRIA_20261030.json`: commit `8b1dff286ea09529ade4dc30c09456639a4e0929`, Git blob `d17ac2ba04be468b92285e76774737c29a3a36df`; ato próprio `auditoria_iniciada`, ainda sem resultado.
- `tools/b02_g5_v5_institutional_audit_start_runner.py` fixa essas duas evidências e o `actor` revisor, sem substituir a identidade pelo proponente; o operador local persistiu e reconciliou pelo papel `solveris_test`, com releitura `solveris_b02_policy_writer` (prova reportada no comentário PR #26 `6527016818`).

**Início SQL reconciliado, conforme log local comunicado pelo operador:**
- `decision_id=B02-G5-V5-GPT6-auditoria-iniciada-v1`;
- `record_hash=da26dccf706582ef71868a6523d286e1bfe3aeae7b0272e3b8bd6a89ff8608d3`;
- `previous_decision_id=B02-G5-V5-GPT6-submetida-v1` / `previous_decision_record_hash=dfa49ca6a05fae13e649a04ba795f6bf9f0576151a0b3751a582b903d4599f2a`;
- política G5 V5 v2, `policy_hash=007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf`.

**Resultado próprio ainda não emitido.** A trigger aplicada `migrations/versions/0022_adr020_policy_foundation.py::adr020_validate_policy_decision_chain` obriga `auditada_favoravelmente` **ou** `auditada_desfavoravelmente` a suceder a `auditoria_iniciada` com **mesmo `actor`** e `institutional_role=auditor_independente`; a 0064 candidata reforça a cadeia sem ramos, quatro eventos e atores distintos. Não criar segundo início para outro auditor nem mutar a linha existente: o contrato atual não demonstra substituição de ator compatível com o mesmo encadeamento. Como a emissora foi localizada, **não se iniciou substituição** nem um expediente novo.

**Encaminhamento à execução revisora original:** deve concluir por exame próprio e emitir parecer fundamentado com a mesma identidade funcional, contendo a decisão favorável ou desfavorável que a sua evidência sustente. A emissão documental do resultado **precede** qualquer inserção, que terá de respeitar o predecessor/hash exatos, cronologia e reconciliação. A análise R2 já foi delimitada e não pode ser reaplicada como bloqueio G5 por inferência. Não solicitar identidade permanente ou chave criptográfica G4 ao revisor; não atribuir assinatura de Miguel.

**Relógios separados:** mandato revisor até `2026-11-08T00:00:00Z`; política material V5 até `2026-10-30T13:00:00Z`, já expirada ao corte desta secção. O exame documental pode prosseguir dentro do mandato sem supor direito de operação retroativa. Proibida qualquer ativação/instalação baseada em janela expirada. O comentário no PR é canal de entrega documental compartilhado, **não prova de leitura pela execução revisora original**.

**Preservação:** nenhuma escrita nova SQL, política e submissão COMMITTED intactas, G4/MEI intocados, testes anteriormente encerrados não reexecutados.

## 8. Inventário físico de versões e matriz original de fecho B02

**Ferramenta única publicada e EXECUTADA no Windows:** `tools/b02_g5_v5_current_inventory_readonly.py` usa `b02_g5_v5_local_bridge.py` com sessão SQL `READ ONLY`, verifica leitor restrito e consulta versões 1/2, decisões, bootstrap, ativações, execução, geração, outbox, intervalo, hashes, identificadores, TXID quando presente, rotinas nativas e existência de reserva one-shot. Prova física 2026-10-30T16:51:33.765376Z, `solveris_b02_r4g_test`, leitor `solveris_b02_policy_writer`, PostgreSQL 17.10; zero escritas. Se futura tabela one-shot negar SELECT ao leitor restrito, o resultado marca **não legível**, sem elevar privilégios.

| Objeto | Âmbito/evidência já disponível | Conclusão atual |
|---|---|---|
| G4 | `B02_G4_RESULTADO_RECONCILIADO_OUTUBRO_20261029.json`: txid `926`, ativação `B02-05ede-activation-v3`, hash `504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4` | **Reconciliado no âmbito G4**, sem delegação automática G5 |
| G5 V1 | Hash `57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa`; ativação física `B02-57982-activation-v1` com record_hash `0ccc9f90b9f338d14548189d48612e220b3b7b673e9e99c5aa55a9b4cdfb0ac2`, TXID `920`; intervalo até 23/10 às 07:56:30 UTC | **ATIVADA HISTORICAMENTE, REGISTO PRESENTE, INTERVALO EXPIRADO**; `state=activa` não dá autoridade temporal atual |
| G5 V2 | Hash `007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf`, política `B02-G5-V5-policy-v2`, `record_hash=fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9`; duas decisões SQL de hash válido | **ZERO ativações, bootstrap, execução, geração ou outbox** na consulta física atual; resultado de auditoria e ratificação SQL ainda ausentes |
| Instalação G5 | `alembic_version=0063_adr020_policy_activation_atomicity`, `native_symbols=[]`, `one_shot_table=false` na leitura física 30/10 16:51Z | **0064/0065 não instaladas no alvo observado**; sem funções nativas G5 nem tabela one-shot |
| Binário G5 | C e header históricos em `native/g5/historical_20261022/`; root original V1 expirada, não há ELF sucessor aprovado | **Não homologado** para V2 ou futuro V3 |
| One-shot real | V30 sintético comprovou concorrência e ACK simulado nos seus limites; nenhum comprovativo de duas unidades reais atual | **Operação protegida não demonstrada** |

**Matriz de fecho original recuperada:** `SOLVERIS_B02_HANDOFF_EXECUTOR_V31_20261024.md`, secção 11. Não substituir os critérios por novo checklist.

| Gate original | Saída exigida | Estado com prova atual |
|---|---|---|
| R1 | Prova nativa V31 no Docker Windows com binário exato, incluindo negativos, recuperação e evidência primária | Ensaios V30 sintéticos preservados; **sem homologação V31/ELF sucessor PG 17.10** |
| R3 | Sucessores temporais aprovados pelo titular, decisões, operador, raiz/binário e hashes coerentes | Plano `B02_G5_V5_SUCESSOR_TEMPORAL_PLANO_CONDICIONAL_20261030.json`; janela nova **não decidida** |
| R4 | Preparação protegida, identidade, migração/ACL, backup privado e restauro em descartável, confiança e sanitização | **Pendente prova física atual**, não reutilizar V13 como backup privado atual |
| R5 | 0064/0065 no alvo, duas unidades reais, reserva PRE_COMMIT/COMMIT, one-shot, prova atómica e reconciliação independente | **Não comprovado**; nenhum COMMIT operacional inferido de testes ou de início de auditoria |
| R6 | Pertinência normativa por item, vigência/alterações/revogação e vínculo norma→RuleVersion→item | **Não comprovado**, sem redução da prateleira Enterprise |
| R7 | Centro de Comando/Miguel ratificam fecho somente com provas R1–R6 | **B02 OPEN; B03 BLOCKED** |

**Rastreio temporal específico V5:** há **nove campos de identidade/tempo** diretamente afetados pela proposta de versão sucessora: `policy_version`; `declared_material_applicability.from/until`; `rules.b02_noncredential.security.g5_release.from/until`; `documents[0].g4.valid_from/valid_until`; `documents[1].g4.valid_from/valid_until`. Mudar os últimos quatro sem autoridade G4 efetivamente vigente produziria falsa validade. O próximo hash canónico permanece **indeterminado** até a versão livre, os vínculos reais e a janela decidida por Miguel.

**Verificação de capacidade nativa deste executor:** o ambiente de trabalho aqui disponível anuncia PostgreSQL **17.11** e não contém `postgres.h` do servidor. Não serve para homologar o ELF de **17.10** no Docker Windows alvo. A compilação e o ensaio de backup/restauro do protegido exigem o runtime físico; não foram fingidos.

**Regra de fecho:** uma alegação de `G5 ativado` é `NAO_DEMONSTRADA` sem `activation_id`, hash válido, decisão `ratificada`, intervalo e transação coerente na **base correta**. Não afirmar que um registo físico desapareceu sem esse inventário; não confundir rollbacks, perfis sintéticos e provas protegidas.

## 9. Prova física reconciliada 30/10 — ativação histórica V1 distinta de V2

**Fonte primária apresentada pelo operador (ficheiro de saída local nesta conversa):** `Texto colado(20261030-165201).txt`, SHA-256 integral `477d4ac1c724908bf8aa1f2d9786394b34ccfe20edc0725fea7b1774c58895e1`. Consulta `2026-10-30T16:51:33.765376Z` ao PostgreSQL **17.10**, `solveris_b02_r4g_test`, `session_user=current_user=solveris_b02_policy_writer`, revisão `0063_adr020_policy_activation_atomicity`, `database_writes=0`. Testes focais no Windows: **7/7 R2-G5, 5/5 auditor-result, 6/6 physical-inventory**; não provaram operação real ou assinatura.

| Elemento físico | G5 V1 histórica | G5 V2 atual |
|---|---|---|
| `policy_hash` | `57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa` | `007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf` |
| `policy_record_hash` | `705c7e2879abb37069f65eb39b544aa3028fc4b0dea282e60d3dd1628046171d` | `fa3e4684b32b1bba38f975493f19f182aa77fe2f80a13563198ace7357b992e9` |
| Decisões | `submetida → auditoria_iniciada → auditada_favoravelmente → ratificada` | `submetida → auditoria_iniciada` |
| Ativação | `B02-57982-activation-v1` | **nenhuma** |
| Hash ativação | `0ccc9f90b9f338d14548189d48612e220b3b7b673e9e99c5aa55a9b4cdfb0ac2` válido | n/a |
| ID/hash execução | `B02-57982-execution-v1` / `1434149d1b3dc9593bbe51e6f1fbd170c32deaa29e2437eb0ff1b6e40b36ddf1` | n/a |
| ID/hash geração | `B02-57982-generation-v1` / `1ae64d751814014ce598858a572d0cfaf12e108b2f025985e6eb7ef118a5116f` | n/a |
| ID/hash outbox | `B02-57982-outbox-v1` / `9694b41258dbc43339d4b77a1b85457d0e20cff425f5b349f97c537a29bf140f` | n/a |
| TXID execução/ativação/geração/outbox | **`920` comum** | nenhum |
| `state` atual na tabela | `activa` (registo histórico) | ausência |
| Validade material | até `2026-10-23T07:56:30.910737Z` | até `2026-10-30T13:00:00Z` |

A G5 V1 ficou **historicamente ativada e reconciliada na mesma transação**, mas essa transação não constitui liberação documental protegida one-shot e o intervalo da ativação expirou; a coluna `state=activa` não prolonga vigência temporal. Não houve desaparecimento de ativação. A G5 V2 tem `activation_count=0` efetivamente verificado; isso difere de "não encontrei documento de ativação".

**G4 txid 926:** `B02-05ede-activation-v3`, hash `504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4`, intervalo `2026-10-29T13:00:00Z → 2026-10-30T13:00:00Z`. Preservada como evidência, mas também expirada à hora da consulta. Não delega nova autoridade G5.

**Estado de instalação no mesmo alvo:** `alembic_version=0063`; nenhuma função G5 nas `native_symbols` pesquisadas; `one_shot_table=false`; `one_shot_reservations=null` porque a tabela não existe. Logo, a operação G5 de duas unidades reais não foi demonstrada e **não poderia ser inferida dos quatro registos da V1**.

**Sucessor temporal:** V3 é a próxima versão livre **fisicamente observada**, não uma janela aprovada. A proposta condicionada mantém os nove campos afetados e a dependência de G4 prospectivamente válido. Não alterar hashes, linhas ou limites V1/V2; não alegar homologação de binário ou backup privado.

**R1–R7:** sem fecho de R1 nativo real, R3 temporal, R4 preparação protegida/backup, R5 one-shot real, R6 norma→RuleVersion→item e R7 ratificação final. B02 **OPEN**, B03 **BLOCKED**.

## 10. Preparação nativa e ligação normativa (corte 30/10/2026)

**R1:** foram adicionados `tools/b02_g5_native_pg1710_isolated_build.py` e `tests/test_b02_g5_native_pg1710_isolated_build.py` (sete testes novos, **não executados**). O compilador exige header sucessor distinto do histórico, SHA-256 fixo, hash de política sucessora diferente das V1/V2 expiradas e versões `pg_config` e `postgresql-server-dev-17` efetivamente 17.10. Compila apenas num Docker isolado; inspeciona ELF/símbolos e SHA-256, retira container/imagem temporários e não monta o volume protegido. **Sem header exato e aprovado não há build; sem execução física não há ELF nem homologação R1.** O script `COMPILAR_CANDIDATO_ISOLADO_SEM_INSTALAR.ps1` histórico já existe na Biblioteca, mas traz raiz/código V1 e não legitima root V3. Mantêm-se os ensaios V13–V31 nos limites antes documentados.

**R6:** foram adicionados `tools/b02_r6_normative_linkage_readonly.py` e `tests/test_b02_r6_normative_linkage_readonly.py` (cinco testes novos, **não executados**). O leitor liga diretamente os dois hashes SEFA/PR (101202501245 e 101201900571) a `normative_artifacts`, `extraction_results`, `rule_versions`, `normative_relation_versions` e `tabela_mva` em **READ ONLY**, com papel documental `solveris_b02_writer`. Privilégios insuficientes causam relatório de inacessibilidade, não GRANT; formato do hash de artefacto não é apresentado como prova de canonicalização `PolicyDecision`. Qualquer candidato encontrado é apenas **evidência de vínculo documental a investigar**, nunca prova automática de vigência, CEST, produto, incidência, crédito ou venda.

**Referência oficial observada nesta pesquisa:** o portal da Secretaria de Estado da Fazenda do Paraná, página `https://www.fazenda.pr.gov.br/Pagina/Legislacao`, lista a **Resolução SEFA nº 571/2019** como legislação vigente para MVA/Substituição Tributária, contrapondo-a à Resolução 020/2017 anterior; a página `https://www.fazenda.pr.gov.br/Pagina/ICMS-Substituicao-tributaria` repete essa classificação. Essa informação oficial é **um índice público**, não certifica ausência de alterações/revogações parciais, conteúdo consolidado completo, vigência de cada item/NCM ou aplicabilidade fiscal de um contribuinte. O R6 continua dependente da cadeia normativa integral e da prova norma→`RuleVersion`→item real.

**Outros critérios:** R3 aguarda janela material concreta e sucessores G4/G5 coerentes; R4 continua a exigir backup/restauro privado físico, ACL e custódia; R5 não tem 0064/0065, raiz, assinatura ou one-shot real; R7 continua não emitido. **B02 OPEN, B03 BLOCKED**. Nenhuma reexecução histórica, SQL de escrita, chave, extensão temporal, operação protegida ou homologação nativa foi realizada por estes dois novos utilitários.
