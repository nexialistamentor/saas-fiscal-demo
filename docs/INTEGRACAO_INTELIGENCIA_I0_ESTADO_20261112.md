# Integracao de inteligencia I0 — estado 2026-11-12

Trabalho independente de B04/B05. Nao altera `_CAPACIDADES`, G12–G17 nem a ponte B04.

## Inventario real
O grupo `inteligencia` tem **14 capacidades** no catalogo I0: 3 `snapshot` e 11 com origem estatica `pendente`. A contagem historica de 16 nao corresponde a esse catalogo.

## Cinco produtores ligados (commit 145a807b)
- `score_tributario`: dict real de `calcular_score_global_tributario`.
- `maturidade`: dict real de `calcular_maturidade_tributaria`.
- `ranking_restituicao`, `ranking_estrategico`, `impacto_financeiro`: listas completas capturadas nas chamadas existentes, antes da selecao dos cinco primeiros insights.

A captura chega ao resultado persistido e ao I0 via `enterprise_inteligencia_i0_bridge.py`. O consumidor verifica o fingerprint do relatorio, o vinculo empresa/relatorio/XML e nao cria chamadas novas. Todos os resultados continuam internos, sem prova fiscal. Nao ha alteracao do catalogo estatico: somente a cobertura projetada em runtime muda.

Prova local isolada: **256 testes PASS**, anti-duplicacao PASS, compilacao Python e diff-check PASS. Nao equivale a homologacao com dados fiscais reais.

## Seis capacidades ainda pendentes
- `anomalias`: produtor `detectar_anomalias_tributarias`, usado indiretamente pelo risco. Captura do resultado integral exige propagacao do retorno no grafo existente; nao recalcular.
- `eficiencia`: produtor `calcular_eficiencia_tributaria`, usado indiretamente por score/maturidade; mesmo impedimento.
- `complexidade`: produtor `calcular_complexidade_tributaria`, usado pela maturidade; mesmo impedimento.
- `projecao_recuperacao`: `projetar_recuperacao_tributaria`, chamado no router, nao no escritor; nova chamada requer decisao explicita.
- `benchmark`: `gerar_benchmark_empresas`, chamado no router com conjunto de empresas; isolamento exige comprovacao antes de integrar.
- `radar`: o produtor declarado e `radar_tributario_service::gerar_radar_tributario`, chamado no router. O `InsightEngine._obter_radar_tributario` produz apenas um resumo do mapa de oportunidades; nao e o mesmo contrato, nem o substitui.

Nenhuma destas seis capacidades foi promovida. Nao inventar resultado ou chamar produtores do router no escritor sem decisao previa.

## Dependencia entre branches
A correcao transacional esta isolada em `fix/atomicidade-insights-commit`, commit `912cb309`. Esta integracao esta em `integracao-inteligencia-i0`, commit `145a807b`. Ambos alteram partes de `insights_engine.py` e `registro_analise_service.py` e devem ser reconciliados antes de qualquer merge. Nenhum deploy ou merge para `main` foi efetuado.
