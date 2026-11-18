# SOLVERIS — HANDOFF soberano de continuidade B03/B04 → B06

**Missão:** recuperar a linhagem B03/B04 sem afetar MEI ou produção, para posteriormente retomar `MISSION-015-B06-FASE0-MAPEAMENTO-INVESTIGACAO-V1.0`.

**Corte:** 18/11/2026, horário de Brasília. **Estado:** investigação, preparação e restauro seletivo **NÃO COMMITADOS**. **Não iniciar Fase 1 de B06.**

**Autoridade:** Miguel ratificou somente a recuperação B03/B04 em ambiente isolado e, excepcionalmente, uma catraca de testes diferencial que aceite **exatamente** 13 RED preexistentes da `main`, sem declarar GREEN global. Não houve ratificação do desenho de uma nova integração Enterprise nem de qualquer alteração ao escritor XML compartilhado.

## 1. Onde está o trabalho e como não o perder

| Objeto | Local / identificador |
| --- | --- |
| Repositório | `nexialistamentor/saas-fiscal-demo` |
| `origin/main` fixada | `a6a2da6cbf07c7b9922f8571bf2e6016376304d5` |
| Branch **local de recuperação** | `recovery/enterprise-b00-b04-20261117` |
| Worktree desta execução | `/workspace/scratch/2a148438772d/enterprise-recovery` |
| HEAD atual da recuperação | `a6a2da6c`, **sem commits novos** |
| Worktree Windows original de Miguel | `C:\dev\saas-fiscal-demo-a1` — branch `main`, com numerosos ficheiros B02/G5 não rastreados. **NÃO TOCAR.** |
| Worktree Windows de baseline | `C:\dev\saas-fiscal-demo-b06-green-20261118` — originalmente detached em `a6a2da6c`, com dois ajustes de teste ratificados; contém o JUnit bruto |
| Origem integral de B04 fechado | `c9a17fd1bc21f5abc50450e258cce490f3d196c6` |
| Marco anterior B02 | `f7825ecd` |
| Patches ainda **não integrados** | `fix/atomicidade-insights-commit` @ `912cb309`; `integracao-inteligencia-i0` @ `3f20b271` |

**Aviso de persistência:** os ficheiros descritos abaixo existem **apenas como alterações locais do worktree de recuperação**, sem commit, push ou PR. Um novo executor deve primeiro comprovar que esse worktree ainda existe e contém os mesmos objetos; se tiver desaparecido, **não assumir** que a preparação foi publicada. Não reconstruir por downloads avulsos nem modificar o worktree Windows original.

Não usar `git reset --hard`, `git clean -fd`, `git checkout --`, `git merge -X theirs` ou outros atalhos que apaguem custódia, descartem mudanças ou substituam indevidamente o hook fail-closed da `main`.

## 2. Por que o incidente aconteceu

1. B03 e B04 foram desenvolvidos e testados em linhagem própria, mas **não integrados na `main`**.
2. O commit `cd579473` trouxe manualmente à `main` a catraca (`tools/check_duplicacao.py` e `docs/REGISTRO_CANONICO.json`), sem parentesco de merge. A história Git resultante contém conflitos `add/add`.
3. O hook `githooks/pre-commit` fail-open da linhagem B03 diverge da correção fail-closed da `main` (`33f787c2`). **Preservar o hook da `main`.**
4. O diff `origin/main..c9a17fd1` tem **566 caminhos** porque a própria base B02/G12–G17/I0–I2 não está integrada, não porque os dois patches finais sejam tão grandes. O delta exclusivamente B03/B04 (`f7825ecd..c9a17fd1`) corresponde a **23 caminhos**.
5. A ligação Railway relatada por Miguel é `release/optional-meta-privacy-20261019`, com **auto-deploy OFF**. O executor B03/B04 confirmou não ter efetuado deploy. **Não presumir** que `main` ou B04 estão em produção.

## 3. Baseline integral e gate ratificado

Miguel executou no Windows, **sobre `main@a6a2da6c`, antes de incorporar B03/B04**, a suite integral sem `-x`, sem `--stepwise` e sem excluir testes:

- Python `3.12.10`; FastAPI `0.135.1`; Pydantic `2.12.5`; Docker Engine `29.6.1`.
- `ENVIRONMENT=test`, `DATABASE_URL=sqlite:///./b06_main_baseline.sqlite`.
- **4.102 `testcase` no JUnit; 4.074 passed; 13 failed; 15 skipped; 34 subtests passed; exit 1.** Duração 2.722,94 s.
- JUnit bruto em `C:\dev\saas-fiscal-demo-b06-green-20261118\.pytest_cache\b03b04_baseline_main.xml` (não transportar nem adicionar ao Git).
- SHA-256 **integral** do JUnit, fornecido por Miguel:
  `798a14e3a2c6c517dd179559395a12e7fc370cdb49eb2fa3bd674b1599523692`.
- Manifesto ratificado (13 IDs e versões/hashes, sem mensagens sensíveis): `docs/B03_B04_BASELINE_RATIFICADA_20261118.json`.
- Fingerprint canónico da exceção:
  `6a03eac66637c81181d7d9a0db9f978fd071734e8ac6fc41b091371447db8081`.

As 13 falhas preexistentes distribuem-se por **MEI (2), pagamentos (8), OPS12 (2) e pipeline XML (1)**. A mera anterioridade não significa que sejam erros sem importância. Os IDs exatos e a allowlist autorizada constam do manifesto, que a catraca verifica contra o JUnit integral e seu digest.

**Dois ajustes ratificados só de infraestrutura de testes**, sem alterações ao código de produto:

| Ficheiro | Modificação | Git blob local |
| --- | --- | --- |
| `tests/test_adr020_activation_postgresql.py` | URL do PostgreSQL **descartável** recebe `?sslmode=disable` | `b7e551df23c3f2ec60bcf95d1a1c3c9be9a68d50` |
| `tests/test_agent_contract_architecture.py` | leitor AST usa `utf-8-sig` para BOM pré-existente | `0d24fd62d66277d0107af182e035059523d72dae` |

Quatro contratos RED congelados (ver hashes integrais em `docs/B03_B04_BASELINE_RATIFICADA_20261118.json`) permanecem intocados. **Não modificar, ignorar, dar skip/xfail, reescrever fixtures ou alterar expectativa deles.**

**Catraca:** `tools/enterprise_recovery_test_gate.py`, com **20 controlos próprios aprovados** em `tests/test_enterprise_recovery_test_gate.py`. Ela exige:

1. JUnit baseline **exato** pelo SHA-256, versão de ambiente e 13 falhas ratificadas;
2. todos os 4.102 casos antigos executados e sem novas regressões/skips;
3. nenhuma modificação de MEI, de contrato protegido, do harness ratificado ou de caminho fora do manifesto;
4. **25 casos de integração obrigatórios e GREEN**: B01 (12), B03 (7) e B04 (6), fixados por node ID diretamente da origem `c9a17fd1`;
5. saída explícita `GLOBAL_GREEN=false` e somente `ENTERPRISE_RECOVERY_STATUS=PASS_WITH_BASELINE_RED` se todos esses critérios forem verdadeiros.

**Situação presente:** `ENTERPRISE_RECOVERY_STATUS=BLOCKED`, `GLOBAL_GREEN=false`. O gate ainda **não** recebeu os JUnit integrais real baseline+candidato no mesmo ambiente. Os 25 testes obrigatórios **não foram comprovados GREEN**. Nenhum commit está permitido com este estado.

## 4. Artefactos realmente preparados no branch isolado

**36 ficheiros provenientes, byte por byte, de `c9a17fd1`:**

- 14 módulos `app/services`: B03, B04, G12, G13, G14, G15, G16, G17, G19, I0, I1, I2, vínculo XML e composição do resultado empresarial;
- 5 ferramentas G1.13 C3–C7 em `tools/`;
- 17 testes originais: B01 (circuito), B03, B04 e testes dirigidos dos módulos anteriores.

**Cadeia de custódia completa por caminho e Git blob:** `docs/B03_B04_BLOB_PROVENIENCE_20261118.json`, source commit `c9a17fd1bc21f5abc50450e258cce490f3d196c6`. Foram verificados **36/36 blobs sem divergência**. Nenhum ficheiro foi obtido por ZIP/download manual.

Os 19 módulos passaram no parser AST e na resolução estática de imports internos explícitos. O G19 foi identificado como dependência dinâmica de G15, e também restaurado da mesma origem.

**Testes parciais executados neste Linux:** 215 testes passaram em oito grupos (G13 24; G15 34; G17 42; G19 37; G1.13 C7 25; C3 temporal 30; I0 7; I1 16). B03, B04, G14, G16, I2 e G1.13 C4–C6 ficaram bloqueados/parciais por faltarem `sqlalchemy`/`defusedxml` aqui. O ambiente **Windows com Docker** continua necessário para a verificação integral.

Também estão preparados, sem publicação, os bloqueios de preview deste branch nos ficheiros `frontend-dashboard/vercel.json` e `vercel.json` na raiz. Há **três projetos Vercel ligados ao repo**; sem verificar os seus diretórios-raiz não considerar estes bloqueios suficientes para autorizar push.

Os restantes ficheiros novos são precisamente o manifesto, esta documentação, o gate e seus testes. **Não se alterou** `app/models.py`, `app/database.py`, `app/services/registro_analise_service.py`, `app/xml_service.py`, `fiscal_utils.py`, MEI, pagamentos, o motor ICMS-ST/MVA ou as migrações.

Os caminhos preparados estão enumerados em `allowed_recovery_paths`; verificar a igualdade exata com `git diff --name-only a6a2da6c` mais `git ls-files --others --exclude-standard` antes de prosseguir.

## 5. Fronteira de arquitetura que impede declarar B04 integrado

Em `c9a17fd1`, a função `executar_circuito_enterprise_01` foi ligada no mesmo `app/services/registro_analise_service.py` que contém `executar_e_registrar_analise_xml`. A função de escrita **não é exclusiva de Enterprise**: a `main` chama-a por `app/main.py`, rotas de relatório e jobs.

O contrato I2 exige que `_enterprise_xml_evidence` esteja **dentro do resultado já selado** do relatório, com ligação verificável a `documento_id`, empresa, utilizador, chave e SHA-256 do XML. O escritor atual da `main` não emite esse campo. **Copiar apenas o consumidor B01 sem a mudança do escritor não recupera o circuito**: I2 falha fechado em `I2_NO_BOUND_DOCUMENT` (inferência de código, sem execução fim a fim ainda).

Não importar inteiro o escritor de `c9a17fd1`: ele altera a captura documental, a semântica de duplicação, produtor de proveniência e formato da saída para os seus consumidores compartilhados. Uma regressão pode atingir vertical MEI e outros relatórios mesmo sem tocar num caminho chamado `mei`.

**Proposta submetida a Miguel, ainda NÃO ratificada:** investigar a viabilidade de uma **entrada/adapter exclusivamente Enterprise, opt-in**, que reuse o escritor atual, preserve atomicidade e proveniência e deixe inalterados os fluxos legados. Se não for tecnicamente viável, reportar `CONTRACT_CONFLICT`/fronteira de autoridade e propor decisão específica antes de qualquer alteração do escritor. Não criar adaptador, novo motor, schema nem caminho de exceção até haver ratificação.

## 6. G12: prova de teste faltante já conhecida antes do incidente

`tests/test_enterprise_g12_st_item_readonly.py` carrega `g1_reference_engine.py` da raiz, mas esse ficheiro **não existe** em `c9a17fd1` nem no histórico Git consultado. A ausência **já estava documentada** em `docs/HANDOFF_COORDENACAO_FASE4_B05_20261113_CONTINUACAO.md`; B04 fechou com **120 testes dirigidos**, e não com GREEN global. O teste G12 não foi copiado para o candidato por criar erro inevitável de coleção; isto **não autoriza chamar G12 integralmente verificado**. Se necessário, consultar o executor B02/G12 para identificar a localização **original e SHA** do ficheiro; não o inventar.

## 7. Migrações, hooks e produção: exclusões permanentes deste escopo

- `main` contém até Alembic `0059`; a linhagem introduz `0060`–`0063`, incluindo `0062`/`0063` com estado de candidatura não ratificada. A produção Railway tem `alembic upgrade head` no predeploy. **Jamais merge/deploy da linhagem integral sem uma missão específica de migrações.**
- Os SQLs não rastreados `0064`–`0066b` do B02/G5 no worktree original de Miguel são custódia de outra missão. Não tocar nem utilizar.
- O hook de `main` permanece **fail-closed**; não o trocar pelo de B03. Não alterar a lista canónica de duplicações por conveniência.
- Não iniciar `railway up`, deploy manual, migração, merge na `main`, criação de PR, push, nem assumir que a produção usa a branch atual.
- A fase original de B06 é **investigação e mapeamento, zero PDF**. O produto SERPRO Consulta CNPJ, MVA por categoria do remetente e a escolha `TabelaMVA` vs `RuleVersion` continuam fora do escopo.

## 8. Ordem de retomada após ratificação de Miguel

1. **Verificação sem escrita:** localizar este worktree, confirmar `git branch --show-current`, `git rev-parse HEAD` = `a6a2da6c`, `git status --short`, conferir os **36 blobs** contra o manifesto, `git diff --check`, e os **20 controlos do gate**. Se o worktree desaparecer, parar e reconstruir a partir de Git com recibo de origem — não fingir continuidade.
2. **Decisão de arquitetura pendente:** analisar estritamente a viabilidade da entrada Enterprise opt-in, no ambiente de testes isolado, sem alterar o escritor compartilhado; confrontar todos os consumidores atuais e os contratos de identidade/atomicidade. Apresentar **uma proposta de delta mínimo e testes de não regressão**; pedir ratificação específica antes de escrever novo código.
3. **Se ratificado e viável:** integrar B01/B03/B04 exclusivamente no branch de recuperação, por intenção, guardas fail-closed e contratos sem alterações; nunca presumir que copiar funções corresponde à integração concluída.
4. **Validação:** executar testes B01/B03/B04, dependências e depois a suite integral do candidato **no Windows isolado**, usando o mesmo ambiente/coleção da baseline, gerar JUnit fora do Git e executar a catraca com o JUnit baseline fixado. Uma falha nova, um dos 25 obrigatórios ausente/RED, ou hash alterado => `BLOCKED` e parar.
5. **Só após gate real aprovado:** considerar commits atómicos no branch de recuperação e verificar o gatilho de deploy de **todos** os projetos Vercel antes de qualquer push. O gate diferencial **não** autoriza promoção `main`/deploy.
6. **Depois de base B03/B04 comprovada:** estudar e integrar em atos separados `912cb309` (atomicidade) e `3f20b271` (inteligência I0), com testes entre eles; não misturar os commits nem tocar em MEI sem mandato novo.
7. **Somente então** retomar `MISSION-015-B06-FASE0`: mapear `executar_circuito_enterprise_01`, 52 capacidades I0, cinco produtores de inteligência e **todos** os consumidores MVA; células MVA ambígua devem ser **"não apurado - pendente categoria do remetente"**. Entregar `docs/B06_MAPEAMENTO_CAPACIDADES_RELATORIO.md` para ratificação. **Não gerar PDF** nesta fase.

## 9. Próxima resposta esperada e critério de conclusão

**Aguardando de Miguel:** ratificação (ou restrição) da investigação da via Enterprise opt-in sem editar o escritor compartilhado. Ratificar a **investigação** não significa autorizar automaticamente implementar o adaptador ou alterar contratos.

**Não considerar esta missão concluída enquanto:** (a) B01/B03/B04 não estiverem ligados e testados, (b) os 25 testes de ligação não passarem, (c) a suite candidata/gate não tiverem recibo real, (d) a recuperação não estiver preservada num branch Git com commits rastreáveis e (e) Miguel não tiver ratificado o mapeamento B06 Fase 0.

**No momento deste handoff: `GLOBAL_GREEN=false`; `ENTERPRISE_RECOVERY_STATUS=BLOCKED`; ZERO commits/pushes/merges/deploys.**

## 10. Adendo após ratificação de investigação — 18/11/2026

Miguel ratificou **continuar a investigação de viabilidade** do adaptador Enterprise exclusivo, sem autorizar alterações ao escritor, novas regras ou implementação. Essa investigação de leitura foi concluída e formalizada em **`docs/B03_B04_VIABILIDADE_ADAPTADOR_ENTERPRISE_20261118.md`**.

**Resultado causal:** a `main` confirma o documento fiscal, o relatório inicial, o relatório final e o consumo em transações distintas; I2 exige `_enterprise_xml_evidence` já incluído no payload selado. Um adaptador pós-escrita não recupera atomicidade/uma só selagem. O circuito B01 `c9a17fd1` exige somente SQLite in-memory e a sua guarda `optante_mei is True` não cobre `NULL` (campo nullable). A opção de porta `opt-in` **no próprio escritor compartilhado** é tecnicamente mais próxima da origem, mas a sua avaliação/implementação toca fronteira não autorizada e não resolve por si todos os commits internos.

**Próximo ato requer nova escolha expressa de Miguel:** (1) manter a fronteira absoluta e admitir B03/B04 apenas como módulos restaurados, permitindo eventualmente mapeamento B06 **documental** por mandato novo, ou (2) abrir uma missão cirúrgica e segregada para desenhar a porta não-MEI na fronteira compartilhada, exigindo testes de atomicidade e não regressão antes da implementação. **Não presumir qualquer uma das duas escolhas pelo simples “ratifico” da investigação precedente.**

## 11. Ratificação posterior de desenho e custódia em Git

Miguel ratificou avançar com **o desenho e a validação documental**, reiterando que **todos os registos devem ficar no Git, não apenas em ficheiros locais**. Foi produzido `docs/B03_B04_DESENHO_PORTA_OPTIN_ENTERPRISE_20261118.md`, sem código novo de produção: define o contrato opt-in, o ponto anterior à selagem, riscos dos commits internos e o plano mínimo de testes. A implementação continua sem mandato.

Para preservar esta investigação, o próximo ato é **um commit documental isolado no branch de recuperação, sem incluir os 36 blobs de implementação, ficheiros MEI, migrações ou alterações de motor**, protegido por configuração Vercel de `git.deploymentEnabled["recovery/enterprise-b00-b04-20261117"]=false` na raiz e no frontend. O commit/remote devem ter recibos independentes e status explícito `GLOBAL_GREEN=false`. Nunca confundir esta custódia documental com aprovação técnica da recuperação.
