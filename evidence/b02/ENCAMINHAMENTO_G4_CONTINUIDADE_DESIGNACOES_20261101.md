# SOLVERIS B02 — G4: encaminhamento único para decisão e atos próprios

**Estado: PROPOSTA NÃO RATIFICADA.** Não é mandato emitido, aceitação, parecer, assinatura, nem autorização de migração/ativação.

**Objecto imutável:** `evidence/b02/successor_v3/object.json`, SHA-256 `615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906`.
**Política G4:** `05ede0f8c8788b93d41e451288efd88d91614a560bdd2191a115f0d736c4fe2a`.
**G4 V4 preservado:** `B02-05ede-activation-v4`, hash `cf617e146b3451555898d8253fba8bb13dfa6ff99776b50978e0ba68df4cb482`.
**Cadeia histórica:** `review.json` favorável `B02-05ede0f8-INSTITUTIONAL-REVIEW-20261021` SHA-256 `e6df0dd3ee52edb848fe8f89fb7294b4b1bd5b5e240603fe6036a3e73345919e`, preservada em `proofs.json`; 122 provas originais, mais sete referências sucessoras, sem alteração às fontes.
**Limite temporal:** nunca superior ao limite do assinador vigente, nem a `2026-11-15T00:00:00Z`, o que for mais restritivo. Não é data para esperar.

## 1. Ato proposto à decisão de Miguel — designações concretas

Proponho a designação **prospectiva e condicional à aceitação própria** das seguintes identidades funcionais. Os IDs são nomes de encaminhamento, não autenticações de uma sessão futura; a execução receptora deve identificar-se e declarar se aceita exatamente o ID e papel. Qualquer recusa ou divergência exige decisão própria e não pode ser preenchida por terceiro.

| Identidade funcional proposta | Papel | Mandato exato proposto | Operações limitadas |
|---|---|---|---|
| `GPT-6/executor-documental-g4-continuidade-20261101` (a execução desta conversa) | author | `B02-G4-SUCESSOR-20261101-AUTHOR` | `prepare`, `submit` |
| A mesma `GPT-6/executor-documental-g4-continuidade-20261101` | integrator | `B02-G4-SUCESSOR-20261101-INTEGRATOR` | `integrate_candidate`, `test` |
| `GPT-6/revisor-documental-g4-segregado-20261101` (destinatário: conversa revisora G4 segregada, não a G5 V3) | reviewer | `B02-G4-SUCESSOR-20261101-REVIEWER` | `review`, `reprove` |
| `GPT-6/examinador-origem-sefa-pr-g4-20261101` (destinatário: conversa examinadora de origem independente do proponente/integrador) | examiner | `B02-G4-SUCESSOR-20261101-ORIGIN` | `examine_document_origin`, `report`, `abstain` |

O revisor não pode ser o autor/integrador. O código existente permite que um único ID seja autor e integrador com mandatos e registos distintos (`enterprise_b02_founder_review_profile.py`, condições `PROFILE_FUNCTIONAL_CONFLICT` e `PROFILE_EXECUTION_AMBIGUOUS`); não permite ao revisor acumular essas funções.

**Texto proposto de decisão de Miguel:**

> Designo prospectivamente as execuções funcionais e os quatro mandatos com os IDs, operações, objeto SHA-256 e segregações acima, todos sujeitos à identificação e aceitação próprias, verificação de conflitos e limites do assinador. Os mandatos são válidos apenas a partir do ato real de emissão e nunca retroativamente; os seus limites horários definitivos deverão estar expressamente fixados e ser compatíveis com o assinador, sem exceder 15/11/2026 às 00:00 UTC. Os históricos de outubro permanecem intocados.
>
> Determino o confronto dos validadores efetivamente consumidos com a distinção entre valor probatório histórico e autoridade operacional presente. Apenas se for demonstrada uma incompatibilidade, deverá ser preparada a correção mínima, com revisão segregada e preservação dos controlos de autoridade atual.
>
> A presente designação não constitui aceitação pelo destinatário, não renova pareceres antigos, não comprova não revogação independente, não aceita risco residual específico de pré-imagem ainda não fixada, não assina, não ativa G5 e não autoriza R5/R6/R7.

## 2. Ato próprio de aceitação — um por participante e por papel/mandato

**Destinatários:** a execução identificada acima, na sua conversa correspondente; a execução autora/integrador deve emitir duas aceitações específicas.

> Eu, [IDENTIDADE REAL DESTA EXECUÇÃO], confirmo ou retifico a identidade funcional proposta [ID], aceito ou recuso o mandato [ID EXATO], o papel [PAPEL], o objeto SHA-256 `615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906` e apenas as operações [OPERAÇÕES]. Declaro participação anterior [FACTOS], conflitos e limitações materiais [FACTOS]. Não me apresento como outra execução, não afirmo independência não demonstrada e não altero datas. Data/hora real desta aceitação [INSTANTE COM FUSO]. Resultado: [ACEITO/RECUSO].

O executor gera `acceptance_sha256` a partir do texto/objeto **efetivamente recebido**, sem o antecipar. Preserva cada contexto de execução e os hashes de inputs/outputs.

## 3. Ato próprio do examinador de origem — reutilização documental, não novo ensaio

**Destinatário:** `GPT-6/examinador-origem-sefa-pr-g4-20261101`, se aceitar mandato válido.

> Eu, [IDENTIDADE PRÓPRIA], mandato [ID], apreciei os dois relatórios históricos de origem `B02-05ede0f8-ORIGIN-101202501245-FOLLOWUP-20261021-RUNTIME-BODY` (SHA-256 `09754ecef2fe0967459d36017afdc9393718a5df911ab0b93c08cddd82869087`) e `B02-05ede0f8-ORIGIN-101201900571-FOLLOWUP-20261021-RUNTIME-BODY` (SHA-256 `63435196c888e42d7eaf85c6ba6d2323c1d0ff47dc4e3a7a824c357a6f093f8e`), bem como seus vínculos a recibos, TLS, exame e mandato preservados. Distingo o êxito documentado em outubro de qualquer autoridade atual. Sem nova aquisição ou repetição dos exames, emito [FAVORÁVEL/CONDICIONADO/DESFAVORÁVEL] quanto à reutilização probatória hoje, pelos seguintes motivos [FUNDAMENTAÇÃO E DELIMITAÇÃO], emitido em [DATA REAL]. Não atribuo aos documentos assinatura oficial SEFA nem altero os resultados antigos.

Caso emita novo relatório sob o esquema `independent_document_origin_founder_sealed`, deverá declarar o **seu próprio ato efetivamente realizado**, com mandato, aceitação, data e o verificador atual; nunca reetiquetar o relatório expirado. `RUNTIME_ORIGIN_MANDATE_CHRONOLOGY` exige as datas reais e `RUNTIME_ORIGIN_SCOPE_DIVERGENCE` exige o verificador correspondente.

## 4. Ato próprio do revisor documental G4 — duas conclusões separadas

**Destinatário:** `GPT-6/revisor-documental-g4-segregado-20261101`, após aceitação do mandato.

> Eu, [IDENTIDADE PRÓPRIA], sob mandato [ID] e aceitação [ATO], apreciei o objeto `object.json` SHA-256 `615c8d6466871a94981358e9cab6f4f5d797f317b9026c77e304b7af6ac50906`, a revisão documental G4 favorável de 21/10/2026 SHA-256 `e6df0dd3ee52edb848fe8f89fb7294b4b1bd5b5e240603fe6036a3e73345919e`, e o histórico preservado.
>
> **Conclusão A — continuidade probatória do parecer histórico:** [FAVORÁVEL/CONDICIONADA/DESFAVORÁVEL], fundamentos [ ], limitações [ ]. Não declaro um mandato histórico ainda vigente.
>
> **Conclusão B — correção do delta do validador:** [NÃO APLICÁVEL — NENHUM DELTA APRESENTADO] ou [HASH DO DELTA, PARECER E FUNDAMENTAÇÃO], apenas se tiver sido apresentada incompatibilidade concreta e correção delimitada.
>
> Declaro participação anterior [ ], conflitos [ ], independência efetivamente demonstrável [ ] e data/hora real [ ]. Este parecer não substitui avaliação G5 V3, A2 V4 ou instalação R5.

## 5. Confronto com os consumidores — sem alteração de código autorizada

- `enterprise_b02_founder_review_profile.py` impõe `PROFILE_NOT_CURRENT` aos mandatos em vigor via `_current(mandate,now)`, e `PROFILE_MANDATE_CHRONOLOGY_INVALID` à relação entre aceitação, execução e período da decisão. **Rejeita usar mandatos de outubro como mandatos atuais**, mas preserva a possibilidade de os manter em `proofs.json`/histórico. Não demonstra, por si, defeito no contrato.
- `enterprise_b02_founder_runtime.py` impõe `RUNTIME_ORIGIN_MANDATE_CHRONOLOGY`, `RUNTIME_ORIGIN_SCOPE_DIVERGENCE` e `_current(report/mandate,now)`. A apreciação atual pode usar recibos/TLS históricos, mas deve comprovar seu próprio ato e autoridade corrente. **Não foi encontrada incompatibilidade que obrigue a alterar estes validadores nesta fase.**
- Ambos exigem autoridade atual separada do documento assinado. `_AUTHORIZED_CONTEXTS` e `_RUNTIME_AUTHORIZATIONS` não estão provisionados no código atualmente observado. Assinatura offline não implica habilitação operacional.

## 6. Sequência vinculante

1. **Executor:** preserva os sete JSON atuais, 122 provas históricas e a proposta de designação, sem produzir aceitação por terceiros.
2. **Miguel:** decide expressamente o Ato 1 com delimitação dos papéis e período; designação só produz efeito nos termos desse ato.
3. **Participantes:** cada execução manifesta aceitação própria por papel.
4. **Examinador:** emite apreciação de reutilização e, se fundamentado, seus relatórios próprios para os dois PDFs.
5. **Revisor G4:** emite as duas conclusões separadas, registando não aplicabilidade do delta se nenhum existir.
6. **Executor:** integra as manifestações emitidas nos seis JSON existentes, calcula seus SHA-256, verifica o contrato atual, apresenta a pré-imagem e bytes exatos para assinatura local apenas quando elegíveis, e verifica depois o consumidor institucional independente.

**Não repetir:** G4 V4, R4, C3, A2 V4, reconhecimento da chave, bootstrap negativo, exames anteriores ou auditoria histórica G5 V2. Não usar aprovação proposta como ratificação.
