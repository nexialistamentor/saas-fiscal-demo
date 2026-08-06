# NOTA OPERACIONAL — Estado da Raiz Vercel — Versão 1.0

- Data: `2026-08-06`
- Repositório: `nexialistamentor/saas-fiscal-demo`
- Projecto Vercel: `saas-fiscal-demo`
- Ambiente observado: produção
- Estado: `CONFIGURAÇÃO GUARDADA — EFICÁCIA AGUARDA PROVA EM PUSH FUTURO SEM ALTERAÇÃO DE FRONTEND`

## 1. Configuração vigente

- Root Directory: `frontend-dashboard`
- Incluir ficheiros fora do directório raiz na etapa de construção: `DESACTIVADO`
- Ignorar implantações quando não houver alterações no directório raiz ou nas suas dependências: `ACTIVADO`
- Ignored Build Step / Etapa de compilação ignorada: `PERSONALIZADO`

Comando exacto guardado:

```bash
test -n "$VERCEL_GIT_PREVIOUS_SHA" && test -n "$VERCEL_GIT_COMMIT_SHA" && git diff --quiet "$VERCEL_GIT_PREVIOUS_SHA" "$VERCEL_GIT_COMMIT_SHA" -- .
```

O comando é executado no contexto do Root Directory `frontend-dashboard`. Quando os dois SHAs existem e não há diferenças dentro dessa raiz, retorna `0` e a Vercel deve ignorar a compilação. Quando existe alteração no frontend, ou algum SHA está ausente, retorna valor diferente de zero e o build deve prosseguir de forma segura.

## 2. Evidência anterior à regra personalizada

Antes da introdução do comando personalizado, dois pushes sem alterações em `frontend-dashboard` ainda produziram deployments de produção na Vercel:

- `4feceeb06798e49b939daaa455b38dbf1eeb1d12` — fechamento documental da MISSION-013 / intenção 9B4;
- `9646a5fb9a92fcfb21419cbe2fb8242a07deeb33` — actualização do `DEPLOY_CHECKLIST.md`.

Ambos tinham zero alterações no frontend. A implantação de `4feceeb` concluiu com sucesso, processou 579 módulos e apresentou apenas o aviso informativo de um bloco JavaScript com `603,66 kB`, acima do limite de aviso de 500 kB.

## 3. Estado de validação

A configuração personalizada está guardada no painel da Vercel, mas ainda não foi provada por um push posterior contendo apenas documentação, backend, migrations ou testes.

A próxima publicação sem alteração em `frontend-dashboard` deverá confirmar cumulativamente:

1. nenhum novo deployment de produção na Vercel;
2. nenhum build Vite iniciado;
3. o deployment de produção anterior permanece activo;
4. nenhuma intervenção manual, reversão ou redeploy foi necessária.

Até essa prova, o estado permanece `CONFIGURADO_MAS_NAO_PROVADO`.

## 4. Invariantes operacionais

- Alterações exclusivamente em `docs/`, `migrations/`, `tests/`, backend ou ficheiros operacionais não devem implantar o frontend.
- Alterações efectivas dentro de `frontend-dashboard` devem permitir o build.
- Um deployment inesperado após push sem alteração de frontend deve bloquear o fluxo e ser tratado como incidente operacional.
- Esta nota não autoriza deploy, redeploy, reversão, alteração de domínio ou operação em produção.
- A configuração do Railway permanece separada; o Auto Deploy do backend está desactivado.

## 5. Marcador

`VERCEL_ROOT_FRONTEND_DASHBOARD_CONFIGURADO_AGUARDA_PROVA_DE_SKIP`
