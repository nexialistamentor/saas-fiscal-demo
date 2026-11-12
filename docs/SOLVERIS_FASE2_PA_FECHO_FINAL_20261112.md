# SOLVERIS — Cobertura Nacional de Jurisdições
## Fase 2 — Encerramento técnico-documental: PA / NCM 22021000

**Data do encerramento:** 12/11/2026  
**Âmbito exclusivo:** Pará (PA), NCM `22021000`  
**Branch preservado:** `cobertura-nacional-jurisdicoes-fase2-fonte-pa`  
**Commit preservado:** `0be47671aa9003509a4ce6cdab1581b6ff7810ce`  
**Natureza:** documento de encerramento, sem alteração do repositório ou do banco

### 1. Decisão final

A Fase 2 está **encerrada no seu objetivo investigativo**, com a conclusão ratificada: **“fonte oficial identificada; aplicabilidade à linha genérica não comprovada”.** A fonte foi localizada, mas o registo existente `tabela_mva(estado='PA', ncm='22021000')` não pode ser promovido a regra fiscal autorizada apenas com UF e NCM.

**Mantém-se o bloqueio:** `fonte_legal=NULL`, `url_fonte=NULL`, `autoridade_normativa_verificada=False` e `calculo_autorizado=False` na seleção da Fase 1. Não se atribui autoridade normativa por inferência.

### 2. Alíquota interna: conclusão da pesquisa

**21% para refrigerantes**, conforme o art. 20, IV, do Regulamento do ICMS do Pará (Decreto estadual nº 4.676/2001), na redação conferida pelo Decreto nº 73, de 24/04/2019, publicado em 25/04/2019, com fundamento também no art. 12, IV, da Lei estadual nº 5.530/1989. A alteração da alíquota **geral** para **19%** a partir de **16/03/2023** não é, por si, substituição da regra **específica** para refrigerantes. O valor **18%** presente no seed PA não ficou fundamentado para o produto e o período em questão.

Essa conclusão é normativa de referência, **não** uma autorização automática para alterar o seed ou liquidar ICMS: a incidência no caso concreto depende da data, do tipo de operação, de eventuais exceções e do enquadramento jurídico.

Fontes primárias identificadas na investigação:
- Decreto nº 73/2019 (portal oficial): https://www.sistemas.pa.gov.br/sisleis/legislacao/4755
- Lei nº 5.530/1989 (legislação oficial): https://www.legispara.pa.gov.br/lei/3356
- Regulamento do ICMS/PA: Decreto nº 4.676/2001, art. 20, IV.

### 3. CEST e condição do remetente: MVA estruturada

A tabela do **Decreto Estadual nº 2.588, de 29/08/2022**, disponível com errata em portal oficial, distingue categorias de refrigerantes e condições do remetente:

| CEST | Categoria | Distribuidor, depósito ou atacadista | Industrial, importador, arrematante ou engarrafador |
|---|---|---:|---:|
| `03.010.00` | Refrigerante em vidro descartável | **40%** | **140%** |
| `03.010.01` | Refrigerante em embalagem PET | **40%** | **140%** |
| `03.010.02` | Refrigerante em lata | **40%** | **140%** |
| `03.011.00` | Demais refrigerantes, segundo o enquadramento legal | **70%** | **140%** |

Os três primeiros CESTs abrangem itens nas classificações `2202.10.00` e `2202.99.00`, mas o **NCM isolado não decide a categoria**. O decreto e a sua atualização pelo Decreto nº 2.931/2023 exigem leitura das colunas e da modalidade de antecipação/entrada no território do Pará, não uma aplicação indistinta a saídas internas.

Fontes oficiais:
- Decreto nº 2.588/2022 com errata: https://www.cge.pa.gov.br/sites/default/files/2023-03/decreto_estadual_n_2588_de_29_08_2022_com_errata.pdf
- Decreto nº 2.931/2023: https://www.pge.pa.gov.br/sites/default/files/alerta-legislativo/DE2931.pdf

### 4. Limitação do registo PA/22021000

Na Fase 1 foi verificada a linha local existente com `mva=40.0`, `aliquota_interna=0.18`, `vigencia_inicio=2024-01-01`, `vigencia_fim=NULL` e `nivel_confianca_fonte='oficial'`, mas com `fonte_legal=NULL` e `url_fonte=NULL`. A linha **não contém CEST, material de embalagem, categoria do remetente, natureza da operação nem alíquota interestadual**. A indicação de confiança `oficial` não supre estas faltas.

Para a **empresa real `empresa_id=4`**, cuja identificação/regime estão incompletos no contexto reportado, **não é possível confirmar a condição do remetente para este caso real**. A condição do remetente de cada documento não pode ser deduzida automaticamente do cadastro da empresa destinatária.

### 5. Inventário arquitetural — duas estruturas e os seus limites

**A. `TabelaMVA`: ligada ao serviço fiscal, mas insuficiente para esta regra.**
- Modelo existente em `app/models.py`: UF, NCM, MVA, alíquota, vigência e fonte.
- `app/services/tabela_normativa_service.py::buscar_mva` seleciona por **UF + NCM + data**, sem filtros para CEST, categoria do remetente ou operação.
- É reutilizada pela seleção de jurisdição da Fase 1, já validada.
- Consequência: preencher `fonte_legal` na linha genérica poderia converter uma margem **condicionada** em autoridade fiscal **indevida**.

**B. `RuleVersion` e cadeia ADR-020: estruturalmente expressivas, mas sem consumidor fiscal operacional confirmado.**
- `normative_artifacts`: custódia da fonte imutável e proveniência.
- `extraction_runs` / `extraction_results`: execução e conteúdo estruturado da extração, com evidências.
- `rule_versions`: regra versionada com `structured_content`, `declared_material_validity`, `normative_references`, hashes e vínculo obrigatório com a extração.
- `enterprise_b02_normative_binding.py::cotejar_vinculo_normativo_b02`: cotejo *read-only* de registo L2 e `RuleVersion`, incluindo dimensões fiscais, mas é expressamente **investigativo e sem promoção a autoridade fiscal**.
- Verificação de chamadas efetuada diretamente no repositório e reproduzida por `git grep` no Windows: fora de testes, apenas as ocorrências da **definição** da função (linha 128) e de **`__all__`** (linha 322). **Nenhum chamador operacional foi identificado.**
- `registro_analise_service.py` inclui chamadas G13/G14/G17 noutro circuito, mas esse circuito declara-se **opt-in e limitado a SQLite em memória**; isto também não equivale, por si, a execução em PostgreSQL de produção. O cotejo B02 **não** é chamado nesse circuito.
- O contrato B02 analisado para `RuleVersion` exige `operacao='saida_interna'` no trecho observado; a margem do decreto examinado refere-se à antecipação na entrada em PA. Não é semanticamente intercambiável.

**Diagnóstico:** `TabelaMVA` está ligada, mas tem chave normativa demasiado simples; `RuleVersion` dispõe de representação jurídica e documental mais rica, mas a ligação ao motor fiscal **não está demonstrada**. Nenhuma das duas está hoje comprovadamente pronta para produzir cálculo autorizado deste caso.

### 6. Decisão de arquitetura adiada

**Não há escolha ratificada** entre estender `TabelaMVA`, integrar `RuleVersion`/ADR-020, ou qualquer outra solução. A avaliação será objeto de **Fase 2.5/3 futura, com missão e ratificação próprias**. Esta Fase 2 **não** autoriza desenho de integração, alteração de schema, migração, novas regras condicionadas nem alteração do resolvedor.

### 7. Preservação e fecho

- Não escrever em `test.db` ou em PostgreSQL de produção.
- Não preencher `fonte_legal`/`url_fonte` do registo PA genérico.
- Não alterar `jurisdicao_normativa_service.py`, `resolver_aliquota_e_mva`, testes ou migrações.
- Não tocar no B02/G12–G17/B04 nem importar trabalho de outros branches.
- Não realizar merge nem deploy.
- **Preservar o branch e o commit `0be47671` sem novo commit.** Este documento é entregue separadamente, fora do repositório, até existir autorização explícita para versioná-lo.

**Estado final:** Fase 2 **FECHADA — pesquisa normativa concluída, aplicabilidade genérica não comprovada, bloqueio preservado e decisão arquitetural adiada**.
