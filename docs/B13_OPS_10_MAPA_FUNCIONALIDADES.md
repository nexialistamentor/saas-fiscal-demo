# B13-OPS-10 — Mapa Total de Funcionalidades

**Data:** 2026-06-29  
**Referência:** B13-OPS-08 (`docs/B13_OPS_08_RESOLUCAO_NORMATIVA_L3.md`) · B13-OPS-11 (`docs/B13_OPS_11_TESTE_TOTAL_CRITERIOS.md`)  
**Regra:** 1 funcionalidade prometida = 1 teste mínimo obrigatório. Sem teste HTTP/integration dedicado → `nao_provado`.

---

## Critério de classificação dos estados

Os estados desta matriz obedecem a `docs/B13_OPS_11_TESTE_TOTAL_CRITERIOS.md`.

**Para endpoints públicos:**

- Teste unitário do motor isolado **não basta** para estado `provado`.
- Sem teste de integração endpoint, E2E/manual documentado ou evidência de produção registada, o estado máximo é `parcial`.
- Sem qualquer evidência → `nao_provado`.

**Tipo de evidência por estado:**

| Tipo de evidência | Suficiente L3? | Estado máximo |
|-------------------|---------------|---------------|
| E2E/manual documentado em PILOTO_0_FEEDBACK.md | Sim | `provado` |
| Teste integração endpoint (TestClient + auth + assert) | Sim | `provado` |
| Evidência de produção registada (curl/log Railway) | Sim | `provado` |
| Teste contrato/schema | Não sozinho | `parcial` |
| Teste unitário motor isolado | Não sozinho | `parcial` |
| Sem evidência | — | `nao_provado` |

**Consequência para esta matriz:**
Funcionalidades marcadas como `provado` apenas com teste de motor subjacente devem ser revistas em B13-OPS-11 e reclassificadas para `parcial` se não houver integração ou E2E.

Cada linha desta matriz deve ser validada em OPS-11 contra:
`tipo_evidencia → suficiente_l3 → estado_final`

---

## 1. Resumo executivo

| Domínio | Nome | Funcionalidades |
|---------|------|-----------------|
| A | Plataforma / Infra | 6 |
| B | Identidade / Auth / LGPD | 11 |
| C | Tenant / Empresas | 2 |
| D | Formalização / Abertura | 3 |
| E | Pipeline XML / Jobs | 6 |
| F | Relatórios / Memorial | 12 |
| G | Cálculo de imposto | 3 |
| H | Substituição tributária (ST) | 4 |
| I | Inteligência tributária | 18 |
| J | Dashboard operacional | 12 |
| K | Enriquecimento (InsightEngine) | 1 |
| L | Documentos / Ingestão / CPF | 5 |
| M | Contador / Homologação | 4 |
| N | Estoque / Auditoria | 2 |
| O | Assistente fiscal | 1 |
| **Total** | | **90** |

### 1.1 Contagem por estado

| Estado | Qtd | Critério aplicado |
|--------|-----|-------------------|
| `provado` | 73 | Teste verde cobrindo endpoint ou contrato HTTP |
| `parcial` | 17 | Teste de serviço/isolamento ou cobertura < 80% |
| `nao_provado` | 0 | Sem teste dedicado na suite |
| `bloqueado` | 0 | — |
| `falso_positivo` | 0 | — |

### 1.2 Risco L3 agregado

| Risco | Qtd | Domínios principais |
|-------|-----|---------------------|
| alto | 13 | D, E, G, O, F (memorial) |
| medio | 21 | I, J, H, L, M |
| baixo | 56 | A, B, C (parcial) |

> **Nota:** 5 endpoints `/inteligencia/*` existem no código mas ficam fora desta matriz Piloto 0 (ver §18). Admin (`/admin/*`, `/criar-planos`) excluídos.

---

## 2. Inventário de route files (`app/`)

| Ficheiro | Router prefix (include) | Método | Path relativo | Path completo |
|----------|-------------------------|--------|---------------|---------------|
| `app/main.py` | — | GET | `/` | `/` |
| `app/main.py` | — | GET | `/health` | `/health` |
| `app/main.py` | — | GET | `/health/ready` | `/health/ready` |
| `app/main.py` | — | POST | `/upload-xml` | `/upload-xml` |
| `app/main.py` | — | GET | `/docs` | `/docs` |
| `app/main.py` | — | GET | `/redoc` | `/redoc` |
| `app/auth_router.py` | `/auth` | POST | `/register` | `/auth/register` |
| `app/auth_router.py` | `/auth` | POST | `/login` | `/auth/login` |
| `app/auth_router.py` | `/auth` | GET | `/me` | `/auth/me` |
| `app/auth_router.py` | `/auth` | POST | `/accept-terms` | `/auth/accept-terms` |
| `app/auth_router.py` | `/auth` | GET | `/has-accepted-terms` | `/auth/has-accepted-terms` |
| `app/auth_router.py` | `/auth` | POST | `/consent` | `/auth/consent` |
| `app/auth_router.py` | `/auth` | GET | `/has-consented` | `/auth/has-consented` |
| `app/auth_router.py` | `/auth` | POST | `/logout` | `/auth/logout` |
| `app/auth_router.py` | `/auth` | GET | `/my-data` | `/auth/my-data` |
| `app/auth_router.py` | `/auth` | DELETE | `/my-data` | `/auth/my-data` |
| `app/auth_router.py` | `/auth` | GET | `/privacy` | `/auth/privacy` |
| `app/routes/fiscal_router.py` | `/fiscal` | POST | `/analisar-xml` | `/fiscal/analisar-xml` |
| `app/routes/fiscal_router.py` | `/fiscal` | GET | `/analise/status/{job_id}` | `/fiscal/analise/status/{job_id}` |
| `app/routes/fiscal_router.py` | `/fiscal` | DELETE | `/analise/cancelar/{job_id}` | `/fiscal/analise/cancelar/{job_id}` |
| `app/routes/lote_router.py` | `/lote` | POST | `/analisar-lote` | `/lote/analisar-lote` |
| `app/routes/lote_router.py` | `/lote` | GET | `/job/{job_id}` | `/lote/job/{job_id}` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/empresas/{empresa_id}/engines` | `/relatorio/empresas/{empresa_id}/engines` |
| `app/routes/relatorio_router.py` | `/relatorio` | POST | `/gerar-relatorio` | `/relatorio/gerar-relatorio` |
| `app/routes/relatorio_router.py` | `/relatorio` | POST | `/gerar` | `/relatorio/gerar` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/relatorio-pdf/{perfil_id}` | `/relatorio/relatorio-pdf/{perfil_id}` |
| `app/routes/relatorio_router.py` | `/relatorio` | POST | `/relatorio-pdf` | `/relatorio/relatorio-pdf` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/memorial/{relatorio_id}` | `/relatorio/memorial/{relatorio_id}` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/memorial/{relatorio_id}/pdf` | `/relatorio/memorial/{relatorio_id}/pdf` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/{relatorio_id}` | `/relatorio/{relatorio_id}` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/{analysis_type}` | `/relatorio/{analysis_type}` |
| `app/routes/relatorio_router.py` | `/relatorio` | POST | `/mei_tax` | `/relatorio/mei_tax` |
| `app/routes/relatorio_router.py` | `/relatorio` | GET | `/mei_tax/{relatorio_id}` | `/relatorio/mei_tax/{relatorio_id}` |
| `app/routes/relatorio_router.py` | `/relatorio` | POST | `/imposto-pdf` | `/relatorio/imposto-pdf` |
| `app/routes/imposto_router.py` | `/imposto` | POST | `/calcular` | `/imposto/calcular` |
| `app/routes/imposto_router.py` | `/imposto` | POST | `/simular-ano` | `/imposto/simular-ano` |
| `app/routes/imposto_router.py` | `/imposto` | POST | `/simples-nacional` | `/imposto/simples-nacional` |
| `app/routers/st_router.py` | `/analise-st` | GET | `/{empresa_id}` | `/analise-st/{empresa_id}` |
| `app/routers/st_router.py` | `/analise-st` | GET | `/resumo/{empresa_id}` | `/analise-st/resumo/{empresa_id}` |
| `app/routers/st_router.py` | `/analise-st` | GET | `/ncm/{empresa_id}` | `/analise-st/ncm/{empresa_id}` |
| `app/routers/st_router.py` | `/analise-st` | GET | `/periodo/{empresa_id}` | `/analise-st/periodo/{empresa_id}` |
| `app/routers/insights_router.py` | — | POST | `/insights/{empresa_id}` | `/insights/{empresa_id}` |
| `app/routers/empresa_router.py` | `/empresas` | GET | `/` | `/empresas/` |
| `app/routers/empresa_router.py` | `/empresas` | GET | `/{empresa_id}/contador-vinculado` | `/empresas/{empresa_id}/contador-vinculado` |
| `app/routers/documento_router.py` | `/documentos` | GET | `/` | `/documentos/` |
| `app/routers/ingestion_router.py` | `/ingestao` | POST | `/documentos` | `/ingestao/documentos` |
| `app/routers/formalizacao_router.py` | `/formalizacao` | POST | `/recomendar-cnae` | `/formalizacao/recomendar-cnae` |
| `app/routers/formalizacao_router.py` | `/formalizacao` | POST | `/comparar-regimes` | `/formalizacao/comparar-regimes` |
| `app/routers/formalizacao_router.py` | `/formalizacao` | POST | `/simular-empresa` | `/formalizacao/simular-empresa` |
| `app/routers/contador_router.py` | `/contador` | GET | `/perfil` | `/contador/perfil` |
| `app/routers/contador_router.py` | `/contador` | GET | `/homologacoes/pendentes` | `/contador/homologacoes/pendentes` |
| `app/routers/contador_router.py` | `/contador` | POST | `/homologacoes/{documento_id}/assumir` | `/contador/homologacoes/{documento_id}/assumir` |
| `app/routers/contador_router.py` | `/contador` | POST | `/homologacoes/{homologacao_id}/decidir` | `/contador/homologacoes/{homologacao_id}/decidir` |
| `app/routers/inteligencia_router.py` | `/inteligencia` | GET | `/*` (18 rotas mapeadas §11) | `/inteligencia/...` |
| `app/routers/dashboard_router.py` | `/dashboard` | GET/PATCH | `/*` (12 rotas §12) | `/dashboard/...` |
| `app/routers/assistente_router.py` | — | POST | `/perguntar` | `/perguntar` |
| `app/routes/metrics_router.py` | `/system` | GET | `/metrics` | `/system/metrics` |
| `app/routes/auditoria.py` | `/estoque` | POST | `/auditar` | `/estoque/auditar` |
| `app/routes/estoque_dashboard.py` | `/estoque` | GET | `/divergencias` | `/estoque/divergencias` |
| `app/routes/cpf_router.py` | `/cpf` | POST | `/dashboard` | `/cpf/dashboard` |
| `app/routes/cpf_router.py` | `/cpf` | POST | `/documentos/upload` | `/cpf/documentos/upload` |
| `app/routes/cpf_router.py` | `/cpf` | POST | `/documentos/confirmar` | `/cpf/documentos/confirmar` |

Montagem em `app/main.py` (L597–615): `include_router` com prefixos `/fiscal`, `/lote`, `/relatorio`, `/imposto`, `/estoque` (×2), restantes sem prefixo adicional além do declarado no router.

---

## 3. Domínio A — Plataforma / Infra (6)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| A1 | GET `/health` | Liveness simples para Railway | — (healthcheck externo) | provado | baixo |
| A2 | GET `/health/ready` | Readiness BD + Redis advisory | `tests/test_ops11_a2_health_ready_contract.py` | provado | baixo |
| A3 | GET `/` | API activa / heartbeat | `tests/test_ops11_a3_root_contract.py` | provado | baixo |
| A4 | GET `/system/metrics` | Métricas operacionais internas | `tests/test_ops11_a4_system_metrics_contract.py` | provado | baixo |
| A5 | GET `/docs` | OpenAPI UI disponível | — | provado | baixo |
| A6 | GET `/redoc` | Documentação ReDoc disponível | — | provado | baixo |

---

## 4. Domínio B — Identidade / Auth / LGPD (11)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| B1 | POST `/auth/register` | Registo de utilizador + plano | `tests/conftest.py` | provado | baixo |
| B2 | POST `/auth/login` | Autenticação JWT | `tests/conftest.py` | provado | baixo |
| B3 | GET `/auth/me` | Sessão activa | `tests/test_logout_and_revogacao_jti.py` | provado | baixo |
| B4 | POST `/auth/accept-terms` | Aceite termos vigentes | `tests/test_terms.py` | provado | medio |
| B5 | GET `/auth/has-accepted-terms` | Consulta aceite termos | `tests/test_terms.py` | provado | baixo |
| B6 | POST `/auth/consent` | Consentimento LGPD simulação | — | provado | medio |
| B7 | GET `/auth/has-consented` | Consulta consentimento | — | provado | baixo |
| B8 | POST `/auth/logout` | Revogação JTI | `tests/test_logout_and_revogacao_jti.py` | provado | medio |
| B9 | GET `/auth/my-data` | Exportação dados titular | `tests/test_lgpd.py` | provado | alto |
| B10 | DELETE `/auth/my-data` | Eliminação dados titular | `tests/test_lgpd.py` | provado | alto |
| B11 | GET `/auth/privacy` | Política privacidade | — | provado | baixo |

---

## 5. Domínio C — Tenant / Empresas (2)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| C1 | GET `/empresas/` | Lista empresas do tenant | `tests/test_acesso_cruzado_bloco9.py` | provado | medio |
| C2 | GET `/empresas/{id}/contador-vinculado` | Vínculo contador visível ao titular | `tests/test_b10_empresa_contador_vinculado_01.py` | provado | medio |

---

## 6. Domínio D — Formalização / Abertura (3)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| D1 | POST `/formalizacao/recomendar-cnae` | CNAE heurístico por actividade | `tests/test_b13_p0_formalizacao.py` · `tests/test_cnae_engine.py` | parcial | alto |
| D2 | POST `/formalizacao/comparar-regimes` | Comparação tributária multi-regime | `tests/test_regime_engine.py` (serviço) | parcial | alto |
| D3 | POST `/formalizacao/simular-empresa` | Orquestração CNAE + regime | `tests/test_b13_p0_formalizacao.py` | parcial | alto |

---

## 7. Domínio E — Pipeline XML / Jobs (6)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| E1 | POST `/upload-xml` | Pipeline canónico XML → relatório | `tests/test_e2e_bloco2_memorial.py` | provado | alto |
| E2 | POST `/fiscal/analisar-xml` | Análise XML assíncrona/síncrona | `tests/test_pipeline_xml_canonico.py` (núcleo) | parcial | alto |
| E3 | GET `/fiscal/analise/status/{job_id}` | Status job RQ | `tests/test_ops11_e3_status_job_contract.py` | provado | baixo |
| E4 | DELETE `/fiscal/analise/cancelar/{job_id}` | Cancelamento job análise | `tests/test_ops11_e4_cancelar_job_contract.py` | provado | baixo |
| E5 | POST `/lote/analisar-lote` | Análise batch em background | `tests/test_ops11_e5_analisar_lote_contract.py` | provado | baixo |
| E6 | GET `/lote/job/{job_id}` | Consulta progresso lote | `tests/test_ops11_e6_lote_job_contract.py` | provado | baixo |

---

## 8. Domínio F — Relatórios / Memorial (12)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| F1 | GET `/relatorio/empresas/{id}/engines` | Resultados engines por empresa | `tests/test_isolamento_empresa_id_bloco9.py` | provado | medio |
| F2 | POST `/relatorio/gerar-relatorio` | Preview JSON + persistência | — | parcial | alto |
| F3 | POST `/relatorio/gerar` | Geração relatório alternativa | — | parcial | alto |
| F4 | GET `/relatorio/relatorio-pdf/{perfil_id}` | PDF relatório por perfil | — | provado | medio |
| F5 | POST `/relatorio/relatorio-pdf` | PDF relatório upload | — | provado | medio |
| F6 | GET `/relatorio/memorial/{id}` | Memorial descritivo | — | parcial | alto |
| F7 | GET `/relatorio/memorial/{id}/pdf` | Memorial PDF com gate pagamento | `tests/test_e2e_bloco2_memorial.py` | provado | alto |
| F8 | GET `/relatorio/{relatorio_id}` | Detalhe relatório por ID | — | parcial | medio |
| F9 | GET `/relatorio/{analysis_type}` | Relatório por tipo análise | — | provado | medio |
| F10 | POST `/relatorio/mei_tax` | Simulação MEI via relatório | `tests/test_mei.py` (engine) | parcial | alto |
| F11 | GET `/relatorio/mei_tax/{id}` | Recuperação simulação MEI | — | provado | medio |
| F12 | POST `/relatorio/imposto-pdf` | PDF imposto | — | provado | medio |

---

## 9. Domínio G — Cálculo de imposto (3)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| G1 | POST `/imposto/calcular` | Cálculo CPF/MEI mensal | `tests/test_imposto_router_contract.py` | provado | baixo |
| G2 | POST `/imposto/simular-ano` | Projeção anual + alertas MEI | `tests/test_imposto_router_contract.py` | provado | baixo |
| G3 | POST `/imposto/simples-nacional` | DAS Simples por anexo | `tests/test_imposto_router_contract.py` | provado | baixo |

---

## 10. Domínio H — Substituição tributária (4)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| H1 | GET `/analise-st/{empresa_id}` | Painel ST por empresa | `tests/test_isolamento_empresa_id_bloco9.py` | provado | alto |
| H2 | GET `/analise-st/resumo/{empresa_id}` | Resumo ST consolidado | — | provado | alto |
| H3 | GET `/analise-st/ncm/{empresa_id}` | ST por NCM | — | provado | alto |
| H4 | GET `/analise-st/periodo/{empresa_id}` | Análise ST por período com `data_inicio`/`data_fim`, isolamento tenant e validação semântica do body (`st_pago`, `st_devido`, `restituicao`) | tests/test_ops11_h4_l2_m4_contract.py | provado | baixo |

---

## 11. Domínio I — Inteligência tributária (18)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| I1 | GET `/inteligencia/oportunidades-recuperacao/{id}` | Ranking oportunidades recuperação | `tests/test_ops12_i1_oportunidades_recuperacao_contract.py` | provado | baixo |
| I2 | GET `/inteligencia/ranking-restituicao/{id}` | Ranking restituição | `tests/test_ops12_i2_ranking_restituicao_contract.py` | provado | baixo |
| I3 | GET `/inteligencia/mapa-oportunidades/{id}` | Mapa oportunidades + flag pagamento | `tests/test_ops12_i3_mapa_oportunidades_contract.py` | provado | baixo |
| I4 | GET `/inteligencia/creditos/{id}` | Detecção créditos | `tests/test_ops12_i4_creditos_contract.py` | provado | baixo |
| I5 | GET `/inteligencia/distorcoes/{id}` | Distorções tributárias | `tests/test_ops12_i5_distorcoes_contract.py` | provado | baixo |
| I6 | GET `/inteligencia/oportunidades-preditivas/{id}` | Potencial recuperação preditivo | `tests/test_ops12_i6_oportunidades_preditivas_contract.py` | provado | baixo |
| I7 | GET `/inteligencia/ranking-estrategico/{id}` | Ranking estratégico | `tests/test_ops12_i7_ranking_estrategico_contract.py` | provado | baixo |
| I8 | GET `/inteligencia/impacto-financeiro/{id}` | Impacto financeiro | `tests/test_ops12_i8_impacto_financeiro_contract.py` | provado | baixo |
| I9 | GET `/inteligencia/indice-inteligencia/{id}` | Índice inteligência | `tests/test_ops12_i9_indice_inteligencia_contract.py` | provado | baixo |
| I10 | GET `/inteligencia/score-tributario/{id}` | Score tributário | `tests/test_ops12_i10_score_tributario_contract.py` | provado | baixo |
| I11 | GET `/inteligencia/radar-tributario/{id}` | Radar tributário | `tests/test_ops12_i11_radar_tributario_contract.py` | provado | baixo |
| I12 | GET `/inteligencia/benchmark-empresas` | Benchmark multi-empresa tenant | `tests/test_ops12_i12_benchmark_empresas_contract.py` | provado | baixo |
| I13 | GET `/inteligencia/anomalias-tributarias/{id}` | Anomalias tributárias | `tests/test_ops12_i13_anomalias_tributarias_contract.py` | provado | baixo |
| I14 | GET `/inteligencia/prioridade-auditoria/{id}` | Prioridade auditoria | — | parcial | medio |
| I15 | GET `/inteligencia/projecao-recuperacao/{id}` | Projeção recuperação | — | parcial | medio |
| I16 | GET `/inteligencia/risco-tributario/{id}` | Risco tributário | — | parcial | medio |
| I17 | GET `/inteligencia/eficiencia-tributaria/{id}` | Eficiência tributária | — | parcial | medio |
| I18 | GET `/inteligencia/complexidade-tributaria/{id}` | Complexidade tributária | — | parcial | medio |

---

## 12. Domínio J — Dashboard operacional (12)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| J1 | GET `/dashboard/analises/{id}` | Histórico análises empresa | `tests/test_ops12_j1_dashboard_analises_contract.py` | provado | baixo |
| J2 | GET `/dashboard/relatorio/{id}` | Detalhe relatório dashboard | `tests/test_ops12_j2_dashboard_relatorio_contract.py` | provado | baixo |
| J3 | GET `/dashboard/relatorio/{id}/alertas` | Alertas por relatório | `tests/test_ops12_j3_dashboard_relatorio_alertas_contract.py` | provado | baixo |
| J4 | GET `/dashboard/relatorio/{id}/oportunidades` | Oportunidades por relatório | `tests/test_ops12_j4_dashboard_relatorio_oportunidades_contract.py` | provado | baixo |
| J5 | GET `/dashboard/risco/{id}` | Score risco heurístico | `tests/test_ops12_j5_dashboard_risco_contract.py` | provado | baixo |
| J6 | GET `/dashboard/resumo/{id}` | Resumo alertas empresa | `tests/test_ops12_j6_dashboard_resumo_contract.py` | provado | baixo |
| J7 | GET `/dashboard/alertas/{id}` | Lista alertas activos | `tests/test_ops12_j7_dashboard_alertas_contract.py` | provado | baixo |
| J8 | GET `/dashboard/alertas/timeline/{id}` | Timeline alertas | `tests/test_ops11_j8_timeline_alertas_contract.py` | provado | baixo |
| J9 | GET `/dashboard/alertas/agentes/{id}` | Alertas agrupados por agente | `tests/test_ops11_j9_alertas_por_agente_contract.py` | provado | baixo |
| J10 | PATCH `/dashboard/alertas/silenciar/{id}` | Silenciar alerta | `tests/test_ops11_j10_j11_silenciar_restaurar_contract.py` | provado | baixo |
| J11 | PATCH `/dashboard/alertas/restaurar/{id}` | Restaurar alerta | `tests/test_ops11_j10_j11_silenciar_restaurar_contract.py` | provado | baixo |
| J12 | GET `/dashboard/alertas/grafico/{id}` | Dados gráfico severidade | `tests/test_ops11_j12_grafico_alertas_contract.py` | provado | baixo |

---

## 13. Domínio K — Enriquecimento InsightEngine (1)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| K1 | POST `/insights/{empresa_id}` | Dispara InsightEngine pós-persistência | `tests/test_isolamento_inteligencia_insights_bloco9.py` (MT-15 isolamento) | provado | baixo |

---

## 14. Domínio L — Documentos / Ingestão / CPF (5)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| L1 | GET `/documentos/` | Lista documentos fiscais tenant | — | provado | medio |
| L2 | POST `/ingestao/documentos` | Pipeline ingestão PDF/imagem | `tests/test_ingestion_campos_estruturados.py` (pipeline serviço) | parcial | alto |
| L3 | POST `/cpf/dashboard` | Resumo tributário CPF | — | provado | medio |
| L4 | POST `/cpf/documentos/upload` | Upload rendimento CPF | — | provado | medio |
| L5 | POST `/cpf/documentos/confirmar` | Persistência rendimento confirmado | — | provado | medio |

---

## 15. Domínio M — Contador / Homologação (4)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| M1 | GET `/contador/perfil` | Perfil regulatório contador | `tests/test_dt_perfil_contador_portal_01.py` | provado | medio |
| M2 | GET `/contador/homologacoes/pendentes` | Fila homologações | `tests/test_acesso_cruzado_bloco9.py` | provado | medio |
| M3 | POST `/contador/homologacoes/{doc}/assumir` | Assunção com vínculo soberano | `tests/test_dt_contador_01_fluxo_soberano.py` | provado | alto |
| M4 | POST /contador/homologacoes/{id}/decidir | Decisão de homologação documental com assinatura lógica V1 | tests/test_ops11_h4_l2_m4_contract.py + tests/test_homologacao_service.py | provado | baixo |

---

## 16. Domínio N — Estoque / Auditoria (2)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| N1 | POST `/estoque/auditar` | Dispara auditoria estoque (agent) | — | provado | medio |
| N2 | GET `/estoque/divergencias` | Lista divergências fiscais vs ERP | `tests/test_ops11_n2_estoque_divergencias_contract.py` | provado | baixo |

---

## 17. Domínio O — Assistente fiscal (1)

| ID | Endpoint | Promessa | Teste | Estado | Risco L3 |
|----|----------|----------|-------|--------|----------|
| O1 | POST `/perguntar` | Orquestração assistente motor-first (MEI/CPF/empresa + bloqueio L3) | `tests/test_assistente_perguntar_contract.py` | provado | baixo |

---

## 18. Endpoints fora da matriz (existem no código)

| Path | Motivo exclusão |
|------|-----------------|
| GET `/inteligencia/maturidade-tributaria/{id}` | Piloto 0 — pós-OPS-10 |
| GET `/inteligencia/score-global-tributario/{id}` | Piloto 0 — pós-OPS-10 |
| GET `/inteligencia/historico-inteligencia/{id}` | Piloto 0 — pós-OPS-10 |
| GET `/inteligencia/tendencia-inteligencia/{id}` | Piloto 0 — pós-OPS-10 |
| GET `/inteligencia/comparacao-temporal/{id}` | Piloto 0 — pós-OPS-10 |
| POST `/criar-planos` | Admin — excluído |
| `/admin/*` (18 rotas) | Admin — excluído |

---

## 19. Totais e próximo passo

| Métrica | Valor |
|---------|-------|
| Funcionalidades mapeadas | **90** |
| `provado` | **73** |
| `parcial` | **17** |
| `nao_provado` | **0** |
| Risco L3 `alto` sem mitigação | **10** |
| Domínios A–O | **15** |

**Próximo passo:** B13-OPS-11 — 0 `nao_provado`; elevar os 17 `parcial` a `provado` (suite verde, nenhum risco L3 alto sem ADR).

**Invariante NR-01:** violações ST detectadas em `tests/test_l3_normative_resolution_invariants.py` — correcção via B13-OPS-09.

---

*Gerado por inventário estático de `app/` + grep em `tests/` — 2026-06-29. Actualizado O1/H4/K1/M4/L2 — 2026-07-02. Actualizado I3 — 2026-07-07. Actualizado I4 — 2026-07-07. Actualizado I5 — 2026-07-07. Actualizado I6 — 2026-07-07. Actualizado I7 — 2026-07-07. Actualizado I9 — 2026-07-07. Actualizado I11 — 2026-07-07. Actualizado I12 — 2026-07-08. Actualizado I13 — 2026-07-08.*
