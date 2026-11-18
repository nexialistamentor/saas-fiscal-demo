# SOLVERIS Enterprise — escopo proposto V4.3 após gate global V4.2 (18/11/2026)

**Estado: PROPOSTO / NÃO EXECUTADO.** Complementa `docs/B03_B04_DIAGNOSTICO_GLOBAL_V42_JUNIT_20261118.md`. O estado global V4.2 continua `BLOCKED`; nenhum `GLOBAL_GREEN`, merge em `main`, deploy ou alteração fiscal é autorizado por este documento.

## Evidência de entrada

- Gates dirigidos V4.2: 73/73 históricos e 80/80 funcionais GREEN nas saídas Windows.
- Candidato global: 84 FAIL, 4542 PASS, 17 SKIP, 40 subtestes; 13 falhas históricas presentes + **71 falhas novas**.
- JUnit ratificado baseline: declarado 4136; `testcase` 4102; diferença 34 = 34 subtestes informados; duplicados 0.
- JUnit candidato: declarado 4683; `testcase` 4643; diferença 40 = 40 subtestes informados; duplicados 0.
- A coincidência aritmética **não é por si só prova de completude**. O gate V2 congelado bloqueia corretamente até reconciliação verificável.

## Quatro trabalhos isolados com prova negativa

1. **B01/MEI, guarda sintática sem alteração de autoridade.** A guarda histórica `if empresa_id:` do `InsightEngine` foi trocada por `if empresa_id and not enterprise_opt_in:`. O scanner MEI exige a primeira forma AST, causando pelo menos 61 mensagens `empresa_guard`, no conjunto de 69 falhas novas de alcance MEI. Testar a alternativa `if empresa_id:` externa com `if not enterprise_opt_in:` interna, provando: fluxo MEI original preservado; opt-in Enterprise não chama insights; scanner alcança lineage real; sem editar scanner, relaxar sentinelas ou expor rota legada. Não afirmar antecipadamente que toda a cascata de 69 fica fechada.
2. **Hash canónico, testes-only versionado.** O scanner original detetou dois usos: `tests/test_enterprise_g19_local_cas_custody.py:267` (SHA-256 direto do PDF temporário) e `tests/test_enterprise_recovery_test_gate.py:205` (SHA-256 direto de XML temporário). Substituir apenas as asserções dos testes por equivalentes que mantenham a prova sem violar o helper; não alterar o scanner nem normalizar fontes reais.
3. **JUnit/subtestes, catraca derivada nova e fail-closed.** Não modificar `tools/enterprise_recovery_test_gate.py` congelado. Identificar no próprio XML ou em evidência de execução verificável, ligada ao artefacto, a contabilização de subtestes, e testar explicitamente: diferença legítima, XML truncado com a mesma diferença aritmética, `testcase` duplicado, subteste inconsistente, digest divergente, IDs históricos perdidos e nova falha. Se não existir prova independente suficiente nos artefactos, STOP e pedir apenas inspeção dirigida do XML; não aceitar `difference == subtests` como atalho isolado.
4. **Hold Vercel vs teste legado — decisão separada.** `tests/test_solveris_mei_vercel_routing_contract_red.py` espera `{"main": false}`; o candidato contém adicionalmente `"recovery/enterprise-b00-b04-20261117": false`, proteção explícita do branch. Preservar o hold. Investigar a intenção do contrato e estruturar teste compatível com retenção de múltiplos branches **sem dar autorização de publicação**, sujeito a ratificação distinta se alterar a autoridade de release.

## Gate de saída V4.3

- Delta de código e testes inventariado com hashes/manifesto novo; V2, V3, V4, V4.1, V4.1.1 e V4.2 preservados.
- Testes dirigidos e negativos completos; teste MEI legado e circuitos B01/B03/B04 sem degradação.
- Execução global apenas **depois** do fecho dirigido, evitando repetir os 37 minutos prematuramente.
- Classificador global tem de recuperar os 13 IDs aceites, zero nova falha e contagens reconciliadas por prova independente. Mesmo com tudo GREEN local, promoção e deploy continuam condicionados a ato próprio de Miguel.
