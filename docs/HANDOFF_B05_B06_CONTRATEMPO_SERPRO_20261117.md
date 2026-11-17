# SOLVERIS Enterprise -- HANDOFF DE CONTINUACAO (contratempo SERPRO)

Data: 2026-11-17
Motivo: contratempo na compra/contratacao da SERPRO Consulta CNPJ (em resolucao
por Miguel, fora desta sessao). Esta sessao foi encerrada e outra Claude
continua. Este documento substitui qualquer reconstrucao de memoria -- leia
isto primeiro, antes de perguntar a Miguel o que ja esta aqui escrito.

## 1. Seguranca e disciplina -- regras permanentes (nao negociaveis)

- PowerShell: sempre ';', nunca '&&'.
- PowerShell Set-Content/-replace nunca usados para editar markdown em
  producao (risco de corrupcao UTF-8) -- usar script Python com validacao
  explicita de padrao e raise SystemExit se o padrao nao for encontrado.
  (Nota: esta sessao usou Set-Content -Encoding utf8 para criar varios
  docs/*.md novos e funcionou sem corrupcao observada -- mas a regra
  continua valida como norma; nao confiar na sorte em arquivos grandes ou
  editados em lugar.)
- Heredoc PowerShell para gerar um .py, depois python ficheiro.py -- nunca
  heredoc em pipe para stdin do python (mangla acentos para '?' antes do
  Python ver). Dentro do .py gerado, nao escrever acentos crus em literais
  de string gravados em ficheiro de producao -- usar escapes unicode
  quando necessario.
- Todo ficheiro escrito em disco usa [IO.File]::WriteAllBytes() ou
  equivalente para garantir LF sem conversao CRLF, quando o objetivo e
  producao; para docs/relatorios este handoff usa Python com io.open
  (encoding utf-8, newline LF) e validacao de padrao antes de escrever.
- Nunca commitar sem suite verde. Nunca misturar duas intencoes num commit
  (1 commit = 1 intencao). Nunca investigar depois de construir -- sempre
  investigar antes ("PRIMEIRO SE INVESTIGA, DEPOIS SE CONSTROI").
- SOLVERIS e soberana: nada pode ser construido para depender de um revisor
  humano terceiro, nem de uma autoridade externa de confianca, para o seu
  funcionamento operacional. Miguel e a unica autoridade ratificadora.
- Toda correcao de arquitetura, todo achado, toda decisao fica escrita no
  repositorio (docs/), nunca so na conversa -- para que esta sessao ou
  qualquer futura a consulte antes de repetir o mesmo erro.
- git branch --show-current antes de QUALQUER commit no worktree
  partilhado -- licao desta sessao: um commit ja chegou a pousar no branch
  errado por o worktree ter mudado de branch sem o script verificar primeiro.
- Antes de aceitar como resolvido algo que outro agente (GPT) reportou,
  verificar por leitura direta do codigo real sempre que a decisao for
  consequente -- nesta sessao, uma afirmacao apressada ("CNAE basta", "API
  gratuita e instantanea") foi corrigida depois de outro GPT investigar mais
  a fundo e de inspecao direta do codigo confirmar a correcao.
- Ao escrever uma missao para o GPT investigativo, declarar explicitamente
  se consulta a e-mail da SOLVERIS esta dentro ou fora do escopo -- o GPT
  tem acesso confirmado a repositorio GitHub E a e-mail da SOLVERIS (nao so
  ao repositorio, como se presumia antes nesta sessao).

## 2. Estado git exato

- Branch de trabalho: main
- Commit atual no origin/main (confirmado por fetch direto ao GitHub nesta
  sessao, nao por memoria): deea5fbb16241f7c23731f8e69fd65a64f44e776
  ("docs(fase4): corrige achado - CNAE->categoria e API de CNPJ nao estao
  resolvidos, sao decisao/contratacao pendente")
- Worktree de trabalho do Miguel: C:\dev\saas-fiscal-demo-a1 -- e um git
  worktree de C:\dev\saas-fiscal-demo (o git-common-dir real e
  C:\dev\saas-fiscal-demo\.git; hooks git ficam la, nao dentro do
  worktree). Varias sessoes/agentes podem estar noutros branches no MESMO
  git-common-dir -- sempre confirmar o branch atual antes de commitar.
- PENDENCIA DE ESTADO (verificar antes de assumir): um script para criar e
  commitar docs/FASE4_GPT_CAPACIDADES_CONFIRMADAS_20261116.md foi dado ao
  Miguel nesta sessao, mas a confirmacao de execucao NUNCA chegou de volta
  antes do contratempo da SERPRO interromper o fluxo. Verificar com
  git log --oneline -- docs/FASE4_GPT_CAPACIDADES_CONFIRMADAS_20261116.md
  -- se vazio, o ficheiro nao existe em main, e o conteudo (declarar que o
  GPT tem acesso a email) so existe nesta conversa e neste handoff.
- ACHADO NOVO DESTA SESSAO, NUNCA ANTES REGISTADO EM LUGAR NENHUM: dois
  trabalhos que a memoria registava como "entregues e validados por Miguel"
  NUNCA FORAM MERGEADOS para main -- continuam isolados nos seus proprios
  branches, a frente de main por 1 commit cada:
  - origin/fix/atomicidade-insights-commit -- commit 912cb309 ("fix:
    adia commits de inteligencia ate finalizacao atomica da analise XML")
  - origin/integracao-inteligencia-i0 -- commit 3f20b271 ("docs: registra
    cinco capturas I0 e seis produtores ainda pendentes")
  Confirmado por git log origin/main..origin/<branch> --oneline nesta
  sessao -- nao e suposicao. Isto bloqueia parte do trabalho paralelo
  "antes de B06" ficar realmente disponivel em main. Decidir com Miguel se
  faz merge agora ou se ha razao para terem ficado isolados.

## 3. Roteiro B00-B11 (Diagnostico Fiscal Empresarial Integral -- primeira
## prateleira da SOLVERIS Enterprise)

B00 (mapa e autoridade), B01 (circuito fiscal), B02 (prova normativa,
RCV31-R3), B03 (comparacao monetaria PA/22021000) e B04 (integracao
ponta-a-ponta dos motores, ponte ICMS-ST ligada ao consumidor real via
G13) estao FECHADOS.

B05 (validacao fiscal com caso real empresa_id=4/NCM 22021000/UF PA) esta
EM CURSO -- ver secao 4. B06-B11 NAO INICIADOS:
- B06: relatorio Enterprise integral (PDF)
- B07: contrato e oferta comercial
- B08: interface Enterprise (jornada completa)
- B09: pagamento e liberacao
- B10: homologacao em producao
- B11: piloto empresarial e abertura comercial

Regra para B04-B11: reutilizar primeiro, integrar em seguida, construir
apenas a lacuna demonstrada, validar no mundo real. Atencao transversal
exigida por Miguel: Reforma Tributaria 2027 (extincao PIS/COFINS, entrada
da CBS) deve ser considerada ao longo de B04-B11.

## 4. Estado exato de B05 -- checklist vivo

Fonte canonica (NAO reescrever de memoria -- ler o ficheiro real a cada
retomada): docs/FASE4_B05_CHECKLIST_FECHO_SEM_RESSALVA.md

Resumo do estado dos 9 itens (ver o ficheiro para o detalhe e as
referencias):
1. Dependencia de revisor humano -- RESOLVIDO (removida)
2. Natureza da assinatura digital do ato soberano -- RESOLVIDO (chave
   propria de Miguel, sem certificadora externa)
3. Como o motor consome a autoridade promovida -- RESOLVIDO (I1-I5
   ratificado)
4. Infraestrutura Postgres segregada persistente -- PENDENTE, decisao nao
   pedida ainda
5. Servico do escritor ADR-020 -- PENDENTE, implementacao nao iniciada
6. Cadeia de ativacao + protecao 0035/0036 como codigo -- PENDENTE,
   implementacao nao iniciada
7. CEST/categoria do remetente -- REFRAMED, parcialmente resolvido (ver
   abaixo, e o CONTRATEMPO ATUAL esta aqui)
8. Preflight Postgres descartavel (Docker) -- PENDENTE, nao iniciado
9. Teste ponta-a-ponta com empresa_id=4 -- PENDENTE, depende de 4-8

### Item 7 -- onde parou exatamente, por ordem de sequencia (Miguel pediu
### "atacamos por ordem de sequencia")

Achado normativo FECHADO (nao reabrir sem novo motivo): o decreto PA ja
custodiado sob ADR-020 (DOE_PA_20230307_EXTRA_35315.pdf, Decreto
2.931/2023, Apendice I do Anexo I do RICMS-PA, item 9.1, CEST 03.010.01,
NCM 2202.10.00/2202.99.00, "Refrigerante em embalagem pet") tem MVA DUPLA
por categoria do remetente:
  - Industrial, Importador, Arrematante e Engarrafador: 140%
  - Distribuidor, Deposito e Estabelecimento Atacadista: 40%
O seed de teste (app/scripts/seed_mva.py) usa 40% fixo, sem jamais
declarar que assume a categoria atacadista -- risco de erro de quase 100
pontos percentuais se o remetente real de um caso for industrial. O motor
(app/services/tabela_normativa_service.py::buscar_mva) nao tem nenhum
parametro de categoria/CNAE/CNPJ -- confirmado por leitura direta do
codigo nesta sessao, nao por relato de terceiro. TabelaMVA
(app/models.py:1299-1319) tambem nao tem coluna de CEST nem de
categoria. DocumentoFiscal.cnpj_emitente (app/models.py:1258) ja
existe e ja captura o CNPJ do remetente real quando ha nota de entrada.
Ver docs/FASE4_B05_ACHADO_CATEGORIA_REMETENTE_MVA_DUPLA_20261116.md
(versao ja corrigida -- a primeira versao tinha duas afirmacoes
apressadas, corrigidas no mesmo dia).

Tres pendencias, EM ORDEM DE SEQUENCIA (Miguel decidiu atacar assim):

  (1) CONTRATACAO SERPRO CONSULTA CNPJ -- EM RESOLUCAO, E O CONTRATEMPO
      ATUAL. Contrato SERPRO ja existente da SOLVERIS: numero 302046,
      produto "Integra Contador", CNPJ contratante 68.573.368/0001-82 --
      esse contrato NAO inclui Consulta CNPJ (produto diferente da
      SERPRO; o unico produto SERPRO que a SOLVERIS tem hoje em codigo e
      o PGMEI, geracao de DAS do MEI, ver app/services/serpro_pgmei_client.py,
      _SUPPORTED_SERVICES = {GERARDASPDF21, GERARDASCODBARRA22}
      -- confirmado por leitura direta do codigo, nao e consulta de
      CNAE). Produto a contratar: Consulta CNPJ, modalidade BASICA
      (ja inclui cnaePrincipal + cnaeSecundarias, nao precisa da
      modalidade Empresa/QSA), menor faixa de volume (1 a 999
      consultas/mes, ~R$0,6591/consulta -- preco de referencia, nao
      cotacao oficial confirmada). Pergunta pendente na SERPRO (Gestao
      Contratual -> Contrato - Renovacao/Aditivo/Reajuste): o contrato
      302046 pode receber Consulta CNPJ por aditivo, ou precisa de
      contratacao nova? Pode reusar o e-CNPJ A1 e o cadastro/login
      existentes do PGMEI, mas a Consumer Key/Secret provavelmente sera
      separada (nao confirmado). NAO contratar Consulta Empresa/QSA/CPF/
      CND nem Consulta NF-e nesta fase -- nenhum bloqueio real
      demonstrado para eles ainda. Miguel esta a resolver este
      contratempo fora desta sessao; esta e a UNICA coisa que bloqueia
      o passo 2 abaixo.

  (2) MAPEAMENTO CNAE -> CATEGORIA, decisao soberana a ratificar --
      AINDA NAO FEITA. Nem o Decreto 2.931/2023 nem o Convenio ICMS
      142/2018 estabelecem uma tabela CNAE->categoria para o item 9.1
      especificamente -- confirmado por investigacao de outro GPT,
      verificada. Existe classificacao CNAE/CONCLA generica (1122-4/01
      fabricacao = industria; 4635-4/02 comercio atacadista; 4635-4/03
      atacadista COM engarrafamento associado -- este ultimo e AMBIGUO,
      porque "engarrafador" e "atacadista" sao colunas diferentes no
      decreto). O proprio Fisco usa CNAE como criterio primario em
      litigio real (Conselho de Contribuintes de MG, acordao 22.396/17),
      mas isso nao e uma regra escrita que a SOLVERIS possa copiar sem
      declarar a propria interpretacao. ACAO PENDENTE: Miguel precisa de
      ratificar explicitamente qual mapeamento CNAE->categoria a
      SOLVERIS adota para este segmento, incluindo como tratar o caso
      ambiguo do 4635-4/03, e isso tem de ir para o repositorio como
      decisao soberana documentada -- nao e um fato legal automatico.

  (3) IMPLEMENTACAO DO BRANCH NO MOTOR -- NAO INICIADA, depende de (1)
      e (2). O motor de calculo tem VARIOS pontos de leitura de MVA, nao
      um so (confirmado por outro GPT, verificado parcialmente):
      tabela_normativa_service.py::buscar_mva e o seletor central, mas
      motor_predicao_tributaria.py, fiscal_utils.py, st_service.py,
      xml_service.py, motor_fiscal.py, simulador_st.py e varios
      pontos de insights_engine.py tambem consomem MVA, alguns com
      fallback para app/data/mva.json estatico. Mapear todos esses
      pontos antes de desenhar o branch de categoria -- nao assumir que
      corrigir buscar_mva sozinho basta.

## 5. Trabalho paralelo antes de B06 -- ver ACHADO NOVO na secao 2

Dois trabalhos (atomicidade do escritor de insights; captura de 5 das 11
capacidades de inteligencia para o catalogo I0) foram feitos por GPT,
testados e validados por Miguel segundo a memoria desta linha de trabalho
-- MAS NUNCA MERGEADOS PARA MAIN (ver secao 2). Antes de B06 realmente
poder usar essas capacidades no relatorio PDF, alguem precisa de decidir
com Miguel se faz o merge desses dois branches para main agora, e so
depois fazer o merge, com suite verde e catraca anti-duplicacao, 1 commit
por trabalho (nunca misturar os dois). Ver
docs/TRABALHO_PARALELO_INTELIGENCIA_E_ATOMICIDADE.md (existe nos
branches fix/atomicidade-insights-commit e integracao-inteligencia-i0,
NAO existe em main -- ler a partir de um desses branches, nao do main).

Capacidades de inteligencia ja capturadas (5 de 11): score_tributario,
maturidade, ranking_restituicao, ranking_estrategico, impacto_financeiro.
Ainda sem produtor canonico ligado: radar, benchmark, projecao_recuperacao
(e mais 3 nao detalhadas no doc consultado nesta sessao -- ler o doc
completo no branch antes de continuar esse trabalho).

## 6. O que JA PODE avancar em B06 sem esperar a resolucao da SERPRO

B06 e o relatorio Enterprise integral em PDF. O bloqueio do item 7 de B05
(SERPRO + mapeamento CNAE + branch no motor) afeta SO o calculo de ICMS-ST
para operacoes que caem na combinacao exata PA/NCM 22021000/CEST 03.010.01
(e, por extensao de principio, qualquer outra combinacao NCM/UF que tenha
a mesma MVA dupla por categoria -- ainda nao levantada para outros casos).
Isto NAO bloqueia:

- Estrutura, template e layout do relatorio PDF em si (usar o skill de pdf
  deste ambiente quando for a vez de montar o documento).
- Integracao de todas as outras capacidades do catalogo I0 ja prontas e
  fechadas em B00-B04 (a maioria do catalogo de 52 capacidades nao toca em
  MVA por categoria de remetente).
- As 5 capacidades de inteligencia ja capturadas no trabalho paralelo
  (depois do merge para main, ver secao 5) -- score_tributario, maturidade,
  ranking_restituicao, ranking_estrategico, impacto_financeiro.
- Qualquer secao do relatorio que nao dependa de ICMS-ST com MVA por
  categoria de remetente ambigua (PIS/COFINS, IRPJ/CSLL, outras secoes do
  diagnostico).

O que NAO deve avancar, e deve ficar marcado explicitamente no relatorio
em vez de mostrar um numero silencioso: qualquer celula/secao que exiba o
valor de ICMS-ST calculado para a combinacao PA/22021000/CEST 03.010.01 (ou
qualquer outra com MVA dupla por categoria ainda nao resolvida) sem a
categoria do remetente confirmada -- deve aparecer como "nao apurado -
pendente categoria do remetente", nunca um valor assumindo atacadista em
silencio. Isto e o mesmo principio de fail-closed usado no resto do
projeto.

## 7. Proximo passo imediato quando a sessao retomar

Perguntar a Miguel se o contratempo da SERPRO ja foi resolvido. Se sim,
confirmar a resposta exata que a SERPRO deu (aditivo ou contrato novo,
credenciais separadas ou nao) antes de prosseguir para o passo (2) da
secao 4 (ratificacao do mapeamento CNAE->categoria). Se nao, avancar
diretamente para o trabalho de B06 descrito na secao 6, e decidir com
Miguel se vale a pena resolver primeiro o merge pendente da secao 5.
