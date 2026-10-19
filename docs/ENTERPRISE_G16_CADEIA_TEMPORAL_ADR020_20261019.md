# SOLVERIS Enterprise — G1.6: cadeia temporal de regra ADR-020, somente leitura

Base obrigatória: `work/fiscal-assumptions-c0` HEAD `58c1c3845331ecdd05e2efa1b90040e93abe3d53` (G1.5). G1.6 **não** representa autenticação independente já concluída.

## Ligação causal

A função `cotejar_ciclo_normativo_g16` obriga a passagem pelo G1.5, que por sua vez chama G1.4 → G1.3 → I2/G1.2/G1, usando os mesmos bytes e objeto DB. **Depois** da fronteira de posse/identidade e artefacto preservado, recebe IDs explícitos não confiáveis e consulta por `db.get`:

- `ExtractionResult` e `ExtractionRun`: resultado e execução concluída ligados ao exato `normative_artifact_id`/SHA-256 cotejado em G1.5;
- `RuleVersion`: versão estruturada vinculada por ID e `record_hash` ao resultado da extração; não é por si o texto oficial nem a sua interpretação legal;
- `RuleReviewRecord`: revisão interna concluída/validada sobre a mesma identidade (`rule_id`, versão e `rule_hash`);
- `NormativeActivation`: ativação interna da mesma versão e da revisão exata; `active` é um estado **operacional interno** e não comprova vigência jurídica;
- `NormativeRelationVersion`: os IDs fornecidos podem revelar `revoga`, `substitui`, `altera`, `rectifica`, `republica`, `sucede` ou relações informativas. A presença de mudanças relevantes sinaliza alerta. **A ausência de relações na lista fornecida não prova ausência de mudanças**.

O adaptador lê a data de emissão do mesmo XML com `defusedxml`; esse instante é **declarado nos bytes da NF-e**, não uma prova de publicação, entrada em vigor, nem timestamp independente.

## Estados e limites

- `CADEIA_TEMPORAL_INTERNA_SEM_AUTORIDADE`: vínculo interno entre extração, regra, revisão, ativação e artefacto. A versão e eficácia oficial permanecem não comprovadas.
- `ALERTA_RELACAO_NORMATIVA_SEM_DECISAO`: uma relação de alteração/revogação declarada foi encontrada e precisa ser interpretada e confirmada por evidência externa.
- `LACUNA_CADEIA_TEMPORAL`: dados inexistentes, incompatíveis ou insuficientes. Não se presume regra válida, suspensão definitiva nem não incidência.

Todos os resultados deixam `fonte_primaria_autenticada`, `versao_oficial_verificada`, `atualizacao_e_revogacao_exaustivas`, `vigencia_juridica_comprovada`, `autoridade_fiscal`, `credito_confirmado`, `checkout_autorizado`, `usavel_comercialmente` em **False**.

A função **não** consulta fontes oficiais, cobertura temporal, publicações posteriores, CRLs, EFD, SEFAZ ou banco real; **não** interpreta integralmente os campos `declared_material_validity` e `operational_interval`. Isto exigirá verificações independentes com provas verificáveis e gates específicos. **Não há promoção jurídica por um hash, um URL, uma declaração ou a ativação interna.**

## Provas / implementação

- 36 testes unitários sintéticos isolados (sem conexão, rede, dados empresariais reais ou escrita).
- Smoke com classes/modelos reais Enterprise/ADR-020 e XML/empresa/ato normativo inteiramente sintéticos, DB fake `get` read-only, regressões selecionadas no Windows antes e após instalação.
- Somente três ficheiros novos: serviço, teste e este documento. Nenhum ficheiro rastreado anterior deve ser alterado. Sem commit/push automático; seguir gates existentes.

## Próxima etapa

Prova **externa independente** de publicação/identidade institucional, completude da cobertura de alterações/revogações e interpretação normativa temporal aplicável por operação (incluindo exceções). Trilhar em separado ICMS próprio independente, EFD/recolhimento e direito a crédito.
