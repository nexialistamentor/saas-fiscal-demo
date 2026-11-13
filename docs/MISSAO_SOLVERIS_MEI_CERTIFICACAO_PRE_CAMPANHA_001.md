# SOLVERIS.MEI-CERTIFICACAO-PRE-CAMPANHA-001

**Corte de evidências:** 13/11/2026. **Resultado:** CAMPANHA NÃO AUTORIZADA. Os gates 0–4 não estão todos GREEN.

## Mandato e regras permanentes

- Miguel é a autoridade. **Nunca criar agendamento, horário, watcher, reminder ou job automático sem a consulta e autorização prévias expressas de Miguel.** Dois agendamentos sem autorização foram desativados em 13/11; não os reativar.
- **SOLVERIS.MEI e Fisco Soberano são produtos e ambientes distintos**, em Vercel **e** Railway/BD. O endereço comercial do primeiro é `https://solveris.ia.br/mei`; o Fisco Soberano não é entrada, backend compartilhado nem destino operacional autorizado para o MEI.
- A rota institucional pode encaminhar somente para **projeto e deployment exclusivamente SOLVERIS.MEI**, e a aplicação MEI deve usar **backend/ambiente/BD exclusivamente MEI**, com isolamento comprovado de autenticação, pagamento e autoridade fiscal. Não basta um nome novo ou logo diferente.
- Qualquer diferença entre SHA testado, deployment real, projeto e alias **interrompe a certificação**; jamais usar status HTTP 200, green de preview, build, HEAD ou smoke isolado como equivalentes a produção.
- **Não reverter a publicação atual durante análise, exceto para corrigir RED real do Gate 0 ou Gate 1 com substituto comprovadamente seguro.** Não causar indisponibilidade apontando para projeto vazio.
- Não abrir Bloco 2 (LOA 2027) nem SERPRO DIVIDAATIVA24. Não efetuar consultas reais de dívidas, DAS, pagamentos, compra ou escrita fiscal durante smoke.

## Gate 0 — P0, RED (evidência do ambiente publicado)

| Camada | Público em 13/11/2026 | Projeto/serviço comprovado |
|---|---|---|
| Entrada institucional | `https://solveris.ia.br/mei` | Vercel `solveris-site` `prj_5iT4xoofZUhB0GYzgiFYE5qI8J4P`; deployment `dpl_6fgyQe9s8dk4gMxezZe7YpnRen1M` |
| Rewrite efetivo | `/mei` → `https://saas-fiscal-demo.vercel.app/`; `/mei/:path*` → mesmo host | `nexialistamentor/solveris-institucional/vercel.json`, `main` `2dc82809ac349fac15d2f7ae3ddc00c5da98c1e7` |
| Frontend MEI servido | `saas-fiscal-demo.vercel.app` alias | Vercel **compartilhado com Fisco Soberano**, `saas-fiscal-demo`, `prj_RR2qM8kWxxgwG3IhY9XdhSGbdFvh`; alias aponta a `dpl_5jN7kbAQk9tWjoDwL7pqzo5c59Eu` (PREVIEW READY) |
| Fisco Soberano | `www.fiscosoberano.com.br` | **Mesmo projeto Vercel**, outro deployment `dpl_ECtWkgxoAs29UaB1AfyTpAHXGu5W`; produção antiga mantida |
| API consumida pelo bundle MEI | `https://saas-fiscal-demo-production.up.railway.app` | Railway projeto `disciplined-alignment` `dfbf2a41-854a-4b5f-8e6a-f0d567507975`; produção `8deb6325-9ac2-457d-af7d-6ebed10cdc34`; serviço `saas-fiscal-demo` `75c0f361-72b8-4829-b4ac-eb81412fca2d` |
| Dados compartilhados | PostgreSQL + Redis na mesma Railway | `Postgres` `653205dc-e0b1-475b-a7a5-6d61b0538dfa`; `Redis` `a5e16ac8-749c-4ef7-859e-af36181b3fbb` |

**Resultado:** o domínio tem marca MEI mas usa projeto e API fiscais compartilhados, contrariando o isolamento agora exigido. Sem falso GREEN.

**Preparação corretiva já efetuada:**
- Projeto Vercel **dedicado** `solveris-mei` criado no time `nexialistamentors-projects`, ID `prj_QAjnb2VNcFLTFqF6kUHg4AaRT8xg`; domínio reservado `solveris-mei.vercel.app`; **sem deployment**, **sem integração Git automática**, **sem API configurada**, não público.
- Rota futura preparada em **PR draft** [solveris-institucional#7](https://github.com/nexialistamentor/solveris-institucional/pull/7), altera `/mei` e `/mei/:path*` para `solveris-mei.vercel.app/mei`; **NÃO MESCLAR/ATIVAR** antes de frontend, backend e dados segregados, QA e transição segura.
- A segregação Railway/BD e a migração/sessões dos MEIs existentes continuam por executar; **não criar serviços dispendiosos, replicar dados de clientes nem migrar o banco à revelia das provas e autoridades**.

## Gate 1 — RED (identidade imutável do binário)

- PR [#37](https://github.com/nexialistamentor/saas-fiscal-demo/pull/37) SHA de código realmente testado `325af7b6472c03bafac5fcc2c396ae4c60af7887`, Vite PASS, 18 Node PASS, browser isolado desktop/mobile GREEN.
- Público `solveris.ia.br/mei` consome `index-D4YNMWY7.js` servido por deployment `dpl_5jN7kbAQk9tWjoDwL7pqzo5c59Eu`, SHA `a369ff4233c45961842e5b533101bc81b52a646c`.
- `git compare a369ff4...325af7b`: **2 arquivos divergentes**: `frontend-dashboard/src/App.jsx` (uma linha: logo `/mei/solveris-logo.jpg` → `/solveris-logo.jpg` via Vite base) e `frontend-dashboard/tests/smokeMeiAnistiaIsolado.cjs` (arquivo de teste novo). Conteúdo B1/B3 foi encontrado no bundle, mas **SHA NÃO É IGUAL** e não cabe certificar byte-a-byte.
- **Pin obrigatório para futura produção dedicada:** `325af7b6472c03bafac5fcc2c396ae4c60af7887`. Não substituir por HEAD futuro/branch móvel; antes de promoção cotejar artefacto construído, backend env, SHA e smoke da URL pública.

## Gate 2 — BLOCKED, NÃO EXECUTADO EM PRODUÇÃO

- Evidência anterior [seis capturas isoladas](https://github.com/nexialistamentor/saas-fiscal-demo/tree/evidence/mei-anistia-001-visual-20261113/docs/evidencias/MEI_ANISTIA_001_20261113): Chromium, backend FastAPI + SQLite descartável, login REAL de fixture sintética, 1365/390 px, B1/B3, sem operações fiscais ou financeiras, GREEN **somente isolado**.
- Script real para URL pública: `frontend-dashboard/tests/smokeMeiAnistiaAuth.mjs`; **não executado com login real em `https://solveris.ia.br/mei`**.
- Tenant sintético anterior de produção conhecido: `SOLVERIS SMOKE MEI`, empresa 76, usuário 135; constou `consulta_paga=true` no histórico, portanto **não se presume fixture limpa**. Evitar a criação de registro sintético na BD compartilhada, não pedir nem publicar senha/token. Preferir teste com fixture autorizada num **backend MEI segregado** e zero escrita fiscal. Provas têm de identificar URL, deployment e capturas logadas desktop/mobile.
- Nunca simular autenticação, dados de cliente ou screenshots, nem confundir autorização HTTP 200 com painel autenticado.

## Gate 3 — RED / HOLD VERCEL

- O alias upstream MEI hoje aponta para deployment `READY` de target **preview**, não `production` formal.
- `POST /v13/deployments` respondeu **HTTP 402** `api-deployments-free-per-day` em 13/11/2026; não usar workaround como dispensa de SHA/isolamento.
- Não promover no projeto errado e não publicar outro commit silenciosamente. Publicação final apenas no projeto Vercel **dedicado**, com SHA exato, frontend/backend segregados, prévia validada, produção `READY` e verificação pós-ativação.
- **Sem agendamento de nova tentativa** (proibição expressa).

## Gate 4 — PARCIAL; NÃO GREEN

- Bundle JavaScript obtido ao vivo de `https://solveris.ia.br/mei/assets/index-D4YNMWY7.js`, HTTP 200, contém: `13/10/2026`, `01/01/2027`, exclusão `ICMS nem ISS`, ausência de valor individual; `Inscrições ainda não abertas`, `não processa inscrições`, `não garante acesso`, `dados bancários` em contexto de não solicitação.
- **Prova apenas de código entregue**, não de renderização visível após login. Falta screenshot de produção com conta MEI sintética autenticada.
- `MEI-COPY-001` **PR #32 draft, não mesclada**; aviso único em rodapé **não comprovado/aplicado**. Textos de negação ainda existem no bundle; pendência comercial e visual, não esconder.
- Tetos propostos R$110k/R$140k ausentes no bundle e PR #36 permanece HOLD.

## Aceite final (único que autoriza campanha)

`G0 GREEN` → `G1 GREEN` → `G2 GREEN` → `G3 GREEN` → `G4 GREEN`; registrar URL, projeto, SHA, deployment ID, ambiente Railway/BD, screenshot autenticado por viewport, log sem mutações, links e rodapé. Até lá **NÃO AUTORIZAR CAMPANHA** e nunca chamar missão concluída.

## Sequência L3

**Risco → Evidência → Diagnóstico → Correção mínima → Prova → GREEN**. Primeiro corrigir a fronteira de domínio/ambiente; depois garantir mesmo commit; só então smoke real, promoção formal e revisão visual pública. Não reexecutar provas aceitas sem delta. Não programar tarefas, calendários ou watchers.
