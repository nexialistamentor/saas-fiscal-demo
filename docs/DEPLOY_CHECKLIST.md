# DEPLOY_CHECKLIST.md — Plataforma Tributária L3 / Fisco Soberano

**Versão:** 2.0
**Data:** 2026-08-06
**Origem:** B12-03
**Estado:** protocolo operacional actualizado após separação entre publicação canónica e deploy

---

## 1. Princípio obrigatório

`git push origin main` publica commits no GitHub. Não constitui, por si só, autorização para deploy, migration ou operação em produção.

Cada efeito externo exige uma decisão separada:

1. **Publicação canónica:** envio dos commits para `origin/main`.
2. **Deploy Railway:** implantação manual do backend e eventual execução de migrations.
3. **Deploy Vercel:** implantação do frontend quando `frontend-dashboard` ou dependências efectivas forem alterados.

Auto-commit, auto-push e auto-deploy permanecem proibidos sem aprovação humana.

---

## 2. Configuração externa actualmente adoptada

### Railway — backend

- Repositório ligado: `nexialistamentor/saas-fiscal-demo`.
- Branch ligada ao ambiente `production`: `main`.
- **Auto Deploy: desactivado.**
- `railway.toml` contém:
  - `preDeployCommand = "alembic upgrade head"`;
  - `startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"`.
- Um push para `main` não deve iniciar deployment automaticamente.
- Para implantar o commit mais recente da branch ligada, usar no Railway a acção **Deploy Latest Commit**, somente após autorização explícita.
- **Redeploy** repete o código e a configuração de um deployment anterior; não substitui a acção **Deploy Latest Commit**.

### Vercel — frontend

- Repositório ligado: `nexialistamentor/saas-fiscal-demo`.
- Root Directory: `frontend-dashboard`.
- **Include source files outside of the Root Directory: desactivado.**
- **Skip deployments when there are no changes to the Root Directory or its dependencies: activado.**
- Ignored Build Step: `Automatic`.
- Pushes sem alterações em `frontend-dashboard` ou em dependências efectivas devem ser ignorados, mas o resultado deve ser verificado após cada publicação.
- Alterações às configurações do projecto aplicam-se a deployments posteriores; não reescrevem deployments já concluídos.

As configurações do Railway e da Vercel vivem parcialmente fora do repositório. Devem ser reconfirmadas no painel antes de qualquer publicação que contenha backend, migration ou frontend.

---

## 3. Pré-publicação canónica

Executar antes de qualquer push para `main`:

```text
[ ] Confirmar branch actual: main
[ ] Confirmar working tree limpa
[ ] Confirmar origin/main e HEAD esperados
[ ] Rever os commits ainda não publicados, na ordem exacta
[ ] Rever a fronteira de ficheiros de origin/main..HEAD
[ ] Executar testes proporcionais ao escopo, com 0 failed
[ ] Se frontend-dashboard mudou: executar npm run build
[ ] Se frontend-dashboard não mudou: provar zero alterações nessa fronteira
[ ] Se existir migration nova:
    - confirmar revision e down_revision
    - confirmar dialecto e irreversibilidade
    - testar localmente sem produção
    - avaliar lock, duração, compatibilidade e rollback
    - não consultar nem alterar produção fora de autorização separada
[ ] Confirmar ausência de segredos, dados reais e credenciais nos commits
[ ] Confirmar Railway Auto Deploy desactivado
[ ] Confirmar configuração monorepo da Vercel
[ ] Executar git push --dry-run origin main:main
```

Nunca imprimir valores de `DATABASE_URL`, `SECRET_KEY`, tokens ou outras credenciais durante as verificações.

---

## 4. Publicação canónica no GitHub

A publicação canónica é um acto distinto de deploy:

```text
[ ] Confirmar novamente que origin/main não mudou
[ ] Executar git push origin main:main
[ ] Confirmar que origin/main chegou ao HEAD exacto
[ ] Confirmar working tree limpa
[ ] Confirmar main...origin/main sem ahead/behind
[ ] Registar os commits publicados
```

São proibidos por defeito:

```text
- git push --force
- git push --force-with-lease
- alteração de histórico publicado
- deploy implícito tratado como consequência automática do push
```

Qualquer force push requer ratificação explícita de Miguel e plano de recuperação.

---

## 5. Verificação imediata após publicação

### Railway

```text
[ ] Abrir Railway → serviço saas-fiscal-demo → Deployments
[ ] Confirmar que não surgiu deployment para o novo HEAD
[ ] Confirmar que o deployment activo anterior permanece inalterado
[ ] Confirmar que nenhuma migration foi aplicada
```

Se aparecer deployment inesperado, interromper o fluxo e tratar como incidente operacional. Não executar novo deploy, redeploy ou migration até compreender a causa.

### Vercel

Se `frontend-dashboard` não mudou:

```text
[ ] Confirmar que não surgiu deployment para o novo HEAD
[ ] Se surgir deployment inesperado, inspeccionar logs e configuração
[ ] Não reverter automaticamente se o build estiver verde e o artefacto for equivalente
[ ] Corrigir a causa do gatilho antes da publicação seguinte
```

Se `frontend-dashboard` mudou:

```text
[ ] Confirmar deployment do SHA esperado
[ ] Confirmar build verde
[ ] Rever avisos de bundle
[ ] Confirmar domínio de produção e funcionamento básico
```

---

## 6. Deploy manual do backend no Railway

O deploy do backend exige autorização soberana separada. Com Auto Deploy desactivado, publicar no GitHub não implanta o backend.

### Preflight da janela autorizada

```text
[ ] Identificar o SHA exacto a implantar
[ ] Confirmar que o SHA já está em origin/main
[ ] Confirmar suite e provas vinculadas ao SHA
[ ] Rever todas as migrations pendentes
[ ] Confirmar backup/recuperação adequados ao risco
[ ] Confirmar compatibilidade entre código, schema actual e schema alvo
[ ] Definir critérios de abortar e critérios de sucesso
[ ] Obter autorização explícita para deploy e produção
```

### Execução

No Railway, abrir a Command Palette e seleccionar **Deploy Latest Commit**.

Durante o deployment:

```text
[ ] Confirmar SHA em implantação
[ ] Acompanhar build
[ ] Acompanhar preDeployCommand: alembic upgrade head
[ ] Se o preDeployCommand falhar, não tentar contornar a falha
[ ] Confirmar Application startup complete
[ ] Confirmar Uvicorn iniciado
```

O `preDeployCommand` executa antes da aplicação entrar em serviço. Uma falha deve bloquear a continuação do deployment.

### Validação pós-deploy

```text
[ ] GET /health → HTTP 200 e status ok
[ ] GET /health/ready → HTTP 200 e database ok
[ ] Rever logs sem traceback, ImportError ou migration error
[ ] Confirmar a revision Alembic aplicada, quando autorizado
[ ] Testar endpoint crítico proporcional ao escopo
[ ] Registar deployment, SHA, migration e evidências
```

Redis `unavailable` só é aceitável quando o fallback síncrono previsto permanece funcional e a readiness contratual o permite.

Auto Deploy não deve ser reactivado sem decisão separada.

---

## 7. Deploy do frontend na Vercel

Um deploy de frontend é esperado quando `frontend-dashboard` ou uma dependência efectiva muda.

```text
[ ] Confirmar SHA esperado
[ ] Confirmar Root Directory = frontend-dashboard
[ ] Confirmar Include source files outside Root Directory = Disabled
[ ] Confirmar Skip unaffected deployments = Enabled
[ ] Confirmar Ignored Build Step = Automatic
[ ] Confirmar build Vite verde
[ ] Rever tamanho dos chunks e outros avisos
[ ] Confirmar www.fiscosoberano.com.br no deployment correcto
```

Avisos de chunk acima de 500 kB não equivalem a falha de build, mas devem permanecer registados como dívida de performance.

---

## 8. Rollback

### 8.1. Código publicado no GitHub

Preferir `git revert`, preservando o histórico:

```text
[ ] Identificar o commit problemático
[ ] Criar git revert
[ ] Validar localmente
[ ] Publicar o revert em main
```

Com Auto Deploy do Railway desactivado, publicar o revert **não altera o backend em produção**. Para aplicar o código revertido no Railway, é necessária nova autorização e a acção **Deploy Latest Commit**.

### 8.2. Deployment Railway

- **Redeploy** de um deployment anterior repete exactamente o código e a configuração desse deployment.
- Redeploy não desfaz migrations já executadas.
- Não usar código antigo contra schema novo sem análise de compatibilidade.
- Quando a reversão exigir o commit mais recente de `main`, usar **Deploy Latest Commit**, após autorização.

### 8.3. Deployment Vercel

Se um frontend novo falhar:

```text
[ ] Identificar o último deployment estável
[ ] Usar Instant Rollback somente após confirmar o alvo
[ ] Validar domínio e comportamento
[ ] Criar correcção permanente no Git; não deixar a reversão como estado documental final
```

### 8.4. Force push

Force push é proibido por defeito. Só pode ocorrer se:

```text
- git revert for tecnicamente impossível
- houver ratificação explícita de Miguel
- existir backup e plano de recuperação
- o impacto sobre auditoria e consumidores estiver documentado
```

---

## 9. Rollback de migration destrutiva ou irreversível

```text
ATENÇÃO: migrations com DROP, transformação destrutiva ou downgrade bloqueado
não possuem rollback automático seguro.
```

Antes da execução:

```text
[ ] Confirmar backup restaurável
[ ] Confirmar janela e impacto de lock
[ ] Confirmar plano forward-fix
[ ] Confirmar compatibilidade do código anterior
[ ] Confirmar autorização específica para a migration
```

Depois de uma migration irreversível, não presumir que redeploy de código anterior restaura o estado. A recuperação pode exigir forward-fix, restauração de backup ou plano próprio ratificado.

---

## 10. Backup

### Antes de migrations de risco

```text
[ ] Railway PostgreSQL → Backups → confirmar backup disponível
[ ] Criar backup manual quando exigido pelo risco
[ ] Guardar evidência do backup fora do repositório
[ ] Confirmar que o mecanismo de restauração está disponível
[ ] Não expor credenciais nem conteúdo sensível
```

### Política periódica

```text
- Confirmar no painel o plano e a retenção actualmente contratados
- Para piloto: backup antes de sessões com migrations de risco
- Para produção com utilizadores reais: política diária mínima ou superior
```

---

## 11. Variáveis de ambiente obrigatórias em produção

```text
DATABASE_URL                → PostgreSQL Railway com SSL
ENVIRONMENT                 → production
SECRET_KEY                  → chave não-placeholder
REDIS_URL                   → Railway Redis, quando configurado
REQUEST_LOG_RETENTION_DAYS  → política vigente
```

Verificar presença e escopo no painel sem imprimir os valores.

---

## 12. Referências

| Recurso | Localização |
|---|---|
| Railway — GitHub Autodeploys | https://docs.railway.com/deployments/github-autodeploys |
| Railway — Deployment Actions | https://docs.railway.com/deployments/deployment-actions |
| Railway — Pre-Deploy Command | https://docs.railway.com/deployments/pre-deploy-command |
| Vercel — Monorepos | https://vercel.com/docs/monorepos |
| Vercel — Configure a Build | https://vercel.com/docs/builds/configure-a-build |
| Repositório | https://github.com/nexialistamentor/saas-fiscal-demo |
| Health liveness | `GET /health` |
| Health readiness | `GET /health/ready` |
| ADR-006 | `docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md` |
| Handoff L2 | `docs/HANDOFF_TRIBUTARIA_L2_v3.md` |

---

## 13. Estado final do protocolo

A configuração operacional vigente separa publicação, deploy backend e deploy frontend. Nenhum push autoriza migration ou produção. Qualquer alteração às configurações externas do Railway ou da Vercel deve ser tratada como mudança operacional auditável.

`DEPLOY_PROTOCOL_L3_PUBLICACAO_E_DEPLOY_SEPARADOS`
