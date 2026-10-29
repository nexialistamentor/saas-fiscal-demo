# SOLVERIS B02 — missão do revisor segregado G5 V4

**Estado:** PEDIDO PREPARADO. Não é aceitação de mandato, revisão efetuada, ratificação, assinatura nem autorização SQL. O revisor tem de manifestar-se por atuação própria e ser distinto de quem preparou V4.

## Objetivo e objeto fechado

Emitir **um parecer adversarial, limitado ao delta causal G5**, sobre:

- Candidato: `POLICY_G5_CANDIDATO_SUCESSOR_OUTUBRO_V4_PARA_REVISAO.json`, SHA-256 `2dd00187b3348847a4deb845167d4554749aaa71cdce8556a03163ea1f4f252e`, blob Git `b8538623a53ff4f75a78f44454751259ccfb943e`.
- Delta: `DIFF_G5_V3_PARA_SUCESSOR_OUTUBRO_V4.diff`, 12 alterações de vínculo e período + 3 alterações descritivas; comparar com `POLICY_G5_CANDIDATO_V3_COMPLETO.json`, histórico imutável.
- G4 real: `B02_G4_RESULTADO_RECONCILIADO_OUTUBRO_20261029.json` — `FOUR_RECORDS_RECONCILED`, txid `926`, activation `B02-05ede-activation-v3`, hash `504b7f03b299068786aa73257c809de7f78d6aa5a67ed66c04b38a0230b9c4f4`. Não repetir testes G4.
- Código: `migrations/candidates/0064_b02_g5_controlled_real_cas_CANDIDATE.py`; `0065_b02_g5_one_shot_real_CANDIDATE.py`; fontes em `native/g5/historical_20261022/` (manifesto com SHA-256). Fonte antiga não é autorizada para a nova janela.
- Contexto: `B02_G5_V4_EXAME_TECNICO_CAUSAL_20261029.md` é apenas exame interno pelo preparador, **não** é parecer segregado. Não adotá-lo sem inspeção própria.

## Primeira resposta obrigatória do revisor

Antes de afirmar qualquer parecer, identificar: instância/ator próprio, aceitação ou recusa do mandato para **este hash** V4, âmbito, conflitos de interesse, participação prévia na redação do V4 e limitações de separação real. A mera designação `/root/canonical_executor_technical_review` em material histórico não confere identidade nova.

## Questões críticas a decidir com provas

1. V4 aponta aos hashes G4 reais e mantém os dois PDFs intactos? Os 15 campos alterados têm sustentação jurídica e temporal real, sem efeitos retroativos?
2. O método de inspeção segregada e sanitização documental tem resultado **atual e favorável**, ou ainda é inconclusivo? Não promover `verified_sanitized` previsto no candidato a resultado ocorrido.
3. A função da migration 0065 reserva uma só autorização para as duas unidades, e o PRE_COMMIT em C invoca o validador efetivo com privilégios corretos? O perfil nativo histórico aponta a `57982f46…` e janela vencida; bloquear a sua promoção.
4. Confirmar que `0064` e `0065` estão apenas em `migrations/candidates`, não em `migrations/versions`, e que o servidor físico permanece na revisão `0063` com biblioteca G5 ausente.
5. Identificar **exatamente** os atos adicionais requeridos antes da operação real: decisão/ratificação de V4 por Miguel, mandato de revisor próprio, estado atual da chave e revogação, cabeçalho/ELF aprovados para esta política, backup/restauro, autoridade de instalação/assinatura e reconciliação.
6. A janela G4 atual termina em `2026-10-30T13:00:00Z`; se o percurso não terminar antes, explicar a necessidade de uma nova autoridade temporal sem fingir que a atual é válida depois.

## Saída exigida

- **FAVORÁVEL / DESFAVORÁVEL / INCONCLUSIVO**, com achados causais e localização exata do ficheiro ou campo.
- Separar `BUG_TECNICO_DEMONSTRADO`, `PROVA_NAO_EXECUTADA`, `ATO_INSTITUCIONAL_PENDENTE`, `SEM_BLOQUEIO`.
- Não alterar código, migrations, chaves, autorizações, DB ou operação. Não repetir 32 testes físicos históricos, G4 ou PG inventory.
- Relatar apenas o diff exato adicional necessário; nenhuma ratificação ou prova é criada pela redação do parecer.
