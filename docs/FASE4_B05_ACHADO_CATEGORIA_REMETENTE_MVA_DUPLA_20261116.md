# SOLVERIS — Achado: MVA dupla por categoria do remetente (PA/22021000, CEST 03.010.01)

Data: 2026-11-16

## O que foi verificado
Extração direta do texto do decreto ja custodiado sob ADR-020
(DOE_PA_20230307_EXTRA_35315.pdf, Decreto no 2.931/2023, Apendice I do Anexo I
do RICMS-PA), secao "CERVEJAS, CHOPES, REFRIGERANTES, AGUAS E OUTRAS BEBIDAS".

Linha exata, item 9.1, CEST 03.010.01, NCM 2202.10.00/2202.99.00,
"Refrigerante em embalagem pet":

    INDUSTRIAL, IMPORTADOR, ARREMATANTE E ENGARRAFADOR: 140% / 140% / 140%
    DISTRIBUIDOR, DEPOSITO E ESTABELECIMENTO ATACADISTA: 40% / 40% / 40%

(tres subcolunas por aliquota interestadual: 4%, 7%, 12% — identicas dentro de
cada categoria para este item).

## Achado critico
O seed de teste `app/scripts/seed_mva.py` usa MVA=40% fixo para PA/22021000.
Esse valor corresponde exatamente a coluna ATACADISTA/DISTRIBUIDOR do decreto
— nunca foi comparado ou documentado contra a coluna INDUSTRIAL (140%). A
escolha da categoria atacadista foi feita silenciosamente, sem registro em
lugar nenhum do seed, do teste ou da documentacao anterior.

## Reframing do item 7 do checklist B05
O problema nao e "provar a categoria de um remetente real especifico" via
compra ou Consulta Tributaria. O problema e que **o motor de calculo nao tem
nenhum branch de decisao entre as duas colunas da MVA**. Ele aplica 40% fixo
sem verificar se o remetente real e industrial/importador/arrematante/
engarrafador (140%) ou distribuidor/atacadista (40%). Um caso real com
remetente industrial geraria erro de calculo de quase 100 pontos percentuais,
silenciosamente, sem nenhum alerta.

## Correcao de arquitetura necessaria (sem compra, sem terceiro, sem revisor)
1. Extrair o CNPJ do remetente da nota fiscal real de entrada.
2. Consultar o CNAE desse CNPJ via API publica nacional da Receita Federal
   (gratuita, instantanea, nacional — nao depende de nenhum estado
   especifico nem de nenhuma compra).
3. Mapear CNAE -> categoria (industrial/importador/arrematante/engarrafador
   vs distribuidor/atacadista), conforme o padrao usado pelo proprio Fisco
   (confirmado em litigio real no Conselho de Contribuintes de MG, acordao
   22.396/17/3a) e documentado no benchmark
   docs/FASE4_BENCHMARK_CONCORRENCIA_CATEGORIA_REMETENTE_20261116.md.
4. Selecionar a coluna correta (140% ou 40%) do Apendice I ja custodiado
   (hash ITI validado) — nenhum valor normativo pendente de busca externa.

## Status do item 7 (checklist B05)
Resolvido quanto a origem normativa (ambos os valores de MVA estao
custodiados e hash-validados). Pendente apenas a implementacao do passo
CNAE->categoria no motor — que e trabalho de construcao, nao de investigacao.
