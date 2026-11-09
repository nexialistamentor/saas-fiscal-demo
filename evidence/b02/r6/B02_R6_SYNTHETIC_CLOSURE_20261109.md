# R6 — ESTADO: B02_TECHNICAL_CLOSED_FISCAL_PENDING (sintetico, nao substitui real)
Data: 2026-11-09

## Contexto
R5 fechado na base real (solveris-pg17-migration-test, porta 55432) nesta mesma
sessao: dois documentos SEFA-PR persistidos, politica v8 (consolidacao v7-v12 do
isolado), activation B02-9d115d33-activation-v1. Normative artifacts reais:

- 101202501245: normative_artifact_id B02-G5-101202501245-V3-artifact,
  record_hash aeef111a38d7f97ca2b92dad105157f47a5e4038425c76b594fa8a64a1bd81bd,
  artifact_hash e7bc013d6195e904f780a6be78a1ea0d0ca0bdcff530fba9ec4baa4c348e6832
- 101201900571: normative_artifact_id B02-G5-101201900571-V3-artifact,
  record_hash 85e9d1240267f49150ccb74bc5e1efc347dcec0ff67d7d3aa1269c4671863009,
  artifact_hash af53bf64313fefa45e5ed490fdd7ca57e7b2d87116f2f74a1ba1ae0cff874a5d

## R6 — pipeline sintetico executado
Script: tools/b02_r6_synthetic_nfeproc_pipeline_v1.py
Fixture: tests/fixtures/b02_r6_synthetic_nfeproc_20261105.xml
Resultado real da execucao (2026-11-09):

{
  "status": "R6_SYNTHETIC_PIPELINE_ONLY_NOT_FISCAL",
  "synthetic_only": true,
  "xml_sha256": "9f4d773949d41ef394d8ca7c0203b95b4b0eff946000f5e618df25d0539d01dc",
  "items": [{"nItem": 1, "ncm": "12119090", "cest": "2000100", "cfop": "5102",
             "description": "Henna EXEMPLO SINTETICO SEM VALIDADE FISCAL"}],
  "fiscal_authority_verified": false,
  "real_fiscal_link_completed": false,
  "r7_real_consumer_eligible": false
}

## Declaracao explicita
Este resultado NAO constitui vinculo fiscal real. Nao ha ExtractionResult
conclusivo, RuleVersion vinculada, nem item de NF-e real associado aos
normative_artifacts acima. mva_pr_12119090 permanece vazio na base real
(confirmado por leitura direta em 2026-11-09). R6 fica classificado como
B02_TECHNICAL_CLOSED_FISCAL_PENDING: desbloqueia o fecho tecnico do B02 (R7),
mas o vinculo fiscal real desta materia (NCM 12119090/27121000/28142000,
resolucoes SEFA-PR 571/2019 e 1245/2025) fica pendente para quando houver
caso real com esses NCMs.

Foi considerado usar um NF-e real da SOLVERIS LTDA (CNPJ 68573368000182,
Capanema/PA, NF-e 15260909019077000188550010000048061116345299) mas o item
(ONT GPON WiFi6, equipamento de telecomunicacoes) nao tem NCM pertinente a
esta materia normativa especifica — nao substitui o sintetico para este
proposito.

Decisao de Miguel: avancar com R6 sintetico (via 1), em vez de procurar NF-e
real com NCM pertinente, para nao bloquear o fecho tecnico.