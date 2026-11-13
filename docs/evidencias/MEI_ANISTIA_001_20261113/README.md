# SOLVERIS.MEI-ANISTIA-001 — Prova visual autenticada e isolada (13/11/2026)

Commit de código **exato** testado: `325af7b6472c03bafac5fcc2c396ae4c60af7887` na branch `work/mei-anistia-001-release-20261113`.
Evidência em branch apartada para não alterar o SHA do release.

## Protocolo

- Vercel Sandbox descartável; backend FastAPI real, PostgreSQL de produção **não acessado**; SQLite local isolado e sem credenciais Railway.
- Conta MEI **sintética** criada pelo fluxo HTTP real da API (fixture historicamente aprovada no repositório).
- Aceite de termos e consentimento feitos só na base isolada; login verdadeiro pelo formulário React em Chromium Playwright.
- Desktop 1365 px e mobile 390 px, telas logadas, dados sintéticos.
- Componentes B1 e B3 visíveis; B1: corte 13/10/2026, efeitos 01/01/2027, ICMS/ISS excluídos; B3: sem inscrições, sem garantia, sem cadastro PixMEI.
- 4 checkboxes; a marcação persistiu após recarregar o painel.
- Bloqueio de requisições POST/PUT/PATCH/DELETE fora do login/termos/consentimento, zero operações inesperadas, zero erros JS, zero imagens quebradas, zero overflow horizontal.
- `npm run build` PASS; `node --test tests/*.test.mjs` 18 PASS/0 FAIL.
- Não testou bancos/provedores reais, PGFN, emissão DAS nem login na base de clientes.

## Capturas

| Arquivo | SHA-256 |
|---|---|
| [desktop-anistia.png](desktop-anistia.png) | `e5e63dbe8b4a6c82e4998ecdc1878906cd82461d5803c012a4558893bb8bed2c` |
| [desktop-pixmei.png](desktop-pixmei.png) | `5df2bae9912c45058c8fb30da1d2acbacadc1c0b5370b466e392326c8189ea3b` |
| [desktop-viewport.png](desktop-viewport.png) | `e40498527fa173d878dcd262936904597d18f07fb7a3eadfeecd9b8652bd3761` |
| [mobile-anistia.png](mobile-anistia.png) | `0214af0906223209d99b911df7d1c9ea6a3c8c459be64d7fa07da94c99292597` |
| [mobile-pixmei.png](mobile-pixmei.png) | `001a526bd279fd4bb57b7dc1050c815cdc87bbd183bd7b8317d7144c312e5ce2` |
| [mobile-viewport.png](mobile-viewport.png) | `8a041f3a201e95c75697f729883581509b842ad84098d17c0c6397a02424aad2` |

## Resultado

`GREEN` para smoke autenticado isolado dos Blocos 1 e 3, desktop e mobile.
**Gate operacional de publicação Vercel não confundir com teste:** `POST /v13/deployments` retornou HTTP 402 `api-deployments-free-per-day` (>100/dia; retryAfter=86400) em 13/11/2026. Produção não foi promovida; alias continua no deployment anterior até a próxima janela autorizada.
