
# B13-OPS-13 — Motor Temporal Normativo / Reforma Tributária



**Data:** 2026-06-30

**HEAD:** `7724002`

**Referência:** `docs/B13_OPS_12_DEPENDENCIAS_NORMATIVAS.md`, `docs/B13_OPS_08_RESOLUCAO_NORMATIVA_L3.md`



---



## Princípio



Nenhum cálculo fiscal pode existir sem saber **em que tempo normativo está a operar**.



O achado do salário mínimo (B13-OPS-12B) provou que o problema não é só "ter tabela" — é não ter mecanismo que bloqueie o uso de tempo normativo desactualizado ou invisível.



Este documento generaliza essa lição para toda a plataforma, incluindo a Reforma Tributária (EC 132/2023, LC 214/2025).



---



## 1. Classificação A/B/C/D — Inventário Temporal



### Grupo A — Já tem data/vigência real (padrão L3 maduro)



| Ficheiro | Mecanismo |

|----------|-----------|

| `tabela_normativa_service.py` | `data_referencia` + `vigencia_inicio/fim` — filtro temporal activo |

| `fiscal_utils.resolver_aliquota_e_mva()` | `data_referencia` + `calculo_autorizado` |

| `st_service.py` | `data_referencia=item.documento.data_emissao` |

| `motor_predicao_tributaria.py` | `data_referencia=doc.data_emissao` |

| `insights_engine.py` (pós B13-OPS-09) | `data_referencia=item.documento.data_emissao` |

| `pipeline_normativo.py` | `vigencia_inicio/fim` na ingestão |

| `normative_update_service.py` | Encerra (`vigencia_fim`), nunca apaga |

| `parsers/sefaz_sp_parser.py` | Vigência por portaria (SRE 89/2025) |

| `parsers/sefaz_mg_parser.py` | Vigência jan-jun 2026 modelada |



### Grupo B — Recebe data, mas não usa para resolver norma



| Ficheiro | Problema |

|----------|----------|

| `imposto_service.py` | `ano_atual = datetime.now().year` — usa ano do sistema, não data do documento |

| `regime_engine.py` | `_ano_atual = datetime.date.today().year` — idem |

| `insights_engine.py:337` | Expõe `_ano_vigencia` dos engines — valor fixo herdado |

| `tax_engines/irpj_adicional.py` | Aceita `data_referencia` mas não é obrigatória |

| `assistente_service.py` | Usa data para filtrar documentos, não para resolver norma |



### Grupo C — Usa ano fixo/hardcoded



| Ficheiro | Constante |

|----------|-----------|

| **`tax_engines/base_tax_engine.py:15`** | **`ano_vigencia = 2024`** — herdado por todos os engines |

| `scripts/seed_mva.py` | `vigencia_inicio: date(2024, 1, 1)` (seed) |

| `tax_engines/pis_cofins_engine.py` | Constantes sem vigência (72 ocorrências) |

| `tax_engines/lucro_real_engine.py` | Constantes sem vigência (23 ocorrências) |

| `tax_engines/lucro_presumido_engine.py` | Constantes sem vigência |

| `tax_engines/tax_recovery_engine.py` | Constantes sem vigência |

| `tax_engines/mei_constants.py` | Parcialmente resolvido (B13-OPS-12B) |



### Grupo D — Não tem data nenhuma



| Endpoint/Componente | Problema |

|---------------------|----------|

| `POST /imposto/calcular` | Sem `data_referencia` no request |

| `POST /imposto/simular-ano` | Sem `data_referencia` |

| `POST /imposto/simples-nacional` | Sem `data_referencia` |

| `POST /formalizacao/comparar-regimes` | Sem `data_referencia` |

| **CBS / IBS / EC 132/2023 / LC 214/2025** | **Zero implementação no codebase** |



---



## 2. Achado P0 Temporal — `base_tax_engine.ano_vigencia`



```python

# app/services/tax_engines/base_tax_engine.py:15

ano_vigencia = 2024

```



**Por que é P0:** todos os engines fiscais herdam esta classe. O valor é fixo em 2024, mesmo operando em 2026. `InsightEngine` expõe este valor via `res["_ano_vigencia"]`.



**Regra L3 (não negociável):** não se troca `2024` por `2026`. Isso seria o mesmo erro do salário mínimo — hardcoded novo substituindo hardcoded velho. A correcção correcta é **eliminar a dependência invisível**, não actualizar o número.



**Acção formal:** `B13-OPS-13A` — auditar quem instancia `BaseTaxEngine`, impedir cálculo sem ano/data normativa explícita, ou marcar resposta como `parcial`/`bloqueada` quando usar `ano_vigencia` fixo.



---



## 3. CBS / IBS — Reforma Tributária Ausente



A EC 132/2023 alterou o Sistema Tributário Nacional. A LC 214/2025 instituiu IBS, CBS e Imposto Seletivo. 2026 é ano-teste: CBS 0,9%, IBS 0,1%, compensáveis com PIS/COFINS no mesmo período. Documentos fiscais eletrônicos passam por adequação obrigatória para campos IBS/CBS em 2026, conforme cronograma e orientações oficiais aplicáveis.



**Estado real no codebase:** zero referências a CBS, IBS, EC 132/2023, LC 214/2025, fases de transição.



**Decisão de classificação (não confundir fonte com cálculo):**



| Camada | Estado |

|--------|--------|

| **Fonte normativa** (EC132-001, LC214-001) | `em_revisao` no manifesto — são tributos reais, não vedação |

| **Cálculo/decisão fiscal** com CBS/IBS | `bloqueado` — sem matriz temporal, fonte, vigência, hash e testes |



CBS/IBS não são `proibida_para_decisao` (essa categoria é para LLM e fontes vedadas institucionalmente). São `normativa_oficial` `em_revisao` — fonte real, ainda não internalizada.



---



## 4. Invariantes Reforma (a formalizar em código em sub-blocos seguintes)

INVARIANTE-REFORMA-01:

Nenhum cálculo fiscal pode executar sem data de referência normativa.

INVARIANTE-REFORMA-02:

Todo motor fiscal deve declarar regime temporal:

pre_reforma | ano_teste | transicao | regime_definitivo.

INVARIANTE-REFORMA-03:

CBS/IBS 2026 não podem ser tratados como tributo definitivo comum.

Devem ter estado próprio: teste | compensável | informativo | exigível.

INVARIANTE-REFORMA-04:

Se a fase normativa não estiver internalizada, o cálculo deve bloquear

ou responder como parcial/não provado — nunca silenciosamente "funcionar".



---



## 5. Próximos sub-blocos



| Sub-bloco | Objectivo | Escopo |

|-----------|-----------|--------|

| **B13-OPS-13A** | Eliminar `ano_vigencia` fixo de `BaseTaxEngine` | Auditar callers, impedir cálculo sem data explícita |

| **B13-OPS-13B** | Manifesto: EC132-001, LC214-001, CBS-IBS-2026-001 | `em_revisao`, `pode_fundamentar_decisao=false` |

| **B13-OPS-13C** | Matriz de impacto por endpoint (G/D/E/F/relatórios/dashboard) | Quais endpoints ficam `bloqueado`/`parcial` até resolução |



**Regra de ordem:** 13A antes de 13B antes de 13C. Não pular etapas.



---



## 6. Relação com B13-OPS-12



Este bloco generaliza a lição aprendida em `B13-OPS-12B-P0C/P0D`:



> O problema nunca foi só "ter o valor errado". Foi a ausência de mecanismo que impedisse o sistema de calcular com tempo normativo desactualizado ou invisível — silenciosamente.



`base_tax_engine.ano_vigencia = 2024` é o equivalente estrutural, em escala maior, ao `SALARIO_MINIMO_POR_ANO[2026] = 1518.00` que já corrigimos.


