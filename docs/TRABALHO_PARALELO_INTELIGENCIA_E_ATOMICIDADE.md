# TRABALHO PARALELO -- Atomicidade do escritor + Integracao de Inteligencia ao I0

Este documento define DOIS trabalhos, para serem feitos EM PARALELO ao B05
(que o Claude continua), por outra sessao/agente (GPT). Leia por inteiro
antes de tocar em qualquer ficheiro. Ver `docs/B04_FECHAMENTO.md` primeiro
para o contexto de onde isto surgiu.

## REGRAS QUE NAO PODEM SER QUEBRADAS (ler antes de tudo)

1. Isto NAO e "B4A", nem "parte de B04", nem "parte de B05". Sao DOIS
   trabalhos com nome proprio, cada um no SEU PROPRIO branch, cada um com
   o SEU PROPRIO commit, nunca misturados entre si nem com B04 nem com B05.
2. NAO mexer em `_CAPACIDADES` (`app/services/enterprise_integral_
   projection.py`). Essa alteracao ja foi tentada, quebrou um teste
   canonico, foi revertida. Decisao ratificada, nao reabrir essa discussao.
3. NAO mexer em G12, G13, G14, G15, G16, G17, nem na ponte B04
   (`enterprise_b04_icms_st_integral_bridge.py`). Esses ficheiros sao do
   escopo de B04 (fechado) e da pendencia "dedupe G13 via G14/G17"
   (documentada, separada, NAO e este trabalho).
4. NAO redesenhar a arquitetura L3 inteira, nao propor um orquestrador
   novo, nao criar camadas novas de contrato. O pedido aqui e cirurgico:
   corrigir um ponto de atomicidade e capturar dados ja calculados que
   hoje sao descartados. Nada mais.
5. Antes de escrever qualquer linha: ler o corpo real das funcoes
   envolvidas com a ferramenta do projeto
   (`python tools\mostrar_corpo_funcao.py --ficheiro <X> --funcao <Y>`),
   nunca assumir pelo nome. `git grep` antes de assumir que algo nao existe
   ou nao e chamado em lado nenhum.
6. Rodar a suite de testes relevante ANTES e DEPOIS de cada mudanca, e a
   catraca anti-duplicacao (`python tools\check_duplicacao.py --repo
   C:\dev\saas-fiscal-demo-a1 --registro docs\REGISTRO_CANONICO.json`)
   antes de qualquer commit. Nunca commitar com suite vermelha.
7. Um commit, uma intencao. Nao misturar o trabalho 1 e o trabalho 2 no
   mesmo commit, mesmo estando no mesmo documento.
8. Qualquer decisao de arquitetura (nao so de bug fix) precisa de
   ratificacao explicita de Miguel antes do commit -- nao presumir
   aprovacao so por estar neste documento.

## TRABALHO 1 -- Atomicidade do escritor (prioridade: urgente, correcao de defeito real)

**Branch sugerido**: `fix/atomicidade-insights-commit`

**O problema, confirmado no codigo**: dentro de
`app/services/insights_engine.py::InsightEngine.gerar_insights_empresa`,
ha um `self.db.commit()` perto do fim da funcao -- ANTES de
`app/services/registro_analise_service.py::executar_e_registrar_analise_
xml` (que chama `gerar_insights_empresa` dentro de um `try/except
Exception` que so loga e segue) terminar os seus proprios passos finais:
calculo do score global (linha ~221), `finalizar_registro_analise`, e a
selagem do resultado via `selar_resultado_nao_mei`. Se qualquer coisa
falhar DEPOIS desse commit interno, fica um estado parcialmente persistido
-- `Insight`, `EngineResultado`, `InteligenciaSnapshot` ja gravados -- de
uma analise que pode nao fechar com sucesso (ou fechar com
`status="erro"`), sem que isso seja revertido.

**O que investigar antes de decidir a correcao**:
- Ler o corpo completo de `executar_e_registrar_analise_xml` E de
  `gerar_insights_empresa` (ja parcialmente lido nesta sessao -- conferir
  se mudou).
- Confirmar se `self.db` dentro de `InsightEngine` e a MESMA sessao
  SQLAlchemy que `executar_e_registrar_analise_xml` usa, ou uma sessao
  separada. Isto muda a solucao: se for a mesma sessao, o commit interno
  pode simplesmente ser removido (o commit final do fluxo ja cobre tudo);
  se for sessao separada, precisa de outra abordagem (ex.: so persistir
  via outbox/flag apos confirmacao do fluxo principal).
- Escrever um teste que reproduza o cenario de falha (simular excecao
  depois do commit interno, antes do commit final) e comprove que, apos a
  correcao, nao fica dado orfao persistido.

**Criterio de fechamento**: teste novo passa, suite inteira de
`registro_analise_service`/`insights_engine`/testes de circuito (os 120
ja verificados no B04) continua verde, catraca OK.

## TRABALHO 2 -- Integracao de inteligencia ao catalogo I0 (prioridade: antes de B06, nao antes de B05)

**Branch sugerido**: `integracao-inteligencia-i0` (fora da sequencia
numerada B00-B11 -- isto e uma area de trabalho propria, como
`cobertura-nacional-jurisdicoes`, nao um bloco do roteiro)

**O problema, confirmado no codigo**: 16 produtores do grupo `inteligencia`
no catalogo `_CAPACIDADES` (score_tributario, ranking_restituicao,
ranking_estrategico, projecao_recuperacao, impacto_financeiro, anomalias,
eficiencia, complexidade, maturidade, benchmark, radar, etc.) tem ficheiro
e funcao reais (confirmado via `app/routers/inteligencia_router.py` e
`app/services/insights_engine.py`), a maioria ja chamada dentro de
`InsightEngine.gerar_insights_empresa` -- mas os resultados completos sao
DESCARTADOS antes de chegar a `compor_resultado_empresarial`/I0. So
sobrevivem fragmentos (`oportunidades`, `creditos_detectados`,
`risco_tributario`, que ja estao `snapshot` no catalogo). Score,
maturidade, ranking_estrategico, impacto_financeiro, radar, distorcoes,
restituicao sao calculados e descartados sem chegar ao `return` de
`gerar_insights_empresa`.

**Diferenca importante em relacao ao padrao de B04 (G13)**: em B04, o
motor ja produzia um resultado completo pronto a reutilizar (so faltava
ligar). Aqui, o resultado rico e descartado ANTES de sair da funcao que o
calcula -- isto e captura de dado, nao so reutilizacao de chamada. Nao
tratar como o mesmo tipo de trabalho que B04.

**O que fazer, por ordem**:
1. Para cada um dos 16 produtores, confirmar com
   `mostrar_corpo_funcao.py` a assinatura e o formato real do dict
   devolvido (nao assumir pelo nome -- ja houve erro nesta sessao por
   assumir isso).
2. Decidir, PRODUTOR A PRODUTOR, se e capturado dentro de
   `gerar_insights_empresa` (a maioria) ou so no router HTTP isolado
   (confirmar quais). Os do router isolado podem exigir uma decisao
   arquitetural diferente (chamar dentro do fluxo principal pela primeira
   vez, o que muda o raio de risco) -- isso precisa de ratificacao
   explicita antes de codigo.
3. Para os que ja sao calculados dentro de `gerar_insights_empresa`:
   alterar o `return` dessa funcao (e o dict `resultado_persistido`) para
   incluir os dicts completos hoje descartados, SEM remover nada do que
   ja e devolvido.
4. Mapear cada um dos 16 ao `id` certo na entrada correspondente de
   `_CAPACIDADES` (ja existem no catalogo, com `produtor_ou_chave`
   declarado) -- construir a ponte (nova funcao, padrao similar a
   `enterprise_b04_icms_st_integral_bridge.py` mas para este grupo) que
   funde esses resultados no I0, com o MESMO padrao de quarentena:
   nunca `autoridade_fiscal=True` para metricas estatisticas (score e
   combinacao ponderada, nao prova fiscal).
5. Testes de contrato novos, um por capacidade ligada, seguindo o padrao
   ja usado em `test_enterprise_b04_icms_st_integral_bridge.py`.

**Criterio de fechamento**: todas as 16 capacidades (ou as que se provarem
viaveis -- documentar as que ficarem de fora e porque) deixam de estar
`pendente` sem inventar nada, suite inteira verde, catraca OK. Isto deve
estar fechado ANTES de B06 (relatorio Enterprise PDF) comecar, porque B06
vai precisar de mostrar estas capacidades no relatorio comercial.

## O que NAO esta neste documento

Dedupe de G13 via G14/G17 -- documentado separadamente em
`docs/HANDOFF_PROXIMA_SESSAO.md`, NAO faz parte deste trabalho paralelo.
