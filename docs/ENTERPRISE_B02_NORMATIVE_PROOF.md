# SOLVERIS Enterprise — Missão 02 / R1-C1

Estado: PARCIAL — intervenção documental controlada; ligação normativa ADR-020 pendente de decisão do Centro de Comando.

Baseline: `work/fiscal-assumptions-c0` — `b45ef5396189f5b6be1156535c9af9b19cca17b4`.

## Fonte e integridade

Fonte C3 de referência: Resolução SEFA/PR 571/2019, PDF consolidado de 587 páginas, `https://www.sefanet.pr.gov.br/dados/SEFADOCUMENTOS/101201900571.pdf`.

SHA-256 **aprovado em C3, não recalculado nesta documentação**: `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d`.

- Página física 55: SHA-256 do texto extraído em C3: `49de93b123f058fb3b1062c00eb1ffdeaf2fd8e97aaf93c8fbdfcd307dc91bf0`.
- Página física 86: SHA-256 do texto extraído em C3: `e4d3c4df93ea178040f2c54e0434a0021d4e41ee55a91b5750b48388fc53228b`.
- Referência C3: henna em embalagens até 200 g, NCM 12119090, CEST 2000100; MVA 41,42% no exemplo temporal 31/03/2026, 46,78% em 01/04/2026.
- Ambas as datas são **janelas de observação limitadas**. A ausência de ato posterior não demonstra vigência indefinida.

Os testes de C1 com 587 e 601 páginas usam exclusivamente PDFs **sintéticos**. Somente um segundo gate de bytes, SHA e hashes das páginas do PDF oficial autoriza afirmar que o ficheiro C3 original foi reencontrado. Nenhum destes gates autentica institucionalmente a publicação, assinatura, revogação ou aplicação tributária.

## Alteração C1

Substituição exata e única da condição `1 <= count <= 500` por `1 <= count <= 600` em `tools/enterprise_g113_exact_normative_excerpt.py`. Preservam-se limite de tamanho de 16 MiB, leitura `strict=True`, SHA-256 integral, índice 1-based, SHA da página, excerto exato, offset, identidade do item e flags negativas. Não se altera C3–C7, motores ou contratos ADR-020.

## Conflito de identidade normativa ADR-020

`NormativeRelationVersion` prevê relações `rectifica`, `republica`, `altera`, `substitui`, `revoga`, `complementa`, `referencia` e `sucede` e exige `source_subject_type/id/version/hash` e `target_subject_type/id/version/hash` para sujeitos versionados. A coluna de tipo não está restrita a uma enumeração no SQL; **isso não autoriza semântica nova**.

`TabelaMVA` tem ID inteiro, UF/NCM, MVA, alíquota, datas, fonte/URL e importador, mas **não tem identidade normativa versionada/hash canónico, CEST ou FK com `RuleVersion`**. Uma relação `referencia` ad hoc de `TabelaMVA` para `RuleVersion` seria tecnicamente inserível mas semanticamente não ratificada. Por esta razão, nenhuma relação será gravada, fabricada ou interpretada como juridicamente válida.

**Alternativa proposta, ainda dependente de ratificação:** adaptador estritamente read-only que lê a linha real por `TabelaMVA.id`, verifica o rasto real G12/C5/C6 e os objetos ADR-020 já existentes por IDs exatos (incluindo C1/G16/G18), coteja parâmetros/versão/fonte e devolve somente `CANDIDATO_SEM_VINCULO_CANONICO` ou `ABSTENCAO`. Nunca promove a candidato juridicamente comprovado sem prova externa independente e vínculo canónico autorizado. Se for necessária persistência de associação, o Centro de Comando terá de ratificar previamente o contrato de identidade/fonte da associação e, se indispensável, autorizar caminho/migração adicional. Não modificar `NormativeRelationVersion` nem fabricar relações.

## Limites e autoridade

O teste de 587 páginas e as referências oficiais não provam que certa operação envolve henna até 200 g, incidência de ST, regime, destino, CFOP/CST, alíquota interna, exceções, benefícios, EFD, recolhimentos ou crédito. Os gates G15–G19 mantêm origem externa institucional, exaustividade de alterações e histórico de revogações por provar. Nenhuma autoridade fiscal/comercial, checkout ou venda parcial.

## Execução e ratificação

Executar o instalador *fora do Git*. Preflight local/remoto, HEAD, índice, integridade, RED, mudança mínima, GREEN, regressão C1/C3–C7/G12–G19/B01 e verificação de hashes. Em caso de falha, restauração exclusiva do que foi instalado por este executor. Sem Git add, commit, push, merge, deploy, DB real, MEI ou pagamentos.

## R2 — Cotejo normativo read-only, sem fingir ligacao L2/ADR-020

Contratos inspecionados no HEAD `b45ef5396189f5b6be1156535c9af9b19cca17b4`:
- `TabelaMVA` possui ID inteiro, estado, NCM, MVA, aliquota, vigencias, fonte e URL; nao possui CEST, FK ADR-020, versao de sujeito normativa nem hash canónico de versao.
- `NormativeRelationVersion` suporta `referencia`, mas os campos de sujeito de origem/destino sao versionados e assinados por hash. Nenhum contrato ratificado transforma `TabelaMVA.id` em sujeito normativo ADR-020. **Nao foi criada, persistida nem reinterpretada nenhuma relacao.**
- `RuleVersion -> ExtractionResult` tem relacao exata com hash; `G16` confirma revisao e ativacao internas, nao ausencia completa de alteracoes; `G18` confirma hash de PDF adquirido, nao autenticidade externa.
- C1 confirma excerto fisico de um PDF e parametros declarados, mas `prova_de_relacao_semantica_entre_excerto_e_parametros=False`.
- C3 documenta somente a janela de observacao do caso PR em 31/03 e 01/04/2026, nao vigencia posterior exaustiva. G12/C5/C6 expoem parametros internos do calculo, sem autoridade fiscal.

`app/services/enterprise_b02_normative_binding.py` (novo) le `db.get(TabelaMVA, registro_mva_id)`, `db.get(RuleVersion, rule_version_record_id)` e `db.get(ExtractionResult, extraction_result_id)`, e faz consulta read-only **limitada a 2 linhas** para detectar sobreposicao de regras L2 por UF/NCM/data, dentro da sessao fornecida pelo chamador. Duplicidade ou falha de consulta produz `ABSTENCAO`. Rejeita falsas alegacoes de autoridade, incompatibilidade de documento, item, fonte, regra e parametros e nao escreve no banco. A chamada deve ser realizada por orquestrador confiavel que execute os gates originais na mesma sessao; dicts isolados/ORM fake nao provam essa execucao.

Estados exclusivos: `CANDIDATO_DOCUMENTAL_COTEJADO` (simples coincidencia documental e parametrica), `NAO_APLICAVEL_AO_ESCOPO_DECLARADO` (dimensoes ou periodo declarado incompatíveis), `CONTRADICAO` e `ABSTENCAO`. Em qualquer estado `vinculo_l2_ruleversion_canonico_comprovado=False`, `aplicabilidade_juridica_comprovada=False`, `unicidade_l2_e_regra_comprovada=False`, `fonte_primaria_autenticada=False`, `autoridade_fiscal=False`, `credito_confirmado=False`, `checkout_autorizado=False`, `usavel_comercialmente=False`. A coincidencia nao equivale a validacao juridica.

O modulo nao presume correspondencia semantica entre excerto e produto, embalagem, CFOP/CST, regime, ST/PMPF, aliquota legal, beneficios, excecoes ou obrigacoes acessorias. Nao sabe se existem outras linhas L2 vigentes nem outras `RuleVersion`/alteracoes e nao prova cobertura temporal de todas as publicacoes. `NAO_APLICAVEL_AO_ESCOPO_DECLARADO` refere-se apenas aos dados explicitamente cotejados, nao a uma declaracao final de nao incidência tributaria. A validacao independente das condicoes do produto e do caso concreto continua pendente.

**PDF SEFA/PR original confirmado por executor de leitura externo (relatorio do utilizador, 20/10/2026):** SHA-256 `af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d`, 587 paginas, SHA da extracao p55 `49de93b123f058fb3b1062c00eb1ffdeaf2fd8e97aaf93c8fbdfcd307dc91bf0`, p86 `e4d3c4df93ea178040f2c54e0434a0021d4e41ee55a91b5750b48388fc53228b`. Esta confirmacao e uma prova de identidade dos bytes da publicacao observada, **nao** de autenticacao institucional independente, assinatura/certificado com revogacao, pertinencia de henna para um cliente ou ausencia de alteracoes posteriores.

**Gate R1 ja concluido:** C1 RED limite 500; GREEN 12; regressao 453 casos/16 ficheiros; SEM commit/push/deploy. R2 deve executar RED por adaptador ausente; GREEN 42 testes sintéticos que exercitam o modulo efetivo com `db.get` fake (nao conectam DB real); regressao dos mesmos 16 ficheiros incluindo B01 e ADR-020. Contagens de R2 somente apos execucao local validada.

**Pendencias que nao podem ser convertidas em prova por teste sintético:** acordo versionado canónico `TabelaMVA -> RuleVersion`, unicidade de selecao L2, origem publica autenticada independente, revogacao historica/completude temporal, semantica da regra legal, embalagem/mercadoria do caso e seu contexto, regime, excecoes, beneficio, base e aliquota fiscal, escrituracao e recolhimento. Para ultrapassar estes limites, sera indispensavel autorizacao e evidencia propria; NAO alterar contratos ratificados ou declarar produto parcial vendavel.
