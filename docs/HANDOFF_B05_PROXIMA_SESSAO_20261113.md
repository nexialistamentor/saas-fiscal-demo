# HANDOFF B05 -- para a proxima sessao continuar

Escrito pela sessao Claude de 2026-11-13, para a proxima sessao (Claude ou
GPT) continuar exatamente de onde parou. Ler por inteiro antes de tocar em
qualquer ficheiro, comando ou credencial.

## Onde estamos agora

B04 esta fechado (ver docs/B04_FECHAMENTO.md). B05 ("validacao fiscal com
casos reais") foi iniciado nesta sessao e abriu uma frente de trabalho
paralela gigante de cobertura nacional de jurisdicoes, feita pelo GPT em
varias fases, enquanto o Claude trabalhou diretamente no acesso a producao
e no mapeamento de dados reais.

**Nenhum merge para main foi feito em nenhum branch. Nenhum deploy.**

## B05 -- o que foi feito e descoberto

### Acesso ao Postgres de producao restabelecido

A DATABASE_URL real (Railway, projeto "disciplined-alignment", servico
Postgres) estava corrompida no .env partilhado (C:\dev\saas-fiscal-demo\.env)
e no proprio painel do Railway -- a variavel DATABASE_PUBLIC_URL la
devolvia um valor que nao e uma URL. Isso nunca foi corrigido no .env
partilhado (decisao deliberada, para nao escrever sem validar primeiro).

**Como contornar, se precisar de novo:**

```powershell
railway variables --service Postgres --kv
```

Isto devolve PGHOST=postgres.railway.internal (so funciona DE DENTRO da
rede Railway, nao do seu PC) -- para aceder de fora, usar antes
RAILWAY_TCP_PROXY_DOMAIN e RAILWAY_TCP_PROXY_PORT (tambem devolvidos pelo
mesmo comando). Montar a URL manualmente com esses dois mais
PGUSER/PGPASSWORD/PGDATABASE (todos vindos do mesmo comando `railway
variables`), nunca usar DATABASE_PUBLIC_URL nem o .env partilhado como
estao hoje -- ambos invalidos.

**ATENCAO DE SEGURANCA:** a password do Postgres real ja apareceu em texto
simples varias vezes nesta sessao (historico do terminal, respostas do
assistente). Recomendado, como prioridade imediata: trocar a password no
painel do Railway e atualizar o .env partilhado so depois de validar a
nova ligacao, e rodar `Clear-History` no PowerShell local. Este documento
nao contem a credencial -- buscar sempre via `railway variables` no
momento de uso.

## Dados reais confirmados em producao (read-only, nenhuma escrita feita)

- 80 empresas, 35 documentos fiscais, 0 regras normativas (tabela_mva
  vazia), 0 regras em tabela_pmpf.
- 0 de 80 empresas tem o campo uf preenchido -- mesmo as 46 que tem cnpj
  preenchido. Isto e sistemico, nao um caso isolado.
- Em contrapartida, documentos_fiscais.uf_emit/uf_dest ESTAO preenchidos
  em varios documentos reais: 5 NCMs distintos, 2 UFs (PA e SP)
  confirmados:
  - NCM 22021000, uf_emit=PA, 6 itens (empresa_id=4)
  - NCM 39199090, uf_emit=PA, 7 itens
  - NCM 70072100, uf_emit=PA, 7 itens
  - NCM 85129000, uf_emit=PA, 14 itens
  - NCM 22030000, uf_emit=SP/uf_dest=SP, 11 itens
- empresa_id=4 (o unico caso real mais investigado) tem cadastro quase
  vazio: sem CNPJ, sem regime_tributario, sem UF -- so optante_mei=False.
  Isto bloqueia qualquer tentativa de inferir categoria do remetente para
  este caso real.
- Tabelas confirmadas existentes em producao, relevantes para arquitetura
  futura: normative_artifacts, extraction_runs, extraction_results,
  rule_versions (cadeia ADR-020) -- existem, tem schema rico, mas NAO tem
  consumidor operacional real ainda, so testes.

## O que falta para B05 fechar de facto

B05 nao esta fechado -- nenhum caso real foi validado ponta-a-ponta com
sucesso (autoridade normativa comprovada + calculo autorizado), porque:

- Nenhuma regra normativa real esta cadastrada em producao.
- empresas.uf nunca e preenchida (Fase 3 ja corrigiu o MECANISMO para nao
  depender disso, mas ainda falta o DADO real nalgum caso).
- A unica regra que existe (PA/22021000, mva=40%, aliquota=18%) esta no
  test.db LOCAL, restaurada manualmente nesta sessao a partir de
  app/scripts/seed_mva.py -- NAO esta em producao, e a Fase 2 descobriu
  que os valores dela estao incompletos/parcialmente errados (ver abaixo).

**Proximo passo sugerido para B05:** escolher UM caso real (ex.:
empresa_id=4, NCM 22021000, uf_emit=PA, que ja tem tudo confirmado exceto
a norma) e acompanhar o fecho dele usando o que a Fase 4 esta a
construir -- sem inventar dado nenhum, so ligando o que ja existe.

## Trabalho paralelo do GPT -- quatro frentes, todas documentadas

Regra geral seguida em todas: cada frente tem o seu PROPRIO branch, nunca
misturado com outro; cada decisao de arquitetura exige ratificacao
explicita ANTES do codigo; nenhum patch e aplicado sem ser mostrado em
texto completo (nunca ZIP nem script externo) e revisto linha a linha;
suite + catraca antes de cada commit; nunca merge, nunca deploy.

### 1. Atomicidade do escritor -- FECHADO

Branch `fix/atomicidade-insights-commit`, commit 912cb309. Corrigiu o
`db.commit()` prematuro dentro de `InsightEngine.gerar_insights_empresa`
que ocorria antes de `executar_e_registrar_analise_xml` terminar os seus
proprios passos finais. Validado por Claude: 125/125 testes, catraca OK.
Ressalva documentada: nao prova atomicidade INTEGRAL da ingestao XML.

### 2. Integracao de inteligencia ao I0 -- PARCIAL, fechado nesse escopo

Branch `integracao-inteligencia-i0`, commits 145a807b/3f20b271. Capturou 5
das 11 capacidades inteligencia pendentes (score_tributario, maturidade,
ranking_restituicao, ranking_estrategico, impacto_financeiro). Validado
por Claude: 134/134 testes, catraca OK. Ficam de fora:
anomalias/eficiencia/complexidade e radar/benchmark/projecao_recuperacao.

**Achado critico, documentado como Issue #31 no GitHub, NAO corrigido:**
`app/services/motor_predicao_tributaria.py::prever_impacto_st` chama
`buscar_mva` DIRETAMENTE, sem passar pela guarda de fonte_legal. Ja esta
em producao (cadeia: executar_e_registrar_analise_xml -> InsightEngine ->
prever_impacto_st -> buscar_mva -> Insight persistido). Risco de
seguranca de dado real, aberto.

### 3-6. Cobertura nacional de jurisdicoes -- quatro fases, parcialmente fechado

**Fase 1** (`cobertura-nacional-jurisdicoes-fase1-pa`, commit f868f21e) --
FECHADA, validada (126/126 testes). Construiu
`app/services/jurisdicao_normativa_service.py::selecionar_norma_por_jurisdicao`,
mecanismo generico de selecao de norma por UF/NCM/data.

**Fase 2** (`cobertura-nacional-jurisdicoes-fase2-fonte-pa`, commits
0be47671 + d407dc2e) -- FECHADA como investigacao, mas o OBJETIVO DE
NEGOCIO (PA calcular com autoridade) continua por alcancar. Achados:

- Aliquota real de ICMS para refrigerantes em PA e 21%, nao 18% (seed)
  nem 19% (aliquota geral) -- RICMS/PA art. 20, IV, e Lei 5.530/1989 art.
  12, IV.
- MVA de 40%/NCM 22021000 so se aplica a CEST especificos
  (03.010.00/01/02) E remetente distribuidor/deposito/atacadista
  (Decreto 2.588/2022). Remetente industrial/importador/arrematante/
  engarrafador tem MVA de 140%.
- UF+NCM sozinhos sao chave normativa insuficiente.
- Para empresa_id=4, nao e possivel confirmar a condicao do remetente.
- Decisao de arquitetura adiada para a Fase 4: TabelaMVA tem muitos
  consumidores que nao respeitam guarda de fonte legal; RuleVersion/
  ADR-020 nao tem consumidor operacional real.

Documento completo: `docs/SOLVERIS_FASE2_PA_FECHO_FINAL_20261112.md`.

**Fase 3** (`cobertura-nacional-jurisdicoes-fase3-uf-operacao`, commit
fd3cf371) -- FECHADA, validada (128/128 testes). Corrigiu
`selecionar_norma_por_jurisdicao` para exigir `uf_operacao: str` sempre
explicita do chamador, removendo o fallback para `empresa.uf`.

**Fase 4** (`cobertura-nacional-jurisdicoes-fase4-cest-remetente`, commit
726d130a) -- EM CURSO. Etapa 1 (decisao de arquitetura) ratificada: Via B,
integrar RuleVersion/ADR-020 via consumidor novo e segregado. Etapa 2
(implementacao) PARCIAL: criado e testado
`app/services/pa_entrada_ruleversion_service.py::cotejar_candidato_pa_entrada`
(12/12 testes, suite ampla 140/140, catraca OK) -- le a cadeia
RuleVersion->ExtractionResult->NormativeArtifact, nunca declara mais do
que CANDIDATO_CONDICIONAL_COTEJADO_SEM_AUTORIDADE.

**Falta para a Fase 4 fechar:** (1) este cotejo ainda nao esta ligado a
nada; (2) nao existe registo real de RuleVersion para PA/22021000, so
simulados nos testes; (3) Issue #31 continua aberta.

## Regras de seguranca mantidas a sessao inteira -- nao relaxar

- Um branch por intencao, nunca misturar (ja houve um deslize corrigido
  com cherry-pick+reset --hard).
- Nunca aplicar patch ou pacote ZIP sem ver o texto completo primeiro.
- Nunca confiar em texto colado sem verificar integridade (quebras de
  linha, truncagem).
- Nunca editar um ficheiro sem o ler primeiro com
  `mostrar_corpo_funcao.py`.
- `git grep` real do Windows, nunca so busca do GitHub.
- Nunca escrever em .env partilhado ou producao sem validar primeiro.
- Nunca inventar, aproximar ou inferir dado fiscal/normativo -- parar e
  reportar "nao comprovado".
- Suite relevante + catraca anti-duplicacao antes de todo commit, sem
  excecao.
- Nunca merge para main, nunca deploy.
- Decisoes de arquitetura sempre aguardam ratificacao explicita antes do
  codigo.

## Proximos passos sugeridos, por ordem de prioridade

1. Trocar a credencial exposta do Postgres (e INLABS_PASS/cookies) e
   corrigir o .env partilhado -- isto subiu de prioridade nesta sessao
   porque a password voltou a aparecer em texto simples depois deste
   handoff ter sido redigido.
2. Resolver a Issue #31 (`prever_impacto_st` sem guarda de fonte legal).
3. Continuar a Fase 4: decidir onde ligar
   `cotejar_candidato_pa_entrada`, e criar o registo real de RuleVersion
   para PA.
4. Fechar B05 com o caso real empresa_id=4/NCM 22021000/PA.
5. So depois, avancar para B06 (relatorio Enterprise PDF).
