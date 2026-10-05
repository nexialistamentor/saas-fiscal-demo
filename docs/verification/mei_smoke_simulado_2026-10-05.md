# MEI — smoke simulado aprovado em 2026-10-05

Resultado recebido do terminal: SMOKE_SIMULADO=PASS.
Desktop 1280px e mobile 390px aprovados.

Cobertura: cadastro HTTP, login no navegador, checkout, retomada sem duplicação, confirmação canónica simulada, autorização por competência, download de PDF e apresentação de código de barras de fixture. Outra competência permanece bloqueada.

Sem overflow, erros JavaScript ou pedidos externos inesperados.

Não provados: webhook real, pagamento real, SERPRO real, migrations Alembic e comportamento de rate limiting.
Este resultado não autoriza declarar a abertura comercial concluída.

Scripts: tests/support/mei_smoke_local/
Evidências locais: C:\dev\solveris-mei-evidencias\2026-10-05-smoke-simulado

## SHA256 dos scripts preservados

- `run.py`: `e6a33ba0c4532dee87d56dbe31f20edf6ccc742bd74a1214831020fb34c58e81`
- `server.py`: `2a50a9001461927a47f40c41c935a3ac44b511c4f70dcf3b81c790d08f9f8e22`
- `browser.cjs`: `9250a3c494d62d551edf2ec61ec26f2d1ec8766afa6c676704b546bd9643f431`
- `LEIA-ME.md`: `75b56555bcbf49971e71f0e20f7aa41cb37050b8f764c353a092ef65be1208d8`
