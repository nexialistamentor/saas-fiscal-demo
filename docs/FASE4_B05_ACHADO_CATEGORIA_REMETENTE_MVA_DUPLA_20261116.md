# SOLVERIS — Achado: MVA dupla por categoria do remetente (PA/22021000, CEST 03.010.01)

Data: 2026-11-16 (corrigido em 2026-11-16 apos verificacao cruzada por outro GPT e inspecao direta do codigo)

## O que foi verificado
Extracao direta do texto do decreto ja custodiado sob ADR-020
(DOE_PA_20230307_EXTRA_35315.pdf, Decreto no 2.931/2023, Apendice I do Anexo I
do RICMS-PA), secao "CERVEJAS, CHOPES, REFRIGERANTES, AGUAS E OUTRAS BEBIDAS".

Linha exata, item 9.1, CEST 03.010.01, NCM 2202.10.00/2202.99.00,
"Refrigerante em embalagem pet":

    INDUSTRIAL, IMPORTADOR, ARREMATANTE E ENGARRAFADOR: 140% / 140% / 140%
    DISTRIBUIDOR, DEPOSITO E ESTABELECIMENTO ATACADISTA: 40% / 40% / 40%

(tres subcolunas por aliquota interestadual: 4%, 7%, 12% — identicas dentro de
cada categoria para este item).

## Achado critico (confirmado por inspecao direta do codigo em 10b3b1bc)
`app/services/tabela_normativa_service.py::buscar_mva(db, estado, ncm,
data_referencia)` seleciona o registro de `TabelaMVA` filtrando somente por
estado, NCM e vigencia. Nao recebe CNPJ, CNAE, CEST nem categoria do
remetente. O schema de `TabelaMVA` (`app/models.py:1299-1319`) tambem nao tem
coluna de CEST nem de categoria — so estado, ncm, mva, aliquota_interna,
vigencia, fonte_legal, nivel_confianca_fonte, url_fonte.

O seed de teste `app/scripts/seed_mva.py` usa MVA=40% fixo para PA/22021000.
Esse valor corresponde exatamente a coluna ATACADISTA/DISTRIBUIDOR do decreto
— nunca foi comparado ou documentado contra a coluna INDUSTRIAL (140%). A
escolha da categoria atacadista foi feita silenciosamente, sem registro em
lugar nenhum do seed, do teste ou da documentacao anterior.

`DocumentoFiscal.cnpj_emitente` (`app/models.py:1258`) ja existe — o CNPJ do
remetente real ja e capturado quando ha nota de entrada real.

## CORRECAO (2026-11-16): duas afirmacoes da versao original deste documento
eram apressadas e foram corrigidas apos segunda investigacao (outro GPT) e
verificacao direta do codigo:

1. "CNAE basta para classificar o remetente" — NAO CONFIRMADO. Nem o Decreto
   2.931/2023 nem o Convenio ICMS 142/2018 estabelecem uma correspondencia
   CNAE -> categoria para o item 9.1 especificamente. Existe classificacao
   CNAE/CONCLA generica (1122-4/01 fabricacao = industria; 4635-4/02 comercio
   atacadista; 4635-4/03 atacadista COM engarrafamento associado — esta
   ultima e ambigua, porque "engarrafador" e "atacadista" sao colunas
   diferentes no decreto). Mapear CNAE -> coluna de MVA e, portanto, uma
   INTERPRETACAO SOBERANA da SOLVERIS a ser declarada e ratificada
   explicitamente, nao uma regra legal automatica ja escrita em lugar algum.
2. "API oficial gratuita e instantanea da Receita Federal" — NAO CONFIRMADO.
   ReceitaWS publica: 3 consultas/minuto, so cache, sem garantia para uso
   comercial continuo. BrasilAPI: beta, sem SLA, sem autorizacao expressa
   para alto volume. A unica opcao contratual seria SERPRO Consulta CNPJ —
   que a SOLVERIS NAO TEM hoje. O que a SOLVERIS tem e integracao SERPRO para
   PGMEI (geracao de DAS do MEI, `app/services/serpro_pgmei_client.py`,
   `_SUPPORTED_SERVICES = {"GERARDASPDF21", "GERARDASCODBARRA22"}`) — um
   produto SERPRO diferente, sem capacidade de consulta de CNAE. A infra de
   OAuth2 + mTLS/PKCS12 ja construida para o PGMEI (`serpro_oauth_session.py`,
   `serpro_authenticated_transport.py`, `serpro_pkcs12_transport.py`) e
   reaproveitavel para compor um novo cliente Consulta CNPJ, mas isso e
   contratacao e construcao nova, nao algo gratuito e ja disponivel.

## Reframing do item 7 do checklist B05 (mantido, independente da correcao acima)
O problema nao e "provar a categoria de um remetente real especifico" via
compra ou Consulta Tributaria. O problema e que o motor de calculo nao tem
nenhum branch de decisao entre as duas colunas da MVA. Um caso real com
remetente industrial geraria erro de calculo de quase 100 pontos percentuais,
silenciosamente, sem nenhum alerta. Isso permanece verdadeiro e e o achado
central, nao afetado pela correcao acima.

## Caminho revisado (sem compra, sem revisor humano — mas com decisao
## interpretativa soberana explicita e contratacao a avaliar)
1. Extrair o CNPJ do remetente da nota fiscal real de entrada
   (ja capturado em DocumentoFiscal.cnpj_emitente).
2. Contratar/compor cliente SERPRO Consulta CNPJ (reaproveitando a infra
   OAuth2/mTLS do PGMEI) para obter o CNAE do remetente — pendente de decisao
   de contratacao, nao e gratuito nem imediato.
3. Declarar explicitamente, como decisao soberana da SOLVERIS (ratificada por
   Miguel, documentada no repositorio), qual mapeamento CNAE -> categoria se
   adota para este segmento — incluindo como tratar o caso ambiguo do CNAE
   4635-4/03 (atacadista com engarrafamento associado).
4. Selecionar a coluna correta (140% ou 40%) do Apendice I ja custodiado
   (hash ITI validado) — os valores normativos em si nao estao pendentes.

## Status do item 7 (checklist B05)
Resolvido quanto a origem normativa dos dois valores de MVA (custodiados e
hash-validados). Pendentes: (a) decisao de contratacao SERPRO Consulta CNPJ,
(b) decisao soberana de mapeamento CNAE->categoria, (c) implementacao do
branch no motor. Os tres sao construcao/decisao, nao investigacao adicional.
