# SOLVERIS B02 — exame técnico interno G5 V4 (29/10/2026)

**Autor:** GPT, inspeção técnica do código; **não é** revisão segregada, parecer institucional, ato de Miguel ou autorização de instalação/operação. Estado: `TECNICAMENTE_PREPARADO_COM_GATES_INSTITUCIONAIS_ABERTOS`.

## Evidência preservada e não repetida

- G4 física: `B02_G4_RESULTADO_RECONCILIADO_OUTUBRO_20261029.json`, quatro registos `FOUR_RECORDS_RECONCILED`, txid PostgreSQL `926`, activation ID `B02-05ede-activation-v3`, activation record hash `504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4`. Não repetir G4.
- G5 V4: `POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V4_PARA_REVISAO.json`, SHA-256 reportado `2dd00187b3348847a4deb845167d4554749aaa71cdce8556a03163ea1f4f252e`, blob Git `b8538623a53ff4f75a78f44454751259ccfb943e`, status `G5_NAO_RATIFICADO`; 12 referências materiais alteradas face a V3 e 3 campos descritivos, nenhum outro valor.
- PDF 101202501245: 258302 bytes, SHA-256 `e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832`. PDF 101201900571: 1944929 bytes, SHA-256 `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d`. Iguais ao manifesto de raiz histórico; não reexaminar os documentos sem delta.
- PostgreSQL 17.10, base `solveris_b02_r4g_test`, writer de política `solveris_b02_policy_writer`: Alembic `0063_adr020_policy_activation_atomicity`. `0064`, `0065`, funções G5, tabela one-shot e `b02_g5_native_REAL_CLOSED.so` **ausentes** segundo consultas físicas de 29/10; container restaurado parado.
- Fonte C histórica recuperada, hashs custodiados em `native/g5/historical_20261022/RECOVERY_MANIFEST.json`; não é binário operacional aprovado para janela atual.

## Revisão de código delimitada

1. `native/g5/historical_20261022/b02_g5_native_signature.c`: usa `EVP_PKEY_ED25519` / `EVP_DigestVerify`, exige vinculação exata e rejeita janela não corrente com `G5_NATIVE_CAPABILITY_OR_MANDATE_NOT_CURRENT`. Perfil nativo é marcado real somente com lista de raízes não vazia. A segurança material exige raízes concretas atuais e atestadas, não apenas o retorno textual do perfil.
2. `native/g5/historical_20261022/b02_precommit_guard.c`: contém callback `XACT_EVENT_PRE_COMMIT` e chamada restrita `public.b02g5_precommit_validate()`; preserva fail-closed. Não se alega compilação ou ensaio neste estado.
3. `migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py`: importa as funções C, mecanismos reais de vinculação e validação, mas ainda reside em `migrations/candidates`; não instalada. `0065_b02_g5_one_shot_real_CANDIDATE.py`: contém `b02_g5_reserve_operational_decision`, `b02_g5_assert_one_shot` e tabela `b02_g5_operational_approval_uses` para impedir reutilização. Não reconstruir a reserva por informação anterior desatualizada.
4. Cabeçalho histórico `b02_g5_approved_roots.h` aponta para política `57982f46ca62ff5d0be2e2e27a152483a544ee12d0782876621b5860b6bed7fa`, ativação `B02-57982-activation-v1` e janela `2026-10-22T12:00:00Z` a `2026-10-23T07:56:30.910737Z`. **Incompatível** com o sucessor V4 e com o G4 v3. Não copiar ou instalar como raiz atual.
5. Contratos preservam a finalidade: persistência documental das duas resoluções SEFA/PR, não autoridade fiscal nacional, venda, checkout ou validade normativa prospectiva.

## Próxima cadeia mínima de encerramento — sem repetir testes já aceites

**Ato 1 — segregação e política:** revisor próprio, distinto do proponente, aceita ou recusa mandato específico para o V4 e emite parecer concreto sobre V4, 0064, 0065, método e limites; Miguel ratifica ou rejeita objeto exato e escolhe uma janela operacional válida, sem retroatividade. Os quatro mandatos históricos não se transferem por presunção.

**Ato 2 — confiança e instalação:** após decisão, produzir novo cabeçalho de raiz nativa vinculado a política G5 efetivamente ratificada, decisão e ativação reais, a duas resoluções e à identidade física do servidor; obter aprovação específica dos hashes C/header/ELF. Compilar em ambiente descartável PostgreSQL 17.10 com verificação de ABI, dependências, símbolos e SHA-256. Antes de qualquer instalação protegida: backup e teste de restauro independente, identidade/ACL e ato exato para aplicar 0064→0065. Nenhuma instalação a partir deste parecer.

**Ato 3 — operação:** usar writer documental segregado `solveris_b02_writer`; emitir autorização one-shot e assinatura Ed25519 válida fora do PostgreSQL, persistir as duas unidades em uma única transação, confirmar veto nativo PRE_COMMIT, COMMIT único e releitura independente com txid, hashes, ACL, reserva e recibos. Não repetir INSERT em ACK incerto.

**Ato 4 — fecho:** declarar B02 CLOSED só após matriz jurídica/normativa e cadeia física completas; então liberar B03. A janela G4 atual termina `2026-10-30T13:00:00Z`; se decorrer antes do ato G5, rever vigência institucional por percurso próprio, sem alterar relógios nem reutilizar a autorização -02.

## Decisão técnica

**Reutilizar** código C, base 0064/0065, dois PDFs e provas G4 existentes. **Não executar** binário histórico nem simular assinatura/parecer/ratificação. Não é necessário qualquer novo comando PowerShell enquanto os atos do passo 1 não estiverem disponíveis.
