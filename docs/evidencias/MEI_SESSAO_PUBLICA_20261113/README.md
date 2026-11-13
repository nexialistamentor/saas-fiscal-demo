# SOLVERIS.MEI — prova visual pública de sessão, 13/11/2026

**URL real:** `https://solveris.ia.br/mei`  
**Deployment upstream Vercel verificado:** `dpl_rW17vyNoK8Bz64HtHNhXEsTKrQ4N`  
**SHA Git exato:** `4a15c6d9f29c5677cf19856d6da33bd6e0530d2d`  
**Scope:** correção UX da [PR #40](https://github.com/nexialistamentor/saas-fiscal-demo/pull/40), **não** certificação Gate 2 de autenticação real.

## Método de prova

Chromium Playwright foi apontado **diretamente para `https://solveris.ia.br/mei`**. HTML, JS e CSS foram obtidos do domínio público real após a nova atribuição do alias. A instância de teste inseriu somente um token propositalmente inválido no navegador e **interceptou `GET /auth/me`**, simulando 14 segundos de latência seguidos de HTTP 401. Todas as demais chamadas fora do domínio público foram bloqueadas. **Não foi transmitida credencial; não houve login real, registro de cliente, consulta fiscal ou pagamento.** O objetivo foi testar exatamente a tela de validação com latência e retorno ao formulário.

**Resultados:** desktop 1365×844 PASS; mobile 390×844 PASS; página escura SOLVERIS/MEI, aviso de publicidade oculto durante a validação, botão de tentar novamente após 12 segundos, formulário de login e preferências publicitárias acessíveis depois do HTTP 401; overflow horizontal zero; erros JavaScript zero; zero escrita fiscal ou financeira.

O registro estruturado está em [public_ui_smoke_result.json](./public_ui_smoke_result.json). Capturas visuais guardadas como **arquivos SVG textuais que incorporam os bytes PNG originais codificados em base64 sem alteração**, já que a API de publicação GitHub disponível neste ambiente recebe apenas arquivos de texto:

| Evidência | Arquivo | SHA-256 dos bytes PNG originais |
|---|---|---|
| Desktop verificando sessão | [desktop-loading.svg](./desktop-loading.svg) | `f619be206b5d20be0c1cf961dfb12c34f47296b36f07f5f611d6f7efee29794e` |
| Desktop após 401 simulado | [desktop-login.svg](./desktop-login.svg) | `9d5ce67a1626ce125dd52e335bcf4adb4b9e59e6dfb84518a04d050e3369a888` |
| Mobile verificando sessão | [mobile-loading.svg](./mobile-loading.svg) | `547fb35c7a5327658f44a7bbf3fcf4844c10cbfb6465d78551d6e47773772a33` |
| Mobile após 401 simulado | [mobile-login.svg](./mobile-login.svg) | `57d7c562d1a4d4d8831982d428b9f8172126b771cc8f5075f8257ac870202fd5` |

**Arquivo de log original:** SHA-256 `a4ab6c94cc15fed2fe00c280d3af161a82c100670877a5cde26ffcefc3b0a50a`.

## Gates e integridade

- `Gate 1` da PR #37 era GREEN no release anterior `325af7b...`; esta correção cria novo SHA `4a15c6d...` com diff somente `App.jsx` + `App.css` e exige registro específico pós-publicação.
- **Gate 2 (smoke autenticado real) NÃO está GREEN** com estas capturas, pois não houve autenticação real; as capturas manuais enviadas por Miguel são evidência independente parcial, não substituem log automatizado autenticado.
- `Gate 0` (separação completa dos ambientes) continua RED; o projeto Vercel intermediário/alias e backend Railway ainda são compartilhados com Fisco Soberano.
- `Gate 3` (Production formal) continua pendente: o deployment atribuído ao alias tem `target=null`, Vercel Preview.
- `Gate 4` (rodapé único MEI-COPY-001) continua pendente.
- Esta branch é **somente evidência**, baseada no SHA de frontend publicado. **Nunca usar HEAD desta branch como candidato a deployment** ou substituir o pin `4a15c6d9f29c5677cf19856d6da33bd6e0530d2d`.
- Nenhuma campanha, agendamento, job ou migracão foi criada nesta etapa.
