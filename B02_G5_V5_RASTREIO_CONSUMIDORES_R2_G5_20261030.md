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
