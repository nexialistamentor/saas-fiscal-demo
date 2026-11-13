# ALERTA -- Catraca anti-duplicacao: le isto antes de criar qualquer branch

**Resolvido em 2026-11-13, em `main`, commits `cd579473` -> `33f787c2`.**
**Mas o padrao de falha pode repetir-se -- ler isto sempre que algo
parecer estranho com `check_duplicacao.py`.**

## O que aconteceu

`tools/check_duplicacao.py`, `docs/REGISTRO_CANONICO.json` e
`githooks/pre-commit` foram criados em B03 (commit `a31ee81b`,
10/11/2026) mas **nunca chegaram a `main`** -- viveram so nos branches de
trabalho (`b03/...`, `b04/...`, `cobertura-nacional-jurisdicoes-*`, etc.).

Qualquer branch criado a partir de `main` (nao de um desses branches de
trabalho) **nascia sem a catraca**. O hook, ao nao encontrar os
ficheiros, **avisava e deixava o commit passar sem verificacao
nenhuma** -- silenciosamente, sem bloquear nada.

Isto causou um commit real (correcao da Issue #31, branch
`fix/issue-31-guarda-fonte-legal-prever-impacto-st`, criado a partir de
`main`) a ser feito **sem nenhuma verificacao de duplicacao**, e so foi
detetado porque o aviso ficou visivel no terminal e alguem reparou.

## O que foi corrigido

1. `tools/check_duplicacao.py` e `docs/REGISTRO_CANONICO.json` agora
   existem em `main` (commit `cd579473`).
2. `githooks/pre-commit` (a copia versionada, fonte para
   `tools/instalar_hooks.ps1`) e `.git/hooks/pre-commit` (a copia ativa
   no git-common-dir, `C:\dev\saas-fiscal-demo\.git\hooks\`) agora
   existem e estao **identicos** em `main` (commits `15310aab`,
   `3bbd1df2`, `33f787c2`).
3. O comportamento do hook mudou de **fail-open** para **fail-closed**:
   se os ficheiros da catraca faltarem, o commit agora e BLOQUEADO (exit
   1), com uma mensagem explicando a causa provavel (branch criado a
   partir de uma base sem o commit `a31ee81b`) e os comandos de
   diagnostico (`git log --oneline -1 -- $SCRIPT`,
   `git merge-base HEAD origin/main`).
4. Testado e confirmado a funcionar: um commit de teste foi recusado
   com a nova mensagem quando `REGISTRO_CANONICO.json` foi removido
   temporariamente.

## O que fazer, SEMPRE, antes de criar um branch novo

1. Nunca ramificar diretamente de `main` para trabalho de bloco/fase --
   ramificar de um branch de trabalho recente (ex.: o ultimo branch de
   B04 ou de Cobertura Nacional em curso), ou confirmar primeiro que
   `main` ja tem a catraca (agora tem, a partir de `33f787c2`).
2. Depois de criar qualquer branch, antes do primeiro commit, confirmar:
   Se qualquer um devolver `False`, PARAR -- nao commitar, nao usar
   `--no-verify` para contornar. Investigar a causa primeiro.
3. Se o pre-commit hook mostrar "AVISO" em vez de rodar a verificacao
   de verdade ("OK: nenhuma duplicacao..." ou "COMMIT BLOQUEADO pelo
   pre-commit hook"), isso e sinal de que o hook esta desatualizado ou
   os ficheiros estao em falta -- parar e investigar, nunca prosseguir.
4. Nunca usar `git commit --no-verify` sem motivo documentado no
   proprio commit -- o hook ja avisa disso, mas vale repetir aqui.

## Para quem esta a ler isto num handoff

Se chegaste aqui vindo de um handoff que nao mencionou isto
explicitamente, e sinal de que o handoff ficou incompleto -- confirma
sempre, por ti mesmo, com os dois `Test-Path` acima, antes de assumir
que a catraca esta presente no branch onde vais trabalhar.
