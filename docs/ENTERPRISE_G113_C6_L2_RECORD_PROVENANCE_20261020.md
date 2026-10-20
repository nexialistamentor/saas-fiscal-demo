# SOLVERIS Enterprise — G1.13-C6 — proveniência L2 do registo MVA observado

Corte 20/10/2026; branch `work/fiscal-assumptions-c0`, HEAD-base `f7d1090b301461c5179034aa39828cd111b247e0`. Não tocar no MEI.

## Lacuna demonstrada na fonte do repositório

`TabelaMVA` possui `id`, `estado`, `ncm`, `mva`, `aliquota_interna`, vigências, fonte, URL e importador. O serviço `buscar_mva()` seleciona uma linha ordenando confiança declarada, início de vigência e ID descendente, mas não devolve esse ID. A G1.2/C5 preserva os parâmetros realmente usados na simulação, ainda sem associar a linha concreta do cadastro à execução.

O **CEST não integra a tabela `TabelaMVA` nem a chave da consulta atual**. Esta limitação é comercialmente importante: correspondência UF/NCM/data não prova por si a classificação e aplicabilidade de ST para determinado produto, operação, regime ou benefício. Também não existe FK demonstrada entre `TabelaMVA` e `RuleVersion` ADR-020.

## Alterações autorizadas pelo pacote

- `app/services/tabela_normativa_service.py`: acrescentar `registro_mva_id` e `importado_por` ao dict existente de `buscar_mva()`, **sem mudar a query, os filtros nem a precedência**.
- `app/services/enterprise_g12_st_item_reconciliation.py`: adicionar `proveniencia_l2_g12_v1` no ramo de simulação que já passou as verificações de MVA/alíquota, **somente se ID inteiro positivo for devolvido**. Conservar intacto `rastro_parametros_g12_v1` da C5 e as fórmulas G1.2 existentes.
- `tools/enterprise_g113_c6_l2_record_provenance.py`: verificador puro do ID, fonte, vigência e parâmetros L2 com C4/C5/G13; STOP em contradições, abstenção sem ID.
- Testes e documentação C6 novos. Nenhuma migração/ALTER TABLE/rotas/API/DB write/pagamento.

## Fronteiras de autoridade

A identidade observada é a da linha interna selecionada no cadastro L2, **não** uma autenticação da origem dos bytes oficiais, não é confirmação de unicidade de linhas vigentes, nem vínculo ADR-020, nem confirmação de incidência da ST. A G1.2 realiza consultas sucessivas ao resolvedor, ao cadastro e ao cálculo de base; estes retornos devem coincidir em parâmetros mas não provam isolamento transacional perante atualizações concorrentes. Esta limitação permanece explícita.

O módulo C6 não executa DB nem verifica se snapshots fornecidos pelo chamador vieram de execução autenticamente controlada; tais provas pertencem ao orquestrador autorizado. Todos os indicadores de autoridade fiscal, crédito, checkout e utilização comercial permanecem `False`.

## Gates

O executor protegido verifica HEAD local/remoto e o SHA Git de ambos os ficheiros base; escopo tracked limpo, índice limpo e integridade do pacote antes da instalação. Aplica apenas inserções aditivas ancoradas, sem substituições destrutivas; valida sintaxe, 25 testes sintéticos C6 e a suite C5 de 32 testes como regressão; calcula hashes e escopo final dos cinco ficheiros (2 modificados, 3 novos). Sem commit, push, deployment, database, MEI ou pagamento.

## Critério de venda

Ainda faltam: prova de cobertura legal e exceções; relação auditada entre L2 e ADR-020; NF-e real com autorização; conferência de EFD/tributos recolhidos; recálculo independente; dossiê com risco e revisão especializada. O próximo milestone deve ser **um piloto E2E de diagnóstico de âmbito contratualmente limitado**, não mais uma prateleira documental indefinida.
