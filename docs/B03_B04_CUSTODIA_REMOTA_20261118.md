# SOLVERIS B03/B04 — recibo de custódia documental remota (18/11/2026)

- Repositório: `nexialistamentor/saas-fiscal-demo`.
- Branch exclusivo: `recovery/enterprise-b00-b04-20261117`.
- Base imutável: `main@a6a2da6cbf07c7b9922f8571bf2e6016376304d5`.
- Primeiro commit de custódia no GitHub: `0c0138fb6e02f3d5b14e605e0954eb4dc592a78d`.
- Commit local equivalente em árvore: `b4669d8243da262077a006979ae728b8a649c6d8`.
- SHA-1 da árvore idêntica de ambos: `d7053b8fd917281e1bea843f455b09fef363111a`.
- O primeiro commit remoto introduziu **somente seis documentos** em `docs/` e duas configurações `vercel.json`, com branch de recuperação explicitamente desabilitado para auto deploy.
- Consulta aos três projetos Vercel associados (`saas-fiscal-demo`, `frontend-dashboard` e `saas-fiscal-demo-ubop`): **zero deployments associados ao branch**, no momento da verificação.
- `main` permaneceu em `a6a2da6c`; nenhuma integração, migração, mudança no MEI, no motor de cálculo ou publicação Railway ocorreu.
- Fonte Enterprise c9: 36 blobs originais recuperados somente no worktree isolado, sem commit; a custódia dos respectivos hashes está no manifesto documental.
- Verificação sintática não executiva dos 36 arquivos com `ast.parse` usando `utf-8-sig`: `AST_OK 36`.
- Na máquina de execução Linux desta sessão, `pytest` não está instalado; **nenhuma suite global ou de integração foi executada após a custódia remota**. A linha de base do Windows permanece a já ratificada: 4.102 casos, 13 RED preexistentes, JUnit SHA-256 `798A14E3A2C6C517DD179559395A12E7FC370CDB49EB2FA3BD674B1599523692`.
- Estado soberano: `ENTERPRISE_RECOVERY_STATUS=BLOCKED`, `GLOBAL_GREEN=false`; a porta opt-in Enterprise no escritor compartilhado **foi apenas desenhada**, não implementada nem autorizada por este ato.
- Passo dependente: ratificação específica de Miguel para alterar a fronteira do escritor compartilhado, se essa for a decisão. Não interpretar o registro documental como autorização de implementação.
