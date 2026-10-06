# Smoke documental MEI — 2026-10-06

Commit da aplicação: f39bdcfbf84572b65da3d6b343be9e5c01ec0943.

Resultado reportado: SMOKE_SIMULADO=PASS.

Desktop 1280px e celular 390px:
- Inventário documental, troca de ano e documentos sem data.
- Ausência de documentos e erro HTTP 503.
- Checkout, retomada, confirmação simulada, PDF e código de barras.
- Isolamento por competência.

Ambiente: PostgreSQL descartável; provedores simulados.
Evidências locais: C:\Users\Oem\AppData\Local\Temp\solveris-mei-e2e-tdkzpuis.

Não prova pagamento, webhook ou SERPRO reais, migrations ou conferência
automática das evidências fiscais. Não autoriza abertura comercial.

Execução:
python tests/support/mei_documental_smoke/run.py C:\dev\saas-fiscal-demo-mei

O launcher exige o commit da aplicação acima. Após o commit dos próprios
scripts, essa guarda precisará de revisão explícita antes da reexecução.