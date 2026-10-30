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
