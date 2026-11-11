# Reforma Tributária — alinhamento para B04-B11

Registado a pedido de Miguel em 2026-11-11, para qualquer sessão futura
(Claude ou GPT) que trabalhe nos blocos B04-B11 ter esta noção antes de
construir ou priorizar capacidades fiscais.

## Cronograma confirmado (EC 132/2023 + LC 214/2025)

| Ano | O que muda |
|---|---|
| 2026 | Ano de teste: CBS (0,9%) e IBS (0,1%) aparecem na NF-e, **sem cobrança efetiva**. PIS/COFINS/ICMS seguem normais. |
| **2027** | **PIS e COFINS extintos.** CBS passa a ser cobrada de facto (alíquota de referência, reduzida 0,1pp). Campos de IBS/CBS tornam-se **obrigatórios na NF-e**. Início do Imposto Seletivo. |
| 2028 | Continuação de 2027 (mesmas alíquotas). |
| 2029-2032 | ICMS e ISS reduzem 10%/ano cada (substituídos por IBS). |
| 2033 | ICMS e ISS extintos. Modelo IVA dual (CBS+IBS) pleno. |

Fontes: Congresso em Foco, Serasa Experian, Tax Group, Pactum, SIJUR,
Metacursos, Assertif (pesquisa web em 2026-11-11, todas convergentes).

## Implicações diretas para o catálogo de 52 capacidades

O catálogo (`app/services/enterprise_integral_projection.py::_CAPACIDADES`)
tem `pis`, `cofins`, `credito_pis`, `credito_cofins` como capacidades
próprias, com um módulo dedicado inteiro
(`enterprise_pis_cofins_authority_i1.py`). **Estas capacidades têm prazo
de validade conhecido: extintas em 01/01/2027.** Investimento pesado
nelas agora tem retorno limitado — avaliar antes de priorizar.

## O que NÃO é afetado (confirmado)

`icms_st` e `mva` — o que B03 construiu — **sobrevivem até 2029 no
mínimo** (ICMS só começa a reduzir em 2029, extinção em 2033). B03
continua válido e não precisa de revisão por causa desta reforma.

## Lacuna nova identificada, ainda não construída por ninguém

`app/xml_service.py::ler_xml_unico` **não extrai nenhum campo de
IBS/CBS** da NF-e. A partir de 01/01/2027 esses campos são obrigatórios
no XML. Isto é trabalho novo genuíno (não "pendente" no catálogo porque
o catálogo em si é de 16/10/2026, anterior a esta análise) — não
confundir com lacuna já mapeada, nem construir prematuramente antes de
confirmar o leiaute oficial do campo IBS/CBS na NF-e 4.0/5.0 quando
publicado pela SEFAZ/Receita Federal.

## Regra prática para B04-B11

Antes de construir ou priorizar qualquer capacidade da área `tributos`
(grupo PIS/COFINS no catálogo), confirmar se o esforço ainda faz sentido
dado o prazo de extinção em 2027. Áreas `icms_st`, `regimes` (exceto o
que depender de PIS/COFINS) e `documentos` não têm essa urgência de
obsolescência.
