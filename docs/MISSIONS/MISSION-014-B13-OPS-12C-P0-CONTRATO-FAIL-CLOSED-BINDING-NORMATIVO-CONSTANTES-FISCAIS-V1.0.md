# MISSION-014 — B13-OPS-12C-P0 — Contrato fail-closed de binding normativo das constantes fiscais — Versão 1.0

## 1. Identidade, versão e estado

- Documento: `MISSION-014-B13-OPS-12C-P0-CONTRATO-FAIL-CLOSED-BINDING-NORMATIVO-CONSTANTES-FISCAIS-V1.0`
- Versão: `1.0`
- Data de redacção: `2026-08-06`
- Intenção: `B13-OPS-12C-P0`
- Natureza: missão técnica futura, exclusivamente documental nesta rodada
- Estado: **MINUTA REDIGIDA — AGUARDA AUDITORIA GPT E RATIFICAÇÃO DE MIGUEL**

Esta minuta não autoriza implementação ou execução técnica. As escolhas descritas como proposta permanecem sujeitas a auditoria GPT e ratificação posterior, expressa e específica de Miguel sobre bytes e SHA-256 exactos.

## 2. Baseline Git e preflight

### FACTO FÍSICO

- Branch: `main`.
- `HEAD = ee1ce93fd733409cc5305bd823456724ffbcb70a`.
- `origin/main = ee1ce93fd733409cc5305bd823456724ffbcb70a`.
- Stage inicial: vazio.
- Working tree inicial: limpa.
- A listagem física de `docs/MISSIONS/` termina em `MISSION-013`; não existe outra identidade `MISSION-014`.
- O caminho desta missão não existia, rastreado ou não rastreado, no preflight.

## 3. Ratificação de Miguel — transcrição literal e integral

```text
EU, MIGUEL, AUTORIDADE FINAL DE PRODUTO, RATIFICO EXCLUSIVAMENTE A INTENÇÃO B13-OPS-12C-P0 — CONTRATO FAIL-CLOSED DE BINDING NORMATIVO DAS CONSTANTES FISCAIS.

O OBJECTIVO É DEFINIR UM CONTRATO DETERMINÍSTICO E VALIDÁVEL QUE VINCULE CADA CONSTANTE A CONSTANTE_ID, FONTE_ID, VERSÃO, VIGÊNCIA, JURISDIÇÃO, RISCO, INVARIANTES E AUTORIZAÇÃO PARA FUNDAMENTAR DECISÃO.

AUSÊNCIA, CONFLITO, AMBIGUIDADE, VIGÊNCIA INCOMPATÍVEL OU FONTE NÃO AUTORIZADA DEVEM BLOQUEAR RESULTADO FISCAL DEFINITIVO, SEM DEFAULT, FALLBACK OU PRESUNÇÃO.

A FUTURA MISSÃO TÉCNICA DEVE, ANTES DE FIXAR O SEU ESCOPO, RECONCILIAR E JUSTIFICAR DOCUMENTALMENTE A DIVERGÊNCIA ENTRE AS CONTAGENS DE 17 E 13 DEPENDÊNCIAS OU CONSTANTES RESTANTES. DEVE APRESENTAR INVENTÁRIO NOMINAL COMPLETO, INDICANDO ITENS CONCLUÍDOS, RESTANTES, DUPLICADOS, AGRUPADOS OU EXCLUÍDOS E A EVIDÊNCIA DE CADA CLASSIFICAÇÃO. SE A CONTAGEM NÃO PUDER SER RECONCILIADA SEM INFERÊNCIA OU ESCOLHA ARBITRÁRIA, A MISSÃO DEVE BLOQUEAR.

ESTA RATIFICAÇÃO NÃO AUTORIZA ALTERAR VALORES FISCAIS, PROMOVER FONTES PARA PODE_FUNDAMENTAR_DECISAO=true, ESCOLHER SILENCIOSAMENTE NORMAS, INTEGRAR MOTORES, ALTERAR REGIME_ENGINE, EXECUTAR TESTES, MIGRATIONS, DEPLOY, PRODUÇÃO, 9C, 8B2, PILOTO OU UTILIZADORES REAIS.

O PRÓXIMO ACTO AUTORIZADO É SOMENTE A REDACÇÃO DE UMA MISSÃO TÉCNICA ÚNICA, COM ESCOPO, FICHEIROS, TESTES RED/GREEN, CRITÉRIOS DE PARAGEM E RECONCILIAÇÃO DA CONTAGEM EXACTAMENTE DEFINIDOS.

A MISSÃO DEVERÁ SER SUBMETIDA A AUDITORIA GPT, CORRIGIDA SE NECESSÁRIO, CONGELADA EM BYTES E IDENTIFICADA POR SHA-256 EXTERNO. QUALQUER IMPLEMENTAÇÃO OU EXECUÇÃO TÉCNICA DEPENDERÁ DE RATIFICAÇÃO POSTERIOR, EXPRESSA E ESPECÍFICA DE MIGUEL SOBRE ESSA VERSÃO E HASH EXACTOS.

COMMIT, PUSH, DEPLOY E PRODUÇÃO PERMANECEM NÃO AUTORIZADOS.
```

## 4. Autoridade concedida e não concedida

### FACTO DOCUMENTAL — autoridade concedida nesta rodada

Somente redigir esta missão técnica única, reconciliar a contagem, fixar uma proposta de fronteira futura e submetê-la à sequência soberana definida na ratificação.

### FACTO DOCUMENTAL — autoridade não concedida

Não há autoridade para implementar, executar testes, alterar valores fiscais, promover fonte para `pode_fundamentar_decisao=true`, escolher normas, integrar motores, alterar `regime_engine.py`, alterar engines, manifesto, ADR-020, persistência, router ou frontend, executar migrations, rede, deploy, produção, 9C, 8B2, piloto, utilizadores reais, stage, commit, push ou publicação canónica.

## 5. Problema

### FACTO DOCUMENTAL

`docs/B13_OPS_12_DEPENDENCIAS_NORMATIVAS.md` determina que nenhuma constante normativa hardcoded pode operar sem fonte, vigência, tipo de uso, autoridade e risco, e formaliza os invariantes NR-02 e NR-03. O mesmo documento deixa B13-OPS-12C pendente e alterna entre “17 constantes” no estado do sub-bloco e “13 constantes restantes” na indicação do próximo passo.

### FACTO FÍSICO

As dependências ainda existem nos quatro ficheiros físicos inventariados. O manifesto contém fontes usadas pela auditoria, enquanto `SALARIO-MINIMO-001` e `IRPF-PROGRESSIVO-001` permanecem `em_revisao`, com `pode_fundamentar_decisao=false` e sem `hash_referencia`, conforme os testes físicos de manifesto.

## 6. Objectivo único

### PROPOSTA SUJEITA A RATIFICAÇÃO

Definir e validar, sem calcular imposto nem chamar engine, um contrato determinístico fail-closed que represente o binding de uma constante fiscal a `constante_id`, `fonte_id`, `versao`, vigência, jurisdição, risco, invariantes e autoridade da fonte para fundamentar decisão, devolvendo bloqueio estruturado diante de qualquer ausência, invalidade, conflito, ambiguidade ou incompatibilidade.

## 7. Gate soberano — reconciliação nominal 17 versus 13

### FACTO DOCUMENTAL

A lista nominal original é a tabela “Mapa de dependências normativas hardcoded” de `docs/B13_OPS_12_DEPENDENCIAS_NORMATIVAS.md`, com 18 registos. Dezassete são constantes ou regras fiscais; o registo `obter_salario_minimo() fallback silencioso` é uma conduta de fallback e não uma constante fiscal. Daí vem o número 17 usado na linha de estado de B13-OPS-12C.

Dos 17 itens constantes/regras, quatro têm fecho documental histórico anterior ao recorte “restantes”: os dois itens DAS MEI eliminados por B13-OPS-12A e os dois itens encaminhados por B13-OPS-12B. Daí vem o número histórico 13 usado em “Mapear as 13 constantes restantes”. `CONCLUÍDO` nesse histórico não significa conformidade com o novo binding. `IRPF-PROGRESSIVO-001` e `SALARIO-MINIMO-001` ficam classificados `CONCLUIDO_12B_BINDING_PENDENTE`; os dois itens DAS MEI eliminados permanecem historicamente concluídos. O fallback é o décimo oitavo registo da tabela e está concluído fisicamente por B13-OPS-12B-P0D, mas é classificado `EXCLUÍDO` da contagem de constantes.

Equação exacta:

`18 registos originais - 1 EXCLUÍDO da classe constante/regra = 17 constantes/regras; 17 - 4 historicamente CONCLUÍDOS = 13 RESTANTES históricos.`

Totais separados e não intercambiáveis:

- contagem histórica B13-OPS-12: `13`;
- universo actual de constantes/regras existentes que exigem o novo binding: `15`, formado pelos 13 restantes históricos mais `IRPF-PROGRESSIVO-001` e `SALARIO-MINIMO-001`, cujo encaminhamento 12B não completou binding normativo.

Não há itens `DUPLICADO` nem `AGRUPADO`. Nenhum agrupamento foi usado para fechar a soma.

## 8. Inventário nominal completo com evidências

As linhas são identidades documentais da auditoria original; as referências físicas abaixo usam os ficheiros actuais, cujas linhas podem ter evoluído.

| # | Item nominal original | Classificação | Evidência documental | Evidência física verificável |
|---:|---|---|---|---|
| 1 | Tabela Anexo I (Comércio) | RESTANTE | Acção `B13-OPS-12C` na tabela original | `app/services/imposto_service.py`, tabela do Anexo I, linhas 110–120 |
| 2 | Tabela Anexo II (Indústria) | RESTANTE | Acção `B13-OPS-12C` | `app/services/imposto_service.py`, tabela do Anexo II, linhas 122–128 |
| 3 | Tabela Anexo III (Serviços gerais) | RESTANTE | Acção `B13-OPS-12C` | `app/services/imposto_service.py`, tabela do Anexo III, linhas 130–136 |
| 4 | Tabela Anexo IV (INSS separado) | RESTANTE | Acção `B13-OPS-12C` | `app/services/imposto_service.py`, tabela do Anexo IV, linhas 138–144 |
| 5 | Tabela Anexo V (Serv. intelectuais) | RESTANTE | Acção `B13-OPS-12C` | `app/services/imposto_service.py`, tabela do Anexo V, linhas 146–152 |
| 6 | Teto Simples 4.800.000 | RESTANTE | Acção `B13-OPS-12C` | `app/services/imposto_service.py`, limites finais `4_800_000`, linhas 120, 128, 136, 144 e 152 |
| 7 | Tabela IRPF progressiva (5 faixas) | CONCLUIDO_12B_BINDING_PENDENTE | Acção histórica `Adicionado ao manifesto — B13-OPS-12B`; commit `772400251ad624ecc445cbf2fde3d9727b750802`; esse fecho histórico não prova conformidade com o novo binding | `app/services/imposto_service.py`, linhas 53–77; `tests/test_fontes_tributarias_manifest.py` prova `IRPF-PROGRESSIVO-001`, `em_revisao`, `false`, sem hash |
| 8 | Fator R limiar 0.28 | RESTANTE | Acção `B13-OPS-12C` | `app/services/regime_engine.py`, lógica de factor R nas linhas 106–109 |
| 9 | `LIMITE_SIMPLES_ANUAL = 4.800.000` | RESTANTE | Acção `B13-OPS-12C` | `app/services/regime_engine.py:37`, uso nas linhas 278–280 |
| 10 | `_SECAO_PARA_ANEXO` (CNAE→Anexo) | RESTANTE | Acção `B13-OPS-12C` | `app/services/regime_engine.py:41–63`, uso na linha 106 |
| 11 | DAS MEI 756/63 hardcoded | CONCLUÍDO | Marcado “Eliminado B13-OPS-12A”; `docs/B13_OPS_12A_PAD001_DAS_MEI.md`; commit `6073a0ccbf7dc574093eff6dec3bad615263ce5e` | `app/services/regime_engine.py:257` usa `calcular_das_mei(obter_salario_minimo(...))`; não existe literal 756 |
| 12 | `MEI_LIMITE_ANUAL_FATURAMENTO = 81000` | RESTANTE | Acção `B13-OPS-12C` | `app/services/tax_engines/mei_constants.py:6` |
| 13 | `MEI_DAS_FATOR_SALARIO_MINIMO = 0.05` | RESTANTE | Acção `B13-OPS-12C` | `app/services/tax_engines/mei_constants.py:12`, uso na linha 76 |
| 14 | `PARCELA_FIXA` (1.00/5.00) | RESTANTE | Acção `B13-OPS-12C` | `app/services/tax_engines/mei_constants.py:19–22` |
| 15 | `SALARIO_MINIMO_POR_ANO` | CONCLUIDO_12B_BINDING_PENDENTE | Acção histórica `Adicionado ao manifesto — B13-OPS-12B`; commit `772400251ad624ecc445cbf2fde3d9727b750802`; esse fecho histórico não prova conformidade com o novo binding | `app/services/tax_engines/mei_constants.py:28–33`; testes provam `SALARIO-MINIMO-001`, `em_revisao`, `false`, sem hash |
| 16 | `obter_salario_minimo()` fallback silencioso | EXCLUÍDO | Não é constante; marcado “Eliminado B13-OPS-12B-P0D” | `app/services/tax_engines/mei_constants.py:36–47` bloqueia ano ausente com `ValueError` |
| 17 | `_SECOES_FATOR_R = {J,M,S}` | RESTANTE | Acção `B13-OPS-12C` | `app/services/regime_engine.py:66`, uso na linha 107 |
| 18 | DAS MEI legado `1412*0.05+1` | CONCLUÍDO | Marcado “Eliminado B13-OPS-12A”; documento 12A; commit `6073a0ccbf7dc574093eff6dec3bad615263ce5e` | `app/services/tax_engines/mei_engine.py:43–47` delega em funções canónicas; literais legados ausentes |

Totais históricos exclusivos: `CONCLUÍDO=2`, `CONCLUIDO_12B_BINDING_PENDENTE=2`, `RESTANTE=13`, `DUPLICADO=0`, `AGRUPADO=0`, `EXCLUÍDO=1`; total `18`. Contagem histórica B13-OPS-12: `13`. Universo actual que exige novo binding: `15`.

## 9. Fronteira exacta do futuro P0

### PROPOSTA SUJEITA A RATIFICAÇÃO

O futuro P0 fica limitado aos três ficheiros da Secção 11: classes novas e independentes no schema, uma função pública nova no guard e um teste novo. Poderá ler o manifesto pelo mecanismo já existente exclusivamente para verificar existência, metadados e autoridade da fonte. Não poderá calcular imposto, chamar ou importar engine, alterar valor fiscal, modificar `regime_engine.py`, engines fiscais ou manifesto, integrar ADR-020, persistir, expor router ou frontend.

O P0 valida a forma e autoridade de bindings fornecidos; não cria bindings reais para o universo actual de 15, não escolhe normas e não declara qualquer valor fiscal correcto. Se um quarto ficheiro se tornar necessário, a execução deve parar.

## 10. Proposta de contrato fail-closed

### PROPOSTA SUJEITA A RATIFICAÇÃO

O contrato público proposto é exacto.

Enums:

1. `NormativeBindingUsage`: `diagnostico`, `estimativa`, `decisao_definitiva`.
2. `NormativeBindingStatus`: `invalido`, `valido_sem_autoridade_decisoria`, `valido_com_autoridade_decisoria`.
3. `NormativeBindingReasonCode`, nesta precedência exacta: `CAMPO_OBRIGATORIO_AUSENTE`, `CAMPO_DESCONHECIDO`, `CONTEXTO_INVALIDO`, `IDENTIFICADOR_INVALIDO`, `VERSAO_INVALIDA`, `VERSAO_FONTE_INCOMPATIVEL`, `VIGENCIA_INVALIDA`, `VIGENCIA_FONTE_INCOMPATIVEL`, `FORA_DA_VIGENCIA`, `JURISDICAO_INVALIDA`, `JURISDICAO_INCOMPATIVEL`, `RISCO_INVALIDO`, `RISCO_FONTE_INCOMPATIVEL`, `INVARIANTES_INVALIDOS`, `BINDING_DUPLICADO`, `BINDINGS_CONFLITANTES`, `FONTE_INEXISTENTE`, `FONTE_INCOMPLETA`, `FONTE_NAO_AUTORIZADA`, `DECISAO_DEFINITIVA_BLOQUEADA`.

Classes públicas: `NormativeBindingItem`, `NormativeBindingContext`, `NormativeBindingBatchRequest`, `NormativeBindingReason`, `NormativeBindingResult`. Função pública nova: `validar_bindings_normativos(payload: Mapping[str, Any]) -> NormativeBindingResult`. `verificar` não será sobrecarregada nem alterada.

Campos exactos:

- `NormativeBindingItem`: `constante_id` string obrigatória não nula; `fonte_id` string obrigatória não nula; `versao_fonte` string obrigatória não nula; `vigencia_inicio` date obrigatória não nula; `vigencia_fim` campo obrigatório com date ou null; `jurisdicao_codigo` string obrigatória não nula; `risco` valor obrigatório do conjunto fechado físico `alto`, `baixo`, `critico`, `medio`; `invariantes` tuplo obrigatório não vazio de strings.
- `NormativeBindingContext`: `data_referencia` date obrigatória não nula; `jurisdicao_codigo` string obrigatória não nula; `uso_solicitado` obrigatório do enum `NormativeBindingUsage`.
- `NormativeBindingBatchRequest`: `contexto` obrigatório; `bindings` tuplo obrigatório não vazio.
- `NormativeBindingReason`: `code` obrigatório do enum `NormativeBindingReasonCode`; `binding_index` inteiro ou null; `field` string ou null.
- `NormativeBindingResult`: `status`; `autorizado_fundamentar_decisao` booleano derivado somente pela validação; `reasons` tuplo ordenado; `bindings_validados` inteiro não negativo; método JSON canónico UTF-8 com `ensure_ascii=false`, `sort_keys=true` e separadores compactos.

Validação exacta do contexto: `contexto.data_referencia` é obrigatório; chave ausente produz `CAMPO_OBRIGATORIO_AUSENTE`. Quando presente, null, tipo incorrecto, datetime, data ISO `YYYY-MM-DD` malformada ou data de calendário impossível produzem `CONTEXTO_INVALIDO`, com `binding_index=null` e `field="data_referencia"`. `contexto.uso_solicitado` é obrigatório; chave ausente produz `CAMPO_OBRIGATORIO_AUSENTE`. Quando presente, qualquer valor diferente exactamente de `diagnostico`, `estimativa` ou `decisao_definitiva` produz `CONTEXTO_INVALIDO`, com `binding_index=null` e `field="uso_solicitado"`. Não há trim, conversão de caixa, coerção, fallback, data substituta ou uso default. Se ambos os campos forem inválidos, emitem-se duas razões `CONTEXTO_INVALIDO`, ordenadas lexicograficamente por `field`: `data_referencia` antes de `uso_solicitado`. Qualquer `CONTEXTO_INVALIDO` produz `status=invalido`, `autorizado_fundamentar_decisao=false` e `bindings_validados=0`. Com `data_referencia` inválido, não se emite `FORA_DA_VIGENCIA`. Com `uso_solicitado` inválido, não se executa o mapeamento de política de autoridade e não se emite `FONTE_NAO_AUTORIZADA` nem `DECISAO_DEFINITIVA_BLOQUEADA` apenas por esse uso inválido. A validação estrutural dos bindings, a existência e completude das fontes e as verificações pairwise podem ainda executar quando forem independentemente verificáveis. Nenhum valor de contexto substituto pode ser criado.

Todos os modelos proíbem campos desconhecidos e não têm defaults implícitos. Não há trim, conversão de caixa ou normalização Unicode silenciosa. Espaço inicial ou final e caracteres de controlo são rejeitados. Identificadores que mudam sob NFKC são rejeitados. Gramáticas exactas: `constante_id` usa `^[A-Z][A-Z0-9_]{2,127}$`; `fonte_id` usa `^[A-Z0-9][A-Z0-9-]{2,127}$`; `versao_fonte` usa `^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$`; invariante usa `^[A-Z][A-Z0-9_-]{2,127}$`. Invariantes são únicos e já ordenados lexicograficamente; o validador não os reordena nem normaliza.

Semântica temporal: somente datas ISO `YYYY-MM-DD`; datetime é rejeitado. `vigencia_inicio` não admite null. A chave `vigencia_fim` é obrigatória e null significa vigência aberta. Limites são inclusivos; fim anterior ao início é inválido; `data_referencia` deve pertencer ao intervalo inclusivo válido do binding. `FORA_DA_VIGENCIA` fica reservado exclusivamente para `data_referencia` fora desse intervalo válido e nunca substitui incompatibilidade temporal com a fonte.

Semântica de jurisdição: gramática canónica exacta `^(BR|BR-[A-Z]{2}|BR-[A-Z]{2}-[0-9]{7})$`; `BR` é âmbito nacional ou federal, `BR-UF` estadual e `BR-UF-IBGE7` municipal. P0 usa somente igualdade exacta, sem herança ou hierarquia. Códigos diferentes não conflitam e nenhuma precedência é inferida.

Campos físicos da fonte: `versao_fonte` é comparada somente com `fonte["versao"]` na entrada individual da fonte; a `versao` raiz é exclusivamente a versão do manifesto ou catálogo e nunca constitui fallback de versão da fonte. Ausência ou null de `fonte["versao"]` produz `FONTE_INCOMPLETA`; as fontes reais actuais permanecem fail-closed para validação de versão da fonte. Fixtures sintéticas positivas podem conter o campo individual `"versao":"1.0.0"`. Vigência é `vigencia_inicio` e `vigencia_fim` em cada fonte; jurisdição é `jurisdicao`; hash é `hash_referencia`; risco é `risco_se_desatualizada`. Qualquer campo requerido ausente ou null onde o contrato exige valor produz `FONTE_INCOMPLETA`. O P0 não adiciona nem altera campo do manifesto real. O risco do binding deve pertencer exactamente a `alto`, `baixo`, `critico`, `medio` e ser igual ao risco da fonte; ausência ou diferença bloqueia. Como os valores físicos actuais de `jurisdicao` não usam a gramática canónica, casos positivos usam fixture sintética e nenhuma equivalência é inferida.

Compatibilidade temporal exacta com a fonte: cada fonte individual deve conter `vigencia_inicio` válida e a chave `vigencia_fim`; `vigencia_fim` da fonte pode ser date ou null. Campo ausente, `vigencia_inicio` null, formato inválido ou fim anterior ao início produzem `FONTE_INCOMPLETA`; quando a fonte estiver incompleta, não se emite `VIGENCIA_FONTE_INCOMPATIVEL`. O intervalo do binding deve estar integralmente contido no intervalo inclusivo da fonte. `binding.vigencia_inicio` anterior a `fonte.vigencia_inicio` produz `VIGENCIA_FONTE_INCOMPATIVEL`, com `binding_index` do binding e `field="vigencia_inicio"`. Se `fonte.vigencia_fim` for finita, `binding.vigencia_fim` null ou posterior a `fonte.vigencia_fim` produz `VIGENCIA_FONTE_INCOMPATIVEL`, com `binding_index` do binding e `field="vigencia_fim"`. Se `fonte.vigencia_fim` for null, o binding pode ter fim finito ou null. Se início e fim forem incompatíveis, recolhe-se uma razão para cada campo. `VIGENCIA_FONTE_INCOMPATIVEL` torna o resultado `invalido`.

Uso solicitado existe somente em `contexto.uso_solicitado`; não existe campo separado de intenção para fundamentar decisão. Para todos os valores de `NormativeBindingUsage`, a autoridade é consultada por `verificar(SourceAuthorityRequest(fonte_id=..., uso_pretendido="fundamentar_decisao"))`. `diagnostico` e `estimativa` podem ter validade estrutural sem autoridade decisória. Em `decisao_definitiva`, a autoridade é obrigatória e sua ausência adiciona `DECISAO_DEFINITIVA_BLOQUEADA`. O uso solicitado nunca cria, promove ou amplia autoridade. Fonte false permanece false; fonte ausente é inválida. O validador nunca cria resultado fiscal nem autoriza valor fiscal.

Chave exacta de escopo: (`constante_id`, `jurisdicao_codigo`). Um binding é elegível para comparação entre bindings apenas quando não possui nenhuma destas razões estruturais: `CAMPO_OBRIGATORIO_AUSENTE`, `CAMPO_DESCONHECIDO`, `IDENTIFICADOR_INVALIDO`, `VERSAO_INVALIDA`, `VIGENCIA_INVALIDA`, `JURISDICAO_INVALIDA`, `RISCO_INVALIDO`, `INVARIANTES_INVALIDOS`. Razões relativas à fonte — `FONTE_INEXISTENTE`, `FONTE_INCOMPLETA`, `FONTE_NAO_AUTORIZADA`, `VERSAO_FONTE_INCOMPATIVEL`, `VIGENCIA_FONTE_INCOMPATIVEL` e `RISCO_FONTE_INCOMPATIVEL` — não impedem comparação quando todos os campos do payload necessários à comparação forem estruturalmente válidos. Comparam-se pares somente quando ambos forem elegíveis; se algum membro não for elegível, não se emite `BINDING_DUPLICADO` nem `BINDINGS_CONFLITANTES` para esse par. Verifica-se duplicado exacto antes de conflito. Duplicado exacto exige igualdade exacta de todos os campos de `NormativeBindingItem` e produz somente `BINDING_DUPLICADO`, nunca também `BINDINGS_CONFLITANTES`, no índice posterior, com `field="bindings"`. Conflito é avaliado apenas para pares elegíveis, não duplicados, da mesma chave de escopo e com intervalos inclusivamente sobrepostos, e produz `BINDINGS_CONFLITANTES` no índice posterior, com `field="bindings"`. Constantes ou jurisdições diferentes não são comparadas. Intervalos adjacentes conflitam somente se partilharem um dia de calendário. Nenhuma hierarquia ou precedência é inferida.

Metadados canónicos exactos das razões:

| reason | `binding_index` | `field` |
|---|---|---|
| `CAMPO_OBRIGATORIO_AUSENTE` | numérico para campo de binding; null para contexto ou lote | nome exacto do campo ausente |
| `CAMPO_DESCONHECIDO` | numérico se estiver num binding; null se estiver no contexto ou lote | chave desconhecida |
| `CONTEXTO_INVALIDO` | null | `data_referencia` ou `uso_solicitado`, conforme o campo inválido |
| `IDENTIFICADOR_INVALIDO` | índice do binding | `constante_id` ou `fonte_id` |
| `VERSAO_INVALIDA` | índice do binding | `versao_fonte` |
| `VERSAO_FONTE_INCOMPATIVEL` | índice do binding | `versao_fonte` |
| `VIGENCIA_INVALIDA` | índice do binding | `vigencia_inicio` ou `vigencia_fim`, conforme o defeito |
| `VIGENCIA_FONTE_INCOMPATIVEL` | índice do binding | `vigencia_inicio` ou `vigencia_fim`, conforme o defeito |
| `FORA_DA_VIGENCIA` | índice do binding | `data_referencia` |
| `JURISDICAO_INVALIDA` | null para contexto; numérico para binding | `jurisdicao_codigo` |
| `JURISDICAO_INCOMPATIVEL` | índice do binding | `jurisdicao_codigo` |
| `RISCO_INVALIDO` | índice do binding | `risco` |
| `RISCO_FONTE_INCOMPATIVEL` | índice do binding | `risco` |
| `INVARIANTES_INVALIDOS` | índice do binding | `invariantes` |
| `BINDING_DUPLICADO` | índice do item posterior | `bindings` |
| `BINDINGS_CONFLITANTES` | índice do item posterior | `bindings` |
| `FONTE_INEXISTENTE` | índice do binding | `fonte_id` |
| `FONTE_INCOMPLETA` | índice do binding | `fonte_id` |
| `FONTE_NAO_AUTORIZADA` | índice do binding | `fonte_id` |
| `DECISAO_DEFINITIVA_BLOQUEADA` | null | `uso_solicitado` |

Nenhuma razão pode deixar `binding_index` ou `field` à escolha do executor fora destas regras.

O validador recolhe todas as razões independentemente verificáveis sem criar valores substitutos. Ordenação: precedência do enum, `binding_index` com null antes de números e `field` lexicográfico com null antes de texto. A agregação de um batch com N bindings é exacta:

- todos válidos e autorizados: `status=valido_com_autoridade_decisoria`, booleano true, sem razões e `bindings_validados=N`;
- todos válidos mas não autorizados: `status=valido_sem_autoridade_decisoria`, booleano false, um `FONTE_NAO_AUTORIZADA` por índice afectado com `field="fonte_id"` e `bindings_validados=N`; para `decisao_definitiva`, adicionar um `DECISAO_DEFINITIVA_BLOQUEADA` contextual com `binding_index=null` e `field="uso_solicitado"`;
- mistura de válidos autorizados e não autorizados: o mesmo status e booleano do caso anterior, um `FONTE_NAO_AUTORIZADA` por índice não autorizado, `bindings_validados=N` e, para `decisao_definitiva`, um `DECISAO_DEFINITIVA_BLOQUEADA` contextual;
- um ou mais inválidos: `status=invalido`, booleano false, todas as razões ordenadas independentemente verificáveis e `bindings_validados=0`;
- `bindings` vazio: `status=invalido`, booleano false, `CAMPO_OBRIGATORIO_AUSENTE` com `binding_index=null` e `field="bindings"`, e `bindings_validados=0`.

Input idêntico e bytes idênticos de fonte produzem resultado e JSON canónico idênticos.

Baselines imutáveis dos schemas existentes usam canonicalização UTF-8, `ensure_ascii=false`, `sort_keys=true` e separadores compactos. `SourceAuthorityRequest` tem schema de 310 bytes, SHA-256 `C5003C4E23024A399FC1B577115020E17B590021A0CBF045CBE7DA66CAB7AFCF` e dump canónico exacto `{"fonte_id":"LC123-001","uso_pretendido":"fundamentar_decisao"}`. Sua ordem de campos é `fonte_id`, `uso_pretendido`; ambos são obrigatórios sem defaults; usos permitidos são `fundamentar_decisao`, `validar_fato_operacional`, `apoiar_explicacao_ux`, `contexto_llm`; uso ausente produz `missing`; uso inválido produz `literal_error`; `fonte_id=1` produz `string_type`; campos extras são aceites e omitidos do dump.

`SourceAuthorityResult` tem schema de 956 bytes, SHA-256 `971F9F4D2E62052FA1D8A2D9B5F65D74726CAAF4A491A170EE823378F718FDA2` e dump canónico exacto `{"acao":null,"fonte_id":"LC123-001","motivo":"ok","nome":null,"permitido":true,"pode_fundamentar_decisao":null,"pode_ser_usada_por_llm":null,"pode_validar_fato_operacional":null,"tipo":null,"uso_pretendido":"fundamentar_decisao"}`. Sua ordem de campos é `permitido`, `fonte_id`, `nome`, `tipo`, `uso_pretendido`, `motivo`, `acao`, `pode_fundamentar_decisao`, `pode_validar_fato_operacional`, `pode_ser_usada_por_llm`; `permitido`, `fonte_id`, `uso_pretendido` e `motivo` são obrigatórios; os opcionais têm default null e aparecem no dump; `fonte_id=null` produz `string_type`; campos extras são aceites e omitidos; qualquer string é aceite em `uso_pretendido`; `permitido=1` é aceite e convertido em true.

## 11. Ficheiros futuros exactos

### FACTO FÍSICO

Já existem `app/schemas/source_authority_schema.py`, que define o contrato de autoridade de fonte, e `app/services/source_authority_guard.py`, validador determinístico read-only ligado ao manifesto. Não foi encontrado contrato reutilizável que já inclua `constante_id`, versão, vigência, jurisdição, risco e invariantes. Esses dois ficheiros constituem o menor encaixe técnico existente; criar nova camada seria desnecessário.

### PROPOSTA SUJEITA A RATIFICAÇÃO

Somente estes ficheiros poderão integrar a futura implementação P0:

1. `app/schemas/source_authority_schema.py` — somente classes e enums novos e independentes; nenhum campo, default, serialização ou comportamento de `SourceAuthorityRequest` e `SourceAuthorityResult` muda;
2. `app/services/source_authority_guard.py` — somente a nova função pública `validar_bindings_normativos`; assinatura, mensagens, ordem e comportamento observável de `verificar` permanecem exactos;
3. `tests/test_b13_ops_12c_binding_normativo.py` — novo ficheiro dedicado aos RED/GREEN exactos abaixo.

Não existe quarto ficheiro. Qualquer necessidade de quarto ficheiro, nova camada, alteração de manifesto, engine ou teste existente obriga a parar imediatamente e pedir nova autoridade.

## 12. Testes RED exactos

### PROPOSTA SUJEITA A RATIFICAÇÃO

Checkpoint `RED-0`: criar somente `test_api_publica_binding_normativo_existe`, cujo corpo importa os cinco modelos, os três enums e `validar_bindings_normativos`, e executar somente `pytest -q tests/test_b13_ops_12c_binding_normativo.py::test_api_publica_binding_normativo_existe`. Provar falha de importação porque a API nova não existe, parar e registar evidência.

Checkpoint `API-SKELETON`: adicionar somente classes, enums e assinatura pública exactas; a função deve ter comportamento explícito `raise NotImplementedError`; não adicionar validação de negócio. Reexecutar o mesmo node até passar. Não fazer commit.

Para cada comportamento posterior: adicionar exactamente um teste novo, executar somente o node exacto e provar falha de asserção desse comportamento, implementar o mínimo, reexecutar todo `tests/test_b13_ops_12c_binding_normativo.py` acumulado e avançar somente com tudo GREEN.

Payloads canónicos exactos usados pela tabela de testes, sem campos implícitos:

```json
{"contexto":{"data_referencia":"2026-01-01","jurisdicao_codigo":"BR","uso_solicitado":"diagnostico"},"bindings":[{"constante_id":"CONST_001","fonte_id":"SYNTH-001","versao_fonte":"1.0.0","vigencia_inicio":"2025-01-01","vigencia_fim":"2026-12-31","jurisdicao_codigo":"BR","risco":"alto","invariantes":["INV_001"]}]}
```

Este payload chama-se `P0`. `P0D` é exactamente `P0` com `uso_solicitado="decisao_definitiva"`. `P0E` é exactamente `P0` com `uso_solicitado="estimativa"`. A fonte `S_AUTH` é exactamente `{"id":"SYNTH-001","tipo":"normativa_oficial","nome":"Fonte sintética autorizada","pode_fundamentar_decisao":true,"pode_validar_fato_operacional":false,"pode_ser_usada_por_llm":false,"versao":"1.0.0","vigencia_inicio":"2025-01-01","vigencia_fim":"2026-12-31","jurisdicao":"BR","risco_se_desatualizada":"alto","hash_referencia":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`. `S_FALSE` difere somente por `pode_fundamentar_decisao=false`. `S_INCOMPLETE` é `S_AUTH` sem `hash_referencia`. Cada mutação abaixo é aplicada isoladamente a `P0` e todos os campos não citados permanecem byte-for-byte iguais. A expectativa lista `status`, booleano e códigos exactos ordenados; cada razão esperada congela também `binding_index` e `field` exactamente segundo a tabela canónica acima; `bindings_validados=0` para `invalido` e `1` nos demais, salvo testes com dois bindings, em que é `0` se inválido.

1. `test_unknown_field_is_rejected`: adicionar `bindings[0].extra=1`; `invalido`, false, [`CAMPO_DESCONHECIDO`].
2. `test_missing_required_field_is_rejected`: remover `bindings[0].vigencia_fim`; `invalido`, false, [`CAMPO_OBRIGATORIO_AUSENTE`].
3. `test_invalid_identifiers_are_rejected`: definir `constante_id="ＣONST_001"` e `fonte_id=" synth-001"`; `invalido`, false, [`IDENTIFICADOR_INVALIDO`, `IDENTIFICADOR_INVALIDO`], nessa ordem por fields `constante_id`, `fonte_id`.
4. `test_invalid_version_is_rejected`: definir `versao_fonte=" 1.0.0"`; `invalido`, false, [`VERSAO_INVALIDA`].
5. `test_source_mismatched_version_is_rejected`: definir `versao_fonte="2.0.0"`; `invalido`, false, [`VERSAO_FONTE_INCOMPATIVEL`].
6. `test_invalid_interval_is_rejected`: definir `vigencia_inicio="2027-01-01"`, `vigencia_fim="2026-12-31"`; `invalido`, false, [`VIGENCIA_INVALIDA`] com `binding_index=0` e `field="vigencia_fim"`; não emitir `FORA_DA_VIGENCIA`.
7. `test_inclusive_start_boundary_is_valid`: definir `data_referencia="2025-01-01"`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`] com `S_FALSE`.
8. `test_inclusive_end_boundary_is_valid`: definir `data_referencia="2026-12-31"`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`] com `S_FALSE`.
9. `test_open_ended_end_is_valid`: definir binding e `S_FALSE.vigencia_fim=null`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`].
10. `test_outside_validity_is_rejected`: definir `data_referencia="2027-01-01"`; `invalido`, false, [`FORA_DA_VIGENCIA`].
11. `test_invalid_jurisdiction_is_rejected`: definir `jurisdicao_codigo="br"` no contexto e binding; `invalido`, false, [`JURISDICAO_INVALIDA`, `JURISDICAO_INVALIDA`], contexto com `binding_index=null` antes do índice zero.
12. `test_incompatible_jurisdiction_is_rejected`: definir somente `contexto.jurisdicao_codigo="BR-SP"`; `invalido`, false, [`JURISDICAO_INCOMPATIVEL`].
13. `test_invalid_risk_is_rejected`: definir `risco="severo"`; `invalido`, false, [`RISCO_INVALIDO`].
14. `test_source_mismatched_risk_is_rejected`: definir `risco="baixo"`; `invalido`, false, [`RISCO_FONTE_INCOMPATIVEL`].
15. `test_invalid_invariants_are_rejected`: definir `invariantes=["x"]`; `invalido`, false, [`INVARIANTES_INVALIDOS`].
16. `test_duplicated_invariants_are_rejected`: definir `invariantes=["INV_001","INV_001"]`; `invalido`, false, [`INVARIANTES_INVALIDOS`].
17. `test_unsorted_invariants_are_rejected`: definir `invariantes=["INV_002","INV_001"]`; `invalido`, false, [`INVARIANTES_INVALIDOS`].
18. `test_duplicate_binding_is_rejected`: anexar cópia exacta de `bindings[0]`; `invalido`, false, [`BINDING_DUPLICADO`] no índice 1.
19. `test_conflicting_overlapping_binding_is_rejected`: anexar binding igual, excepto `fonte_id="SYNTH-002"`, `vigencia_inicio="2026-01-01"`, `vigencia_fim="2027-12-31"`; fornecer `S_AUTH_2` igual a `S_AUTH`, excepto `id="SYNTH-002"` e vigência igual ao segundo binding; `invalido`, false, [`BINDINGS_CONFLITANTES`] no índice 1.
20. `test_missing_source_is_rejected`: definir `fonte_id="MISSING-001"`; `invalido`, false, [`FONTE_INEXISTENTE`].
21. `test_incomplete_source_is_rejected`: usar `S_INCOMPLETE`; `invalido`, false, [`FONTE_INCOMPLETA`].
22. `test_existing_false_source_is_not_promoted`: usar `P0E` e `S_FALSE`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`].
23. `test_definitive_use_without_authority_is_blocked`: usar `P0D` e `S_FALSE`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`, `DECISAO_DEFINITIVA_BLOQUEADA`].
24. `test_structurally_valid_binding_without_decision_authority`: usar `P0` e `S_FALSE`; `valido_sem_autoridade_decisoria`, false, [`FONTE_NAO_AUTORIZADA`].
25. `test_synthetic_authorized_source_allows_definitive_use`: usar `P0D` e `S_AUTH`; `valido_com_autoridade_decisoria`, true, [].
26. `test_deterministic_reason_ordering`: remover `vigencia_fim`, adicionar `bindings[0].extra=1`, definir `constante_id="x"`, `versao_fonte=" 1"`, `jurisdicao_codigo="br"`, `risco="severo"`, `invariantes=[]` e `fonte_id="MISSING-001"`; `invalido`, false, [`CAMPO_OBRIGATORIO_AUSENTE`, `CAMPO_DESCONHECIDO`, `IDENTIFICADOR_INVALIDO`, `VERSAO_INVALIDA`, `JURISDICAO_INVALIDA`, `RISCO_INVALIDO`, `INVARIANTES_INVALIDOS`, `FONTE_INEXISTENTE`].
27. `test_canonical_json_is_stable`: duas chamadas com `P0D`, `S_AUTH` e bytes de fonte idênticos; ambas `valido_com_autoridade_decisoria`, true, []; bytes JSON exactamente `{"autorizado_fundamentar_decisao":true,"bindings_validados":1,"reasons":[],"status":"valido_com_autoridade_decisoria"}` em UTF-8.
28. `test_real_manifest_bytes_are_unchanged`: usar `P0D` com `S_AUTH` na fixture sintética isolada; `status=valido_com_autoridade_decisoria`, `autorizado_fundamentar_decisao=true`, razões vazias e `bindings_validados=1`. Calcular SHA-256 directamente de `data/fontes_tributarias_manifest.json` antes e depois da chamada enquanto `MANIFEST_PATH` aponta para o ficheiro sintético; os dois hashes do manifesto real devem ser idênticos.
29. `test_existing_verificar_behavior_is_preserved`: para `SourceAuthorityRequest(fonte_id="INEXISTENTE-999", uso_pretendido="fundamentar_decisao")`, resultado exacto `permitido=false`, `fonte_id="INEXISTENTE-999"`, `uso_pretendido="fundamentar_decisao"`, `motivo="Fonte 'INEXISTENTE-999' não existe no manifesto soberano."`, `acao="Verificar o id da fonte em data/fontes_tributarias_manifest.json."`, demais opcionais null.
30. `test_existing_source_authority_models_are_preserved`: comparar directamente schemas JSON, tamanhos, SHA-256, dumps canónicos, ordem de campos, obrigatoriedade, defaults, aceitação, omissão, coerções e erros de `SourceAuthorityRequest` e `SourceAuthorityResult` com os valores imutáveis congelados na Secção 10; não capturar nem alegar capturar estado antigo depois da implementação.
31. `test_validator_does_not_import_or_call_engine`: usar `P0D`, `S_AUTH`, sentinelas de import e chamada para `app.motor_fiscal`, `app.services.regime_engine` e `app.services.tax_engines`; `valido_com_autoridade_decisoria`, true, []; zero imports e zero chamadas.
32. `test_validator_creates_no_fiscal_value_fallback_or_presumption`: usar `P0D`, `S_AUTH`; `valido_com_autoridade_decisoria`, true, []; dump contém exactamente as quatro chaves do resultado, nenhum valor monetário ou fiscal, e nenhuma chamada a fallback ou criação de binding.
33. `test_binding_starts_before_source_validity_is_rejected`: usar `P0`; alterar `binding.vigencia_inicio` para `"2024-12-31"`; manter `S_AUTH` com `vigencia_inicio="2025-01-01"`; `invalido`, false, razão única `VIGENCIA_FONTE_INCOMPATIVEL`, `binding_index=0`, `field="vigencia_inicio"` e `bindings_validados=0`.
34. `test_open_binding_exceeds_finite_source_validity_is_rejected`: usar `P0`; alterar `binding.vigencia_fim` para null; manter `S_AUTH` com `vigencia_fim="2026-12-31"`; `invalido`, false, razão única `VIGENCIA_FONTE_INCOMPATIVEL`, `binding_index=0`, `field="vigencia_fim"` e `bindings_validados=0`.
35. `test_pairwise_checks_skip_structurally_invalid_binding`: usar dois bindings com a mesma chave de escopo e períodos inclusivamente sobrepostos; ambos usam `fonte_id="SYNTH-001"` e a `S_AUTH` existente, completa e autorizada; o segundo binding é cópia exacta do primeiro excepto `invariantes=["x"]`; não criar segunda fonte nem `S_AUTH_2`; por ter `INVARIANTES_INVALIDOS`, o segundo binding é estruturalmente inelegível para comparação pairwise; se `invariantes` fosse uma tupla válida diferente, os dois bindings não duplicados e sobrepostos qualificariam para comparação de conflito; `invalido`, false, razão exactamente única `INVARIANTES_INVALIDOS`, `binding_index=1`, `field="invariantes"`; não emitir `BINDING_DUPLICADO`, `BINDINGS_CONFLITANTES` nem qualquer razão relacionada com fonte; `bindings_validados=0`.

36. `test_invalid_context_reference_date_is_rejected`: usar `P0` e `S_AUTH` completa e autorizada; definir `contexto.data_referencia="2026-02-30"`; `invalido`, false, razão exactamente única `CONTEXTO_INVALIDO`, `binding_index=null`, `field="data_referencia"`; não emitir `FORA_DA_VIGENCIA`; `bindings_validados=0`.
37. `test_invalid_context_usage_is_rejected`: usar `P0` e `S_AUTH` completa e autorizada; definir `contexto.uso_solicitado="definitiva"`; `invalido`, false, razão exactamente única `CONTEXTO_INVALIDO`, `binding_index=null`, `field="uso_solicitado"`; não emitir `FONTE_NAO_AUTORIZADA` nem `DECISAO_DEFINITIVA_BLOQUEADA`; `bindings_validados=0`.
38. `test_invalid_context_reasons_have_deterministic_order`: usar `P0` e `S_AUTH` completa e autorizada; definir `contexto.data_referencia="2026-02-30"` e `contexto.uso_solicitado="definitiva"`; `invalido`, false, exactamente duas razões `CONTEXTO_INVALIDO`; primeira com `binding_index=null` e `field="data_referencia"`; segunda com `binding_index=null` e `field="uso_solicitado"`; `bindings_validados=0`.

## 13. Testes GREEN exactos

### PROPOSTA SUJEITA A RATIFICAÇÃO

Os casos positivos não alteram fontes reais. O teste novo deve monkeypatchar exactamente `app.services.source_authority_guard.MANIFEST_PATH` para um `tmp_path` contendo manifesto sintético e usar `app.services.source_authority_guard._carregar_manifest.cache_clear()` antes e depois de cada caso, com fixture `yield` que restaura o monkeypatch e limpa a cache também no teardown. Loader exacto: `app.services.source_authority_guard._carregar_manifest`; lookup exacto: `app.services.source_authority_guard._fonte_ou_none`; path exacto: `app.services.source_authority_guard.MANIFEST_PATH`; cache exacta: wrapper `functools.lru_cache` exposto por `_carregar_manifest.cache_clear`. Se o isolamento não couber integralmente em `tests/test_b13_ops_12c_binding_normativo.py`, parar porque a fronteira de três ficheiros falhou.

Após o último comportamento, executar o ficheiro novo completo e exigir GREEN. Só então executar, sem editar, os nodes de compatibilidade exactos:

- schema: `tests/test_b13_ops_12c_binding_normativo.py::test_existing_source_authority_models_are_preserved`;
- guard: `tests/test_source_authority_guard.py` completo e `tests/test_b13_ops_12c_binding_normativo.py::test_existing_verificar_behavior_is_preserved`;
- manifesto: `tests/test_fontes_tributarias_manifest.py` completo;
- consumidores `mission_factory`: `tests/test_agent_mission_factory.py::test_factory_valida_cada_fonte_no_guard`, `tests/test_agent_mission_factory.py::test_factory_bloqueia_fonte_nao_permitida`, `tests/test_agent_mission_factory.py::test_factory_sem_fontes_nao_chama_guard`, `tests/test_agent_mission_factory.py::test_factory_rejeita_source_ref_invalida`.

Confirmar que output, assinatura, mensagens, ordem e comportamento observável de `verificar` não mudaram. Zero commits durante RED, skeleton, implementação e GREEN; stage vazio. Depois de GREEN e regressão de compatibilidade, parar para auditoria GPT. Commit e push exigem autorização posterior separada de Miguel.

## 14. Critérios de paragem

Parar sem implementar ou ampliar se:

- a auditoria rejeitar a equação 17/13 ou qualquer classificação nominal;
- a identidade ou o hash ratificado não corresponderem aos bytes congelados;
- surgir colisão de caminho, stage não vazio ou working tree não limpa;
- o menor encaixe técnico deixar de ser inequívoco ou surgir necessidade de quarto ficheiro;
- qualquer teste exigir escolher norma, valor ou comportamento fora do contrato exacto desta minuta;
- for necessário promover fonte, alterar manifesto, engine, `regime_engine.py`, persistência, router, frontend ou ficheiro fora dos três propostos;
- a validação exigir default, fallback ou presunção;
- a fonte `false` tiver de ser alterada para obter GREEN;
- a implementação exigir autoridade inexistente.

## 15. Invariantes de preservação

- `pode_fundamentar_decisao=false` permanece `false`.
- Fonte e manifesto são read-only e byte-identical antes/depois da validação.
- Contratos e comportamento existentes de `SourceAuthorityRequest`, `SourceAuthorityResult` e `verificar` são preservados.
- Nenhum valor fiscal é criado, corrigido, normalizado ou calculado.
- Nenhuma engine é importada ou chamada pelo contrato/validador.
- Ausência, conflito, ambiguidade, fonte não autorizada, jurisdição incompatível e vigência incompatível permanecem bloqueios.
- Nenhum bloqueio pode ser convertido em resultado fiscal definitivo.
- `vigencia_fim=null` significa vigência aberta; ambos os limites existentes são inclusivos.

## 16. Exclusões

Ficam fora: criação dos 15 bindings reais do universo actual; alteração das constantes; escolha ou validação externa de normas; promoção de fontes; cálculo fiscal; engines; `regime_engine.py`; manifesto; ADR-020; migrations; base de dados; persistência; routers; frontend; rede; produção; 9C; 8B2; piloto; utilizadores reais; testes nesta rodada; stage; commit; push; deploy.

## 17. Sequência soberana obrigatória

`auditoria GPT → correcções → congelamento dos bytes → SHA-256 externo → ratificação expressa de Miguel sobre versão e hash exactos → eventual implementação por autorização posterior específica`

Nenhuma etapa posterior pode antecipar a anterior. Esta minuta e o seu hash externo não constituem ratificação nem autorização de implementação.

## 18. Integridade documental

- Codificação requerida: UTF-8 sem BOM.
- Finais de linha requeridos: LF puro.
- Newline final requerido.
- O documento não contém auto-hash; bytes e SHA-256 são calculados externamente depois da escrita.

`B13_OPS_12C_P0_MINUTA_AGUARDA_AUDITORIA_E_RATIFICACAO`
