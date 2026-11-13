# SOLVERIS.MEI-SMOKE-REAL-001 — resultado de execução

**Corte:** 2026-11-13, 05:49 BRT (08:49 UTC).
**Alvo:** PR #32, branch `work/mei-copy-001-20261113`.
**Build testado:** `be432c3ca33531ccf4bd417e75b1e18a6e7c5641`.
**Preview protegida:** `https://saas-fiscal-demo-k6f6fpy4z-nexialistamentors-projects.vercel.app/mei`.
**Produção (somente comparação):** `https://www.fiscosoberano.com.br/mei`.
**Execução:** navegador Chromium headless, desktop 1365×900 e celular 390×844 em ambiente Vercel Sandbox isolado, sem credenciais MEI nem operações fiscais/financeiras.

## Resultado material

`PASS=16`, `FAIL=0`, `BLOCKED=2`, **veredito PARTIAL-BLOCKED**.

| Etapa verificada em cada perfil | Desktop | Celular |
| --- | --- | --- |
| Produção abre para captura de referência | PASS | PASS |
| Preview abre e apresenta entrada SOLVERIS MEI | PASS | PASS |
| Logotipo carrega, dimensão real positiva, caminho correto | PASS | PASS |
| Favicon responde HTTP 200 com imagem | PASS | PASS |
| Rodapé jurídico único presente | PASS | PASS |
| Sem overflow horizontal | PASS | PASS |
| “Já tenho MEI”: cadastro e validação de email/senha; sem POST | PASS | PASS |
| Voltar ao login sem criar conta | PASS | PASS |
| Login MEI, dashboard, histórico, assistência, XML, receitas, conferência e DAS | BLOCKED | BLOCKED |

O teste automatizado reside em `frontend-dashboard/tests/smokeMeiRealJourney.mjs`. Exige `MEI_SMOKE_URL` e opcionalmente `MEI_SMOKE_SHARE_URL` para preview SSO. A etapa autenticada exige **credenciais de conta de teste explicitamente autorizada** (`MEI_SMOKE_EMAIL` e `MEI_SMOKE_PASSWORD` via ambiente local, nunca no Git ou em chat). O teste não emite DAS, não confirma compras, não envia XML, não registra receitas e não gera novas contas.

## Defeitos identificados e correção mínima

1. Logotipo: a UI tentava `/mei/solveris-logo.jpg`, HTTP 404, exibindo texto alternativo SOLVERIS à direita do cabeçalho. O arquivo válido é `/solveris-logo.jpg`. Corrigido o `src` do JSX; navegador desktop e mobile comprovam carga real da imagem.
2. Favicon: o Vite prefixava caminho `/mei/` indevidamente para o arquivo público servido na raiz. `index.html` agora referencia explicitamente `https://www.fiscosoberano.com.br/favicon.svg`; navegador comprova HTTP 200. Nenhuma rota foi alterada.

## Comandos e resultados adicionais

- `npm run build`: **PASS** (`vite v8.3.8`).
- `node --test tests/*.test.mjs`: **13 PASS**, 0 FAIL.
- `npm run lint`: **FAIL** (16 erros, 3 avisos). A atribuição à versão base não foi concluída porque a sessão de teste expirou durante a verificação; não afirmar que são regressões nem problemas preexistentes sem comparativo concluído.
- Screenshots `antes-publico`, `depois-publico` e `depois-cadastro-sem-envio` foram geradas para desktop e mobile no sandbox temporário, mas **não foram anexadas de modo persistente à PR**. Não caracterizar o gate de ratificação visual como satisfeito.

## HOLD e entradas finais

- **Não fazer merge / não promover / não publicar.**
- Executar a fase autenticada com **conta MEI de teste autorizada** e conferir portal, XML (somente seletor, sem upload), histórico, assistente, conferência, receitas (somente formulário, sem submissão) e caminho do DAS (sem comprar/emitir).
- Preservar recibos/capturas antes/depois de forma acessível para ratificação visual de Miguel.
- Decidir sobre os avisos de lint apenas após cotejo exato com o commit de produção.
- Nenhuma alteração de backend, SERPRO, Mercado Pago ou dados reais está autorizada por este smoke.

**Gate atual:** `PUBLIC-UI-GREEN / FULL-JOURNEY-BLOCKED / RELEASE-HOLD`.
