# Smoke local de observações da operação — 2026-10-06

Commit da aplicação: 531ae263b38a8c784c7bcc2fade366a898e7899b.

Resultado: SMOKE_SIMULADO=PASS em 1280px e 390px.

Verificados: natureza e finalidade observadas, CFOPs por item,
dados ausentes, texto escapado, troca de ano e erro 503.
Também verificados: checkout, retomada, confirmação simulada,
PDF, código de barras e isolamento por competência.

PostgreSQL descartável e provedores simulados.
Webhook, pagamento e SERPRO reais não testados.
Esta prova não valida a cadeia completa de migrations nem produção.

Scripts: tests/support/mei_operacao_smoke.
Resultado: resultado_2026-10-06.json.
Execução: python tests/support/mei_operacao_smoke/run.py C:\dev\saas-fiscal-demo-mei
O launcher exige o commit da aplicação indicado acima.