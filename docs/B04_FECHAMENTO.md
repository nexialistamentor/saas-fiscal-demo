# B04 -- FECHAMENTO

Bloco B04 do roteiro B00-B11 (Diagnostico Fiscal Empresarial Integral).
Objetivo original: integracao ponta a ponta do motor ICMS-ST (G12/G13) a
cadeia de projecao integral I0-I1-I2. Fechado nesta data, com o escopo
estrito abaixo -- nao inclui os achados colaterais documentados na secao
"Fora do escopo deste fechamento".

## O que foi entregue

1. Ponte `enterprise_b04_icms_st_integral_bridge.py::projetar_diagnostico_
   integral_icms_st` -- liga G13 (que ja chama G12 internamente) a cadeia
   I0-I1-I2, preenchendo `icms_st`/`mva`/`consistencia_fiscal` no catalogo
   `_CAPACIDADES`. Nunca promove `autoridade_fiscal=True`, nunca excede o
   escopo honesto (G12/G13 so cobrem o metodo `iva_st`, nao PMPF).
2. Ligacao ao consumidor real `executar_circuito_enterprise_01` (em
   `registro_analise_service.py`), via novo parametro `g13_precomputado`
   na ponte -- reaproveita o G13 ja calculado na mesma analise em vez de
   recalcular (eliminou uma 3a execucao de G13 por analise).
3. Dois defeitos reais da ponte, encontrados e corrigidos durante o
   trabalho:
   - `itens_simulados == 0` (G12/G13 rodam mas nenhum item tem obrigacao
     ST aplicavel) agora produz estado `nao_apurado`, nao mais
     `informativo_sem_prova` (que sugeria erradamente haver uma simulacao
     presente).
   - Validacao de identidade de `g13_precomputado` (empresa_id,
     relatorio_id, xml_sha256) agora cai no mesmo tratamento gracioso
     (`falha_motor`) que a chamada ao vivo de G13 ja tinha -- antes,
     uma divergencia de identidade propagava excecao crua e podia
     derrubar `executar_circuito_enterprise_01` inteiro.
4. Teste canonico `tests/test_solveris_b01_circuit.py` atualizado: a
   contagem de capacidades `nao_integrado_ao_snapshot` cai de 33 para 30
   (exatamente as 3 capacidades que a ponte passa a preencher), com
   asser??es explicitas confirmando os novos estados.

## Decisao arquitetural ratificada (nao reabrir)

`_CAPACIDADES` (o catalogo estatico em `enterprise_integral_projection.py`)
NAO foi alterado. Tentativa de mudar `origem` de `pendente` para outro
valor quebrou o contrato canonico de I0
(`test_enterprise_integral_projection_contract.py::test_01_no_omission...`)
e foi revertida via `git restore`. A ponte B04 ja faz a fusao necessaria
em runtime -- nao depende do catalogo estatico para isso.

## Commits (branch `b04/integracao-g13-icms-st-20261111`)

- `1af67fe4` -- ponte ligada ao consumidor real, dedupe de G13.
- `8081ec58` -- handoff atualizado com a correcao de premissa do passo 2.
- `769304c3` -- dois defeitos da ponte corrigidos, 4 testes novos.

Suite completa (120 testes relevantes) verde antes de cada commit. Catraca
anti-duplicacao (`tools/check_duplicacao.py`) verde antes de cada commit.

## Fora do escopo deste fechamento (achados reais, nao resolvidos aqui)

Estes tres achados sao reais, verificados no codigo, e nao fazem parte do
objetivo original de B04. Cada um tem o seu proprio documento de trabalho
(ver `docs/TRABALHO_PARALELO_INTELIGENCIA_E_ATOMICIDADE.md`) e NAO deve
ser tratado como continuacao numerada de B04 (nao existe "B4A"):

1. **Duplicacao de G13 via G14/G17**: G13 pode rodar ate 3x na mesma
   analise (chamada direta + via G14 + via G17->G16->G15->G14). Dedupe
   exige mapear o grafo de chamadas inteiro antes de mudar qualquer
   assinatura nessa cadeia.
2. **`commit()` prematuro em `InsightEngine.gerar_insights_empresa`**:
   risco de atomicidade -- commit ocorre antes de
   `executar_e_registrar_analise_xml` terminar os seus proprios passos
   finais (`finalizar_registro_analise`, selagem do resultado). Uma falha
   posterior pode deixar `Insight`/`EngineResultado`/`InteligenciaSnapshot`
   persistidos de uma analise que nao fecha com sucesso.
3. **16 produtores do grupo `inteligencia` (score, maturidade, eficiencia,
   ranking_*, benchmark, radar, anomalias, etc.) ja existem e ja rodam**
   (a maioria dentro de `InsightEngine.gerar_insights_empresa`), mas os
   seus resultados completos sao descartados antes de chegar a
   `compor_resultado_empresarial`/I0 -- so sobrevivem fragmentos. Ligar
   isto ao catalogo exige capturar dados hoje descartados, nao so
   reaproveitar uma chamada ja feita (diferente do padrao de G13).

## Proximo bloco do roteiro

B05 -- validacao fiscal com casos reais. B03_FECHAMENTO.md ja registra que
so ha 1 regra real confirmada na BD (UF=PA, NCM=22021000); B05 vai
precisar de mais dados reais ou de casos sinteticos claramente rotulados
como tal.
