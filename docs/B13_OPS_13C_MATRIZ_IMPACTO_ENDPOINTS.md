# B13-OPS-13C — Matriz de Impacto por Endpoint

**Data:** 2026-07-02  
**HEAD:** `ae6a166`  
**Pré-requisitos concluídos:** B13-OPS-13A (tempo normativo explícito), B13-OPS-13B (manifesto EC132/LC214/CBS-IBS), B13-OPS-13E (MVA/ST com `data_referencia`)  
**Referência:** `docs/B13_OPS_13_MOTOR_TEMPORAL_NORMATIVO.md`

---

## Princípio deste bloco

Mapear **promessas públicas** de cada endpoint fiscal e classificar o **estado L3** (`operacional` | `parcial` | `bloqueado`) **sem alterar motores nem implementar CBS/IBS**.

A matriz responde: *o que o endpoint promete*, *de onde vem o tempo normativo*, *o que acontece se faltar*, e *o que continua pendente*.

---

## Legenda

### Classificação temporal (Grupo A/B/C/D)

| Grupo | Significado |
|-------|-------------|
| **A** | Tempo normativo real — `data_referencia` / `vigencia_inicio/fim` / `data_emissao` do documento persistido |
| **B** | Recebe campo temporal no request, mas o serviço subjacente não o usa para resolver norma |
| **C** | Constantes ou tabelas hardcoded sem vigência versionada |
| **D** | Sem campo temporal no contrato público nem inferência confiável |

### Estado L3 exposto ao cliente

| Estado | Significado |
|--------|-------------|
| **operacional** | Cálculo/decisão autorizado quando pré-condições normativas satisfeitas |
| **parcial** | Resposta útil, mas com lacuna normativa explícita (`calculo_parcial`, skip de NCM, alertas) |
| **bloqueado** | HTTP 422 estruturado ou resposta com `bloqueado: true` / `estado_l3: bloqueado` |

### Payload de bloqueio temporal (padrão 13A)

```json
{
  "bloqueado": true,
  "tipo_bloqueio": "TEMPO_NORMATIVO_AUSENTE",
  "estado_l3": "bloqueado",
  "erro": "..."
}
```

### CBS / IBS / Reforma

| Estado | Regra |
|--------|-------|
| **bloqueado** (todos) | Zero implementação no codebase. Fontes EC132-001, LC214-001, CBS-IBS-2026-001 no manifesto com `pode_fundamentar_decisao=false`. INVARIANTE-REFORMA-03/04 aplicam-se a qualquer endpoint futuro. |

---

## Resumo executivo

| Área | Endpoints fiscais | Operacional | Parcial | Bloqueado (temporal) | CBS/IBS |
|------|-------------------|-------------|---------|----------------------|---------|
| `/imposto` | 3 | 0 | 1 | 2 (MEI sem ano) | n/a |
| `/formalizacao` | 3 | 2 | 0 | 1 (regimes sem ano) | n/a |
| `/relatorio` | 14 | 8 | 2 | 4 (MEI + engines empresa) | n/a |
| `/assistente` | 1 | 0 | 1 | 1 (MEI) | n/a |
| `/fiscal` + `/lote` | 5 | 5 | 0 | 0 | n/a |
| `/insights` + `/inteligencia` | 22 | 6 | 16 | 0 | n/a |
| `/analise-st` | 4 | 4* | 0 | 0 | n/a |
| `/cpf` | 1 | 0 | 1 | 0 | n/a |
| `/dashboard` | 12 | 12 | 0 | 0 | n/a |

\* ST operacional quando documentos persistidos têm `data_emissao` e UF/NCM dentro do piloto PA; fora disso → parcial via `resolver_aliquota_e_mva`.

**Achados P0 remanescentes (documentados, não corrigidos neste bloco):**

1. `POST /cpf/dashboard` — Grupo **D**: cálculo CPF sem tempo normativo no request.
2. Endpoints `/inteligencia/*` que chamam `resolver_aliquota_e_mva` sem `data_referencia` explícita — inferem de dados persistidos; **parcial** fora do piloto PA.
3. Engines LP/LR/PIS-COFINS em pipeline XML — Grupo **C** parcial: usam `resolver_ano_referencia` pós-13A, mas constantes internas ainda sem vigência versionada.
4. **CBS/IBS** — bloqueado em 100% dos endpoints até sub-bloco futuro dedicado.

---

## 1. `/imposto` — cálculo directo (Grupo D original → pós-13A)

| Método | Rota | Promessa pública | Input temporal | Serviço / engine | Grupo | Estado L3 | CBS/IBS | Testes |
|--------|------|------------------|----------------|------------------|-------|-----------|---------|--------|
| POST | `/imposto/calcular` | Imposto mensal/anual MEI ou CPF | `ano_referencia` opcional (MEI) | `executar_analise(mei_tax\|cpf_tax)` | A† / D‡ | **bloqueado** MEI sem ano; **operacional** MEI com ano; CPF sem exigência | bloqueado | `test_b13_ops_13a` |
| POST | `/imposto/simular-ano` | Projeção anual + alertas limite MEI | `ano_referencia` opcional | `calcular_imposto_simples()` | A / D | **bloqueado** MEI sem ano | bloqueado | — |
| POST | `/imposto/simples-nacional` | DAS Simples Nacional por anexo | `ano_referencia` ou `data_referencia` | `calcular_imposto_simples_nacional()` — tabela `_ANEXOS` fixa | **A/C** | **bloqueado** sem ano/data; **parcial** com ano (tabela interna, validação normativa L3 pendente) | bloqueado | `test_b13_ops_13a_bloqueio_tempo_normativo` |

† MEI com `ano_referencia` → Grupo A via `obter_salario_minimo(ano)`.  
‡ CPF não exige tempo normativo — engine fora de `BaseTaxEngine`.

---

## 2. `/formalizacao` — orquestração empresarial (F)

| Método | Rota | Promessa pública | Input temporal | Serviço | Grupo | Estado L3 | CBS/IBS | Testes |
|--------|------|------------------|----------------|---------|-------|-----------|---------|--------|
| POST | `/formalizacao/recomendar-cnae` | CNAE + compatibilidade MEI/regimes | n/a (heurística CNAE) | `recomendar_cnaes()` | — | **operacional** (não calcula tributo) | bloqueado | `test_b13_p0_formalizacao` |
| POST | `/formalizacao/comparar-regimes` | Comparação LP/LR/Simples/MEI | `ano_referencia` **ou** `data_referencia` | `comparar_regimes()` + `_exigir_tempo_normativo()` | A | **bloqueado** sem ano/data; **operacional** com ano | bloqueado | `test_regime_engine` |
| POST | `/formalizacao/simular-empresa` | CNAE + regime numa resposta | idem | idem + CNAE | A | idem | bloqueado | `test_b13_p0_formalizacao` |

---

## 3. `/relatorio` — relatórios e PDFs

| Método | Rota | Promessa pública | Input temporal | Serviço / pipeline | Grupo | Estado L3 | CBS/IBS | Testes |
|--------|------|------------------|----------------|---------------------|-------|-----------|---------|--------|
| POST | `/relatorio/gerar-relatorio` | Preview JSON pós XML | `data_emissao` do XML persistido | `executar_e_registrar_analise_xml` → InsightEngine | **A** | **operacional** / **parcial**† | bloqueado | — |
| POST | `/relatorio/relatorio-pdf` | PDF pós XML | idem | idem | **A** | idem | bloqueado | — |
| POST | `/relatorio/gerar` | PDF completo paywall | dados persistidos empresa | `gerar_mapa_oportunidades` | **A** | **parcial**† | bloqueado | — |
| GET | `/relatorio/relatorio-pdf/{perfil_id}` | Download PDF paywall | idem | idem | **A** | **parcial**† | bloqueado | — |
| GET | `/relatorio/{relatorio_id}` | Relatório persistido | snapshot persistido | leitura DB | — | **operacional** (dado congelado) | bloqueado | — |
| GET | `/relatorio/memorial/{id}` | Memorial de cálculo | snapshot | `coletar_contexto_memorial` | — | **operacional** | bloqueado | — |
| GET | `/relatorio/memorial/{id}/pdf` | Memorial PDF | idem | idem | — | **operacional** | bloqueado | — |
| GET | `/relatorio/tax_planning` | Planejamento tributário | inferido de NF-e / pergunta | `simular_planejamento_tributario` → `tax_planning` | **B/C** | **parcial** — engines exigem contexto temporal | bloqueado | — |
| GET | `/relatorio/tax_recovery` | Recuperação tributária | idem | `simular_recuperacao` / InsightEngine | **A/C** | **parcial** | bloqueado | — |
| POST | `/relatorio/mei_tax` | Persiste relatório MEI/CPF | `ano_referencia` opcional | `calcular_imposto_simples()` | A / D | **bloqueado** MEI sem ano | bloqueado | `test_b13_ops_13a` |
| GET | `/relatorio/mei_tax/{id}` | PDF MEI persistido | snapshot | leitura DB | — | **operacional** | bloqueado | — |
| POST | `/relatorio/imposto-pdf` | PDF imposto MEI/CPF | `ano_referencia` opcional | `calcular_imposto_simples()` | A / D | **bloqueado** MEI sem ano | bloqueado | `test_b13_ops_13a` |
| GET | `/relatorio/empresas/{id}/engines` | Resultados engines persistidos | snapshot | `EngineResultadoService` | — | **operacional** | bloqueado | — |
| GET | `/relatorio/{analysis_type}` | GET genérico tax_* | — | roteamento interno | — | ver linhas acima | bloqueado | — |

† Parcial quando UF ≠ PA, NCM sem cobertura MVA, ou engine retorna `TEMPO_NORMATIVO_AUSENTE` embutido em `resultados_engines`.

---

## 4. `/assistente` — interface conversacional

| Método | Rota | Promessa pública | Input temporal | Serviço | Grupo | Estado L3 | CBS/IBS | Testes |
|--------|------|------------------|----------------|---------|-------|-----------|---------|--------|
| POST | `/perguntar` | Resposta fiscal por NLU | inferido da pergunta; MEI exige ano na pergunta ou bloqueia | `responder_pergunta()` → `imposto_service` / InsightEngine / agents | **B/D** | **bloqueado** fluxo MEI sem ano (`bloqueado` no JSON, não 422); **parcial** empresa | bloqueado | `test_b13_ops_13a` (serviço) |

**Promessa implícita:** não inventar tributo — pedir ano quando MEI. Empresa/Simples usa dados persistidos ou preview limitado.

**Simples Nacional via assistente:** bloqueia sem `ano_referencia` — devolve mensagem textual pedindo o ano (não usa relógio do servidor). Limitação: bloqueio é texto livre, não estruturado (`bloqueado`/`tipo_bloqueio`/`estado_l3`) como o fluxo MEI. Melhoria futura, não bloqueante.

---

## 5. `/fiscal` + `/lote` — pipeline XML (E)

| Método | Rota | Promessa pública | Input temporal | Pipeline | Grupo | Estado L3 | CBS/IBS | Testes |
|--------|------|------------------|----------------|----------|-------|-----------|---------|--------|
| POST | `/fiscal/analisar-xml` | Análise unitária NF-e | `data_emissao` no XML | `processar_xml_job` → `executar_analise_xml` → persistência → InsightEngine | **A** | **operacional** / **parcial** | bloqueado | vários XML |
| GET | `/fiscal/analise/status/{job_id}` | Status job | n/a | fila RQ | — | **operacional** | n/a | — |
| DELETE | `/fiscal/analise/cancelar/{job_id}` | Cancelar job | n/a | fila RQ | — | **operacional** | n/a | — |
| POST | `/lote/analisar-lote` | Lote XML | `data_emissao` por nota | mesmo pipeline | **A** | idem | bloqueado | — |
| GET | `/lote/job/{job_id}` | Status lote | n/a | fila | — | **operacional** | n/a | — |

**Invariante arquitectural respeitada:** XML → persistir → enriquecer (InsightEngine) → agents sob gatilho.

---

## 6. `/insights` + `/inteligencia` — inteligência sobre dados persistidos (E)

### 6.1 Insight agregado

| Método | Rota | Promessa pública | Input temporal | Serviço | Grupo | Estado L3 |
|--------|------|------------------|----------------|---------|-------|-----------|
| POST | `/insights/{empresa_id}` | Painel completo de insights | `data_emissao` dos itens persistidos | `InsightEngine.gerar_insights_empresa()` | **A** | **operacional** / **parcial** |

### 6.2 Inteligência granular (`/inteligencia/*`)

Todos leem **dados já persistidos** (nunca XML bruto). Serviços com cálculo financeiro ST/MVA usam `resolver_aliquota_e_mva` — skip silencioso quando `calculo_autorizado=false`.

| Método | Rota | Usa MVA/ST | Estado L3 | Nota |
|--------|------|------------|-----------|------|
| GET | `/inteligencia/oportunidades-recuperacao/{id}` | indireto | **parcial** | ranking sobre créditos detectados |
| GET | `/inteligencia/ranking-restituicao/{id}` | sim | **parcial** | PA piloto |
| GET | `/inteligencia/mapa-oportunidades/{id}` | sim | **parcial** | decomposição impacto |
| GET | `/inteligencia/creditos/{id}` | sim | **parcial** | skip NCM não autorizado |
| GET | `/inteligencia/distorcoes/{id}` | sim (MVA) | **parcial** | `mva_autorizada` required |
| GET | `/inteligencia/oportunidades-preditivas/{id}` | sim | **parcial** | |
| GET | `/inteligencia/ranking-estrategico/{id}` | sim | **parcial** | |
| GET | `/inteligencia/impacto-financeiro/{id}` | sim | **parcial** | |
| GET | `/inteligencia/indice-inteligencia/{id}` | agregado | **operacional** | métricas compostas |
| GET | `/inteligencia/score-tributario/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/radar-tributario/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/benchmark-empresas` | agregado | **operacional** | |
| GET | `/inteligencia/anomalias-tributarias/{id}` | sim | **parcial** | |
| GET | `/inteligencia/prioridade-auditoria/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/projecao-recuperacao/{id}` | sim | **parcial** | |
| GET | `/inteligencia/risco-tributario/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/eficiencia-tributaria/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/complexidade-tributaria/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/maturidade-tributaria/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/score-global-tributario/{id}` | agregado | **operacional** | |
| GET | `/inteligencia/historico-inteligencia/{id}` | série temporal | **operacional** | |
| GET | `/inteligencia/tendencia-inteligencia/{id}` | série temporal | **operacional** | |
| GET | `/inteligencia/comparacao-temporal/{id}` | série temporal | **operacional** | |

**Promessa pública comum:** interpretação de dados persistidos, não processamento primário de XML.

---

## 7. `/analise-st` — substituição tributária (E, pós-13E)

| Método | Rota | Promessa pública | Input temporal | Serviço | Grupo | Estado L3 |
|--------|------|------------------|----------------|---------|-------|-----------|
| GET | `/analise-st/{empresa_id}` | Restituição ST total | `item.documento.data_emissao` | `STAnalyzer.calcular_restituicao` | **A** | **operacional** / **parcial** |
| GET | `/analise-st/resumo/{empresa_id}` | idem | idem | idem | **A** | idem |
| GET | `/analise-st/ncm/{empresa_id}` | ST por NCM | idem | `analise_por_ncm` | **A** | idem |
| GET | `/analise-st/periodo/{empresa_id}` | ST no período | `data_inicio`, `data_fim` query | `analise_por_periodo` | **A** | **operacional** |

Pós-13E: `buscar_mva` / `buscar_pmpf` exigem `data_referencia` — STAnalyzer propaga `data_emissao`.

---

## 8. `/cpf` — contribuinte pessoa física

| Método | Rota | Promessa pública | Input temporal | Serviço | Grupo | Estado L3 |
|--------|------|------------------|----------------|---------|-------|-----------|
| POST | `/cpf/dashboard` | Resumo imposto CPF | **nenhum** | `CPFDashboardService.calcular_resumo` | **D** | **parcial** — calcula sem ano/data |
| POST | `/cpf/documentos/upload` | Upload rendimento | n/a | persistência | — | **operacional** |
| POST | `/cpf/documentos/confirmar` | Confirma rendimento | `ano_referencia` opcional (metadado) | persistência | — | **operacional** (não calcula) |

---

## 9. `/dashboard` — apresentação (D)

Endpoints **não calculam** — leem `RelatorioAnalise`, `AlertaFiscal`, `EngineResultado` persistidos.

| Método | Rota | Promessa | Estado L3 |
|--------|------|----------|-----------|
| GET | `/dashboard/analises/{empresa_id}` | Histórico análises | **operacional** |
| GET | `/dashboard/relatorio/{relatorio_id}` | Detalhe análise | **operacional** |
| GET | `/dashboard/relatorio/{id}/alertas` | Alertas do relatório | **operacional** |
| GET | `/dashboard/relatorio/{id}/oportunidades` | Oportunidades | **operacional** |
| GET | `/dashboard/risco/{empresa_id}` | Risco agregado | **operacional** |
| GET | `/dashboard/resumo/{empresa_id}` | Resumo cards | **operacional** |
| GET | `/dashboard/alertas/{empresa_id}` | Alertas empresa | **operacional** |
| GET | `/dashboard/alertas/timeline/{empresa_id}` | Timeline | **operacional** |
| GET | `/dashboard/alertas/agentes/{empresa_id}` | Por agente | **operacional** |
| PATCH | `/dashboard/alertas/silenciar/{id}` | Silenciar alerta | **operacional** |
| PATCH | `/dashboard/alertas/restaurar/{id}` | Restaurar alerta | **operacional** |
| GET | `/dashboard/alertas/grafico/{empresa_id}` | Gráfico alertas | **operacional** |

**Impacto temporal:** reflecte qualidade do cálculo upstream (XML/insights). Dashboard em si = **Grupo —** (read-only).

---

## 10. Endpoints periféricos (sem cálculo fiscal primário)

| Prefixo | Rotas | Impacto temporal | Estado |
|---------|-------|------------------|--------|
| `/auth/*` | registo, login, termos | n/a | operacional |
| `/empresas/*` | listagem, vínculo contador | n/a | operacional |
| `/documentos/*` | listagem documentos | metadados | operacional |
| `/ingestao/documentos` | ingestão | `data_emissao` na persistência | operacional |
| `/contador/*` | homologações | n/a | operacional |
| `/estoque/*` | auditoria estoque | n/a | operacional |
| `/system/metrics` | métricas | n/a | operacional |

---

## 11. Mapa serviços → contrato temporal

| Serviço | `ano_referencia` | `data_referencia` | Bloqueio explícito | Campos soberanos |
|---------|------------------|-------------------|--------------------|------------------|
| `BaseTaxEngine.resolver_ano_referencia` | sim | sim | `TempoNormativoAusenteError` | — |
| `fiscal_utils.resolver_aliquota_e_mva` | via date | sim | `calculo_autorizado`, `mva_autorizada`, `calculo_parcial` | sim |
| `tabela_normativa_service.buscar_mva` | — | sim (13E) | retorna None | `vigencia_inicio/fim` |
| `imposto_service.calcular_imposto_simples` | MEI obrigatório | — | `TempoNormativoAusenteError` | — |
| `imposto_service.calcular_imposto_simples_nacional` | **não** | **não** | nenhum | — |
| `regime_engine.comparar_regimes` | obrigatório | via formalização | raise / 422 upstream | — |
| `InsightEngine` | via contexto | `data_emissao` item | `estado_l3: bloqueado` por engine | `resultados_engines` |
| `assistente_service` | inferido / bloqueio MEI | filtros documento | soft block MEI | — |
| `STAnalyzer` | — | `data_emissao` | skip via resolver | — |

---

## 12. Cobertura de testes (grep `tests/`)

| Contrato | Ficheiro teste | Coberto |
|----------|----------------|---------|
| MEI bloqueio 422 `/imposto/calcular` | `test_b13_ops_13a_bloqueio_tempo_normativo.py` | sim |
| MEI bloqueio `/relatorio/mei_tax`, `/imposto-pdf` | idem | sim |
| Assistente MEI pede ano | idem | sim |
| `resolver_ano_referencia` engines | `test_b13_ops_13a_motor_temporal.py` | sim |
| Formalização com `ano_referencia` | `test_b13_p0_formalizacao.py` | sim |
| `calculo_autorizado` MVA | `test_dt_mva_01.py` | sim |
| `buscar_mva` + `data_referencia` | `test_buscar_mva_prioridade_fonte.py`, `test_tabela_pmpf.py` | sim |
| `/imposto/simples-nacional` temporal | — | **não** |
| `/cpf/dashboard` temporal | — | **não** |
| `/inteligencia/*` parcial PA | — | **não** |
| CBS/IBS | — | **n/a** (bloqueado by design) |

---

## 13. Decisões explícitas (este bloco)

1. **Não implementar CBS/IBS** — nenhum endpoint expõe ou calcula IBS/CBS/IS; manifesto 13B mantém `pode_fundamentar_decisao=false`.
2. **Não alterar motores** — matriz documenta estado actual pós-13A/13E; engines LP/LR/PIS-COFINS permanecem Grupo C internamente.
3. **Promessas públicas mapeadas** — tabelas acima são a fonte para frontend, OpenAPI e testes de contrato.
4. **Próximo sub-bloco sugerido (13D?)** — fechar lacunas P0 da matriz:
   - `POST /imposto/simples-nacional` → exigir `ano_referencia` ou `data_referencia` + bloqueio 422
   - `POST /cpf/dashboard` → alinhar com contrato temporal CPF
   - Testes de contrato para `/inteligencia/*` fora do piloto PA (resposta parcial explícita)
   - Documentar no OpenAPI os campos `estado_l3` / `calculo_parcial` onde aplicável

---

## 14. Relação com invariantes da Reforma

| Invariante | Endpoints afectados | Estado actual |
|------------|---------------------|---------------|
| REFORMA-01 — cálculo exige tempo normativo | `/imposto/simples-nacional`, `/cpf/dashboard` | **REFORMA-01:** cumprido em `/imposto/simples-nacional` desde ae6a166 (B13-OPS-13A.1). Violação remanescente: `/cpf/dashboard`. |
| REFORMA-02 — regime temporal declarado | todos engines | **parcial** — não exposto no API |
| REFORMA-03 — CBS/IBS 2026 ≠ tributo comum | todos | **ok** — bloqueado |
| REFORMA-04 — fase não internalizada → bloquear | CBS/IBS futuros | **ok** — zero código |

---

*Documento gerado por inventário estático (routes + services + tests). Revalidar após qualquer alteração de contrato HTTP.*
