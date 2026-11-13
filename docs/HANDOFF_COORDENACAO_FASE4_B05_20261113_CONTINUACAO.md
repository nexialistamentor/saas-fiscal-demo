# HANDOFF — Continuação da coordenação (GPT Fase 4 "Cobertura Nacional de Jurisdições" + visão geral B05)

Data: 2026-11-13
Sessão anterior: Claude (esta sessão, papel de coordenação da Fase 4 do GPT + overseeing geral do B05)
Destinatário: a próxima sessão Claude que assumir este papel

## 0. Leia isto antes de tudo

Este documento existe porque, mesmo com toda a disciplina descrita abaixo, já tivemos DOIS incidentes reais nesta mesma sessão em que as coisas derivaram para o erro apesar das regras estarem todas em vigor. Não assuma que "ter as regras" é proteção suficiente. A proteção real é: verificar o estado real a cada passo, nunca confiar em relato (seu, do GPT, ou de outra sessão Claude) sem ver o output literal colado pelo Miguel. Os dois incidentes estão descritos na secção 4 — leia-os com atenção, porque o padrão deles provavelmente vai repetir-se de alguma forma.

## 1. Quem é Miguel e como ele trabalha

- Miguel é o fundador e arquiteto soberano de duas plataformas: Fisco Soberano (SaaS fiscal para PMEs brasileiras, repo nexialistamentor/saas-fiscal-demo) e Cartório Digital Soberano L2 (infraestrutura notarial soberana, repo separado).
- Miguel corre TODOS os comandos PowerShell ele mesmo e cola o resultado de volta. Esta sessão Claude NUNCA tem acesso direto à máquina dele. Nunca peça para ele "editar um ficheiro" manualmente nem sugira abrir um editor — ele já não usa Cursor (desde 2026-10-27). O único método seguro de editar ficheiros é gerar um script (PowerShell here-string ou Python heredoc) para ele correr.
- Miguel tem autoridade de ratificação final sobre toda decisão de arquitetura. Nunca se escreve código de uma decisão de arquitetura sem ratificação explícita dele primeiro.
- Repo: nexialistamentor/saas-fiscal-demo. Worktree local: C:\dev\saas-fiscal-demo-a1. Git-common-dir: C:\dev\saas-fiscal-demo\.git (ou seja, este é um worktree de um repo que tem outro worktree em paralelo — pode haver mais sessões a operar no mesmo git-common-dir).

## 2. Disciplina de engenharia padrão (não negociável, repetida ao longo de toda a sessão)

1. Nunca inventar ou aproximar dado legal/fiscal. Fail-closed sempre: dado em falta ou não comprovado = abster-se, nunca aproximar.
2. Nunca confiar no relato do GPT (nem de outra sessão Claude) sobre resultado de teste. Sempre pedir o comando exato e ver o output colado literal.
3. Uma branch por intenção. Nunca misturar.
4. Suite de teste ALVO (não a pasta tests/ inteira) + catraca anti-duplicação (tools/check_duplicacao.py + docs/REGISTRO_CANONICO.json) antes de cada commit. A suite alvo = os ficheiros de teste que tocam direta ou indiretamente a mudança feita. Só se amplia para suite larga quando a mudança toca algo genuinamente compartilhado (app/database.py, models.py, rotas, motor de projeção enterprise). A pasta tests/ inteira tem 3 ficheiros com erro de coleta PRÉ-EXISTENTE e NÃO relacionados com este trabalho — não tentar corrigi-los nem entrar em pânico com eles, só excluir com --ignore se precisar rodar a suite inteira por algum outro motivo:
   - tests/test_b02_documentary_signer_v2.py — erro de sintaxe real no ficheiro (parêntese incompatível)
   - tests/test_enterprise_g111_legacy_pdf_signature_audit.py — falta o módulo asn1crypto no venv
   - tests/test_enterprise_g12_st_item_readonly.py — falta o ficheiro g1_reference_engine.py no disco
5. Nunca fazer merge para main nem deploy sem instrução explícita do Miguel.
6. Nunca aplicar um patch sem revisar o texto literal completo primeiro. Proibido ZIP, proibido script externo não revisto.
7. Verificar o estado real do código/branch via git grep ou mostrar_corpo_funcao.py antes de assumir qualquer coisa sobre código já existente.
8. Edição de ficheiro = sempre via script (PowerShell here-string literal com Test-Path guard, ou Python heredoc com contagem obrigatória old.count(new)!=1 -> raise SystemExit antes de escrever). Nunca pedir edição manual.
9. Cuidado com mojibake: caracteres acentuados (ã, ê, á, ç) corrompem-se às vezes ao colar através do heredoc/terminal. Preferir texto ASCII-puro em qualquer trecho de patch que toque uma linha com acento, ou confirmar o texto real do ficheiro primeiro.
10. O catálogo _CAPACIDADES em app/services/enterprise_integral_projection.py é INTOCÁVEL por qualquer missão GPT ou trabalho paralelo. Também fora de alcance sem instrução explícita: contratos G12-G17, B04, Postgres de produção.
11. Toda mensagem de commit termina com:
    Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01BHr8cqPQGHh7N575fxDYzY
    (confirme o URL de sessão atual com o próprio sistema no momento — pode mudar entre sessões).
12. Handoff escrito e detalhado em português sempre que o trabalho passa de uma sessão para outra, explicitando todas as salvaguardas mantidas até aqui.

## 3. Estado do roteiro geral (SOLVERIS Enterprise / Diagnóstico Fiscal Empresarial Integral)

12 blocos B00-B11. B00, B01, B02, B03 fechados. B04 (integração do motor ICMS-ST G12/G13 na cadeia de projeção integral I0-I1-I2) fechado — ver docs/B04_FECHAMENTO.md. B05 ("validação fiscal com casos reais") é o bloco corrente, dividido em duas frentes paralelas que se cruzam:

### 3a. Frente GPT — "Cobertura Nacional de Jurisdições" (camada de jurisdições federal/estadual/municipal, para o SOLVERIS Enterprise/Fisco Soberano cobrir todo o território, não só PR/PA)

- Fase 1 (PA, mecanismo genérico de seleção de regra por jurisdição, baseado em TabelaMVA): fechada. Função selecionar_norma_por_jurisdicao em app/services/jurisdicao_normativa_service.py.
- Fase 2 (fonte legal real para PA/22021000): fechada. Ver docs/SOLVERIS_FASE2_PA_FECHO_FINAL_20261112.md — citações legais completas (Decreto 2.588/2022, Decreto 2.931/2023, RICMS/PA art. 20 IV, Lei 5.530/1989 art. 12 IV), achado da alíquota de 21%.
- Fase 3 (uf_operacao obrigatório, sem fallback para empresa.uf — achado de que 0/80 empresas cadastradas têm uf preenchida): fechada, commit fd3cf371. Testes atualizados no mesmo ficheiro tests/test_jurisdicao_normativa_fase1_pa.py (não há ficheiro separado de Fase 3 — está tudo neste único ficheiro de teste).
- Fase 4 ("cotejo documental" ADR-020 para a combinação condicional PA/22021000):
  - Etapa 1/2: cotejar_candidato_pa_entrada em app/services/pa_entrada_ruleversion_service.py, commit 726d130a, 12 testes em tests/test_pa_entrada_ruleversion_service.py. Lê a cadeia hash-verificada RuleVersion->ExtractionResult->NormativeArtifact (ADR-020), exige CEST+categoria_remetente+tipo_operacao explícitos do chamador, compara só a subchave pa_entrada_22021000_v1 (não o dict inteiro, seguindo o padrão já usado em cotejar_vinculo_normativo_b02 do B02), nunca autoriza cálculo.
  - Etapa 3, Tarefa A: FECHADA E APLICADA. Adaptador read-only cotejar_item_pa_entrada em app/services/pa_entrada_cotejo_adapter.py, hardcoded ao único caso ratificado (PA, NCM 22021000, CEST 0301001, remetente distribuidor_deposito_atacadista), nunca autoriza cálculo, não infere nenhuma dimensão. Commit 8e8b72c8 na branch cobertura-nacional-jurisdicoes-fase4-cest-remetente (branch base: 726d130a). PUSH JÁ FEITO para origin. Validação antes do commit: 32/32 testes isolados do adaptador + 52/52 na suite combinada (adaptador + ruleversion service + jurisdição fase1/pa) + catraca limpa.
  - Etapa 3, Tarefa B: EM INVESTIGAÇÃO, NÃO IMPLEMENTADA. Escopo ratificado pelo Miguel: preparar SÓ a combinação candidata (CEST 03.010.01, remetente distribuidor-atacadista, versões V1=2022 e V2=2023) — as outras 7 combinações possíveis (4 CEST x 2 categorias de remetente) ficam fora de qualquer trabalho nesta etapa, sem modelo, sem subchave, sem antecipação de formato. Dois requisitos têm de fechar ANTES de qualquer escrita em NormativeArtifact/ExtractionResult/RuleVersion:
    1. Hash SHA-256 real e custodiado do PDF fonte. STATUS: RESOLVIDO. O GPT localizou as edições originais do Diário Oficial do Estado do Pará no portal IOEPA (DOE nº 35.096 de 30/08/2022 para o Decreto 2.588/2022; DOE nº 35.315 edição extra de 07/03/2023 para o Decreto 2.931/2023) e o Miguel correu, na própria máquina dele, um script PowerShell que baixou os dois PDFs para %LOCALAPPDATA%\SOLVERIS\Fase4\CustodiaPendente\, verificou o cabeçalho %PDF-, e gravou um manifesto com hash real:
       - DOE_PA_20220830_35096.pdf — SHA256 3BD54AA6A6B28D3F94D3FF0957A3F6BD0935F5B07FDA08DFD97E192E7268543A — 3282334 bytes
       - DOE_PA_20230307_EXTRA_35315.pdf — SHA256 C3F75D50C23912BFDDD43195A03C9DBD2DC61FE34D02311628EF3DBA1849CC9A — 4701089 bytes
       - manifesto em %LOCALAPPDATA%\SOLVERIS\Fase4\CustodiaPendente\manifesto_sha256.json
       RESSALVA: este hash vem de um único download, numa única máquina. Antes de tratar como prova final e imutável de um NormativeArtifact, vale confirmar de forma independente (segundo download, ou checksum publicado pela própria IOEPA se existir). Não é bloqueante para a investigação, mas não deve ser tratado como definitivo sem essa segunda confirmação.
    2. Escritor ADR-020 operacional fora do B02. STATUS: NÃO RESOLVIDO. O GPT investigou e confirmou: stage_completion (em app/services/enterprise_b02_noncredential_acquisition.py) exige explicitamente a base solveris_b02_r4g_test e o utilizador solveris_b02_writer — não é reutilizável diretamente em test.db. A cadeia completa (NormativeArtifact -> ExtractionResult -> RuleVersion) exige execuções concluídas e vínculos exatos, não é só inserir três objetos isolados. tests/test_adr020_integrated_pipeline.py demonstra contratos com objetos simulados, mas não é um escritor operacional. PRÓXIMO PASSO (ainda não enviado ao GPT no momento deste handoff): mandar o GPT estudar e PROPOR (não implementar) o desenho de um escritor ADR-020 fora do B02 — que tabelas/sessão precisaria, que garantias de isolamento do B02 manteria, se é um serviço novo ou uma extensão controlada de algo existente. Só depois de proposta revista e ratificada é que se escreve qualquer código.

### 3b. Frente outra sessão Claude — recriação do Issue #31 + continuação de dados reais do B05

- Issue #31: app/services/motor_predicao_tributaria.py::prever_impacto_st chamava buscar_mva diretamente, contornando a guarda de fonte_legal. O GPT corrigiu isto, mas a primeira tentativa de commit (190efdeb2465db3208e720dcb38352d8fc39681a) foi feita numa branch criada a partir de um main desatualizado (sem a catraca anti-duplicação) — teve de ser recriada numa branch correta.
- Coordenação combinada nesta frente: docs/COORDENACAO_B05_FASE4_20261113.md — instrução exata para a outra sessão Claude: git cherry-pick 190efdeb2465db3208e720dcb38352d8fc39681a sobre um main fresco (já com a catraca corrigida, ver secção 4.1), depois continuar o trabalho de validação com dados reais de produção do B05.
- STATUS DESTA FRENTE NO MOMENTO DESTE HANDOFF: não confirmado nesta sessão se a outra sessão Claude já completou o cherry-pick e o fechamento do Issue #31. Primeira ação da próxima sessão: verificar isso antes de assumir qualquer coisa.

## 4. Incidentes reais — leia com atenção, aconteceram APESAR da disciplina da secção 2

### 4.1 Catraca anti-duplicação fail-open (RESOLVIDO)

tools/check_duplicacao.py e docs/REGISTRO_CANONICO.json foram criados no B03 (commit a31ee81b) mas NUNCA tinham sido trazidos para main. Qualquer branch nova criada a partir de main nascia sem a catraca. O hook de pre-commit (githooks/pre-commit, copiado para .git/hooks/pre-commit) falhava ABERTO quando os ficheiros não existiam — ou seja, o commit passava sem nenhuma verificação de duplicação, com apenas um aviso textual fácil de ignorar. Foi assim que o commit 190efdeb (Issue #31, outra sessão Claude) passou sem nenhuma verificação real.

Correção estrutural: os dois ficheiros foram trazidos para main (commit cd579473). O hook foi reescrito para falhar FECHADO quando os ficheiros não existem (exit 1 com instrução de diagnóstico, commits 15310aab + 33f787c2 — houve um erro no meio em que o primeiro commit de teste capturou a versão antiga do hook por causa de um git add feito antes da edição; corrigido com um segundo commit). O incidente está documentado em ALERTA_CATRACA_ANTIDUPLICACAO.md na raiz do repo. A correção foi testada ao vivo: removendo os ficheiros deliberadamente e confirmando que o commit era bloqueado.

LIÇÃO PARA A PRÓXIMA SESSÃO: antes do PRIMEIRO commit em qualquer branch nova (sua, do GPT, ou de qualquer sessão Claude), confirme com:
Test-Path tools\check_duplicacao.py
Test-Path docs\REGISTRO_CANONICO.json
Os dois têm de devolver True. Não assuma — confirme.

### 4.2 Linha PA/22021000 desaparecida do test.db físico (RESOLVIDO MAS COM CAUSA RAIZ NÃO 100% CONFIRMADA)

A linha PA/22021000 na tabela tabela_mva do test.db físico (C:\dev\saas-fiscal-demo-a1\test.db), semeada manualmente via python -m app.scripts.seed_mva horas antes, desapareceu entre checkpoints desta mesma sessão sem qualquer alteração de código. Isto causou 4 falhas em tests/test_jurisdicao_normativa_fase1_pa.py que tinham passado momentos antes (126/126, 128/128, 140/140 em checkpoints anteriores).

Investigação feita (nesta ordem, cada passo com comando real colado pelo Miguel, nunca assumido):
1. Confirmado que o fixture db() deste ficheiro de teste é local (não vem de conftest.py) e abre o test.db físico em MODO SOMENTE LEITURA (sqlite3 URI mode=ro) — o próprio ficheiro de teste nunca escreve nada. Ou seja, não é bug do teste.
2. git grep em toda a pasta tests/ e app/ por "create_all", "drop_all" e "test.db" — todos os outros ficheiros de teste que recriam schema usam engines ISOLADOS (sqlite:///:memory: ou ficheiro temporário com DATABASE_URL próprio). Nenhum teste deste repositório, além da leitura read-only da Fase 1/PA, toca no test.db físico.
3. Conclusão: a causa é EXTERNA a este repositório/suite de testes. A hipótese mais provável (não confirmada com certeza absoluta) é que outra sessão Claude ou o GPT (via ponte Codex), operando no MESMO worktree físico (C:\dev\saas-fiscal-demo-a1) na mesma máquina, correu algo (reset de schema, migração, recriação de ambiente) que apagou a tabela/linha sem deixar rasto no git, porque test.db não é versionado.

Correção: python -m app.scripts.seed_mva de novo, confirmado via query direta antes de voltar a rodar os testes.

LIÇÃO PARA A PRÓXIMA SESSÃO: test.db físico é ESTADO VOLÁTIL COMPARTILHADO entre sessões de IA concorrentes na mesma máquina. NUNCA assuma que uma linha semeada numa sessão anterior ainda está lá. Antes de rodar qualquer teste de jurisdição/pa_entrada, ou antes de qualquer commit da Fase 4, reseed + verificação da linha é passo OBRIGATÓRIO de checklist, não uma suposição. Comando de verificação real que funciona no PowerShell deste ambiente (evita o erro de aspas que ocorreu da primeira vez que tentámos):
python -c "import sqlite3; c = sqlite3.connect(\"test.db\"); rows = c.execute(\"SELECT estado, ncm, mva, aliquota_interna, vigencia_inicio, nivel_confianca_fonte, fonte_legal FROM tabela_mva WHERE estado=? AND ncm=?\", (\"PA\", \"22021000\")).fetchall(); print(rows)"
Deve devolver exatamente [('PA', '22021000', 40.0, 0.18, '2024-01-01', 'oficial', None)].

## 5. Pendências abertas no momento deste handoff

- Enviar ao GPT a missão de investigação (não implementação) do requisito 2 da Tarefa B: desenho de um escritor ADR-020 operacional fora do B02. Ainda não foi enviada.
- Confirmar com a outra sessão Claude o estado real da recriação do Issue #31 e da continuação de dados reais do B05 (ver docs/COORDENACAO_B05_FASE4_20261113.md).
- Rotação de credenciais — flagged múltiplas vezes nesta sessão, NUNCA executada: a credencial Postgres do Railway (que apareceu em texto simples no chat) e INLABS_PASS + cookies INLABS (idem) precisam ser rotacionadas. Recomendado também correr Clear-History no PowerShell local do Miguel.
- Confirmação independente (segundo download/checksum) dos dois hashes SHA-256 do requisito 1 da Tarefa B, antes de tratá-los como prova definitiva num NormativeArtifact.
- Eventualmente fechar B05 com um caso real validado (empresa_id=4, NCM 22021000, PA) assim que o trabalho de registo ADR-020 da Tarefa B avançar.
- Eventualmente avançar para B06 (relatório Enterprise PDF) depois do trabalho de integração de "inteligência" (atomicidade já corrigida, commit 912cb309) avançar mais.

## 6. Branches relevantes (confirme sempre com git branch -a e git log --oneline -3 antes de assumir qualquer head)

- main — cd579473 (catraca trazida) + 33f787c2 (hook fail-closed corrigido) + 1067b5f1 (ALERTA_CATRACA_ANTIDUPLICACAO.md)
- cobertura-nacional-jurisdicoes-fase4-cest-remetente — 8e8b72c8 (Tarefa A aplicada e com push feito), base 726d130a
- cobertura-nacional-jurisdicoes-fase3-uf-operacao — fd3cf371 (Fase 3 fechada)
- cobertura-nacional-jurisdicoes-fase2-fonte-pa — d407dc2e (Fase 2 fechada, cherry-pick)
- fix/atomicidade-insights-commit — 912cb309 (correção de atomicidade do InsightEngine)
- branch da outra sessão Claude para o Issue #31 — nome não confirmado nesta sessão; ver docs/COORDENACAO_B05_FASE4_20261113.md para a instrução original dada a ela

## 7. Como confirmar que leu isto corretamente antes de agir

Antes do primeiro comando que escrever para o Miguel rodar, confirme pelo menos:
git status
git branch --show-current
git log --oneline -5
Test-Path tools\check_duplicacao.py
Test-Path docs\REGISTRO_CANONICO.json
Nunca assuma que o estado descrito neste documento ainda é o estado real — ele pode já ter mudado desde que foi escrito, inclusive pelas mesmas razões descritas na secção 4.2.
