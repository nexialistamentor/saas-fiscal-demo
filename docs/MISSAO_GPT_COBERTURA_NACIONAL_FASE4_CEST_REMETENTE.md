# MISSAO GPT -- Cobertura Nacional de Jurisdicoes, FASE 4 (CEST/remetente, decisao de arquitetura + implementacao)

Sexto trabalho paralelo do GPT. Continuacao do objetivo de negocio que a
Fase 2 deixou em aberto (ver docs/SOLVERIS_FASE2_PA_FECHO_FINAL_20261112.md,
secao 6: "decisao de arquitetura adiada"). Ler esse documento por inteiro,
e este documento por inteiro, ANTES de tocar em qualquer ficheiro.

## Objetivo final desta missao

PA/NCM 22021000 passa a ter `fonte_legal` preenchida de forma correta
(distinguindo CEST e condicao do remetente), e o mecanismo de selecao
de norma (`selecionar_norma_por_jurisdicao`, ja corrigido na Fase 3)
passa a devolver `NORMA_VERIFICADA`/`calculo_autorizado=True` para o
caso real que a combinacao CEST+remetente autorizar -- nunca para o
registo generico UF+NCM sozinho.

## ESTRUTURA DESTA MISSAO: DUAS ETAPAS SEPARADAS, SEM PULAR A PRIMEIRA

Esta missao tem DUAS etapas distintas. A Etapa 2 NAO comeca enquanto a
Etapa 1 nao tiver sido reportada e ratificada explicitamente por
Miguel. Isto nao e opcional nem um detalhe -- e a condicao que evita
que uma decisao de schema de producao seja tomada as pressas.

### ETAPA 1 -- Decisao de arquitetura (so proposta, zero implementacao)

Decidir, com justificacao escrita, qual das duas vias seguir:

**Via A -- Estender `TabelaMVA`:** acrescentar colunas
(`cest`, `categoria_remetente`, `tipo_operacao`, `aliquota_interestadual`)
a tabela ja existente e ligada ao motor (`buscar_mva`,
`resolver_aliquota_e_mva`, `selecionar_norma_por_jurisdicao`).
Vantagem: menor distancia do codigo ja funcional. Risco: pode nao
caber bem o modelo de proveniencia documental (hash, vigencia por
ato normativo especifico) que `RuleVersion` ja tem.

**Via B -- Ligar `RuleVersion`/ADR-020 ao motor fiscal:** usar a
estrutura ja existente (`normative_artifacts`, `extraction_runs`,
`extraction_results`, `rule_versions`), mas criar o PRIMEIRO consumidor
operacional dela (hoje nao tem nenhum, so testes -- ver Fase 2).
Vantagem: proveniencia documental ja pronta (hash, vigencia, evidencias).
Risco: maior distancia do codigo atual, maior area de mudanca, maior
tempo.

Para decidir, confirmar por leitura real (nao assumir):
1. `git grep` por todos os usos de `TabelaMVA`/`buscar_mva` fora de
   testes -- confirmar o raio de impacto real de mudar o schema.
2. Ler o corpo completo de `cotejar_vinculo_normativo_b02` e do
   contrato `operacao='saida_interna'` mencionado no fecho da Fase 2 --
   confirmar se d? para generalizar esse contrato para "antecipacao na
   entrada" sem quebrar o que ja existe, ou se precisa de um contrato
   novo e paralelo.
3. Verificar se ha migracoes Alembic recentes tocando `TabelaMVA` ou
   `RuleVersion` que sugiram uma direcao ja em curso no projeto.

Reportar a recomendacao (via A ou via B), com os pr?s/contras
confirmados por leitura real, e PARAR. Nao escrever schema, migracao
ou codigo nenhum nesta etapa.

### ETAPA 2 -- Implementacao (so apos ratificacao explicita da Etapa 1)

So comeca depois de Miguel confirmar qual via seguir. O escopo exato
desta etapa sera definido na propria ratificacao (pode incluir
migracao, povoamento da linha PA/22021000 real, e testes) -- nao
presumir o escopo agora.

## REGRA ABSOLUTA, SEM EXCECAO: nao inventar nem aproximar dado normativo

- MVA, aliquota, CEST, categoria de remetente: todos ja confirmados
  pela Fase 2 (ver documento de fecho). Usar exatamente esses valores,
  citando a mesma fonte (Decreto 2.588/2022, Decreto 2.931/2023,
  Decreto 73/2019, Lei 5.530/1989). Nao reinterpretar nem arredondar.
- Se durante a Etapa 2 surgir qualquer ambiguidade nao coberta pela
  Fase 2 (ex.: qual CEST se aplica ao caso real de `empresa_id=4`,
  que a Fase 2 ja disse nao poder confirmar), PARAR e reportar --
  nunca escolher um CEST a palpite.
- Nunca promover `categoria_remetente` desconhecida a um valor padrao.
  Remetente desconhecido = fail-closed, igual a fonte_legal ausente.

## REGRAS QUE NAO PODEM SER QUEBRADAS

1. Branch proprio: `cobertura-nacional-jurisdicoes-fase4-cest-remetente`,
   criado a partir de `cobertura-nacional-jurisdicoes-fase3-uf-operacao`
   (precisa da correcao de `uf_operacao` ja feita la). Nao misturar
   com os branches da Fase 1, 2 ou 3, nem com nenhum outro trabalho em
   curso (atomicidade, inteligencia, B04, B05).
2. NAO tocar no acesso Postgres de producao -- exclusivo do lado
   Claude/B05. Trabalhar so com `test.db` local.
3. NAO tocar em `_CAPACIDADES`, G12-G17, ponte B04. NAO reabrir a
   decisao de G13/G14/G17 dedupe (trabalho separado, ja documentado).
4. NAO expandir para outras UFs, NCMs, ou categorias de produto alem
   de refrigerantes/NCM 22021000 em PA.
5. NAO declarar "cobertura nacional avancou" ou qualquer formulacao
   equivalente. O documento de entrega fala so sobre PA/22021000.
6. Qualquer patch neste repositorio deve ser aplicado por um script
   Python com validacao explicita (padrao ja usado em todas as fases
   anteriores: `count != 1 -> SystemExit` antes de escrever qualquer
   ficheiro) -- nunca editar as cegas, nunca assumir que um texto
   existe sem o confirmar por leitura real primeiro.
7. NAO entregar pacotes ZIP, scripts externos pre-compilados, nem
   pedir para correr `git apply` de um patch nao revisto em texto
   simples antes. Todo patch deve ser mostrado em texto (diff ou
   trecho de codigo) ANTES de qualquer aplicacao, para revisao linha a
   linha -- isto ja causou um incidente de confianca nesta mesma frente
   de trabalho (Fase 3) e nao deve repetir-se.
8. Suite relevante (incluindo os testes ja existentes de Fase 1 e 3)
   + catraca anti-duplicacao antes de qualquer commit.
9. Nunca merge para `main`. Nunca deploy. Nunca escrever em producao.
10. Se a Etapa 1 concluir que nenhuma das duas vias (A ou B) e viavel
    num prazo razoavel, ou que falta mais informacao, isso e um
    resultado valido -- reportar e parar, nao forcar uma escolha so
    para ter algo para implementar.

## Entrega esperada

- Etapa 1: documento `docs/COBERTURA_NACIONAL_FASE4_DECISAO_ARQUITETURA_<data>.md`
  com a recomendacao (via A ou via B), os pr?s/contras confirmados por
  leitura real, e a pergunta explicita de ratificacao para Miguel.
- Etapa 2 (so apos ratificacao): implementacao conforme o escopo
  definido na ratificacao, com testes e documento de estado final.
