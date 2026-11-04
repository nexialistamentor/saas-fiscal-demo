# SOLVERIS B02 — emissão delimitada da store V2, Windows (04/11/2026)

**Estado:** procedimento preparado; nenhuma operação PostgreSQL ou escrita de custódia
foi realizada por esta entrega. Não é ROOT, adoção, prova R5/R6, revisão, nem R7 CLOSED.
Preservar a PR #27 e a correção focal submetida à PR #29.

## Artefactos efetivos
- Entrada Windows: `B02_EMITIR_STORE_V2_WINDOWS.ps1`.
- Emissor: `tools/b02_store_emission_v2_windows.py`.
- Fonte preservada fixada: `evidence/b02/successor_v3/` (sete JSON com os hashes
  existentes, sem os reescrever); adota os dois relatórios ORIGIN fixados em
  `B02_G4_CONTINUIDADE_DOCUMENTAL_V2_ADOCAO_EMITIDA_20261103.json`.
- `signature.bin` original: SHA-256
  `479c9304724e0a92a5d02145e74d99485792b6e8e54b6c098590d3e0c3ca2c8c`;
  é somente lido, nunca substituído ou novamente assinado.
- PostgreSQL: `solveris_b02_r4g_test`, conta de acesso
  `solveris_b02_writer`, sem superuser, memberships ou bypass;
  transação `REPEATABLE READ, READ ONLY`, conforme o guard existente
  `enterprise_b02_founder_runtime._read_identity`.

## Fase 1 — inspeção (sem escrita de custódia)
**Não é necessário configurar `SOLVERIS_B02_READER_DSN` manualmente.**
Quando a variável não existe, o mesmo executor utiliza
`tools/b02_store_v2_readonly_bridge.py`, que reutiliza
`b02_g5_v5_local_bridge.py`: verifica branch e HEAD remoto, o contentor
`solveris-pg17-migration-test` e o volume protegido exato, cria somente
uma porta efémera de loopback, estabelece a ligação como
`solveris_b02_writer` e passa a DSN apenas ao processo Python. Não
imprime palavras-passe, não abre uma porta PostgreSQL no host e não
altera `pg_hba`, roles, volumes ou esquema. O emissor exige
`REPEATABLE READ, READ ONLY` e a identidade PostgreSQL já fixada no
verificador. Se uma DSN autorizada já estiver definida, continua
compatível com o caminho direto original, sujeito aos mesmos guardas.

A pasta `BUNDLE_ASSINADO` é a mesma do assinador V2 existente e
deve conter `decision.json`, `manifest.json`, `signature.bin` e os sete JSON.

O executor Windows já utiliza, por defeito, a pasta concreta do assinador
V2 preservado:
`%USERPROFILE%\Downloads\SOLVERIS_B02_ASSINATURA_AUTORIZADA_20261022\BUNDLE_SUCESSOR_V2_24H_20261103_1800UTC`.

No checkout `C:\dev\solveris-b02-g5-v5-publicacao`, com a variável de processo
`SOLVERIS_B02_READER_DSN` já configurada pela custódia (não imprimir
credenciais), executar **sem reconstruir JSON**:

```powershell
.\B02_EMITIR_STORE_V2_WINDOWS.ps1 -Etapa Inspecionar
```

O script deve abortar caso a pasta ou o contentor protegido estejam
ausentes ou divergentes, caso qualquer hash diverja, caso o leitor não seja restrito, ou caso
a ativação G4 V4 real, a execução e **todas** as decisões PostgreSQL não
correspondam à cadeia assinada. A verificação da vigência operacional é
prospectiva; não prolonga autorizações expiradas.

Saída: `%USERPROFILE%\Downloads\B02_STORE_V2_PLANO.json` completo e
`plan_sha256`. Esse plano contém os **objetos efetivamente derivados**,
os hashes, os vínculos, a proveniência e o estado `PLAN_NOT_AUTHORITY`.
A única escrita nesta fase é o plano na área de preparação do utilizador,
**fora de** `B02Trust\SUCCESSOR_V3\STORE`.

## Ato delimitado a pedir a Miguel ANTES da fase 2
A decisão incide sobre **um plano exato**, identificado pelo SHA-256 devolvido
na fase 1, e apenas nos termos seguintes:

> Autorizo a emissão prospectiva na custódia local
> `%LOCALAPPDATA%\SOLVERIS\B02Trust\SUCCESSOR_V3\STORE`
> exclusivamente dos objetos CAS integralmente identificados no plano
> `B02_STORE_V2_PLANO.json`, cujo SHA-256 será o hash apresentado após
> inspeção. Autorizo somente a escrita local imutável dos seis objetos
> identificados (head/genesis da revisão 1 compartilham um único corpo,
> writer derivado de PostgreSQL, mandato ORIGIN, dois relatórios ORIGIN e
> snapshot). Mantenho PostgreSQL somente leitura. Este ato não cria ROOT,
> não adota confiança, não autoriza SQL protegido, G5, R5, R6 ou R7,
> e não altera assinaturas ou atos históricos.

O titular deve manifestar a decisão **depois de ler o SHA real do plano**.
Não preencher hashes por suposição; não aceitar um token `--authorized-plan-sha256`
como prova independente da autoria do ato.

## Fase 2 — emissão local (apenas após ato do titular sobre hash exato)
```powershell
.\B02_EMITIR_STORE_V2_WINDOWS.ps1 -Etapa Emitir -HashPlanoAprovado 'SHA256_EXATO_DO_PLANO_RATIFICADO'
```

É o **mesmo script**, sem coletor. Reabre uma transação de leitura restrita,
recomputa o snapshot e compara todos os objetos, pins, decisões, ativação e
execução com o plano aprovado. Mudança de dados/HEAD/hash = STOP.
O destino usa endereçamento `STORE/sha256/XX/<hash>.json`, criação
`O_EXCL` (não sobrescreve história) e leitura física de retorno.
O recibo imprime os SHA-256 efetivamente escritos, `sql_writes=0`,
`root_issued=false` e `r7_closed=false`.

O plano define início futuro de vigência como 15 minutos após a observação
PostgreSQL. É **proposta prospectiva**, não cronologia histórica forjada.
Se a janela original de `decision.json` terminar ou o início previsto
passar antes da fase 2/ROOT, o procedimento deve parar. **Não retroagir
nem prolongar a decisão assinada.**

## Adoção do assinador competente já existente — não reutilizar ato histórico

A execução não precisa recriar a adoção do código final. O ato OWNER aplicável
ao assinador V2 final foi publicado em
[PR #28, comentário 6629393455](https://github.com/nexialistamentor/saas-fiscal-demo/pull/28#issuecomment-6629393455)
em `2026-11-04T11:26:57Z`. O corpo canónico do comentário deve ser consumido
pelos mecanismos verificados do assinador, sem usar hash fornecido por request
como fonte de autoridade. Fixa:

- `signer_source_git_blob=f1e866ba31d02a5e6c7f99c80d1e9833a9a0bbc2`;
- `review.review_sha256=34353ce4dad00bbd3e8a9fc04ed66929d5f952054138d9c127cd7664d0f9b3fe`;
- `valid_from=2026-11-04T11:36:00Z`,
  `valid_until=2026-11-04T18:00:00Z`;
- `revoked=false`, `no_operational_authority=true`.

O ato antigo no ficheiro
`evidence/b02/SOLVERIS_B02_SIGNER_V2_ADOCAO_ESPECIFICA_EMITIDA_20261104.json`
refere-se ao blob **anterior** `b8ff97373476bb3ef1b34362612eedd014f0ff21`,
e portanto **não** é `SIGNER_AUTHORITY.json` elegível para o consumidor final.
O parecer final do assinador na PR #28 tem Git blob
`4f4fec7dba218991983f1edf07edbdcec828862a`. A fonte Git e o SHA
dos bytes canónicos do parecer devem ser conferidos antes da custódia.

A aprovação do assinador e a assinatura Ed25519 existentes **não** autorizam
automaticamente a emissão de novos objetos CAS, ROOT ou ROOT_ADOPTION.
Essas etapas continuam sujeitas ao ato delimitado e à revisão competente.

## Consumo posterior, sem reabrir precedentes
1. Revisor competente verifica os objetos reais, respetivos SHA-256, histórico
   preservado e writer vinculado à ativação G4 V4 **atual** na transação PG.
   A revisão da correção V2 na PR #29 é ato separado.
2. Emissão e revisão competentes de `ROOT.json` com snapshot existente,
   assinatura Ed25519 já preservada, chave pública DER, revisão/adoções próprias
   e `issued_at` UTC verificável **anterior ou igual** ao `valid_from` do
   snapshot. Calcular SHA-256 da ROOT realmente emitida.
3. Decisão específica de Miguel sobre os **hashes reais** da ROOT e do
   snapshot; só então produzir `ROOT_ADOPTION.json` e o respetivo SHA-256,
   sem documentos com identidades ou vigências inventadas.
4. Revisão e commit separado dos sete `V2_DEPLOYMENT_PINS`, incluindo blob
   da revisão competente, sem aceitar pins de requisição ou ambiente.
   Execução de `provision_v2_documentary_for_process` com base e PostgreSQL
   reais, seguida de `readback_v2_documentary_for_process` positivo.
   Custódia matemática, custódia validada e admissão no runtime são estados distintos.
5. Usar provas G5/R5/R6 existentes primeiro. Somente alterações realmente
   autorizadas e pendentes prosseguem. Reconciliação final R7 por
   `tools/b02_r7_v2_readonly.py` compatível com o commit
   `4d658483b9aa0c1d7be5dc340053e38bb348183b`;
   o verificador histórico é apenas leitor predecessor, não decisor de
   compatibilidade. Requer-se decisão R7 competente própria antes de `B02 CLOSED`.

## STOP concreto
Se não existir ativação G4 V4 corrente, o papel restrito falhar, a decisão
de 24 horas expirar, os objetos históricos preservados não coincidirem,
ou faltar aprovação exata do plano, **não emitir**. A ação mínima caberá ao
responsável do respetivo ato: custódio Windows para fonte/DSN/caminhos;
titular Miguel para autorização de emissão e adoção; revisor independente
para parecer; autoridade operacional competente para novos eventos, se
algum predecessor tiver expirado. Nenhum destes impedimentos pode ser
resolvido fabricando ROOT ou estendendo uma janela.
