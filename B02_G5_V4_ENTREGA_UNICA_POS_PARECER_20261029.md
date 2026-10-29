# SOLVERIS Enterprise B02 — entrega única após parecer G5 V4

**Estado: PROPOSTA CONSOLIDADA, NÃO EMITIDA, SEM AUTORIZAÇÃO DE INSTALAÇÃO OU OPERAÇÃO.**
**Objeto de revisão fixo:** PR #26, commit `909fd78b2db6add6727f834a0abf189511eddf47`. Esta entrega é posterior ao objeto fixo, não modifica o V4, não constitui revisão GitHub independente e não é aprovação criptográfica/física.

## 0. Ratificação documental V5 — manifestação recebida, sem autorização operacional

**PONTO DE ENTREGA:** este é o único texto de ratificação preparado para apresentação a Miguel **depois** do aditamento favorável do revisor sobre o delta V4→V5. Não é uma segunda ficha, nem ratificação por este executor. Referência de revisão atual: [PR #26, comentário 6501412721](https://github.com/nexialistamentor/saas-fiscal-demo/pull/26#issuecomment-6501412721). Até prova de aditamento próprio, este texto fica em estado **PRONTO_PARA_DECISÃO_NÃO_SUBMETIDO**.

> **SOLVERIS — ATO ÚNICO DE RATIFICAÇÃO DOCUMENTAL DA POLÍTICA G5 SUCESSORA, VERSÃO 2**
>
> Na qualidade de autoridade institucional final, **Miguel**, examino o objeto **POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json**, identificado pelo SHA-256 dos bytes integrais **bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9**, Git blob **87dd0560d842f8b9f20d808363496fa60786710c**, e o seu corpo **policy_candidate_body**.
>
> O sujeito canónico proposto é **policy_type=activation_authority**, **policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE**, **policy_version=2**. O SHA-256 calculado sobre a serialização canónica do corpo é **007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf** (12268 bytes); **este é um candidato de identidade do conteúdo, distinto do hash do ficheiro e do record_hash da base**. Exijo conferência do contrato canónico e dos bytes aceites pelo motor antes da inserção em policy_versions e antes da assinatura da cadeia.
>
> **Base causal:** a versão 1 dessa política já existe na base solveris_b02_r4g_test com policy_hash **57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa** e record_hash **705c7e2879abb37069f65eb39b544aa3028fc4b0dea282e60d3dd1628046171d**. O V5 diferencia-se do V4 por uma alteração única: **policy_candidate_body.policy_version de 1 para 2**. Não altera as referências dos dois documentos ao G4, cuja política mantém a versão 1.
>
> **Escopo material:** apenas persistência documental das resoluções SEFA/PR **101202501245** (258302 bytes, SHA-256 e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832) e **101201900571** (1944929 bytes, SHA-256 af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d). Preservo G4 **B02-05ede-activation-v3**, hash **504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4**, txid **926**, sem repetição de exame, ativação ou escrita G4.
>
> **Apreciação:** considero o parecer técnico G5 V4 **favorável condicionado**, cujo autor reconheceu participação anterior e **não demonstrou segregação material**. Antes de atribuir eficácia institucional ao V5, apreciarei o aditamento de revisão sobre o único delta 1→2, mantendo expressamente as condições B1–B4 e exigindo qualquer aceitação segregada que a governação e os contratos em vigor efetivamente requeiram. Não transformo um parecer GPT em assinatura institucional independente.
>
> **Janela proposta original, sem antecipação:** de **2026-10-29T13:00:00+00:00** a **2026-10-30T13:00:00+00:00** para declared_material_applicability e g5_release. A ratificação documental pode ser deliberada sobre este objeto exato, mas **não retroage, não prolonga automaticamente o G4 e não habilita operações após o fim dessa janela**. Se a execução não couber em uma janela e cobertura G4 efetivamente vigentes, será necessário percurso temporal atualizado com novo objeto/hash e deliberação correspondente; não se editará a vigência por conveniência.
>
> **Decisão reservada a minha manifestação expressa:** **RATIFICO / NÃO RATIFICO** o corpo canónico **V5 versão 2** nos limites acima, à vista do aditamento e das reservas B1–B4. Esta minuta não é decisão enquanto não existir manifestação identificável de Miguel; o executor não deve preencher a decisão em seu nome.
>
> **Efeitos e exclusões:** eventual ratificação identifica documentalmente o corpo V5 e seus limites. **Não** é por si só: aceitação segregada não demonstrada, inserção em policy_versions, decisão/ativação efetiva do G5 na base, autoridade de novo header/ELF, aprovação de binário futuro, autorização de instalação 0064/0065, GRANT/DDL, assinatura Ed25519, concessão de reserva one-shot, COMMIT documental, validação da sanitização, abertura comercial ou liberação do B03. Cada ato de efeito diferente exige prova exata, e a aprovação administrativa e operacional pode ser consolidada em um só instrumento condicionado a hashes conhecidos e gates verificados, sem recomeçar a cadeia técnica.

**Propagação de identidade obrigatória, depois da decisão real (não antes):**

| Elemento | Versão/identidade correta | Fonte de prova |
| --- | --- | --- |
| Ficheiro V5 submetido | SHA-256 bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9 | Bytes exatos da submissão |
| Corpo V5 | policy_version=2; SHA canónico candidato 007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf | canonical_bytes; hash definitivo pelo contrato de registo |
| policy_versions / policy_decisions / policy_activations G5 | **policy_version=2**, mesmo policy_id e policy_hash canónico final; IDs e record_hash de decisão/ativação G5 **reais** | Atos e inserções institucionais autorizadas |
| native root: g5_policy_binding | policy_version=2 e **decision_hash, decision_id, activation_id, activation_record_hash G5 emitidos**; nunca os do G4 | Hash do header novo após provas reais |
| native root: release_policy_hash | Hash canónico do corpo G5 **realmente ratificado** | Coincidência com tabela e decisão efetiva |
| reservation 0065 / manifesto assinado | policy_version=2 derivada do binding G5 real; txid do PostgreSQL | Precommit e COMMIT único |
| Referências g4.policy_binding em ambos os PDFs | **policy_version=1** mantida | G4 txid 926, sem alteração |

**Preparação executável sem autoridade:** fontes C recuperados e hashes pinados, candidatas 0064→0065 preservadas e sua revisão estática focada concluída; nenhuma restrição literal à versão 1 foi encontrada nas candidatas. Resta gerar header novo apenas após a decisão/ativação reais, compilar ELF específico em descartável PG17.10, realizar backup **e restauro** no alvo autorizado e confirmar ACL/owner/lock e situação de sanitização. Não executar DDL nem DB writes com base nesta minuta.

---

## 0-A. Registo da decisão recebida e pacote de autorização G5 V5

**Manifestação literal de Miguel:** «RETIFICADO, AVANÇA». Não se atribui timestamp certificado, assinatura digital ou conteúdo adicional a esta frase.

**Interpretação previamente comunicada pelo executor:** ratificação **documental** da política sucessora `SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, versão `2`, objeto `POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V5_VERSION_2_PARA_REVISAO.json`, SHA-256 integral `bf7cdb951ac8e4fb8e5b8e2a1aa6fa3095fad194cbd5845a0dc0e20afd7a3ae9`, corpo canónico candidato SHA-256 `007f6e919816365dc78d1c1df53e38a3b802549cdac83f717155d5796cf5ffcf`. A interpretação do executor não é citação literal de Miguel nem autorização de escrita.

**Parecer recebido na conversa:** aditamento técnico V4→V5 FAVORÁVEL CONDICIONADO, delta semântico único `policy_candidate_body.policy_version: 1→2`, com declaração do revisor GPT-6 de participação anterior no B02 e **sem independência institucional material demonstrada**. Não é aprovação formal GitHub. G4 txid 926, versões G4 `1`, documentos, hashes e condições B1–B4 preservados.

**Estado:** ratificação documental recebida; não pedir repetição. Não há prova nesta entrega de que versão 2, decisão ou ativação G5 estejam persistidas. G5 operacional não ativado. B02 OPEN; B03 BLOCKED.

### Primeiro procedimento protegido — política G5 versão 2, decisão e ativação

**Alvo previsto:** PostgreSQL isolado `solveris_b02_r4g_test` no container `solveris-pg17-migration-test`. O alvo deve ser confirmado por leitura física antes de qualquer escrita; nomes conhecidos não provam conectividade, identidade nem autorização.

**Entradas imutáveis:** bytes exatos do JSON V5 e corpo `policy_candidate_body`, `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, `policy_version=2`, hash canónico candidato acima, documentação das duas resoluções SEFA/PR e evidência G4 txid 926.

**Descoberta read-only obrigatória:** identificar o caller real e a assinatura pública do serviço de registo de `PolicyVersion`, decisão de `PolicyDecision` e ativação de `PolicyActivationExecution`, nos modelos `app/models.py`, no serviço `app/services/enterprise_b02_noncredential_acquisition.py` e nas migrations aplicáveis. Identificar campos obrigatórios e identidade do ator **a partir de atos e registos verificáveis**, não de valores supostos. Conferir `alembic_version`, identidade de servidor/base, papéis/ACL, inexistência de `(policy_id,2)`, integridade de G4, status e revogação da chave Ed25519, vigência temporal real e janela G5. Exigir evidência B1 de aceite/segregação aplicável e B2 de vigência e custódia. Se o contrato concreto não puder ser confirmado, **STOP antes de escrita**.

**Sequência condicionada:** (1) registar `PolicyVersion` V5 com bytes e hash conferidos pelo contrato canónico do motor; (2) reconciliar ID, `policy_hash` e `record_hash` persistidos por leitura independente; (3) submeter a decisão G5 por ator e mandato comprovados, capturar `decision_id` e `decision_hash` reais; (4) registar ativação G5 apenas se as pré-condições e vigência forem satisfeitas, capturar `activation_id` e `activation_record_hash` reais; (5) verificar encadeamento, cardinalidade, audit trail e idempotência. **Não afirmar atomicidade entre etapas sem comprovar o contrato transacional dos serviços.** Cada transição protegida exige autorização correspondente ou instrumento único que expressamente a abranja.

**Falha / ACK incerto:** não repetir automaticamente; reabrir somente leitura e procurar `(policy_id,2)`, decisão e ativação pelos identificadores naturais reais; comparar hashes e estado transacional, classificar `COMMITTED`, `ROLLED_BACK` ou `UNKNOWN`; `UNKNOWN` implica STOP e reconciliação humana. Não executar `DELETE`, `UPDATE` ou `INSERT` compensatório improvisado.

**Saídas exigidas antes do header:** `policy_hash` persistido, `record_hash` da política, `decision_id`, `decision_hash`, `activation_id`, `activation_record_hash`, chave pública e `key_id` reconhecidos, constraints, janela válida e pins físicos reais. O header sucessor deve consumir estes dados, não identidades históricas G4. Reutilizar `COMPILAR_CANDIDATO_ISOLADO_SEM_INSTALAR.ps1` no PG17.10 descartável, sem volumes protegidos; validar SHA do header e ELF, símbolos, ABI, dependências e perfil real. A aprovação do ELF só ocorre **depois** de existir o seu hash.

**Gates posteriores:** backup custom com restauração ensaiada em ambiente distinto, ACL/owner, aprovação expressa do ELF e dos bytes de `0064/0065`, instalação exclusivamente Alembic `0063→0064→0065`, releitura independente, sanitização real, autorização one-shot separada, PRE_COMMIT, COMMIT e reconciliação. Nenhum desses atos está autorizado por esta ratificação.

### Texto único para apreciação da primeira escrita protegida — NÃO APROVADO

> Autorizo / NÃO AUTORIZO a execução controlada do registo institucional da política G5 sucessora, `policy_id=SOLVERIS-B02-SEFA-PR-G5-REAL-CAS-RELEASE`, `policy_version=2`, exclusivamente na base `solveris_b02_r4g_test` cuja identidade física deverá ser confirmada, usando os bytes exatos do V5 e o serviço de registo existente, condicionado à prova prévia de B1 (ator, mandato, aceite/segregação exigível e contrato canónico) e B2 (vigência, chave Ed25519, custódia e não revogação), à inexistência prévia de versão 2 e à validação de ACL/transaction boundaries. Exijo captura e reconciliação independente de `policy_hash`, `record_hash`, ID e resultado transacional. Não autorizo por este ato instalação `0064/0065`, ELF, assinatura, operação one-shot, GRANT/DDL ou alterações G4. Decisão e ativação G5 subsequentes só poderão ocorrer quando a autorização as abranger expressamente e os respetivos atores e pré-condições estiverem comprovados. Qualquer divergência ou ACK incerto implica STOP sem repetição automática.

**Evidência ainda necessária e ponto de consumo:** (i) aceitação/mandato e segregação B1 no serviço de decisão; (ii) estado temporal G4/G5 e revogação/custódia B2 antes do registo e novamente antes da ativação; (iii) assinaturas reais dos serviços e campos de `PolicyVersion`, `PolicyDecision`, `PolicyActivationExecution` antes de produzir runner de escrita; (iv) leitura de identidade e unicidade do PostgreSQL antes da primeira transação. Sem esses elementos não é seguro fornecer SQL de escrita como se fosse validado.

---

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

## 2. Deliberação única — referência ativa ao V5 versão 2

**O único texto destinado à decisão de Miguel é a minuta da secção 0**, condicionada ao aditamento do revisor V4→V5. A minuta V4/versão 1 anteriormente presente neste ponto tornou-se inexequível em razão da colisão física de `(policy_id,policy_version)` e foi substituída, preservada no histórico Git. **Não apresentar V4 versão 1 para nova ratificação ou inserção.**

A eventual ratificação documental do V5 **não** é autorização de instalação das candidatas 0064/0065, aprovação do binário ainda por compilar, prova atual de sanitização ou concessão de assinatura/COMMIT.

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

**Preparação já existente para Fase B (sem nova implementação):** o ficheiro histórico `COMPILAR_CANDIDATO_ISOLADO_SEM_INSTALAR.ps1` da custódia de Biblioteca contém construtor isolado por imagem SHA-256 `7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317`, com `postgresql-server-dev-17=17.10-1.pgdg13+1`, verificação `pg_config --version`, compilação `gcc -Wall -Wextra -Werror -Wno-unused-parameter -fPIC -shared ... -lcrypto`, `ldd` e SHA-256 do ELF. Não monta a base, container ou volumes protegidos e remove exclusivamente o builder próprio. **Reutilizar método, não o header nem o ELF histórico**; a raiz sucessora exige binding/intervalo/provas atuais e a compilação subsequente necessita de aprovação separada do hash do novo ELF. Não gerar ZIP ou compilador duplicado enquanto este método puder ser comprovadamente reutilizado.

**Compatibilidade focal da versão 2:** inspeção estática ao SQL integrado das candidatas 0064 e 0065 confirma procura de `policy_version` a partir de `binding->>'policy_version'`, sem `policy_version=1` literal. A 0065 inclui reserva vinculada a `pg_current_xact_id()`, unicidade de `approval_id` e `release_id`, inclusão `g5_one_shot` no manifesto canónico e trigger diferido que exige duas unidades. Verificação estática não substitui ensaio físico nem prova de instalação.

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
| V4 documental | **FAVORÁVEL CONDICIONADO**; preservado como revisão histórica |\n| V5 versão 2 | **CANDIDATO CORRIGIDO**; aditamento focal de revisão e ratificação de Miguel pendentes |
| Política canónica G5/ratificação/ativação | **NÃO DEMONSTRADAS** |
| Raiz atual, header e binário compilado aprovado | **AUSENTES**; código C histórico recuperado |
| Backup **e restauro** atual comprovados | **NÃO DEMONSTRADOS** |
| 0064 / 0065 em PostgreSQL protegido | **AUSENTES**; último Alembic 0063 |
| Inspeção e sanitização operacionais atuais | **NÃO DEMONSTRADAS** |
| Assinatura e COMMIT real das duas unidades | **NÃO EXECUTADOS** |
| Matriz normativa e aceitação B02 global | **PENDENTES**, não transferir ao B03 |

**Decisão operacional final:** preservar `G4 CLOSED`; `G5 OPEN`; `B02 OPEN`; `B03 BLOCKED`; MEI intocado. Não repetir testes encerrados, não criar nova ficha intermédia, não prolongar nem editar janelas V4/V5 à pressa, não disparar deploy, não fingir consentimento/assinatura/independência.
