# SOLVERIS — Benchmark: como o setor resolve a categoria do remetente (ICMS-ST)

Data: 2026-11-16

## Pergunta investigada
Como fornecedores de motor fiscal (Systax, Sovos e outros) determinam se um
remetente é industrial/importador ou atacadista/distribuidor, para fins de
aplicação da MVA de ICMS-ST — sem depender de comprar o produto do remetente
nem de consulta formal estado a estado?

## Achado
O setor NAO resolve isto por transacao. Resolve por duas camadas publicas e
nacionais, sem dependencia de terceiro nem de revisor humano:

1. CNAE do remetente, consultavel gratuita e instantaneamente via API publica
   da Receita Federal (nacional, nao depende de estado), e usado pelo proprio
   Fisco como criterio primario. Confirmado em litigio real no Conselho de
   Contribuintes de MG (acordao 22.396/17/3a): "O Fisco se baseou apenas no
   CNAE Fiscal principal para tal analise."
2. A MVA diferenciada por categoria (industria vs atacadista/distribuidor) e
   publicada diretamente no proprio decreto/anexo da legislacao estadual —
   nao e algo a descobrir por investigacao externa. Confirmado em RICMS/MG
   Anexo VIII (tabela com colunas separadas "Industria" e "Atacadista/
   Distribuidor" para o mesmo CEST/NCM) e em acordao de MG que vincula
   responsabilidade de ST a codigos CNAE especificos ("classificada na CNAE
   4634-6/01, 4634-6/02 ou 4634-6/99 sera o responsavel pela retencao").

Fornecedores como Systax mantêm uma base de regras fiscais construida a
partir da legislacao publicada (mais de 21 milhoes de regras, 27 UFs), nao
de transacoes de teste.

## Implicacao para a arquitetura SOLVERIS
A compra real (SOLVERIS como cobaia) permanece valida como caso de fechamento
pontual do B05 e como validacao de ponta a ponta do pipeline — mas NAO deve
ser adotada como metodo geral de descoberta de categoria de remetente. O
metodo geral correto, sem dependencia de terceiro:

1. Extrair o CNPJ do remetente da nota real.
2. Consultar o CNAE desse CNPJ via API publica nacional da Receita Federal
   (sem depender de nenhum estado especifico).
3. Cruzar esse CNAE com a tabela de MVA por categoria publicada no proprio
   decreto normativo ja custodiado (sob ADR-020), quando o decreto a
   diferenciar.

Pendente de verificacao: se o decreto PA ja custodiado (DOE_PA 35096/35315)
diferencia a MVA por categoria do remetente ou define apenas uma MVA unica.
Essa verificacao decide se o metodo acima se aplica tal como esta ao caso PA
ou precisa de ajuste.

## Fontes
- Conselho de Contribuintes MG, acordao 22.396/17/3a (helios.fazenda.mg.gov.br)
- Conselho de Contribuintes MG, acordao 24.015/22/1a (fazenda.mg.gov.br)
- Decreto MS 15.367/2020, via Systax (systax.com.br)
- RICMS/MG Anexo VIII (coad.com.br)
- Systax — base de regras fiscais (systax.com.br, baguete.com.br)
