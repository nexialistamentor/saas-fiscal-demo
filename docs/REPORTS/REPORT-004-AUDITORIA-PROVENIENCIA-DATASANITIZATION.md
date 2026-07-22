# REPORT-004 — Auditoria da proveniência do DataSanitizationAgent

## 1. Identificação da missão

Missão: `MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION`. Gate: `ADR-011-PROVENIENCIA-001`. Baseline auditada: `2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f`.

Estado: PROVADO  
Ficheiro: `docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`  
Linhas: 1-390  
Evidência: missão read-only, documental, limitada ao presente relatório.  
Implicação: nenhuma decisão arquitectural ou implementação é produzida.

## 2. Estado inicial do repositório

```text
branch: main
HEAD:        2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
origin/main: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
REPORT-004 preexistente: não
```

| Ficheiro protegido | Hash índice | Hash normalizado working tree |
|---|---|---|
| `app/agents/adapters/ag_encerramento.py` | `f1880088018a0760d57e09d1866a882fa9898460` | `f1880088018a0760d57e09d1866a882fa9898460` |
| `app/agents/engines/ag_encerramento.py` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` | `ef99aa7e8ced9e1dcd52936467d9bda1c412a17d` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` | `f78b8c15d0d07e2b4aaf23cd45c2d14e34620c3d` |
| `tests/test_ag_encerramento_mission_adapter.py` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` | `5dc8d0c68c526ff16e5adc73a6d734d91dc69ce8` |

Estado: PROVADO  
Ficheiro: estado Git e quatro ficheiros protegidos  
Linhas: não aplicável  
Evidência: hashes índice/working tree iguais e diff nominal vazio; os `M` decorrem de normalização CRLF/LF. A própria missão é um untracked preexistente fornecido como entrada.  
Implicação: baseline e conteúdo protegido preservados; stage inicialmente vazio.

## 3. Metodologia e limites

Leitura estática da fonte candidata, contrato/adapter/engine L3, modelos, base de dados, reader de comparação, contrato/factory de missão, teste autorizado, referências ao gate e migrations directamente relacionadas. Não se reauditaram matérias excluídas pela missão; não se consultaram dados produtivos e não se inferiram regras fiscais ausentes.

## 4. Contrato L3 observado

Estado: PROVADO  
Ficheiro: `app/agents/contracts/data_sanitization.py`  
Linhas: 31-59, 67-106, 143-165  
Evidência: o `DataSanitizationContext` contém `empresa_id` e oito campos fiscais canónicos: `faturamento`, `custos`, `lucro_contabil`, `lucro`, `base_calculo`, `icms_pago`, `icms_devido` e `custo_fiscal_entradas`. `regime` não integra o contrato. O contrato usa `extra="forbid"`, aceita nos valores fiscais os tipos estritos `int|float|str|bool|None`, representa ausência por default `None` e define limite de faturamento.  
Implicação: campos extras são rejeitados; omissão e `null` são estruturalmente distinguíveis por `model_fields_set`.

Estado: PROVADO  
Ficheiro: `app/agents/engines/data_sanitization.py`  
Linhas: 38-107, 117-132  
Evidência: ausência total gera `CONTEXTO_SEM_CAMPOS_FISCAIS`; `None`, texto e booleano geram não-numérico; negativos são preservados no contexto mas sinalizados, sem normalização.  
Implicação: zero numérico é aceite e distingue-se de ausência no contrato L3.

## 5. Fonte produtiva candidata

Estado: PARCIAL  
Ficheiro: `app/services/insights_engine.py`  
Linhas: 68-127  
Evidência: `_montar_contexto_engines` agrega `ItemFiscal`/alias `NotaFiscalItem`, lê `Empresa` e retorna os valores candidatos.  
Implicação: existe fonte implementada, mas não uma proveniência autorizada/canónica para a fronteira L3.

Estado: PROVADO  
Ficheiro: `app/models.py`; `migrations/versions/0000_baseline_soberana.py`; `migrations/versions/0009_add_documento_sha256.py`  
Linhas: 372-468; 60-68, 104-131; 24-33  
Evidência: schema contém proprietário `Empresa.user_id`, documento com empresa, data/tipo/total, itens com `valor_produto`, `valor_icms` e `valor_st`; unicidade apenas de `(empresa_id, conteudo_sha256)` quando hash não nulo.  
Implicação: colunas existem, mas tipo/status fiscal, validade, pagamento efectivo e deduplicação universal não são comprovados pelo schema.

## 6. Matriz dos oito campos

| Campo | Fonte exacta | Fórmula exacta | Filtros e relações | Unidade | Período/cutoff | Ausência versus zero | Negativos | Default | Autorização | Reprodutibilidade | Estado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| faturamento | `itens_fiscais.valor_produto` via `NotaFiscalItem.documento` | `SUM(valor_produto)` | `DocumentoFiscal.empresa_id=empresa_id`, `tipo='saida'`; sem filtro de cancelamento, validade ou duplicata além da constraint parcial por hash | Float; moeda não formalizada | Todo o histórico; sem cutoff | `coalesce(...,0) or 0`: colapsa ausência em zero | Soma preserva negativos | zero silencioso | só `empresa_id` | consulta repetível para BD estável, sem snapshot | INCOMPATÍVEL COM A FRONTEIRA L3 |
| custos | `itens_fiscais.valor_produto` | `SUM(valor_produto)` | mesmos joins; `tipo='entrada'`; sem devolução/cancelamento/validade | Float; valor de produto, não custo contabilístico/aquisição provado | Todo o histórico | colapsada em zero | preservados na soma | zero | só `empresa_id` | idem | INCOMPATÍVEL COM A FRONTEIRA L3 |
| lucro_contabil | faturamento e custos acima | `max(0, faturamento-custos)` | herda todos os filtros/lacunas | Float; semântica contabilística não provada | Todo o histórico | entradas ausentes viram zero | prejuízo truncado | zero derivável | só `empresa_id` | determinístico apenas sobre estado mutável | INCOMPATÍVEL COM A FRONTEIRA L3 |
| lucro | mesmas fontes | `max(0, faturamento-custos)` | idêntico a `lucro_contabil` | Float; fiscal/operacional/contabilístico não provado | Todo o histórico | idem | truncados | zero derivável | só `empresa_id` | idem | INCOMPATÍVEL COM A FRONTEIRA L3 |
| base_calculo | `faturamento`, `custos` e `Empresa.regime_tributario`; sem coluna própria persistida | `lucro = faturamento - custos`; `base_calculo = lucro` se `regime == "real"`; nos restantes casos, `base_calculo = faturamento * 0.08` | agregados por `DocumentoFiscal.empresa_id=empresa_id`; Empresa actual por id; herda ausência de filtros de validade/cutoff | Float; unidade monetária e semântica fiscal canónica não formalizadas | Todo o histórico agregado com regime actual; sem vigência histórica ou cutoff | faturamento/custos ausentes já colapsados em zero | ramo real preserva resultado negativo; ramo não real não representa prejuízo | regime ausente, vazio, nulo ou Empresa inexistente conduz a `presumido`; percentual `0.08` hardcoded | só `empresa_id`, sem actor/tenant/proprietário | limitada por BD e regime mutáveis e ausência de snapshot | INCOMPATÍVEL COM A FRONTEIRA L3 |
| icms_pago | `itens_fiscais.valor_st` | `SUM(valor_st)` | empresa e `tipo='entrada'`; sem prova de ICMS próprio/pagamento | Float; valor declarado de ICMS-ST | Todo o histórico | colapsada em zero | preservados na soma | zero | só `empresa_id` | mesma família XML mutável | INCOMPATÍVEL COM A FRONTEIRA L3 |
| icms_devido | `itens_fiscais.valor_st` | `SUM(valor_st)` | empresa e `tipo='saida'`; sem cálculo independente | Float; valor declarado de ICMS-ST | Todo o histórico | colapsada em zero | preservados na soma | zero | só `empresa_id` | mesma família XML mutável | INCOMPATÍVEL COM A FRONTEIRA L3 |
| custo_fiscal_entradas | variável `custos` | igualdade: `float(custos)` | herda entrada/empresa | Float; impostos incluídos/excluídos não provados | Todo o histórico | colapsada em zero | preservados antes da conversão | zero | só `empresa_id` | duplicação de custos | INCOMPATÍVEL COM A FRONTEIRA L3 |

Estado: NÃO PROVADO  
Ficheiro: `app/services/insights_engine.py`; `app/models.py`  
Linhas: 70-121; 419-468  
Evidência: não há nas consultas filtros de cancelamento, devolução, validade, competência ou pagamento; `tipo` é string nullable sem constraint de domínio.  
Implicação: nenhuma das oito fontes pode ser declarada canónica ou segura para integração.

### Dependência auxiliar não contratual: regime

Estado: INCOMPATÍVEL COM A FRONTEIRA L3  
Ficheiro: `app/services/insights_engine.py`; `app/models.py`; `app/agents/contracts/data_sanitization.py`  
Linhas: 98-101, 108-127; definição de `Empresa.regime_tributario`; 31-40, 143-159  
Evidência: regime é dependência auxiliar da fonte candidata, não campo fiscal canónico do `DataSanitizationContext`. Origina-se em `Empresa.regime_tributario`, texto sem constraint de domínio comprovada; `(valor or "presumido").lower()` e Empresa inexistente produzem silenciosamente `presumido`, tornando ausência, vazio e nulo indistinguíveis. O estado actual, sem validade histórica, escolhe a fórmula de `base_calculo`; se enviado no dicionário bruto, é campo extra rejeitado por `extra="forbid"`.  
Implicação: regime não integra o contrato; o seu domínio, default, vigência e uso fiscal continuam não ratificados.

## 7. Fronteira temporal

Estado: NÃO PROVADO  
Ficheiro: `app/services/insights_engine.py`  
Linhas: 68-106  
Evidência: agregações não filtram `data_emissao`; `max(data_emissao)` é calculado depois e retornado como `data_referencia`. Não há início, fim, competência, `reference_at`, exclusão de documentos posteriores ou tratamento explícito de data inválida/nula.  
Implicação: `data_referencia` é informativa, não cutoff; a leitura abrange todo o histórico disponível no instante da consulta.

## 8. Ausência, zero, negativos e defaults

Estado: INCOMPATÍVEL COM A FRONTEIRA L3  
Ficheiro: `app/services/insights_engine.py`  
Linhas: 70-121  
Evidência: nos campos contratuais, quatro somas usam `coalesce(...,0)` e `or 0`, colapsando ausência em zero; `lucro` e `lucro_contabil` usam `max(0,lucro)`, truncando negativos. Separadamente, `regime` é dependência auxiliar de `base_calculo`: ausência, nulo, vazio ou Empresa inexistente usa `presumido`. A atribuição de `base_calculo` preserva `faturamento-custos` negativo no ramo real; no ramo não real usa faturamento agregado e não representa prejuízo.  
Implicação: ausência não é preservada e zero real não é distinguido nos agregados; há truncamento nos dois campos de lucro e default silencioso auxiliar que altera a fórmula de `base_calculo`.

## 9. Fronteira de autorização

Estado: NÃO PROVADO  
Ficheiro: `app/services/insights_engine.py`  
Linhas: 68-106  
Evidência: a função recebe somente `empresa_id`; consultas filtram somente esse id. Não recebem/comprovam `actor_id`, `tenant_id`, propriedade `Empresa.user_id`, coerência das três identidades ou reconfirmação final.  
Implicação: a origem candidata não é uma leitura autorizada L3.

Estado: PROVADO (padrão comparativo, não solução ratificada)  
Ficheiro: `app/agents/readers/ag_encerramento.py`  
Linhas: 31-127, 194-213  
Evidência: Session injectada, `no_autoflush`, actor igual a tenant, Empresa filtrada por id/proprietário, predicado de autoridade nas consultas, reconfirmação final e retorno de snapshot sem ORM/Session.  
Implicação: estes controlos são requisitos técnicos candidatos comprovados; nenhum reader foi implementado nesta missão.

## 10. Compatibilidade com extra="forbid"

Estado: INCOMPATÍVEL COM A FRONTEIRA L3  
Ficheiro: `app/services/insights_engine.py`; `app/agents/contracts/data_sanitization.py`; `app/agents/adapters/data_sanitization.py`  
Linhas: 108-127; 143-159; 164-190  
Evidência: o contrato aceita `empresa_id` e exactamente os oito campos fiscais canónicos; os valores fiscais admitem os tipos estritos previstos pelo contrato, não apenas valores numéricos. O contexto produtivo contém ainda `db`, `data_referencia`, `regime`, `atividade` e `context_flags`, todos extras; o adapter valida o dict directamente.  
Implicação: `_montar_contexto_engines` não pode ser entregue directamente ao adapter: `extra="forbid"` rejeita os extras, uma Session não pode atravessar a fronteira, e `regime` não integra o contrato.

## 11. Reprodutibilidade e context_hash

Estado: PARCIAL  
Ficheiro: `app/agents/contracts/mission.py`; `app/agents/mission_factory.py`  
Linhas: 25-28, 70-71, 226-250; 183-203, 206-241  
Evidência: a factory calcula `context_hash` e o contrato reconfirma-o por construção canónica.  
Implicação: um contexto já projectado pode ter hash determinístico, mas a origem actual não tem cutoff/snapshot, inclui Session não serializável e muda com a BD; logo não produz directamente contexto/hash reprodutível.

## 12. Requisitos mínimos do futuro reader/projector

### Requisitos obrigatórios comprovados

- entrada explícita com `actor_id`, `tenant_id`, `empresa_id` e período/`reference_at` efectivo;
- autorização actor/tenant/Empresa antes de qualquer leitura, predicada nas agregações e reconfirmada antes do retorno;
- Session injectada, consultas read-only sob `no_autoflush`, sem escrita;
- regras explícitas de documento válido, cancelamento, devolução e duplicata;
- preservar ausência, zero real e negativos separadamente;
- não devolver ORM/Session; projectar somente campos aceites pelo contrato;
- agregações/ordenação determinísticas, unidade e fórmula documentadas;
- excluir documentos posteriores ao cutoff e definir tratamento de datas nulas/inválidas;
- contexto serializável e apto a `context_hash` reproduzível.
- projectar `base_calculo` apenas após decisão ratificada da fórmula;
- não transportar `regime`; utilizá-lo somente como input autorizado e temporalmente coerente se decisão futura o ratificar.

## 13. Decisões ainda não ratificadas

Fonte/fórmula/unidade canónicas de faturamento e custos; distinção entre lucro e lucro contabilístico; significado canónico de `base_calculo`; fórmula por regime; autoridade normativa do percentual `0.08`; vigência temporal do regime; comportamento perante regime ausente; domínio de regimes; semântica e prova de ICMS pago/devido; significado e composição de custo fiscal de entradas; período/competência; política sobre cancelamentos, devoluções, documentos inválidos e duplicatas. Nenhuma opção é seleccionada neste relatório.

## 14. Teste autorizado

Estado: PROVADO (teste isolado autorizado)  
Ficheiro: `tests/test_data_sanitization_mission_adapter.py`  
Linhas: teste completo  
Evidência: após preflight correcto na raiz, `python -m pytest -q tests/test_data_sanitization_mission_adapter.py` terminou com exit code 0. Resultado literal: `81 passed in 0.55s`.  
Implicação: prova apenas contrato, engine e adapter isolados cobertos pelo ficheiro; não prova a fonte produtiva candidata nem reader/projector, não fecha ADR-011 e não autoriza integração produtiva.

## 15. Matriz do gate ADR-011-PROVENIENCIA-001

| Item | Estado | Evidência | BLOQUEIA INTEGRAÇÃO PRODUTIVA |
|---|---|---|---|
| Fonte canónica dos oito campos | NÃO PROVADO | apenas candidata em `insights_engine.py:68-127` | SIM |
| Fórmula e unidade | PARCIAL | fórmulas implementadas; unidade/semântica não formalizada | SIM |
| Base de cálculo — fonte/fórmula/semântica | NÃO PROVADO | fórmula implementada, mas semântica, percentual, regime e vigência não ratificados | SIM |
| Período/cutoff | NÃO PROVADO | todo histórico; MAX apenas informativo | SIM |
| Ausência versus zero | NÃO PROVADO | `coalesce/or 0` | SIM |
| Preservação de negativos | PARCIAL | somas preservam; lucros truncam | SIM |
| Dependência auxiliar regime — domínio/default/vigência | NÃO PROVADO | texto sem domínio; default silencioso `presumido`; estado actual aplicado ao histórico | SIM |
| Semântica de ICMS | NÃO PROVADO | `valor_st` declarado, sem pagamento/cálculo independente | SIM |
| Semântica de custo_fiscal_entradas | NÃO PROVADO | simples alias de custos | SIM |
| Autorização actor/tenant/empresa | NÃO PROVADO | filtro apenas por empresa | SIM |
| Projector mínimo | PARCIAL | requisitos factuais listados, arquitectura não ratificada | SIM |
| Compatibilidade com contrato | NÃO PROVADO | extras e Session violam `extra="forbid"` | SIM |
| Reprodutibilidade | PARCIAL | hash canónico existe; fonte sem cutoff/snapshot | SIM |
| Testes existentes | PARCIAL | `81 passed in 0.55s` prova apenas contrato, engine e adapter isolados | SIM |

O gate permanece aberto; este relatório não o fecha.

## 16. Riscos não resolvidos

- soma de histórico ilimitado e mutável;
- inclusão potencial de cancelamentos, devoluções, inválidos e duplicatas sem hash;
- confusão de valor de produto com faturamento/custo e de ICMS-ST declarado com pago/devido;
- duplicação semântica de lucros e custos;
- perda de ausência e prejuízo; default de regime;
- regime actual aplicado ao histórico integral e default silencioso `presumido`;
- fórmula não ratificada de `base_calculo` e percentual `0.08` hardcoded, sem fundamento normativo provado nesta missão;
- omissão anterior de `base_calculo` na matriz dos oito campos, corrigida pela MISSION-005;
- leitura sem isolamento de tenant/proprietário;
- Session e extras no contexto; ausência de projector autorizado;
- divergência temporal entre leitura e hash; teste autorizado recolhido com `81 passed in 0.55s`; a prova permanece limitada ao contrato, engine e adapter isolados e não comprova fonte produtiva, reader/projector ou fechamento do ADR-011.

## 17. Estado final do repositório

```text
branch: main
HEAD:        2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
origin/main: 2ac68bb09045fe5e0fc9c198523a29a2af8b2f4f
git status --short:
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
?? docs/MISSIONS/MISSION-004-B14-SVC-01-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
?? docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md
git diff --name-only: vazio
git diff --cached --name-only: vazio
```

Estado: PROVADO  
Ficheiro: estado Git final e quatro ficheiros protegidos  
Linhas: não aplicável  
Evidência: branch e referências mantêm a baseline; stage vazio; hashes índice/working tree dos quatro protegidos continuam exactamente iguais aos registados na secção 2. A missão mantém hash `9147de697dc16628caa42a27a72dca059eacc803`. O único artefacto criado pelo executor é REPORT-004; o outro untracked é a missão preexistente.  
Implicação: nenhuma alteração protegida, commit ou push; apenas o relatório autorizado foi criado nesta execução.

## 18. Declaração de não alteração

Até à criação deste documento, nenhum código, teste, ADR, contrato, migration ou configuração foi alterado; não houve stage, commit ou push. As alterações preexistentes foram preservadas. A missão de entrada permaneceu não rastreada.

## 19. Estado da execução

Estado da execução: EXECUTADA COM PENDÊNCIAS (gate permanece aberto; teste autorizado recolhido com `81 passed in 0.55s`, limitado ao escopo isolado).  
Relatório criado: `docs/REPORTS/REPORT-004-AUDITORIA-PROVENIENCIA-DATASANITIZATION.md`  
Outros ficheiros alterados: NENHUM  
Gate ADR-011-PROVENIENCIA-001: ABERTO — decisão GPT e ratificação Miguel pendentes  
Stage: VAZIO  
Commit: NÃO EFECTUADO  
Push: NÃO EFECTUADO  
Auditoria: PENDENTE — autoridade GPT  
Ratificação: PENDENTE — autoridade Miguel
