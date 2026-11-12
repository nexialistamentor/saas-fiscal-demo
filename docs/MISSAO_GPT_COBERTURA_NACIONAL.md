# MISSAO GPT -- Cobertura Nacional de Jurisdicoes, FASE 1 (mecanismo generico, prova com PA)

Terceiro trabalho paralelo do GPT, distinto dos outros dois ja em curso
(`docs/TRABALHO_PARALELO_INTELIGENCIA_E_ATOMICIDADE.md`). Nao misturar
os tres entre si. Ler este documento por inteiro, do inicio ao fim,
ANTES de tocar em qualquer ficheiro ou propor qualquer desenho.

## Limite estrito desta missao -- ler isto primeiro, e so depois o resto

Esta missao tem UM objetivo, e nenhum outro: construir um mecanismo de
selecao de norma fiscal POR JURISDICAO (generico, nao hardcoded para
uma UF), e prova-lo funcionando com UMA UNICA UF real -- Para (PA),
que ja tem dado confirmado nesta base de codigo desde B03 (UF=PA,
NCM=22021000).

NAO FAZ PARTE DESTA MISSAO, EM NENHUMA CIRCUNSTANCIA:
- Adquirir, extrair ou processar dados de qualquer outra UF (incluindo
  Parana/PR). Os dados de PR pertencem ao caso B02, que usa um
  mecanismo diferente (cadeia politica->decisao->ativacao->assinatura),
  que Miguel decidiu explicitamente EVITAR a partir de B03 em diante.
  Tocar nisso nesta missao reabriria um bloco fechado sem autorizacao.
- Declarar, sugerir, ou escrever em qualquer commit, documento ou
  comentario que "cobertura nacional" ou "todo o Brasil" foi alcancado,
  iniciado de forma ampla, ou esta mais proximo de o ser. Isto e Fase 1
  de UMA UF. Nada alem disso.
- Propor, desenhar ou esbocar uma Fase 2, Fase 3, um roteiro de
  expansao para outras UFs, uma ordem de prioridade entre estados, ou
  qualquer plano de como isto cresceria no futuro. Se achar que isso e
  necessario ou util, PARAR e escrever a sugestao, isolada, no final do
  documento de estado (ver secao de entrega) -- nunca comecar a
  construir, nunca assumir que esta autorizado a avancar so por ter
  tido a ideia.
- Criar qualquer processo, convencao, ciclo de aprovacao, "politica"
  no sentido de regra de governanca (NAO confundir com o schema de
  dados `policy`/`scope`/`domain` ja existente no B02, que pode e deve
  ser REUTILIZADO), checklist obrigatorio, ou qualquer outro mecanismo
  novo que vincule como trabalho futuro devera ser feito. Esta missao
  entrega CODIGO e TESTES para uma UF, nao um processo para todas.
- Inventar nomes de UFs, NCMs, aliquotas, valores de MVA, ou qualquer
  dado fiscal que nao esteja comprovado por leitura real da base de
  dados ou de uma fonte ja citada no historico deste projeto. Se nao
  encontrar o dado, PARAR e reportar "dado nao encontrado", nunca
  simular, estimar ou aproximar.

Se, a qualquer momento, parecer que o trabalho exige tocar em algo da
lista acima, o GPT para e pede ratificacao explicita antes de
continuar -- nao decide sozinho que "faz sentido" alargar o escopo.

## Contexto -- ler antes de desenhar qualquer coisa

- B03 confirmou, por leitura real desta mesma base SQLite local
  (`test.db`), exatamente UMA regra normativa: UF=PA, NCM=22021000.
  Usar essa UF e essa regra como o unico caso real desta missao.
- B02 (Parana) e um caso de validacao fechado, com mecanismo proprio
  (politica->decisao->ativacao->assinatura). Nao e o limite do produto,
  mas tambem nao e material desta missao -- ver acima.
- Estruturas ja existentes, reutilizaveis (confirmar por leitura real
  antes de assumir que existem com esse nome exato -- `git grep`
  primeiro, `mostrar_corpo_funcao.py` depois):
  - `app/models.py`: empresas tem colunas `uf`, `municipio`,
    `regime_tributario`.
  - Schema de politicas B02/G5 ja tem `scope`, `domain`,
    `policy_version`, `policy_hash`, `declared_material_applicability`
    -- estrutura de DADOS generica e reutilizavel. Usar este schema
    para representar a jurisdicao de uma norma, NAO inventar um schema
    paralelo novo.
  - Possivelmente existentes, NAO confirmados nesta sessao:
    `NormativeArtifact`, `ExtractionResult`/`extraction_runs`,
    `RuleVersion`. Confirmar com `git grep` antes de qualquer desenho
    que dependa deles.

## O que esta missao constroi, exatamente

1. **Camada de jurisdicao generica**: cada norma indica esfera
   (federal/estadual/municipal), territorio (UF/municipio), fonte
   oficial, vigencia, materia regulada -- usando o schema `scope`/
   `domain` ja existente, nao um novo. O mecanismo de LEITURA dessa
   informacao deve ser generico (le a UF da empresa, procura a norma
   certa dinamicamente) -- nao deve conter nenhum `if uf == "PA"`
   hardcoded. A generalidade do CODIGO e o entregavel; o numero de
   UFs com DADO real continua sendo uma (PA).
2. **Guarda de aplicabilidade fail-closed**: quando a UF pedida nao
   tem norma verificada, o sistema responde "cobertura normativa nao
   comprovada" -- nunca inventa, nunca reaproveita a norma de outra UF.
   Mesmo padrao fail-closed ja usado em toda a cadeia I0-I1-I2-G12-G13
   (ver `enterprise_b04_icms_st_integral_bridge.py` como referencia de
   ESTILO de codigo, nao para editar esse ficheiro).
3. **Teste que prova isolamento, mesmo com uma UF so**: simular uma
   empresa de UF=PA (com a norma real) e uma empresa de UF diferente
   SEM norma cadastrada (ex. SP, SC, qualquer UF sem dado) -- confirmar
   que a empresa PA recebe a norma certa, e a outra recebe
   explicitamente "cobertura normativa nao comprovada", nunca a norma
   de PA por engano nem um calculo inventado.

## REGRAS QUE NAO PODEM SER QUEBRADAS

1. Branch proprio: `cobertura-nacional-jurisdicoes-fase1-pa`. Nao
   misturar com `fix/atomicidade-insights-commit`,
   `integracao-inteligencia-i0`, nem com o branch B04/B05 do Claude.
2. NAO mexer em `_CAPACIDADES`, G12-G17, nem na ponte B04
   (`enterprise_b04_icms_st_integral_bridge.py`). Decisao ja tomada e
   revertida uma vez por ser errada -- nao reabrir essa discussao.
3. NAO tentar resolver ou tocar o acesso ao PostgreSQL de producao
   (Railway). Bloqueio separado, do lado do Claude/B05. Usar SQLite
   local (`test.db`) para todos os testes desta missao.
4. NAO tocar no caso B02 (Parana) nem no seu mecanismo de
   politica->decisao->ativacao->assinatura, por nenhum motivo.
5. Qualquer decisao de nome de schema, formato de `domain`, ou
   qualquer outra decisao de arquitetura precisa de ratificacao
   explicita de Miguel antes do commit. Nao presumir aprovacao por
   estar neste documento.
6. `git grep` e `mostrar_corpo_funcao.py` antes de assumir que algo
   existe, tem esse nome, ou faz o que o nome sugere. Nomes que nao
   batem com o conteudo real ja causaram erros concretos em B03 e B04
   nesta mesma base de codigo -- nao repetir.
7. Suite relevante + catraca anti-duplicacao
   (`python tools\check_duplicacao.py --repo
   C:\dev\saas-fiscal-demo-a1 --registro docs\REGISTRO_CANONICO.json`)
   antes de qualquer commit.
8. Um commit, uma intencao -- nao misturar schema + guarda + teste no
   mesmo commit se forem passos logicos separados.
9. Nunca merge para `main`. Nunca deploy.
10. Nenhuma frase do tipo "isto prepara o terreno para as outras 26
    UFs", "proximo passo natural seria...", ou qualquer formulacao que
    sugira continuidade automatica, deve aparecer em commits, no
    documento de entrega, ou em qualquer comunicacao desta missao.
    Se o GPT achar que ha algo a dizer sobre isso, essa opiniao fica
    de fora de tudo -- o documento de entrega descreve SO o que foi
    feito e testado com PA, nada mais.

## Entrega

Documento `docs/COBERTURA_NACIONAL_FASE1_PA_ESTADO_<data>.md` descrevendo
exatamente o que foi construido e testado para PA, sem qualquer mencao
a planos futuros, outras UFs, ou cobertura nacional como conceito
alcancado ou em curso. Se o GPT identificar algo relevante para uma
eventual Fase 2, essa observacao fica FORA deste documento de entrega
-- comunicar separadamente e aguardar decisao, nunca incluir como parte
do que foi "feito".
