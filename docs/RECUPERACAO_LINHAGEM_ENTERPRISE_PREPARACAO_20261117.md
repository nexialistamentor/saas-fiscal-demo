# SOLVERIS — Recuperação da linhagem Enterprise — preparação isolada

Data: 2026-11-17

Autoridade: ratificação de Miguel para **investigação e preparação de branch isolado**, sem integrar em `main`, migrar base de dados ou executar deploy.
Estado: **PREPARACAO; ZERO MERGES; ZERO COMMITS; ZERO DEPLOYS**.

## 1. Diagnóstico causal

O encerramento técnico de B03/B04 foi demonstrado na linhagem de desenvolvimento,
mas não houve gate que exigisse um recibo de PR/merge para reconhecer esses
blocos como integrados na linha oficial. O `push` de um branch não altera
`main`, tampouco instala código em Railway quando o deploy está desativado.

O commit `cd579473` copiou os ficheiros da catraca de B03 para `main` sem
fundir a história Git de B03. Assim, os mesmos caminhos nasceram de forma
independente nas duas histórias. O hook `githooks/pre-commit` de `main`
foi subsequentemente corrigido para comportamento fail-closed em `33f787c2`;
na linhagem original, o hook diverge. Um merge `-X theirs`, `-s ours` ou
resolução por antiguidade de commit não seria seguro.

**Falha de cobertura da governança:** os controlos locais verificavam
duplicação de lógica e condições de commit, mas não exigiam prova de
ancestralidade/integração na `main`, nem comprovativo da implantação real.
Não inferir ausência de outras proteções sem auditar o ambiente correspondente.

## 2. Pins e destino de recuperação

| Objeto | Referência |
| --- | --- |
| `origin/main` | `a6a2da6cbf07c7b9922f8571bf2e6016376304d5` |
| Branch isolado **local** | `recovery/enterprise-b00-b04-20261117`, criado de `origin/main` |
| Marco de fechamento B04 para estudo | `c9a17fd1` |
| Patch atomicidade | `912cb309` |
| Patch/captura inteligência I0 | `3f20b271` (inclui `145a807b`) |
| Fonte configurada em Railway production | `release/optional-meta-privacy-20261019` (`3185a14e` no Git) |
| Auto-deploy Railway | Desativado, segundo a configuração fornecida por Miguel |

O branch `b04/integracao-g13-icms-st-20261111` avançou **após** `c9a17fd1`
para outras missões de cobertura nacional; o HEAD remoto observado foi
`9434c823`. **Não** integrar indiscriminadamente esse HEAD, nem as novas
missões, no escopo da recuperação B00–B04.

## 3. Preflight read-only do histórico

- O ancestral comum entre `main` e a linhagem B04 é `34bc4ee7`.
- `git merge-tree --write-tree --messages origin/main origin/b04/integracao-g13-icms-st-20261111`
  identificou três conflitos `add/add` em `docs/REGISTRO_CANONICO.json`,
  `githooks/pre-commit` e `tools/check_duplicacao.py`.
- Diferença total (`origin/main` → `c9a17fd1`): **566 ficheiros**, com
  aproximadamente **68.801 linhas adicionadas** e **1.762 removidas**.
  Estes números não equivalem à extensão dos patches finais.
- Os trabalhos `912cb309` e `3f20b271` têm deltas próprios pequenos em
  relação a `c9a17fd1` (cinco e sete ficheiros, respetivamente), mas
  dependem do extenso predecessor não integrado na `main`.
- A simulação read-only da combinação desses dois trabalhos não sinalizou
  conflitos textuais; não há ainda prova de compatibilidade semântica/suite.

## 4. Risco de migração e entrega

`origin/main` contém até `0059`; a linhagem B04 acrescenta `0060` a `0063`.
`0062` e `0063` declaram-se candidatos não ratificados. A configuração
de Railway apresentada por Miguel usa `alembic upgrade head` no pre-deploy.
Não presumir que todas as migrações podem ser aplicadas quando um código
novo for lançado. Nenhuma base operacional foi lida ou modificada nesta missão.

O relato do executor B03/B04 confirma push para GitHub sem deploy Railway.
A ligação atual do Railway a um branch de release não demonstra sozinha
o SHA efetivamente implantado; o último deployment SUCCESS ainda requer
leitura própria antes de qualquer promoção para produção.

## 5. Gates antes de qualquer integração

1. Inspecionar os 566 ficheiros por domínio e os efeitos reais da eventual
   fusão, com atenção a autoridades, pagamentos, MEI, L3 e B02.
2. Inventariar dependências, cabeças Alembic e elegibilidade de `0060–0063`
   em base **descartável**, sem ligar uma base de produção.
3. Preservar o `githooks/pre-commit` fail-closed de `main`; estudar os dois
   restantes conflitos sem apagar provas ou declarações canónicas.
4. Executar a suite num ambiente isolado seguro; não tratar suites
   locais antigas como prova de GREEN após o merge.
5. Só com estes gates cumpridos, pedir/seguir a autorização pertinente
   para um merge da base B00–B04 **no branch de recuperação**;
   os dois patches finais exigem integrações distintas com teste entre elas.
6. Não publicar a `main`, não fazer deploy, não migrar base e não abrir
   a B06 Fase 1 sem ratificação posterior de Miguel.

## 6. Mecanismo preventivo recomendado (ainda não implementado)

Toda declaração de bloco `FECHADO` deve distinguir três recibos:
**GREEN no branch**, **integração verificada na base canónica** e
**implantação efetiva confirmada**, quando aplicável.

Propor numa missão própria um gate obrigatório de PR/merge e de
ancestralidade em GitHub/CI, mais registo `docs/` com os SHA de origem,
integração e release. O scanner de duplicação não é uma ferramenta de
integridade de história Git e não deve ser confundido com tal garantia.

## 7. Custódia desta preparação

Adendo de preparação de publicação (ratificação de Miguel): foi colocada
**somente neste branch local, ainda sem commit**, a entrada
`git.deploymentEnabled["recovery/enterprise-b00-b04-20261117"] = false`
em `frontend-dashboard/vercel.json` e num `vercel.json` de raiz próprio
do branch de recuperação. A intenção única de ambas as configurações é
impedir previews do branch de recuperação sem desativar previews de
outros branches. Existem três projetos Vercel ligados ao repositório;
é necessário confirmar o diretório-raiz usado por cada um antes de
publicar. Até lá, nenhuma configuração foi aplicada remotamente.

### Preflight da suite em 2026-11-18

- Ambiente Python descartável criado fora do repositório, sem credenciais
  de produção; coleção completa: **4.102 testes**, sem erro de importação
  após instalar dependências apenas nesse ambiente efémero.
- Suite iniciada com `ENVIRONMENT=test`, SQLite temporário e `-x`.
  Resultado: **61 passed, 7 skipped, 1 error**, interrompida no primeiro
  erro porque `tests/test_adr020_activation_postgresql.py` executa
  `docker run` e este executor Linux não dispõe de `docker`.
- Isto é **bloqueio ambiental**, não GREEN e não prova de defeito do código.
  Docker Desktop no computador Windows de Miguel não se conecta por si
  só a este executor Linux; a suite completa terá de ser executada num
  ambiente com Docker acessível, após a verificação do worktree de destino.
- Os dois ficheiros `vercel.json` foram validados como JSON;
  `git diff --check` não encontrou problemas. Nenhum commit/push.

### Execução isolada no Windows de Miguel em 2026-11-18

- `origin/main` em `a6a2da6c`; worktree descartável independente
  `C:\dev\saas-fiscal-demo-b06-green-20261118`, HEAD detached e limpo
  antes de iniciar; Docker Engine `29.6.1` e dependências Python disponíveis.
- Com `ENVIRONMENT=test` e `DATABASE_URL=sqlite:///./b06_main_baseline.sqlite`,
  `python -m pytest -q -x --tb=short` terminou com **167 passed,
  7 skipped, 1 failed** após 288,94 s. Não existe GREEN global.
- Falha localizada em
  `tests/test_adr020_activation_postgresql.py::test_real_postgresql_downgrade_is_irreversible_and_preserves_objects`:
  o subprocesso `python -m alembic downgrade ...` tentou usar SSL contra
  o PostgreSQL `postgres:16-alpine` temporário sem SSL. O teste esperava
  `RuntimeError` por downgrade irreversível e recebeu erro de ligação
  `server does not support SSL, but SSL was required` antes de validar
  a cláusula irreversível.
- Causa demonstrada por código: `_postgresql_instance` constrói a URL
  `postgresql+psycopg://...` sem `sslmode` e entrega-a ao subprocesso
  em `env["DATABASE_URL"]`; `migrations/env.py` importa `app.database`,
  que injeta `sslmode=require` por defeito nos ambientes não estritos,
  incluindo `test`. O `create_engine(url)` da fixture principal usa a URL
  original e consegue conectar, razão pela qual o primeiro erro aparece
  somente no subprocesso Alembic. Não é atribuível aos branches B03/B04.
- Após ratificação explícita de Miguel, correção **preparada somente no
  worktree isolado de recuperação e ainda sem commit**: definir
  `sslmode=disable` na URL local do PostgreSQL descartável da fixture,
  seguindo o padrão já presente nos testes de integração MEI locais.
  `git diff --check` e parsing AST passaram, mas **não há ainda GREEN**.
  A repetição da suite no worktree isolado do Windows é o próximo gate.
  Não alterar a política SSL de `app/database.py`, nem migrações;
  não desconsiderar o teste nem declarar GREEN prematuramente.
- Uma repetição isolada do teste no Windows continuou a falhar com SSL
  (`1 failed`, 6,05 s); o `git diff -- tests/test_adr020_activation_postgresql.py`
  subsequente foi **vazio**. Portanto, a modificação ainda **não tinha
  sido aplicada** naquele worktree e esta execução não valida nem invalida
  a correção candidata. Requer aplicar/verificar o diff antes de novo teste.
- Miguel confirmou depois o diff **exato de uma linha** no worktree Windows:
  a URL da fixture passou a incluir `?sslmode=disable`. A reexecução
  dirigida de
  `test_real_postgresql_downgrade_is_irreversible_and_preserves_objects`
  obteve **1 passed, 1 warning, 6,81 s**. Isto fecha a falha SSL pontual;
  o gate de suite global continua pendente.

### Segundo bloqueio da baseline `main` no Windows

- A suite global reiniciada com a correção SSL chegou a **684 passed,
  7 skipped, 1 failed** em 465,95 s (terminou pelo `-x`, sem GREEN).
- Primeiro RED em
  `tests/test_agent_contract_architecture.py::test_production_creates_agent_mission_only_in_factory`:
  `_parse()` usa `path.read_text(encoding="utf-8")` para passar texto a
  `ast.parse()`. O ficheiro varrido `app/routers/empresa_router.py`
  começa com bytes `EF BB BF` (BOM UTF-8), **comprovados no blob do
  próprio commit `a6a2da6c`**, logo anteriores a esta recuperação.
  A conversão para string mantém `U+FEFF` e o `ast.parse` do texto lança
  `SyntaxError: invalid non-printable character U+FEFF`.
- O repositório já aceita esta codificação noutros leitores AST com
  `utf-8-sig`, incluindo `tools/check_duplicacao.py` e
  `app/scripts/mei_publication_reachability_census.py` (com teste de
  regressão específico para BOM). Após ratificação específica de Miguel,
  **foi preparada, ainda sem commit**, a alteração restrita ao leitor
  `_parse()` do teste de arquitetura, de `utf-8` para `utf-8-sig`.
  Preflight estático: `git diff --check` GREEN; parsing AST de **284
  ficheiros Python de `app/`** GREEN; varredura semântica encontra a única
  chamada `AgentMission` em `app/agents/mission_factory.py:206`, exatamente
  como esperado pelo contrato do teste. Falta aplicar no worktree Windows
  e obter resultado real de pytest, depois suite global. Não remover BOM
  ao ficheiro de negócio, não alterar motor e não silenciar o teste.
- Miguel confirmou a execução dirigida real do teste corrigido no
  Windows: **1 passed, 2 warnings, 1,48 s**. A baseline ainda **não**
  possui GREEN global; os dois ajustes de fixture/leitor AST estão
  preparados nos worktrees isolados e não foram commitados.
- Para eventuais RED subsequentes, a estratégia de diagnóstico pode usar
  `pytest --stepwise` (retoma a partir da última falha, sem a ocultar),
  mas essa execução **não substitui** o gate final de suite global
  integral, desde o início e sem retoma, antes de qualquer commit.

### Terceiro bloqueio da baseline: contrato RED e API FastAPI/Pydantic

- Execução Windows de `pytest --stepwise` chegou a **2.516 passed,
  10 skipped, 1 failed**, 536,31 s, aproximadamente 61% da coleção.
- Falha em
  `tests/test_mei_competencia_checkout_intent_http_contract_red.py::test_http_mei_intent_route_authentication_and_schema_red`:
  acesso a `route.body_field.type_.model_fields` lança
  `AttributeError: 'ModelField' object has no attribute 'type_'`.
- O ficheiro RED foi congelado em `79ce7b8e` (2026-09-25);
  `requirements.txt` e `requirements_pinned.txt` declaram desde maio
  FastAPI `0.135.1` e Pydantic `2.12.5`. É necessária confirmação da
  versão *efetivamente instalada* no `.venv-release` Windows, antes de
  concluir se existe deriva de ambiente ou incompatibilidade do contrato.
- Miguel confirmou no mesmo `.venv-release` Windows as versões **exatas**
  `FastAPI: 0.135.1` e `Pydantic: 2.12.5`; não se verificou deriva de
  dependências. O `AttributeError` demonstra incompatibilidade do acesso
  `.type_` do contrato com o objeto recebido no ambiente fixado.
- Há **sete acessos `.type_` em quatro ficheiros `*_contract_red.py`**:
  checkout de intenção MEI, checkout de oferta, aquisição de relatório
  e wiring de intenção de relatório. Não é uma ocorrência isolada.
  **Não alterar contratos RED congelados**, nem API de produção ou
  dependências, sem nova análise/ratificação. `--stepwise` mantém o
  teste bloqueante para retomada, sem o esconder.
- A constituição `AGENTS.md`, secção 3, exige nestas condições
  **CONTRACT_CONFLICT**, interrupção e diagnóstico apenas de leitura;
  mudanças ao contrato exigem **missão separada** e **commit test-only**,
  distinto de alterações de produção. Não há ratificação dessa missão.
- Hashes `git hash-object` dos quatro contratos protegidos no worktree
  de recuperação, antes de qualquer ação corretiva:
  - `tests/test_mei_competencia_checkout_intent_http_contract_red.py`:
    `f8ef579db5052c9b80924bb7de5a0606d70b9413`
  - `tests/test_payments_checkout_offer_one_time_router_contract_red.py`:
    `015ecd0eba8f07268707f162dbe77c120c6789b2`
  - `tests/test_payments_tax_report_acquisition_http_create_contract_red.py`:
    `1f94eb43b9e02c3f5c2b73ac59b4b16918a4e2db`
  - `tests/test_payments_tax_report_checkout_intent_wiring_contract_red.py`:
    `5b7bc772c85704da3f491e3f1b658388246ed064`

### Decisão posterior de escopo de Miguel

- Miguel ratificou a continuidade da **recuperação estrita B03/B04**, com
  proibição explícita de **tocar no MEI**. Portanto, a proposta de
  modernização dos quatro contratos RED **não está autorizada nesta
  missão**, e nenhum dos seus ficheiros foi alterado.
- O gate original `suite global GREEN antes de merge/commit` e a
  proibição de tocar em MEI não são simultaneamente satisfeitos pela
  baseline `main` observada: a suite para em contrato RED de MEI por
  incompatibilidade com o FastAPI fixado. **Não** chamar a baseline de
  GREEN, não excluir/`skip`/`xfail` o contrato e não importar alteração
  de MEI a partir da linhagem de B03/B04.
- Inspeção read-only de escopo: o delta próprio B03/B04 entre
  `f7825ecd` (base B02 fechada) e `c9a17fd1` toca exatamente
  **23 caminhos**, principalmente dois serviços Enterprise, testes,
  documentos, catraca e integração ao circuito B01. Contudo, a própria
  base B02+G12/G13 **não existe na main**. A diferença integral
  `origin/main..c9a17fd1` tem **493 adições, 54 modificações e
  19 exclusões**, incluindo serviços compartilhados, pagamento,
  modelos e esquemas. A recuperação não pode ser tratada como um merge
  simples de 23 caminhos ou como ausência automática de impacto no MEI.
- Continuação segura autorizada: mapear dependências, comparar artefactos
  e preparar uma proposta de integração **sem aplicar merge e sem
  alterar os contratos MEI**. Qualquer mudança no gate de GREEN global
  exige decisão soberana explícita, não pode ser inferida da autorização
  de investigação nem mascarada por seleção de testes.

### Dependências mínimas comprovadas da ponte B04 (somente leitura)

O módulo `enterprise_b04_icms_st_integral_bridge.py` não é independente:

1. B04 chama `enterprise_i2_documentary_bridge` e
   `enterprise_g13_subject_st_bridge`;
2. I2 chama `enterprise_pis_cofins_authority_i1` e
   `enterprise_xml_evidence_binding`, além do serviço de proveniência;
3. I1 chama `enterprise_integral_projection` (catálogo I0);
4. G13 chama I2 e `enterprise_g12_st_item_reconciliation`;
5. G12 chama `MotorFiscal`, `fiscal_utils`, `tabela_normativa_service`,
   `TaxConsistencyEngine` e `xml_service`;
6. O consumidor de produção `executar_circuito_enterprise_01` está em
   `registro_analise_service.py`, que também mudou na linhagem.

Nenhum destes módulos `enterprise_*` referidos existe hoje em `main`.
Preflight `git cat-file -e` confirmou individualmente **oito módulos
Enterprise ausentes da `main`**: `enterprise_b03_item_reconciliation`,
`enterprise_b04_icms_st_integral_bridge`,
`enterprise_i2_documentary_bridge`,
`enterprise_g13_subject_st_bridge`,
`enterprise_pis_cofins_authority_i1`,
`enterprise_xml_evidence_binding`,
`enterprise_g12_st_item_reconciliation` e
`enterprise_integral_projection`. Já estão em `main` os serviços
compartilhados `resultado_provenance_service` e
`registro_analise_service`, mas este último diverge materialmente.
O comparativo integral também modifica `app/models.py` (+226 linhas),
`app/database.py` (+24), `fiscal_utils.py` (+80/-32),
`registro_analise_service.py` (+346/-7) e `xml_service.py` (+6/-36).
Estes são caminhos compartilhados: não há prova de isolamento de MEI
apenas porque o nome não contém `mei`. É obrigatório mapear dependências
e efeitos antes de uma integração seletiva; jamais usar `-X theirs`
ou importar a árvore inteira da linhagem como solução rápida.

**Achado adicional na cadeia de execução B01/B04:** o consumidor
`executar_circuito_enterprise_01` na linhagem é **opt-in e estritamente
sintético**, exigindo base SQLite **em memória** e empresa não MEI com
regime real/presumido antes de prosseguir; não é prova de execução
Enterprise em PostgreSQL de produção. A função importa também G14,
G17 (que exige G15/G16) e ferramentas G1.13 C3–C7, além de G12/G13/I0/I2.
Assim, a dependência fechada excede os oito módulos inicialmente
enumerados.

Mais importante: a revisão da linhagem modifica o **escritor partilhado**
`executar_e_registrar_analise_xml` no mesmo
`registro_analise_service.py`: passa a capturar o `DocumentoFiscal`,
vincular `_enterprise_xml_evidence` e alterar a identidade/produtor do
resultado selado para empresas. O escritor em `main` é invocado com
`empresa_id` e não apresenta um gate explícito de regime no seu corpo.
**Não** importar essa modificação indiscriminadamente: o bloqueio
"sem tocar no MEI" requer demonstrar isolamento de chamadas e
regressões, ou uma decisão específica sobre o consumidor partilhado.
Até lá, nenhuma função do escritor foi alterada no branch de recuperação.

### Gate diferencial de recuperação: ratificação condicional em 2026-11-18

Miguel ratificou **somente para o branch isolado de recuperação**, sem
alterar MEI, o gate diferencial com as seguintes condições reforçadas:

1. **Independência causal:** confirmar documentalmente que o erro RED do
   MEI já se reproduz no worktree separado `main@a6a2da6c`, que não tem
   os módulos Enterprise B03/B04; vincular logs e manifesto à identidade
   dessa revisão, ao Python e às dependências efetivamente instaladas.
   A execução já observada em `main` comprovou o primeiro RED depois de
   2.516 testes aprovados. Isso prova anterioridade dessa falha, mas
   **não** define ainda o conjunto completo das falhas da baseline.
2. **Baseline exaustiva:** executar a suite até ao fim, sem `-x`, sem
   `--stepwise`, sem ignorar/`skip`/`xfail` os contratos; guardar resultado
   JUnit bruto só no ambiente isolado e extrair manifesto sanitizado
   dos node IDs, estados, contagens e fingerprint da cobertura.
3. **Catraca mecânica fail-closed:** para qualquer candidato de B03/B04,
   exigir execução integral da mesma coleção base, igualdade dos hashes
   de contratos protegidos, ausência de modificações de MEI, manutenção
   de todos os testes previamente aprovados, nenhum novo skip/falha e
   GREEN dos testes novos Enterprise. Rejeitar resultados incompletos,
   de SHA divergente ou sem artefactos de prova.
4. **Saída não ambígua:** se persistir qualquer falha aceita por baseline,
   escrever explicitamente `GLOBAL_GREEN=false`,
   `ENTERPRISE_RECOVERY_STATUS=PASS_WITH_BASELINE_RED` e
   `MEI_BASELINE_FAILURE_ACCEPTED_FINGERPRINT=<digest>` no resultado
   versionado; uma simples palavra `GREEN` **não** serve como recibo.
   O fingerprint deve ligar **revisão base + node IDs + hashes dos
   contratos + ambiente de teste**, nunca só os quatro hashes.
5. **Escopo de exceção:** a aceitação de RED preexistente não promove
   código para `main`, não autoriza deploy/migrações e não constitui
   release GREEN. Só habilita preparação/commits segregados no branch
   local/isolado quando a própria catraca e a suite Enterprise passarem.

**Estado atual:** ratificação de princípio recebida; ainda **não** existe
inventário completo da baseline, portanto o gate **não está satisfeito**.
Nenhum merge/commit/deploy foi realizado.

**Catraca em preparação (sem commit):** criada
`tools/enterprise_recovery_test_gate.py`, com 13 controlos negativos
próprios em `tests/test_enterprise_recovery_test_gate.py`
(13/13 GREEN em `unittest`, parsing AST e `git diff --check` GREEN).
Exige manifesto de baseline previamente ratificado, compara a coleção
JUnit inteira, barra falhas/skips novos, barras de contrato, caminhos
MEI alterados, caminhos não aprovados, hashes divergentes e
ambiente fora das versões aprovadas. Em sucesso com RED preexistente,
escreve `GLOBAL_GREEN=false` e status explícito, nunca GREEN global.
O artefacto ainda **não foi exercitado sobre duas suites integrais
reais** e a allowlist de falhas continua vazia até chegar o JUnit
completo de `main`; não pode ser considerado aprovado por si só.

### Resultado integral da baseline `main@a6a2da6c` (Windows, 2026-11-18)

Miguel executou `python -m pytest -q --tb=line --disable-warnings
--junitxml=.pytest_cache/b03b04_baseline_main.xml` no worktree isolado
com os **dois ajustes de infraestrutura de teste ratificados**
(SSL descartável e leitura AST BOM), mas **sem qualquer código B03/B04
ou modificação dos contratos MEI**.

Resultado: **13 failed, 4.074 passed, 15 skipped, 34 subtests passed,
2.689 warnings; 2.722,94 s (45m22s); exit 1**. São 4.102 testes
principais reportados. O JUnit bruto permaneceu no Windows, fora de Git.

Node IDs das 13 falhas, fornecidos pelo resumo completo do pytest:

1. `tests/test_mei_competencia_checkout_intent_http_contract_red.py::test_http_mei_intent_route_authentication_and_schema_red`
2. `tests/test_mei_normative_census.py::test_real_repository_call_site_scan_is_complete_and_has_no_structural_findings`
3. `tests/test_ops12_f2_gerar_relatorio_contract.py::test_f2_gerar_relatorio_sem_empresa_retorna_200`
4. `tests/test_ops12_f2_gerar_relatorio_contract.py::test_f2_gerar_relatorio_com_empresa_retorna_200`
5. `tests/test_payments_checkout_offer_campaign_dispatch_toctou_contract_red.py::test_payments_checkout_offer_campaign_dispatch_toctou_contract_red`
6. `tests/test_payments_checkout_offer_campaign_preference_expiry_contract_red.py::test_payments_checkout_offer_campaign_preference_expiry_contract_red`
7. `tests/test_payments_checkout_offer_one_time_router_contract_red.py::test_payments_checkout_offer_one_time_router_contract_red`
8. `tests/test_payments_checkout_offer_second_legitimate_payment_reconciliation_contract_red.py::test_payments_checkout_offer_second_legitimate_payment_reconciliation_contract_red`
9. `tests/test_payments_mercado_pago_main_wiring_contract_red.py::test_payments_mercado_pago_main_wiring_contract_red`
10. `tests/test_payments_multi_vertical_one_time_dispatch_contract_red.py::test_payments_multi_vertical_one_time_dispatch_contract_red`
11. `tests/test_payments_tax_report_acquisition_http_create_contract_red.py::test_tax_report_acquisition_http_create_route_and_authority_contract_red`
12. `tests/test_payments_tax_report_checkout_intent_wiring_contract_red.py::test_http_intent_endpoint_exists_authenticated_and_has_exact_input_red`
13. `tests/test_pipeline_xml_canonico.py::test_processar_xml_job_delega_para_eixo_canonico`

**Decisão técnica fail-closed:** a ratificação anterior contemplava a
falha MEI preexistente ligada a quatro contratos protegidos, não
**13 falhas distribuídas por MEI (2), pagamentos (8), relatórios OPS12
(2) e pipeline XML (1)**. Destas, **nove** estão fora dos quatro
contratos pinados. Não aceitar automaticamente as nove restantes como
dívida tolerada, nem alterar/ignorar testes, nem declarar
`PASS_WITH_BASELINE_RED`. O gate continua **BLOCKED — BASELINE_SCOPE_UNRATIFIED**.
É necessária decisão soberana sobre este delta de escopo antes de
aprovar manifesto e permitir commits de recuperação.

**Ratificação complementar de Miguel:** após conhecer a distribuição
completa, Miguel ratificou expressamente a ampliação do gate diferencial
**exatamente aos 13 node IDs listados acima**, **só** para recuperação
isolada B03/B04, mantendo `GLOBAL_GREEN=false`, sem alteração de MEI,
sem autorização de `main`, deploy ou migrações. Isto não valida o
comportamento comercial dos pagamentos; os riscos permanecem abertos.
A catraca foi adaptada para rejeitar mecanicamente um 14.º RED ou a
ausência de qualquer um dos 13 da baseline ratificada. Os **14 testes
próprios do gate** passaram em `unittest`, e `git diff --check` passou.
Ainda faltam: (i) SHA-256 do XML integral no Windows, (ii) contagem
de `testcase` do JUnit, (iii) manifesto aprovado que fixe estes valores
com os 13 IDs verificados e (iv) suite integral do candidato.
Até isso, o estado permanece **BLOCKED — EVIDENCE_PENDING**.

**Confirmação posterior pelo XML efetivo do Windows:** os 13 elementos
`testcase` com `failure` devolvem `classname::name` exatamente
equivalentes aos 13 node IDs enumerados nesta secção (prefixo
`tests.` e nome de função), sem nomes adicionais. A versão real do
interpretador é Python **3.12.10**; FastAPI **0.135.1** e Pydantic
**2.12.5** já tinham sido verificados. Atributo `type` dos elementos
`failure` veio vazio no resumo sanitizado, portanto não presumir
`AttributeError` como tipo XML sem ler o documento. O SHA-256 do JUnit,
e o número de elementos `testcase` continuam pendentes de extração,
**sem transferir o XML bruto**. A catraca passou a exigir SHA-256
exato do **ficheiro JUnit integral** para vincular, sem expor, todas
as mensagens de falha e os seus tipos; o manifesto público contém
somente os 13 IDs, os hashes protegidos e esse digest. O conjunto de
controlo do gate foi ampliado para **16 testes**, todos GREEN em
`unittest`, incluindo prova negativa de digest JUnit divergente e de
alteração dos dois ajustes do harness. Os blobs fixados destes ajustes,
preparados no branch de recuperação, são:

- `tests/test_adr020_activation_postgresql.py`:
  `b7e551df23c3f2ec60bcf95d1a1c3c9be9a68d50`;
- `tests/test_agent_contract_architecture.py`:
  `0d24fd62d66277d0107af182e035059523d72dae`.

Devem coincidir com os `git hash-object` no worktree Windows que
produziu o JUnit. Se divergirem, o gate falha fechado.

**Cotejo efetivo (Miguel, Windows):** o JUnit contém exatamente
**4.102 elementos `testcase`**. Os hashes dos dois ficheiros de
harness no worktree Windows foram, na ordem acima, exatamente
`b7e551df23c3f2ec60bcf95d1a1c3c9be9a68d50` e
`0d24fd62d66277d0107af182e035059523d72dae`, sem divergência.
O campo SHA-256 do ficheiro JUnit inteiro não constou da saída
fornecida; **permanece o único valor de identidade da baseline ainda
em falta** para preencher o manifesto de aprovação do gate.

**Recebimento posterior do digest:** Miguel forneceu SHA-256 do JUnit
`798a14e3a2c6c517dd179559395a12e7fc370cdb49eb2fa3bd674b1599523692`.
Foi criado, ainda **sem commit**, o manifesto
`docs/B03_B04_BASELINE_RATIFICADA_20261118.json`, com identidade exata
`main@a6a2da6c`, 4.102 casos, 4.074 passados, 15 ignorados,
13 falhas ratificadas, exit 1, versões e hashes de contratos/harness.
Fingerprint canónico do gate:
`6a03eac66637c81181d7d9a0db9f978fd071734e8ac6fc41b091371447db8081`.
O teste sintético de consistência do manifesto, contra a coleção de
4.102 estados reconstruídos para validação de estrutura, está GREEN;
**não** equivale a executar os 4.102 testes sobre código recuperado.
Ao todo, **18 controlos do gate** passaram em `unittest`, e
`git diff --check` passou. O gate continua **não executado sobre o
JUnit real**, que permanece no Windows, e sobre um candidato recuperado.

Leitura orientada das categorias, ainda **sem diagnóstico causal final**:

- Dois testes MEI: introspecção `ModelField.type_` e um censo normativo
  cujo predicado `scan_complete`/`findings` reprova.
- Oito contratos de pagamentos: três envolvem a superfície
  `ModelField` ou bindings de schema/router; outros cinco invocam
  propriedades de negócio relevantes (TOCTOU fail-closed, expiração de
  preferência, preservação de segundo pagamento legítimo e integração
  Mercado Pago/multivertical). **Não** tratar estes últimos como meros
  defeitos de fixture sem análise independente.
- Dois testes OPS12 F2: fixtures devolvem `SimpleNamespace` sem
  atributo `status`, enquanto o consumidor o exige.
- Um teste de pipeline XML: `ResultadoProvenanceError` numa chamada
  mockada de persistência/resultado, a investigar separadamente.

Isto reforça que um gate aprovado para **quatro** contratos não pode
aceitar automaticamente **treze** falhas apenas por todas serem
anteriores à recuperação. O XML de baseline deve ter hash fixado antes
de qualquer decisão de ampliação.

O presente documento está **somente no worktree isolado da investigação**,
por enquanto sem commit nem push; não substitui a ratificação da estratégia
de integração nem prova que a suite está verde. O worktree original permanece
intacto, e a produção Railway não foi tocada.

## 8. Reconstituição seletiva em worktree isolado — 2026-11-18

Após fixar o SHA-256 da baseline, procedeu-se **somente a restauro exato
de blobs ausentes na `main`**, com origem identificada em `c9a17fd1`, sem
merge/cherry-pick e sem adaptação de código de negócio. Foram restaurados
**36 blobs idênticos à fonte** (19 módulos de implementação Enterprise e
17 testes de seus contratos), todos cotejados por `git rev-parse
c9a17fd1:<caminho>` versus `git hash-object <caminho>`.

O inventário individual e verificável de **caminho → Git blob SHA-1**
destes 36 itens está em
`docs/B03_B04_BLOB_PROVENIENCE_20261118.json`, com origem completa
`c9a17fd1bc21f5abc50450e258cce490f3d196c6`.

- **14 módulos** `app/services`: `enterprise_b03_item_reconciliation`,
  `enterprise_b04_icms_st_integral_bridge`, `enterprise_integral_projection`,
  `enterprise_pis_cofins_authority_i1`, `enterprise_xml_evidence_binding`,
  `enterprise_i2_documentary_bridge`, `enterprise_g12_st_item_reconciliation`,
  `enterprise_g13_subject_st_bridge`, `enterprise_g14_operational_normative_scope`,
  `enterprise_g15_adr020_primary_artifact_link`,
  `enterprise_g16_temporal_rule_chain`,
  `enterprise_g17_publication_coverage_checkpoint`,
  `enterprise_g19_local_cas_custody` e `resultado_empresarial_service`;
- **5 ferramentas de evidência** `tools/enterprise_g113_*`:
  `temporal_mva_evidence`, `c4_fiscal_item_bridge`, `c5_parameter_trace`,
  `c6_l2_record_provenance`, `c7_diagnostic_dossier`;
- **17 testes de origem**: circuito B01, B03, B04, G1.13 C3–C7,
  G13–G17, G19, I0, I1 e I2 (caminhos explícitos no manifesto do gate).

O módulo G19 é uma dependência de importação **dinâmica** de G15 que
uma varredura limitada a `ImportFrom` não detetava; foi restaurado
depois de conferir a sua origem. Os 19 módulos passaram no parser AST,
com 18 imports internos explícitos resolvidos e **zero destinos ausentes**.
Isso demonstra apenas completude sintática/de caminhos, não a capacidade
de executar o circuito nem compatibilidade de dados em produção.

Os 45 caminhos atualmente alterados/criados no worktree de recuperação
(36 blobs de origem + 9 ficheiros de documentação, gate, harness e
configuração Vercel) coincidem **exatamente** com os 45 caminhos da
`allowed_recovery_paths` no manifesto. Nenhum caminho MEI, pagamento,
`main`, motor de cálculo, esquema Alembic ou escritor partilhado
`registro_analise_service.py` foi alterado. Os quatro contratos
congelados mantêm os hashes ratificados.

### Prova parcial de testes em ambiente Linux sem dependências completas

Testes unitários executados com `unittest` e apenas dependências presentes
no executor, sobre blobs recuperados nesta secção:

| Grupo | Resultado | Observação |
| --- | --- | --- |
| G13 | 24 passaram | Testes sintéticos sem BD |
| G15 | 34 passaram | Testes isolados com stubs |
| G17 | 42 passaram | Testes isolados com stubs |
| G19 | 37 passaram | CAS local apenas com ficheiros temporários dos testes |
| G1.13 C7 | 25 passaram | Dossiê de diagnóstico |
| G1.13 C3 temporal | 30 passaram | MVA temporal, sem motor de produção |
| I0 | 7 passaram | Projeção integral |
| I1 | 16 passaram | PIS/COFINS informativo |
| B03, B04, G14, G16, I2, G1.13 C4/C5/C6 | **bloqueados ou parciais** | Faltam `sqlalchemy` e/ou `defusedxml` neste executor |

Total de **215 testes de oito grupos inteiramente aprovados**;
os grupos parcialmente executados não contam como aprovados. Os
**20 controlos próprios da catraca** passaram separadamente. Nenhum destes
resultados é suite global, prova de conexão PostgreSQL ou aprovação de
integração com `main`.

### Lacuna histórica adicional: teste G12 não autocontido

O teste original `tests/test_enterprise_g12_st_item_readonly.py` depende
de `g1_reference_engine.py` na **raiz** do repositório, por carregamento
direto via `importlib.util.spec_from_file_location`. Esse ficheiro **não
existe** na árvore `c9a17fd1` nem apresenta commits no histórico
disponível (`git log --all -- g1_reference_engine.py` vazio). O teste
G12 **não foi importado**, pois acrescentá-lo agora criaria um erro
de coleção certo. A implementação G12 foi preservada sem alterações;
é necessário localizar o artefacto original e sua proveniência com o
executor B02/G12 antes de integrar este teste. Não fabricar motor de
referência, não adaptar o teste e não alegar GREEN de G12.

**O problema não é novo:** o documento já versionado em `main`,
`docs/HANDOFF_COORDENACAO_FASE4_B05_20261113_CONTINUACAO.md`, secção 2,
regista expressamente este mesmo teste como um dos três erros de coleta
anteriores, deliberadamente excluídos das suites dirigidas de B04.
O fechamento B04 (`docs/B04_FECHAMENTO.md` na origem) reportava **120
testes relevantes**, e não GREEN integral do repositório. Portanto a
ausência deste artefacto **não nasceu** da presente recuperação; a sua
falta continua como limite de validação independente de G12.

### Limite de integração que continua aberto

O consumidor `executar_circuito_enterprise_01` não foi ligado: está
na versão de `registro_analise_service.py` de `c9a17fd1` e a sua
transposição cega também substituiria o escritor de análise XML
compartilhado com outras verticais, sem prova de isolamento de MEI.
Esta é uma fronteira **não autorizada** nesta missão. É possível
testar módulos isolados e reconstruir evidências, mas **não é possível
declarar B03/B04 integrados fim a fim** sem solucionar essa fronteira
por decisão de arquitetura específica de Miguel.

A exigência não é apenas chamar uma função adicional: I2 lê o
`_enterprise_xml_evidence` de dentro do resultado **já selado** do
relatório e exige o mesmo `documento_id`, hash XML, empresa e dono.
O escritor atual de `main` não acrescenta esse vínculo. Portanto,
apenas copiar `executar_circuito_enterprise_01` e invocar o escritor
atual **falharia fechado** em `I2_NO_BOUND_DOCUMENT` (inferência
direta dos contratos, ainda sem teste real integrado).

| Caminho arquitetural | Consequência | Decisão nesta missão |
| --- | --- | --- |
| Importar inteiro o escritor antigo de `c9a17fd1` | Altera resultado/produtor e tratamento de duplicatas da função chamada por `app/main.py`, rotas de relatório e jobs | **Proibido** pela fronteira de MEI/compartilhamento sem ratificação própria |
| Criar entrada dedicada/opt-in exclusivamente Enterprise, com vínculo documental atómico e identidades seladas, reutilizando o escritor sem mudar fluxos legados | Exige desenho, testes de não regressão e prova de isolamento; viabilidade ainda não comprovada | **Proposta para decisão de Miguel**, não implementar automaticamente |
| Só conservar módulos com testes isolados | Preserva código e rastreio, mas não recupera execução fim a fim | **Estado de preparação atual**, não conclusão B03/B04 |

**Catraca reforçada para este risco:** o gate diferencial agora exige
exatamente os **25 node IDs** presentes na origem de B01 (12), B03 (7)
e B04 (6), com todos a passar no candidato; a lista rígida foi cotejada
contra o AST dos três testes recuperados (`25 == 25`, zero extras ou
ausências). Sem o teste completo de ligação B01, a catraca retorna
`ENTERPRISE_WIRING_TESTS_MISSING`/`...NOT_PASSED`, mesmo que os módulos
isolados e todas as outras provas passem. Isto impede que uma simples
cópia de ficheiros seja aceite como integração funcional. O teste B01
foi restaurado **intacto** de `c9a17fd1`, mas ainda não passa contra a
`main` porque a função consumidora não existe nela. Não se alterou
o escritor partilhado para fazer passar esse teste.

**Estado após esta preparação:** `GLOBAL_GREEN=false`;
`ENTERPRISE_RECOVERY_STATUS=BLOCKED` (suite global do candidato ainda
não executada, falta fonte original do teste G12 e decisão de integração
do consumidor partilhado). **ZERO commits, ZERO pushes, ZERO merges,
ZERO deploys.** A Fase 0 de mapeamento B06 ainda não foi reaberta.
