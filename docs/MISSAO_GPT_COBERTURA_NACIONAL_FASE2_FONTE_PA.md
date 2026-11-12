# MISSAO GPT -- Cobertura Nacional de Jurisdicoes, FASE 2 (fonte legal real de PA)

Quarto trabalho paralelo do GPT. Continuacao directa da Fase 1
(`docs/MISSAO_GPT_COBERTURA_NACIONAL.md`, branch
`cobertura-nacional-jurisdicoes-fase1-pa`, ja fechada e validada). Ler
este documento por inteiro antes de tocar em qualquer ficheiro.

## O que esta missao e, e o que NAO e

Esta missao NAO constroi mecanismo novo. O mecanismo generico de
selecao por jurisdicao (`app/services/jurisdicao_normativa_service.py`)
ja existe, esta correto, e nao deve ser alterado na sua logica de
guarda -- so pode precisar de pequenos ajustes se a fonte real exigir
(ex. formato de `url_fonte`).

O UNICO objetivo desta missao: encontrar a fonte legal REAL (portaria,
decreto ou ato normativo da SEFAZ/PA) que fundamenta MVA=40% para
NCM 22021000 em PA, e preencher `fonte_legal` (e `url_fonte`, se
disponivel) na linha ja existente da tabela `tabela_mva` (estado=PA,
ncm=22021000) em `test.db`. So depois disso o mecanismo generico passa
a devolver `NORMA_VERIFICADA`/`calculo_autorizado=True` para PA -- sem
que a logica do codigo precise de mudar, so o dado.

## REGRA ABSOLUTA, SEM EXCECAO: nao inventar nem aproximar a fonte

- A fonte legal tem de ser um ato normativo REAL, verificavel, com
  numero, orgao emissor e, se possivel, URL para o Diario Oficial do
  Estado do Para ou para o portal da SEFAZ/PA.
- Se apos pesquisa nao for encontrada uma fonte com confianca
  suficiente, a missao PARA e reporta "fonte nao encontrada com
  confianca suficiente" -- nunca preenche `fonte_legal` com um numero
  de portaria adivinhado, aproximado, ou extrapolado de padroes de
  outras UFs.
- NUNCA usar o nivel_confianca_fonte="oficial" ja existente na linha
  como evidencia de que a fonte existe -- esse campo ja foi
  identificado na Fase 1 como um indicador insuficiente sozinho. A
  prova exigida aqui e mais forte: o ato normativo real, citavel.
- Antes de escrever qualquer coisa em `test.db`, reportar a fonte
  encontrada (numero do ato, orgao, data, e se possivel um link) para
  Miguel confirmar/ratificar -- nunca escrever no banco sem essa
  confirmacao. Esta e a MESMA licao que ja causou um incidente nesta
  sessao com o ficheiro `.env` partilhado: nunca escrever dado nao
  validado num ficheiro ou banco que outros trabalhos dependem.

## Onde procurar (sugestoes, nao exaustivo)

- Portal da SEFAZ/PA (legislacao tributaria, substituicao tributaria,
  bebidas/refrigerantes NCM 2202).
- Diario Oficial do Estado do Para (IOEPA).
- Pesquisa pelo proprio NCM 22021000 + "MVA" + "Para" + "substituicao
  tributaria" em fontes juridicas confiaveis (nao blogs ou agregadores
  nao oficiais).
- Verificar tambem se ha convenio ICMS ou protocolo interestadual que
  fundamente esse MVA para PA, que pode ser a fonte real em vez de uma
  portaria estadual isolada.

## REGRAS QUE NAO PODEM SER QUEBRADAS

1. Branch proprio: `cobertura-nacional-jurisdicoes-fase2-fonte-pa`,
   criado a partir de `cobertura-nacional-jurisdicoes-fase1-pa`. Nao
   misturar com nenhum outro branch em curso.
2. NAO mexer em `_CAPACIDADES`, G12-G17, nem na ponte B04. NAO tocar no
   acesso Postgres de producao (isso e trabalho separado, do lado do
   Claude/B05).
3. NAO alterar a logica de `jurisdicao_normativa_service.py` nem de
   `resolver_aliquota_e_mva` -- so o dado em `tabela_mva`, via um
   script de atualizacao explicito e auditavel (seguir o padrao de
   `app/scripts/seed_mva.py`, nao editar a BD diretamente com SQL solto
   sem script versionado).
4. NAO expandir para outras UFs ou outros NCMs nesta missao. So PA,
   so NCM 22021000, so o campo de fonte legal.
5. NAO declarar "cobertura nacional avancou" ou qualquer formulacao que
   sugira que isto afeta outras jurisdicoes. O documento de entrega
   fala so sobre PA/22021000 e a fonte encontrada (ou a sua ausencia).
6. Reportar a fonte encontrada para ratificacao ANTES de escrever no
   `test.db`. So escrever apos confirmacao explicita.
7. Apos escrever o dado (se ratificado), rodar o teste ja existente
   `tests/test_jurisdicao_normativa_fase1_pa.py` -- o teste
   `test_resolvedor_existente_permanece_fail_closed_para_pa` vai
   PASSAR A FALHAR intencionalmente (porque PA deixa de estar
   fail-closed) -- isso e esperado e correto; o teste precisa de ser
   atualizado para refletir o novo estado (`calculo_autorizado=True`),
   nunca contornado ou apagado sem mais.
8. Suite relevante + catraca anti-duplicacao antes de qualquer commit.
9. Nunca merge para `main`. Nunca deploy.

## Entrega esperada

- Se a fonte for encontrada e ratificada: dado preenchido via script
  versionado, teste atualizado para refletir `NORMA_VERIFICADA` para
  PA, documento de estado
  (`docs/COBERTURA_NACIONAL_FASE2_FONTE_PA_ESTADO_<data>.md`) citando
  a fonte exata (numero, orgao, data, link se houver).
- Se a fonte NAO for encontrada com confianca suficiente: documento de
  estado relatando a pesquisa feita, onde foi procurado, e porque nao
  foi encontrada -- sem nenhum commit de dado no `test.db`. Isto e um
  resultado valido e honesto, nao uma falha da missao.
