# DEPLOY_CHECKLIST.md — Plataforma Tributária L2

**Versão:** 1.0
**Data:** 2026-06-25
**Ticket:** B12-03

---

## Pré-Deploy (obrigatório antes de qualquer push para main)

```
[ ] git status --short → working tree limpa
[ ] git log --oneline -5 → commits na ordem correcta, mensagens claras
[ ] python -m pytest tests/ --tb=short -q → suite 100% verde (0 failed)
[ ] cd frontend-dashboard && npm run build → build sem erros
[ ] Migrations revisadas:
    - nova migration tem down_revision correcto
    - migration não é destrutiva sem plano de rollback
    - testar localmente: alembic upgrade head
[ ] .env de produção conferido:
    - DATABASE_URL aponta para Railway PostgreSQL
    - SECRET_KEY não é placeholder
    - ENVIRONMENT=production
[ ] Sem dados reais em fixtures ou repositório (ADR-006)
```

---

## Deploy (push para main)

```
[ ] git push origin main
[ ] Aguardar Railway iniciar o deploy (logs em tempo real)
[ ] Confirmar no log Railway:
    - "alembic upgrade head" concluído sem erro
    - "Application startup complete."
    - "Uvicorn running on http://0.0.0.0:PORT"
[ ] railway logs --tail 30 → sem traceback, sem ImportError, sem migration error
[ ] curl https://saas-fiscal-demo-production.up.railway.app/health
    → {"status":"ok"} HTTP 200
[ ] curl https://saas-fiscal-demo-production.up.railway.app/health/ready
    → HTTP 200, database="ok"
    → redis pode ser "ok", "not_configured" ou "unavailable"
    → redis unavailable não bloqueia deploy (fallback síncrono existe)
[ ] Testar endpoint crítico manualmente se migration nova foi aplicada
```

---

## Rollback

### Quando activar

```
- /health retorna erro ou não responde após deploy
- /health/ready retorna database="error" HTTP 503
- Traceback no log Railway após startup
- Falha em endpoint crítico (/upload-xml, /auth/login, /relatorio/*)
- Suite verde mas comportamento inesperado em produção
```

### Procedimento

```
[ ] 1. Identificar o último commit estável:
       git log --oneline -10
       → anotar o hash do commit anterior ao problemático

[ ] 2. Opção A — Reverter com git revert (PREFERIDO — preserva histórico):
       git revert HEAD
       git push origin main
       → Railway faz redeploy com a reversão

[ ] 3. Opção B — Redeploy via Railway dashboard:
       Railway → Deployments → seleccionar deploy anterior → Redeploy
       → sem novo commit necessário

[ ] 4. Opção C — Force push (PROIBIDO por defeito)
       REQUER ratificação explícita de Miguel.
       Só usar se A e B forem impossíveis.
       Destrói histórico e quebra auditabilidade.
       git reset --hard <hash_estavel>
       git push origin main --force

[ ] 5. Após rollback:
       curl .../health → {"status":"ok"}
       curl .../health/ready → database="ok"
       railway logs --tail 20 → startup limpo

[ ] 6. Documentar o incidente:
       - O que falhou
       - Qual commit foi revertido
       - Causa raiz
       - Acção correctiva antes do próximo deploy
```

### Rollback de migration destrutiva

```
ATENÇÃO: migrations destrutivas (DROP COLUMN, DROP TABLE) não têm rollback automático.

[ ] ANTES de qualquer migration destrutiva:
    - Fazer backup manual do PostgreSQL (Railway → Database → Export)
    - Confirmar que o dado a eliminar é dispensável
    - Ter script de restauração testado

[ ] Se migration destrutiva correu e precisa reverter:
    1. Restaurar backup do PostgreSQL
    2. Reverter código com git revert
    3. Redeployar
    4. Verificar integridade dos dados
```

---

## Backup

### Backup antes de migrations destrutivas

```
[ ] Railway Dashboard → PostgreSQL → Backups → Create Backup
[ ] Ou via pg_dump (necessita postgresql-client instalado):
    # Em bash/Linux:
    pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql
    # Em PowerShell, preferir Railway Dashboard ou WSL para este comando.
[ ] Guardar backup em local seguro fora do repositório
[ ] Verificar que o backup é legível antes de prosseguir
```

### Backup periódico (recomendado)

```
- Railway PostgreSQL tem backups automáticos (confirmar plano actual)
- Para piloto: backup manual antes de cada sessão com migrations
- Para produção com utilizadores reais: backup diário mínimo
```

---

## Variáveis de Ambiente Obrigatórias em Produção

```
DATABASE_URL                → PostgreSQL Railway (com SSL)
ENVIRONMENT                 → production
SECRET_KEY                  → chave gerada (não placeholder)
REDIS_URL                   → Railway Redis (opcional — fallback síncrono existe)
REQUEST_LOG_RETENTION_DAYS  → 30 (padrão)
```

Ver `.env.example` para lista completa com descrições.

---

## Referências

| Recurso | Localização |
|---------|------------|
| Dashboard Railway | https://railway.app |
| Repositório | https://github.com/nexialistamentor/saas-fiscal-demo |
| Health liveness | GET /health |
| Health readiness | GET /health/ready |
| ADR-006 (dados sensíveis) | docs/ADR-006-DADOS-SENSIVEIS-LGPD-PILOTO.md |
| Handoff | docs/HANDOFF_TRIBUTARIA_L2_v3.md |
