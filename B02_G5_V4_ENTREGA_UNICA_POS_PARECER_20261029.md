# SOLVERIS Enterprise B02 — entrega única após parecer G5 V4

**Estado: PROPOSTA CONSOLIDADA, NÃO EMITIDA, SEM AUTORIZAÇÃO DE INSTALAÇÃO OU OPERAÇÃO.**
**Objeto de revisão fixo:** PR #26, commit `909fd78b2db6add6727f834a0abf189511eddf47`. Esta entrega é posterior ao objeto fixo, não modifica o V4, não constitui revisão GitHub independente e não é aprovação criptográfica/física.

## Adenda causal obrigatória — colisão `policy_version=1` confirmada fisicamente

**Observação PostgreSQL somente leitura, 29/10/2026:** na base `solveris_b02_r4g_test`, `policy_versions` já possui `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, `policy_version=1`, `policy_hash=57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa`, `record_hash=705c7e2879abb37069f65eb39b544aa3028fc4b0dea282e60d3dd1628046171d`. `RUNNER_EXIT=0`, sem alterações; a versão 1 não pode ser reinserida porque `app/models.py:PolicyVersion` exige unicidade `(policy_id,policy_version)`. Trata-se de falha de identidade objetiva não abrangida pelo parecer V4: **não ratificar nem tentar inserir o V4 com versão 1.**

**Correção mínima preparada, sem substituir o V4 revisto:** `POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json`, com uma única alteração semântica ao V4 congelado: `$.policy_candidate_body.policy_version: 1 → 2`. Não alterar os dois `g4.policy_binding.policy_version=1` (referem-se à política G4 distinta), nem testes, PDFs, SQL 0064/0065, raízes, intervalos ou outros campos. O V4 mantém o SHA-256 `2dd00187b3348847a4deb845167d4554749aaa71cdce8556a03163ea1f4f252e` e o blob `b8538623a53ff4f75a78f44454751259ccfb943e`.

**Identidade do novo objeto preparado, ainda NÃO RATIFICADO:**

- Ficheiro V5 completo SHA-256: `bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9`.
- Blob Git V5: `87dd0560d842f8b9f20d808363496fa60786710c`.
- Corpo `policy_candidate_body` em `canonical_bytes` SHA-256 candidato: `007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf` (12268 bytes). O SHA do ficheiro e o SHA do corpo são objetos diferentes. O contrato de hash canónico da política e respetivos campos armazenados deve ser confirmado no ato/inserção ratificados; nenhum destes valores é automaticamente uma assinatura ou um `record_hash` do banco.
- O corpo V4 canonicalizado, apenas para comparação, foi `e35576a437d4f7b1868e281914e878331624106d6e50f4ee7a4e91289933e0d6`; **não usar no sucessor V5**.

**Revisão limitada necessária:** submeter ao revisor somente a correção causal de versão `1→2` e esta prova física, preservando o parecer técnico V4 favorável condicionado como histórico. A apreciação do V4 **não é uma ratificação implícita do V5**; Miguel deverá decidir sobre a identidade canónica **V5 versão 2** e o novo hash, depois de validação do delta, sem mais um conjunto de fichas.

**Compatibilidade estática focal:** as migrations candidatas 0064/0065 procuram `policy_id`, `policy_version`, `policy_hash` efetivos e não contêm uma restrição literal `policy_version=1`. A mudança não demonstra funcionamento físico e não dispensa os quatro gates B1–B4. A janela 29–30/10 é **apenas proposta**, não autoriza operação nem extensão de G4.

---

## 1. Decisão e limites do parecer recebido

Parecer técnico documental recebido: **FAVORÁVEL CONDICIONADO** ao desenho G5 V4; o autor declara a identidade funcional GPT-6 e participação anterior no G4/G5, **sem independência material demonstrada**. Aceite apenas como contribuição técnica ao processo decisório. Não é aprovação formal segregada, não aprova um ELF futuro e não autoriza instalação.

**Quatro bloqueios reais, sem multiplicação de atos:** B1 (autoridade/revisão do objeto canónico), B2 (vigência/revogação da chave e G4), B3 (nova raiz/ELF específico), B4 (backup/SQL/one-shot/sanitização e COMMIT). Estes quatro são reunidos no mesmo instrumento de deliberação e na mesma sequência abaixo. Os atos de efeitos diferentes precisam de comprovação específica no instrumento único; não há autorização tácita entre etapas.

**Provas imutáveis reutilizadas**: G4 quatro registos `FOUR_RECORDS_RECONCILED`, transaction ID `926`, ativação `B02-05ede-activation-v3`, hash `504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4`; fonte `B02_G4_RESULTADO_RECONCILIADO_OUTUBRO_20261029.json`. Não repetir execução nem testes G4. PDFs SEFA/PR: `101202501245`, 258302 bytes, SHA-256 `e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832`; `101201900571`, 1944929 bytes, SHA-256 `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d`.

O V4 `POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V4_PARA_REVISAO.json`, blob Git `b8538623a53ff4f75a78f44454751259ccfb943e`, tem SHA-256 do **ficheiro completo** `2dd00187b3348847a4deb845167d4554749aaa71cdce8556a03163ea1f4f252e` (recalculado no parecer). Este SHA **não é o policy_hash canónico do corpo** e não deve ser escrito no campo `g5_policy_binding.policy_hash`. O corpo é `policy_candidate_body`, com `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, `policy_version=1`, `policy_type=activation_authority`. A identidade, serialização e hash operacionais do corpo serão apurados pela mesma autoridade de canonicalização/record hash usada pelo motor (`app/services/enterprise_b02_noncredential_acquisition.py:canonical_bytes` e o contrato da tabela `policy_versions`), confrontados com os bytes efetivamente ratificados e aceites pelo PostgreSQL **antes de vincular header ou assinar**. Se algum campo institucional do predecessor persistir sem validade no sucessor, corrigi-lo por delta aprovado e novo objeto/hash; não carimbar o hash anterior.

## 2. Minuta única de deliberação — decisões reservadas a Miguel

> **MINUTA — NÃO EMITIDA.** 
>
> **Objeto e alcance:** Examino exclusivamente a política G5 V4 acima, no âmbito de persistência documental SEFA/PR dos dois PDFs fixados; a SOLVERIS Enterprise mantém ambição nacional, mas esta decisão não autentica outras fontes nem autoriza venda, MEI ou fiscalidade nacional.
>
> **Revisor e conflitos (a obter do próprio revisor):** identidade/competência [PENDENTE]; papel e mandato para o hash exato [PENDENTE]; aceitação e conflitos [PENDENTE]; grau demonstrável de segregação material [PENDENTE]; parecer assinado ou documentado do sujeito legítimo e sua referência/hash [PENDENTE]. O parecer técnico GPT-6 recebido é condicionado e não prova separação institucional.
>
> **Decisão de Miguel sobre o corpo canónico:** [RATIFICO / REJEITO / DEVOLVO PARA CORREÇÃO]; `policy_id`, `policy_version`, `policy_hash` canónico derivado, `decision_id`, `decision_record_hash`, modalidades, escopo, evidências/limites e norma da autoridade [FIXAR EM ATO EFETIVO]; data/hora e autoria identificável [PENDENTE]. **V4 inteiro SHA-256 não substitui estes valores.**
>
> **Janela:** V4 propõe `2026-10-29T13:00:00Z` até `2026-10-30T13:00:00Z`. Ratificação posterior não produz efeitos retroativos. O G4 físico possui o mesmo intervalo; **depois de 2026-10-30T13:00:00Z não há cobertura G4 presumida**. Nova janela para instalação/consumo dependerá de percurso institucional temporal G4/G5 próprio e coerente, sem alterar relógio nem repetir exames de origem.
>
> **Chave pública:** Ed25519 raw `ab8dc926512061fee370dfcabc5f11752229c6583546a65592c97ce24c6ae381`, fingerprint SHA-256 DER/SPKI `6f0ede1267a208505b2443d765cf97f2206759049f938a1d95d92a86c4c5d63c`; continuidade histórica verificada **apenas quanto aos bytes públicos**. Custódia atual [PENDENTE]; não revogação [PENDENTE]; direito de utilização para o objeto G5 atual [PENDENTE]. Não gerar nova chave por defeito nem exportar a privada.
>
> **Autorização de implantação:** NÃO CONCEDIDA por esta minuta. Só habilitável após parecer suficiente, ratificação, ativação G5 real, header aprovado, hash de novo ELF compilado/verificado, backup/restauro, identidade física do servidor, ACL e revisão de SQL 0064/0065. Os identificadores de cada artefacto e provas devem ser anexados ao **mesmo ato de autorização** antes da execução, e Miguel deve aceitar expressamente esses hashes e o alvo. Nunca considerar aprovado hoje um binário ainda por gerar.
>
> **Autorização da operação one-shot:** NÃO CONCEDIDA por esta minuta. Uma única operação protegida, assinada e vinculada a dois PDFs, aos respetivos recibos e ao `txid` gerado dentro do PostgreSQL será autorizada especificamente com a manifestação, assinatura e evidências atuais. Nem ativação G4 nem instalação 0064/0065 concede automaticamente a capacidade de assinatura/COMMIT.

## 3. Contrato exato do header sucessor — preparar sem inventar raiz

Usar os fontes originais recuperados, imutáveis e versionados: `native/g5/historical_20261022/b02_precommit_guard.c` SHA-256 `ea0f49d9d686bb9dc33a041b85473f734b41b76236411ce4f7942f47538ad278`; `native/g5/historical_20261022/b02_g5_native_signature.c` SHA-256 `83fbffa030ed861c4f7e70f654db5179574d986e0cab8f21cf657054ceb4b669`. O header histórico SHA-256 `ff513972cd19d123af9d1a85b1b57f76c0935c18c5bc172b07722972bbe254cd` é **incompatível e expirado**: contém `policy_hash=57982f46…`, `B02-57982-activation-v1`, 22–23/10. Preservar, não instalar nem substituir em silêncio.

O novo `b02_g5_approved_roots.h` será um **novo artefacto**, no formato real já previsto em `B02G5NativeRoot`: `key_id`, Ed25519 public key de 32 bytes, `constraints_json`, `valid_from`, `valid_until` e `B02_G5_NATIVE_ROOT_COUNT`. Não haverá root de teste/fallback nem injeção por ambiente.

| Campo/ligação da raiz | Conteúdo já comprovado | Depende de prova/ato atual |
| --- | --- | --- |
| `capability_root_id` / `key_id` | Identificador histórico candidato `SOLVERIS-B02-SEFA-PR-G5-COMMIT-MIGUEL-V1` | Ratificar a capacidade atual; ID histórico não reabre autoridade |
| Chave pública Ed25519 | raw `ab8dc926512061fee370dfcabc5f11752229c6583546a65592c97ce24c6ae381` | Custódia/estado de revogação e autorização atual |
| `documents` | Dois IDs, tamanhos e hashes exatos acima | Inspeção/recibos/sanitização efetivos ao operar |
| `g4_verifier` | `SOLVERIS_B02_SEFA_PR_FOUNDER_ORIGIN` v1, hash `fab019b18d21f8e47e59ff96fd783dc9732cc3ae1d6e1ed429bddf957f0b9472` | Vigência e efeito atual da evidência G4 para a transação |
| `g5_policy_binding` | `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, tipo `activation_authority`, versão 1 | `policy_hash` canónico, `decision_id`/`decision_hash` G5 e `policy_activation_id`/`policy_activation_record_hash` **G5 novos e reais**. Nunca usar G4 como ativação G5 |
| `release_policy_hash` | Ocorre nas constraints históricas | Hash canónico **G5 atual**, não `2dd00187…` sem prova |
| `server` | Base `solveris_b02_r4g_test`, writer documental `solveris_b02_writer` | Revalidar `system_identifier`, OIDs da base e do writer; os pins históricos não bastam. O writer G4 `solveris_b02_policy_writer` é distinto |
| `schema`, `audit_scope`, `synthetic_only` | `B02_G5_TX_RELEASE_V1`, `SEFA_PR_B02_DOCUMENTAL_G5_PERSISTENCE`, `false` no contrato histórico | Conferir compatibilidade do manifesto SQL vigente |
| `valid_from`/`valid_until` | Janela V4 apenas proposta | Ato temporal G5/G4 válido no instante de emissão e utilização; sem retroatividade |

A biblioteca verifica `constraints_json` como subconjunto do manifesto e campos críticos com igualdade exata; o SQL de `b02g5_capability_manifest()` e `b02g5_precommit_validate()` recalcula os bytes transacionais. Por isso a próxima raiz tem de usar as **pré-imagens do mesmo esquema canónico** que o PostgreSQL realmente irá assinar/validar, não um JSON inventado fora do motor.

## 4. Procedimento controlado — compilar, homologar, instalar 0064→0065

**Fase A — preparação sem efeitos protegidos:** conferir o parecer e atos aplicáveis; medir e ratificar as identidades canónicas G5 após corrigir eventuais referências ao predecessor; verificar temporais, status e revogação, os dois PDFs e seus SHA, método e recibos reais. Gerar novo header somente depois de conhecidos/ratificados `policy_hash`, decisão, ativação e janela. Criar novo hash SHA-256 do header, manifestar fontes C e ABI esperada; tudo com rastreio Git. Se houver novo conteúdo, apresentar um único diff à autoridade, não reabrir G4.

**Fase B — compilação em descartável:** builder PG **17.10** da mesma arquitetura/ABI de PostgreSQL, sem montar o volume da base protegida, sem credenciais/privadas, com flags compilação C `-Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared`, fontes `b02_precommit_guard.c` + `b02_g5_native_signature.c`, linker `-lcrypto`, header novo aprovado. Verificar símbolos `b02g5_register_real_precommit`, `b02g5_assert_signature`, `b02g5_native_profile`, dependências, arquitetura, versão PostgreSQL, `SHA256` do ELF e do header e que a ligação do root não caiu em perfil sintético. Provas técnicas/ELF **submetidas** à aprovação exacta, não aprovadas por simples PASS de compilação.

**Fase C — recuperação, gates e autorização administrativa:** confirmar por inspeção somente leitura identidade física do servidor, PG `17.10`, DB/OIDs/writer, Alembic 0063, ACL/owner dos objetos e funções e ausência de 0064/0065/.so, concorrência, vigência e revogações. Preparar `pg_dump` formato custom privado com hash e `pg_restore --list`; restaurar em **base/container descartável distinto**, testar integridade, funções, ACL, triggers e contagens. Backup sem restauro testado não é gate GREEN. Não expor backups/credenciais em Git. A autorização administrativa de Miguel para o **ELF exato** e bytes exatos da 0064/0065 é necessária antes de qualquer alteração protegida; o ato pode abranger os dois passos sequenciais, mas tem de identificar ambos os SHA e condição de rollback/ACK incerto. Nenhum `GRANT` ou privilégio novo fora da autorização.

**Fase D — instalação física única:** após autorização e na janela aplicável, só administrador OS/DB autorizado escreve `/usr/lib/postgresql/17/lib/b02_g5_native_REAL_CLOSED.so` (exclusividade, hash, proprietário, modo, inode, sem sobrescrever) e promove uma versão **revisada** das candidatas `migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py` e `migrations/candidates/0065_b02_g5_one_shot_real_CANDIDATE.py`, respetivamente `0063→0064→0065`, sob Alembic autoridade única. A migration 0064 instala funções C, locks, validação; 0065 cria `b02_g5_operational_approval_uses`, `b02_g5_reserve_operational_decision`, `b02_g5_assert_one_shot` e vincula o validador ao consumo one-shot. Sem renomear histórico nem aplicar SQL em paralelo ao Alembic. Releitura **independente e somente leitura** confirma revisão exata, perfil da lib, funções/ACL/owners/triggers, artefactos G4 preservados, hash ELF e snapshot. Falha ou ACK incerto: STOP, reconciliação antes de qualquer nova tentativa; não remover ficheiro ou mexer na base para aparentar rollback.

## 5. Operação única G5 — somente após atos, runtime e sanitização reais

- **Pré-condições:** G4 vigente para os dois documentos, política G5 canónica ratificada e **ativada** com hash e estado físico, root atual não revogada, método, assinador local e mandatário aprovados, duas inspeções efetivas e recibos/atestação de sanitização **atuais**; o `outcome=verified_sanitized` previsto no V4 não prova execução.
- **Operador:** sessão segregada `solveris_b02_writer`, transação `READ COMMITTED`, alvo e módulos aprovados. Obter bytes CAS dos dois documentos e comparar tamanho/SHA-256 com os pins. Construir os registos reais de acquisition/mode binding/receipt/sanitization/artifact/verifier vinculados ao **txid** do PostgreSQL na mesma transação, com referências à G4 real e à G5 efetivamente ativada.
- **Reserva:** usar exclusivamente `public.b02_g5_reserve_operational_decision(approval_id,release_id,operator_sha256,decision_document_sha256)` uma vez na **mesma transação**. O `assigned_txid` é o real; chaves únicas em `approval_id`, `release_id` e `assigned_txid` vetam duplicidade. Não antecipar txid de fixture nem criar reserva em transação separada.
- **Assinatura:** motor gera `public.b02g5_capability_manifest()`, canonicalização do PostgreSQL com `g5_one_shot` da 0065; assinador Ed25519 privado **fora do Docker/PostgreSQL** assina exatamente o manifesto canónico recalculado, só após correspondência da chave/root/escopo e mandato. Transportar assinatura e chave pública identificadora no GUC previsto, que **não confere autoridade por si próprio**. `b02g5_assert_transaction_capability()` e `XACT_EVENT_PRE_COMMIT` C verificam a assinatura, timebox, root, servidor, dois documentos, autorização e reserva; a rotina SQL valida e rejeita incoerências.
- **COMMIT e saída:** exatamente **um** COMMIT, sem retry automático. Releitura independente noutra sessão confere `COMMITTED_EXACT` dos dois IDs, bytes/hashes, recibos/inspeção, um único `approval_id/release_id` consumido, `assigned_txid`, hashes e auditoria, além de ACL/revogação de temporários e estado do container/Git. Se ACK incerto, STOP e readback, **não repetir DML**.

## 6. Gates finais e regra de abertura do Bloco 03

| Gate | Estado até esta entrega |
| --- | --- |
| G4 físico / quatro registos | **CLOSED**, txid 926, imutável |
| V4 candidato e parecer técnico documental | **FAVORÁVEL CONDICIONADO**; sem segregação institucional demonstrada |
| Política canónica G5/ratificação/ativação | **NÃO DEMONSTRADAS** |
| Raiz atual, header e binário compilado aprovado | **AUSENTES**; código C histórico recuperado |
| Backup **e restauro** atual comprovados | **NÃO DEMONSTRADOS** |
| 0064 / 0065 em PostgreSQL protegido | **AUSENTES**; último Alembic 0063 |
| Inspeção e sanitização operacionais atuais | **NÃO DEMONSTRADAS** |
| Assinatura e COMMIT real das duas unidades | **NÃO EXECUTADOS** |
| Matriz normativa e aceitação B02 global | **PENDENTES**, não transferir ao B03 |

**Decisão operacional final:** preservar `G4 CLOSED`; `G5 OPEN`; `B02 OPEN`; `B03 BLOCKED`; MEI intocado. Não repetir testes encerrados, não criar nova ficha intermédia, não alterar a janela V4 à pressa, não disparar deploy, não fingir consentimento/assinatura/independência.
