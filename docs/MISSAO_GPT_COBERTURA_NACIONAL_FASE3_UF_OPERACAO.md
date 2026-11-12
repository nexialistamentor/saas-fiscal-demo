# MISSAO GPT -- Cobertura Nacional de Jurisdicoes, FASE 3 (UF da operacao, nao da empresa)

QUINTO trabalho paralelo do GPT. NAO INICIAR enquanto a Fase 2
(`cobertura-nacional-jurisdicoes-fase2-fonte-pa`) nao estiver fechada e
ratificada por Miguel. Ler este documento por inteiro antes de tocar em
qualquer ficheiro, e confirmar o estado da Fase 2 primeiro.

## Achado que origina esta missao (B05, dado real de producao)

Consulta directa, read-only, ao PostgreSQL real de producao (Railway,
projeto disciplined-alignment) confirmou: das 80 empresas reais
cadastradas, ZERO tem o campo `empresas.uf` preenchido -- mesmo as 46
que tem `cnpj` preenchido. Em contrapartida, `documentos_fiscais` TEM
`uf_emit`/`uf_dest` preenchidos corretamente em varios documentos reais
(ex.: 5 itens reais de NCM 22021000 ligados a `uf_emit='PA'`).

Isto significa que `selecionar_norma_por_jurisdicao`
(`app/services/jurisdicao_normativa_service.py`, Fase 1), tal como
escrita, nunca vai encontrar jurisdicao para NENHUMA empresa real em
producao -- porque le `empresa.uf`, que esta sempre vazio.

## O problema NAO e so falta de dado -- e um problema de modelagem

Nao corrigir isto preenchendo `empresa.uf` a partir de `uf_emit` do
documento -- isso seria inferir cadastro de empresa a partir de uma
unica operacao, o que pode estar errado (filiais, mudanca de sede,
emissao em nome de terceiros) e repete o erro que ja evitamos na Fase 2
(nunca promover indicio fraco a fonte de verdade).

A correcao estrutural correta: ICMS-ST (e, de forma ainda mais
decisiva, o futuro IBS/CBS da Reforma Tributaria 2027, que e um
tributo de DESTINO) depende da UF DA OPERACAO (`uf_emit`/`uf_dest` do
documento em analise), nao da UF de sede da empresa. `empresa.uf`
continua correto para tributos de ambito empresarial (IRPJ, CSLL,
Simples) -- nao deve ser removido nem alterado, so deixa de ser a
fonte para jurisdicao de ICMS-ST/IBS/CBS.

## O que esta missao constroi, exatamente

1. Alterar a assinatura de `selecionar_norma_por_jurisdicao` para
   aceitar a UF da OPERACAO explicitamente (ex.: um parametro
   `uf_operacao: str`, vindo de `documentos_fiscais.uf_emit` ou
   `uf_dest`, conforme o caso de uso que ja chama esta funcao decidir
   -- NAO decidir isso sozinho, ver proxima seccao), em vez de inferir
   de `empresa.uf`. O parametro `empresa` pode continuar a existir para
   outros fins (ex. regime tributario), mas deixa de ser a fonte de UF.
2. Atualizar `tests/test_jurisdicao_normativa_fase1_pa.py` para passar
   `uf_operacao` explicitamente, preservando todas as asser??es ja
   validadas (nada deve regredir).
3. Escrever um teste novo que reproduz o caso real de producao
   encontrado por B05: documento com `uf_emit='PA'` e `empresa.uf=None`
   -- confirmar que a selecao agora funciona correctamente usando a UF
   da operacao, SEM exigir que `empresa.uf` esteja preenchido.

## Decisao que PRECISA de ratificacao antes do commit, nao decidir sozinho

Qual campo usar como `uf_operacao` por omissao (`uf_emit` ou `uf_dest`)
quando o chamador nao especificar -- ou se a funcao deve exigir sempre
que o chamador decida explicitamente, sem omissao implicita nenhuma
(fail-closed quando a UF da operacao nao for passada). Esta ultima
opcao (sem omissao, sempre explicito) e a mais alinhada com o padrao
fail-closed ja usado em toda a cadeia I0-I1-I2-G12-G13 -- mas e uma
decisao de arquitetura, nao do GPT decidir isoladamente.

## REGRAS QUE NAO PODEM SER QUEBRADAS

1. NAO iniciar antes da Fase 2 estar fechada e ratificada.
2. Branch proprio: `cobertura-nacional-jurisdicoes-fase3-uf-operacao`,
   criado a partir de `cobertura-nacional-jurisdicoes-fase1-pa` (nao da
   Fase 2, que e independente -- confirmar que os commits da Fase 1
   estao presentes antes de comecar).
3. NAO tocar em `empresas.uf` nem em nenhum dado de producao -- esta
   missao e so de CODIGO (assinatura da funcao e testes).
4. NAO mexer em `_CAPACIDADES`, G12-G17, ponte B04, nem no acesso
   Postgres de producao (acesso de leitura ja resolvido do lado do
   Claude/B05 -- nao duplicar esse trabalho).
5. NAO expandir para o desenho do IBS/CBS em si (reforma 2027) -- so
   preparar o mecanismo de selecao para nao depender de um campo
   estrutural que nao existe hoje. Reforma tributaria e trabalho
   futuro, fora desta missao.
6. `git grep`/`mostrar_corpo_funcao.py` antes de assumir qualquer coisa
   sobre quem chama `selecionar_norma_por_jurisdicao` hoje -- confirmar
   se ja ha consumidores reais dessa funcao que precisam de ser
   atualizados tambem.
7. Suite relevante (incluindo
   `tests/test_jurisdicao_normativa_fase1_pa.py` e os testes de B04 ja
   validados) + catraca anti-duplicacao antes de qualquer commit.
8. Nunca merge para `main`. Nunca deploy. Nunca tocar em producao.

## Entrega esperada

Documento `docs/COBERTURA_NACIONAL_FASE3_UF_OPERACAO_ESTADO_<data>.md`
descrevendo a mudanca de assinatura, a decisao ratificada sobre
uf_emit/uf_dest/explicito-sempre, e os testes que provam que o caso
real de producao (PA via uf_emit, empresa sem uf) agora funciona.
