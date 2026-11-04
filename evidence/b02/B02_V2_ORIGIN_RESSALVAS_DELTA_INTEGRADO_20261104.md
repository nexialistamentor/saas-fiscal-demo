# SOLVERIS B02 — Delta único integrado: ressalvas ORIGIN / continuidade V2

**Estado:** correções técnicas PUBLICADAS; PRE-FLIGHT_READONLY_PASS_COM_ENSAIOS; **SEM RATIFICAÇÃO DA TROCA DE CÓDIGO, SEM ASSINATURA, SEM ROOT, SEM SQL, SEM RELEASE**. Autor/integrador: execução técnica GPT-6 desta conversa, NÃO revisor segregado. Base: PR #27, #28 e #29 existentes. Data documental: 2026-11-04 UTC, sem retroatividade.

## 1. Correção EXCLUSIVA do formato dos dois relatórios ORIGIN

O validador anterior, blob `32b4ee9c8c11b5eb9564d4f258cef5a40cae3119`, recusava os dois relatórios custodiados por ausência de campo `limitations`. Ambos têm `outcome=favoravel`, com ressalvas expressas e limites próprios em `mechanism_assessment`. Os SHA-256 canónicos dos relatórios são:
- `a281c48d6107817aca97331e5425f81616847e66853a3e179ca66d3353f23fa8` — 101202501245
- `9250fc933c41dab84e186019f01ed1f2b29828de1d5e1b879568a96e3ef1a6d4` — 101201900571

**Novo validador** `app/services/enterprise_b02_documentary_continuity_v2.py`, Git blob `31be879d8d0fab9c572916b67f66ee32037b3495`. Aceita a localização alternativa das ressalvas **somente** quando o hash do relatório coincide com um dos dois pins e `mechanism_assessment` contém os limites explícitos `COM RESSALVAS`, `Ressalvas:` e `NOT_GRANTED`. Todos os demais relatórios continuam a exigir `limitations`. Recibos, TLS, exames, identidade, origem, mandatos, cronologia, provas e decisões mantêm as guardas anteriores. Controle negativo: relatório não pinado sem `limitations` => RECUSADO; texto sem ressalvas => RECUSADO.

## 2. Dependências exatas e trânsito das três PRs

| Peça | Blob anterior | Novo Git blob | Local / PR |
| --- | --- | --- | --- |
| Continuidade V2 | `32b4ee9c8c11b5eb9564d4f258cef5a40cae3119` | `31be879d8d0fab9c572916b67f66ee32037b3495` | validador PR #27 |
| Assinador V2 | `b8ff97373476bb3ef1b34362612eedd014f0ff21` | `17dc1b4a9a34a8045bddb97717c01b160411c238` | `tools/b02_documentary_signer_v2.py`, PR #28 |
| Consumidor V2 | `492d008308064cbc4b5dd4aac8db1283d492780e` | `52410e3f170117551ffac87d226d6f918c502afb` | `app/services/enterprise_b02_authorized_trust_v2.py`, PR #29 |
| Procedimento Windows | `04269e49e390f9180833f2a0957a5301e9b165b9` | `955ab86233f584d3fcf1d2c2e8f531b5e270d244` | PR #28; origem do signer commit `c70c0ea446dbcbec63ca527dc97c6b3641d228c7` |
| R7 projeção read-only | pin antigo signer `5fd8ed57...` | Git blob `010cfc969d0716804f2c2af137f9e0d2bbc28cd1` | `tools/b02_r7_v2_readonly.py`, PR #27 |

SHA-256 do ficheiro Windows final: `f7cba52512b3070bbbbb2a015983c4641df1295eb8f30366e81cbac10f5e063a`. A fonte exata do assinador, do consumidor e do procedimento foi comparada ao Git blob após integração. O teste positivo da PR #29 foi repinado; a importação do módulo de testes da PR #28 foi corrigida para a localização real em `tools/`.

## 3. Preflight executado — SETE JSON REAIS, intactos

Execução isolada sobre os sete ficheiros `evidence/b02/successor_v3/{execution,history,institutional,mandates,object,proofs,review}.json`, comparados byte a byte e por SHA-256: **7/7 intactos, 149 provas**. O manifesto reconstruído reproduziu o SHA-256 `99d1a424015fc03a5ece71e84341eee748fd0b2fc1bebd238f9df2ede253a6c1`; a decisão canónica reproduziu **1.118 bytes** e SHA-256 `d3602168c53debd10421aa83d1e980c632870b660be18a451d5b5a3d998c6520`.

- Validador V2 anterior => `B02_CONTINUITY_V2_ORIGIN_SCOPE_INSUFFICIENT`. Validador corrigido com os sete JSON reais, a adoção histórica intacta e **pin de ensaio sem ROOT independente** => `continuity_v2_conditions_met`.
- Assinador V2 FINAL, `validate()`, consumiu **os sete JSON reais e a decisão exata de 1.118 bytes** => **PASS** usando substitutos de ensaio para o legado, a chave pública e a nova adoção não emitida; nenhum `sign()` foi executado.
- Consumidor V2 FINAL, `_v2_validate_exact()` + validador V2 REAL, com **os sete JSON reais**, verificou a cadeia estrutural e a assinatura Ed25519 **de ensaio** sobre uma decisão de ensaio isolada (fingerprint sintético, NÃO os bytes autorizados para assinatura real) => `V2_SIGNED_CUSTODY_VALIDATED_NOT_RUNTIME_PROVISIONED`, `runtime_provisioned=false`, `fiscal_authority=false`, `sql_writes=0`. ROOT, adoção do signer, revisão e aprovação de provisionamento de ensaio foram criados somente em `/tmp`, sem autoridade ou valor de custódia.
- R7 V2 read-only => `B02_R7_V2_READONLY_RECONCILED_NO_RELEASE`; `protected_writes=0`.
- Reexecutados somente testes focais tocados pelo novo pin: assinador `3 passed`; consumidor `5 passed, 17 deselected`. Nenhuma suite histórica.

Os resultados de ensaio **não** comprovam chave pública privada real, assinatura matemática de Miguel, ROOT instalado, autoridade de deployment, SQL ou fecho B02. Nenhum dos sete JSON ou das 149 provas foi alterado.

## 4. Ato específico ainda dependente de autoridade própria

**Atos existentes imutáveis:** adoção documental V2 de 2026-11-03, SHA-256 `d0cd1765ea2ef4870a530f8e5367cdde8550b5a60a3a70cb294f9d80678f7fa8`, fixa `continuity_git_blob=32b4ee9c...`; adoção específica do signer emitida em 2026-11-04, SHA-256 `b3e643d3622835e65f28ce404dbdb47ea6b4ab15be51f4206f21095f32959261`, fixa o assinador `b8ff9737...`. **Nenhum dos dois atos é autorização silenciosa da nova versão.** Os pareceres segregados anteriormente emitidos fixam igualmente os blobs anteriores.

**Única alteração de autoridade a submeter à decisão de Miguel, após nova apreciação segregada do delta:** aditamento **prospectivo e exclusivamente de PIN DE CÓDIGO**, passando o validador de `32b4ee9c...` para `31be879d...` e adotando especificamente o assinador corrigido `17dc1b4a...` (com referência ao consumidor `52410e3f...` e Windows `955ab862...`). O contrato do assinador exige que a nova adoção específica seja materializada em `SIGNER_AUTHORITY.json` com o novo parecer real, SHA-256 próprio, emissão e vigência reais e confirmação contemporânea de revogação. A minuta já existente foi repinada para `17dc1b4a...` e desativada; **não** substitui o ato emitido, não transporta aprovação antiga nem autoriza assinatura. Preservar a janela `[2026-11-03T18:00:00Z, 2026-11-04T18:00:00Z)` e os 1.118 bytes exatos; nunca retroagir ou prolongar.

**Ao revisor funcionalmente elegível:** examinar **somente este delta consolidado** e declarar participação, mandato, conflitos, conclusão própria, limitações e SHA-256 para os novos blobs. A autoria/integração da correção nesta conversa impede autoaprovação, não implica conflito automático de outras execuções GPT-6. Ao executor: não tentar comando Windows até receber revisão, emissão e pins coerentes; depois executar UM procedimento guardado, sem chave privada na conversa. Não abrir B03, G4/R4/A2, ORIGIN, certificados ou novas aquisições.
