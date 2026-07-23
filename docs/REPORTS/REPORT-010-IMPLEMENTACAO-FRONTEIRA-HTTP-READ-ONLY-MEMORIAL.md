# REPORT-010 — Implementação da Fronteira HTTP Read-Only do Memorial

**Estado:** RATIFICADO — AGUARDA STAGE EXCLUSIVO, COMMIT CONTROLADO E PUSH
**Data:** 2026-07-23
**Missão:** MISSION-010 / B14-SVC-06
**Branch:** `main`
**Baseline:** `HEAD = origin/main = b6450f50592b06d8f684b5520eb9a808a5314270`

## 1. Estado inicial e preflight

O stage estava vazio. O estado inicial observado foi exactamente:

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
```

Os quatro ficheiros autorizados existiam. O REPORT-010 e qualquer ficheiro
MISSION-010 estavam ausentes.

Hashes SHA-256 protegidos iniciais:

| Ficheiro | SHA-256 |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

## 2. Fontes consultadas

- `docs/ADR-018-FRONTEIRA-SOBERANA-MEMORIAL.md`;
- `docs/REPORTS/REPORT-009-AUDITORIA-PRE-IMPLEMENTACAO-FRONTEIRA-MEMORIAL.md`;
- os quatro ficheiros autorizados;
- `app/security.py` para confirmar a reutilização de
  `verificar_acesso_relatorio`;
- `app/models.py` apenas para confirmar os modelos envolvidos.

## 3. Escopo exacto

Foram alterados exactamente:

- `app/routes/relatorio_router.py`;
- `app/services/memorial_service.py`;
- `tests/test_ops12_f6_memorial_contract.py`;
- `tests/test_e2e_bloco2_memorial.py`.

Foi criado exactamente este relatório. Nenhum outro ficheiro foi criado,
alterado, apagado, movido, renomeado ou formatado pela missão.

## 4. Fase RED

Os testes foram escritos antes do código produtivo.

```text
python -m pytest -q tests/test_ops12_f6_memorial_contract.py
exit code: 1
resultado: 20 failed, 3 passed
duração pytest: 2.63s
```

Falhas relevantes: ausência de `obter_preflight_memorial`; eventos começavam
em `C` em vez de `P`; 403/402 eram decididos depois do colector; autorização
por empresa falhava; os caminhos 200 atingiam o fail-fast de
`marcar_memorial_gerado`; a prova directa das quatro colunas não existia.

```text
python -m pytest -q tests/test_e2e_bloco2_memorial.py -k memorial
exit code: 1
resultado: 3 failed, 3 passed
duração pytest: 2.43s
```

Falhas relevantes: os dois GET PDF 200 persistiam
`memorial_gerado=True`. O terceiro caso RED expôs uma interacção de cleanup
do fixture aninhado; a observação do estado foi colocada antes desse cleanup,
sem alteração de fixture global.

## 5. Implementação

`MemorialPreflight` é um `NamedTuple` imutável com exactamente `id`,
`user_id`, `empresa_id` e `pago`.

`obter_preflight_memorial` selecciona explicitamente apenas as quatro colunas
de `RelatorioAnalise`, devolve `None` quando não encontra row e não autoriza,
não materializa contexto rico e não escreve.

As rotas JSON e PDF executam:

```text
autenticação
→ preflight mínimo
→ 404
→ verificar_acesso_relatorio
→ 403 público "Acesso negado."
→ pagamento
→ 402
→ colector rico
→ 404 em desaparecimento concorrente
→ JSON ou gerador PDF
→ resposta
```

Somente excepções 403 da política partilhada são normalizadas para a mensagem
pública histórica. Outras excepções não são convertidas.

As duas chamadas de `marcar_memorial_gerado` e o seu import na rota foram
removidos. A função e a coluna históricas permanecem. Não há `commit`,
`flush` ou `rollback` no fluxo GET.

## 6. Compatibilidade e testes

Foram preservados o shape JSON rico, as mensagens 404/403/402, os bytes
produzidos pelo gerador existente, `application/pdf` e
`attachment; filename=memorial-{relatorio_id}.pdf`.

O contrato cobre JSON e PDF para 401, 404, 403 sem empresa, 403 por empresa
alheia, 402 por criador, 402 por empresa, 200 por criador, 200 por empresa e
desaparecimento entre preflight e colector. PDF cobre ainda falha do gerador,
bytes, media type e filename. Eventos explícitos provam `P`, `E`, `C` e `G`.
`commit`, `flush`, `rollback` e marcação são fail-fast por `AssertionError`.

A prova directa do preflight confirma inexistente `None`, retorno exacto,
`empresa_id=None`, `pago=False`, `pago=True`, imutabilidade e os quatro
argumentos exactos de `Session.query`.

O E2E real prova 402 sem mutação, 200 PDF sem mutação e actor alheio bloqueado.
A autorização por proprietário da empresa com `user_id` diferente permanece
provada no contrato HTTP. O fixture global não fornece esse estado de forma
íntegra sem alteração fora do escopo.

## 7. Resultados pós-implementação

```text
python -m pytest -q tests/test_ops12_f6_memorial_contract.py
exit code: 0
23 passed
failed: 0; skipped: 0; warnings reportados: 0
duração pytest: 0.46s
```

```text
python -m pytest -q tests/test_e2e_bloco2_memorial.py -k memorial
exit code: 0
6 passed
failed: 0; skipped: 0; warnings reportados: 0
duração pytest: 2.01s
```

```text
python -m pytest -q
exit code: 0
2358 passed, 8 skipped, 5 warnings
duração pytest: 76.98s
```

As cinco warnings globais são deprecações preexistentes: uma sequência de
escape em `danfe_pdf_adapter.py` e quatro usos indirectos de
`HTTP_422_UNPROCESSABLE_ENTITY`.

## 8. Matriz de ficheiros e exclusões

| Ficheiro/grupo | Resultado |
|---|---|
| quatro ficheiros autorizados | alterados |
| este REPORT-010 | criado |
| `app/security.py`, modelo, base e dashboard | inalterados |
| gerador PDF | inalterado e reutilizado |
| ADR-018 e REPORT-009 | inalterados |
| agentes, adapter e teste protegidos | inalterados pela missão |
| migrations | nenhuma criada ou alterada |
| projector/reader/registry/scheduler/LLM | não criados nem integrados |

Pesquisa exacta nos dois ficheiros produtivos não encontrou
`MemorialValidatorAgent`, `MemorialValidatorContext`, `run_mission`,
`registry`, `scheduler`, projector ou adapter L3.

## 9. Hashes finais

Hashes protegidos finais são idênticos aos iniciais:

| Ficheiro | SHA-256 |
|---|---|
| `app/agents/adapters/ag_encerramento.py` | `FDEAF1214EAEE4C3F92C08D6989581BF64A31A4BB2C2815F7027CBC57998527A` |
| `app/agents/engines/ag_encerramento.py` | `640F39160A545E3B1EE9135089D9113FCFA3293DFF9E423E5C96DA78A3A9ECA7` |
| `docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md` | `683A263E3FFB07ED88A5E72501705FAC9A54299D141BDE5024A78515D731E969` |
| `tests/test_ag_encerramento_mission_adapter.py` | `04FA3310D73CE86554380F378511A5E3589B398EB2B824694C173FA53D349CAF` |

Hashes dos quatro ficheiros implementados:

| Ficheiro | SHA-256 |
|---|---|
| `app/routes/relatorio_router.py` | `BEB2705858E0241906B6077D171D9CA6783DBD0A968A11D93AE00EAFA76BC110` |
| `app/services/memorial_service.py` | `89A7A3F5C0148E2ADB3A11C8FE911751F075098A1130E6B7D26BB39746CF098C` |
| `tests/test_ops12_f6_memorial_contract.py` | `AB40ABC12E7C6C830F4ECFFDA38976996AA3305661E9CDFFB4641B44067CB4DA` |
| `tests/test_e2e_bloco2_memorial.py` | `D01D3716BD43C77B209409A03FA49B3E63BE42FD02ABEB88F08819E907277665` |

O SHA-256 deste REPORT-010 é calculado externamente após a sua finalização e
registado no handoff, evitando auto-referência impossível.

## 10. Verificações finais e estado Git

`git diff --check` dos quatro ficheiros implementados passou sem erro.
O REPORT-010 não rastreado foi também inspeccionado separadamente quanto a
whitespace. O stage permaneceu vazio.

Estado final esperado e observado:

```text
 M app/agents/adapters/ag_encerramento.py
 M app/agents/engines/ag_encerramento.py
 M app/routes/relatorio_router.py
 M app/services/memorial_service.py
 M docs/ADR-008-AGENTES-CONTRATOS-SOBERANOS.md
 M tests/test_ag_encerramento_mission_adapter.py
 M tests/test_e2e_bloco2_memorial.py
 M tests/test_ops12_f6_memorial_contract.py
?? docs/REPORTS/REPORT-010-IMPLEMENTACAO-FRONTEIRA-HTTP-READ-ONLY-MEMORIAL.md
```

`HEAD` e `origin/main` permaneceram no baseline. Nenhum `git add`, commit,
push ou deploy foi executado.

## 11. Riscos e blockers

O preflight e a materialização rica não são snapshot atómico. A missão prova
a ordem normal das chamadas, mas não elimina TOCTOU sob mudança concorrente
de propriedade ou pagamento. Não foi introduzido lock, isolamento ou política
transaccional; a decisão fica para futura ADR/missão.

Não há blockers de implementação ou teste. GPT concluiu auditoria integral
VERDE e Miguel ratificou em 2026-07-23.

## 12. Classificação

**RATIFICADO — AGUARDA STAGE EXCLUSIVO, COMMIT CONTROLADO E PUSH**

## 13. Rectificação controlada B14-SVC-06

A prova MG foi rectificada sem alteração dos dois ficheiros produtivos e sem
alteração de fixtures globais. O objecto local desligado
`mg = {"value": False}` e as suas asserções probatoriamente vazias foram
removidos.

Os casos 200 JSON, 200 PDF e falha controlada do gerador PDF verificam agora
directamente que `contexto["relatorio"]["memorial_gerado"]` permanece
`False`. O fail-fast de `marcar_memorial_gerado` e os fail-fast de `commit`,
`flush` e `rollback` foram preservados. O E2E real permaneceu inalterado e
continua a constituir a prova persistente.

Testes reexecutados na rectificação:

```text
python -m pytest -q tests/test_ops12_f6_memorial_contract.py
exit code: 0
23 passed in 0.52s
failed: 0
```

```text
python -m pytest -q tests/test_e2e_bloco2_memorial.py -k memorial
exit code: 0
6 passed in 2.20s
failed: 0
```

```text
python -m pytest -q
exit code: 0
2358 passed, 8 skipped, 5 warnings in 79.77s
failed: 0
```

Os quatro ficheiros protegidos mantiveram exactamente os hashes SHA-256
iniciais registados nas secções 1 e 9. Os dois ficheiros produtivos e o E2E
real mantiveram os hashes registados na secção 9. O hash final do teste
rectificado é:

| Ficheiro rectificado | SHA-256 |
|---|---|
| `tests/test_ops12_f6_memorial_contract.py` | `AB40ABC12E7C6C830F4ECFFDA38976996AA3305661E9CDFFB4641B44067CB4DA` |
| `docs/REPORTS/REPORT-010-IMPLEMENTACAO-FRONTEIRA-HTTP-READ-ONLY-MEMORIAL.md` | calculado externamente após a finalização e registado no handoff |

O risco TOCTOU descrito na secção 11 mantém-se integralmente. O stage
permaneceu vazio. Nenhum `git add`, commit, push ou deploy foi executado
durante a rectificação.

## 14. Preparação criptográfica e pós-quântica

Os hashes SHA-256 desta missão servem exclusivamente como evidência de
integridade byte a byte dos ficheiros.

Não constituem assinatura, prova de autoria, identidade, proveniência,
não repúdio, timestamp confiável ou protecção pós-quântica.

Esta missão não cria nem altera criptografia, JWT/OAuth, assinatura,
canonicalização, gestão de chaves ou transporte protegido.

Qualquer futura evidência assinada deverá entrar por fronteira própria,
versionada, substituível e ratificada em ADR, contendo no mínimo:

```text
algorithm_id
algorithm_version
key_id
canonicalization_version
signature_format
signature
signed_at
```

Nenhuma alegação de segurança pós-quântica é produzida por esta missão.

## 15. Ratificação pós-auditoria

GPT concluiu auditoria integral VERDE e Miguel ratificou em 2026-07-23.

RATIFICO O REPORT-010 E A IMPLEMENTAÇÃO B14-SVC-06.
