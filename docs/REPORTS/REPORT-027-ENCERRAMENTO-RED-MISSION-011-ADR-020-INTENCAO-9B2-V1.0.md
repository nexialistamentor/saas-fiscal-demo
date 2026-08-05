# REPORT-027 — Encerramento do RED da MISSION-011 — ADR-020 — Intenção 9B2 — Versão 1.0

## 1. Identificação

- Relatório: `REPORT-027`
- Versão: `1.0`
- Intenção: `ADR-020 9B2`
- Natureza: encerramento documental exclusivo da fase RED diagnóstica

## 2. Estado documental

PROPOSTA DE ENCERRAMENTO — AGUARDA AUDITORIA, CONGELAMENTO, RATIFICAÇÃO HUMANA E PUBLICAÇÃO — GREEN NÃO AUTORIZADO

Este relatório encerra exclusivamente a fase RED diagnóstica da MISSION-011. Não declara a intenção 9B2 tecnicamente encerrada em produção, não declara a lacuna corrigida e não autoriza implementação GREEN.

## 3. Baseline publicado

No momento deste encerramento documental, o baseline publicado foi confirmado exactamente:

- `HEAD`: `5efe9723ba69a235d0939a4569186d0e06e5b852`
- `origin/main`: `5efe9723ba69a235d0939a4569186d0e06e5b852`

## 4. Autoridade documental

O RED foi autorizado pela seguinte cadeia documental publicada:

- MISSION-011: `docs/MISSIONS/MISSION-011-ADR-020-INTENCAO-9B2-RED-DIAGNOSTICO-V1.0.md`
- SHA-256 da MISSION-011: `88ED6A40C23BF4E5E1BC2BD8764500FFD2A9F02D391518D6947D30E2C3EC361E`
- REPORT-026: `docs/REPORTS/REPORT-026-RATIFICACAO-MISSION-011-ADR-020-INTENCAO-9B2-V1.0.md`
- SHA-256 do REPORT-026: `512BC3EB37EB537CA2D0B06120BB29D001EC69152173E72D07810112826901FB`

As identidades criptográficas foram confirmadas antes da criação deste relatório.

## 5. Artefacto RED congelado

- Ficheiro: `tests/test_adr020_activation_postgresql.py`
- Tamanho: `254789 bytes`
- SHA-256: `B32DB5CE6DB7C3B5FA1350691C03D0FEE73E5A4D5B77CBC3C4871264723D52C7`
- Teste exacto: `test_normative_activation_rejects_generation_from_different_exact_decision_via_core`
- Fixture: `postgresql_intention_9b3`
- Revision PostgreSQL: `0039_adr020_gen_exec_decision_fk`
- Caminho de escrita: SQLAlchemy Core

O teste permanece local, modificado, não staged e integralmente preservado nos bytes congelados.

## 6. Cenário técnico executado

O teste constrói duas decisões exactas, válidas e distintas, `D1/H1` e `D2/H2`.

A cadeia de controlo contém `E_control` e `G_control` coerentes em `D1/H1`. A activação `N_control` também é coerente em `D1/H1`. `N_control` foi persistida e a sua persistência foi confirmada antes da tentativa de inserção falsa.

A cadeia destinada à prova contém `E_false` e `G_false` coerentes em `D1/H1`. `N_false` referencia exactamente `E_false` e `G_false`; `N_false` e `G_false` usam a mesma `activation_execution_id`. Ao mesmo tempo, `N_false` declara a decisão exacta distinta `D2/H2`. O subject e a review de `N_false` são válidos.

Somente a inserção de `N_false` está dentro de `pytest.raises(DBAPIError)`. A preparação das decisões, execuções, gerações e do controlo positivo, bem como a persistência e confirmação de `N_control`, ocorre fora desse bloco.

## 7. Controlo positivo

O controlo positivo demonstrou que a fixture PostgreSQL, a revision 0039, as decisões, a execução, a geração, o subject, a review e os restantes bindings válidos alcançaram o ponto exacto da prova. `E_control`, `G_control` e `N_control` permaneceram coerentes em `D1/H1`, e `N_control` foi persistida e confirmada antes da tentativa falsa.

## 8. Cadeia falsa e falsidade única

`E_false` e `G_false` pertencem coerentemente a `D1/H1`. `N_false` referencia exactamente essa geração e essa execução, usando a mesma `activation_execution_id` de `G_false`, mas declara `D2/H2`.

A única falsidade soberana é, portanto, a divergência entre a decisão exacta declarada por `N_false` e a decisão exacta de `G_false`. Nenhuma outra relação necessária ao cenário foi tornada falsa.

## 9. Execução manual e resultado observado

O comando manual exacto registado foi:

```text
python -m pytest tests/test_adr020_activation_postgresql.py::test_normative_activation_rejects_generation_from_different_exact_decision_via_core -q
```

O resultado observado foi:

```text
FAILED
Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>
1 failed in 7.80s
```

O resultado exacto relevante é `DID NOT RAISE DBAPIError`. Trata-se da falha esperada e válida do RED; o teste não foi aprovado nem passou.

## 10. Interpretação soberana da falha

O PostgreSQL na revision `0039_adr020_gen_exec_decision_fk` aceitou a inserção de `N_false`. Como o controlo positivo persistiu, as duas decisões exactas eram válidas, a cadeia `E_false`/`G_false` era coerente em `D1/H1`, `N_false` referenciava exactamente essa geração e a mesma execução, subject e review eram válidos, e a única falsidade era `N_false` declarar `D2/H2`, a ausência de `DBAPIError` prova fisicamente a lacuna 9B2 no baseline publicado.

Esta conclusão diagnostica a lacuna. Não declara que a lacuna foi corrigida, não selecciona mecanismo GREEN e não encerra tecnicamente a intenção 9B2 em produção.

## 11. Auditoria independente

A auditoria independente read-only emitiu o veredicto:

`APTO_PARA_RELATORIO_DE_ENCERRAMENTO_RED_9B2`

O veredicto autoriza a elaboração desta proposta documental dentro do escopo recebido; não autoriza GREEN.

## 12. Separação obrigatória de 9B4

Nenhuma falsidade autónoma de 9B4 foi introduzida. `N_false` e `G_false` usam a mesma `activation_execution_id`, preservando a coerência de execução exigida. A intenção 9B4 permanece separada, posterior e fora do escopo deste encerramento.

## 13. Preservação do escopo técnico

- nenhum teste 9B3 ou helper global foi alterado;
- nenhuma migration 0040 foi criada;
- `app/models.py` não foi alterado;
- nenhuma migration existente foi alterada;
- nenhum mecanismo GREEN foi implementado;
- nenhum segundo ficheiro técnico foi alterado;
- o artefacto RED congelado não foi modificado durante esta elaboração.

No estado Git local anterior à criação deste relatório, somente `tests/test_adr020_activation_postgresql.py` aparecia modificado, correspondendo ao RED já congelado, e nada estava staged. Após a criação, o único novo ficheiro é este REPORT-027; nenhum ficheiro existente foi alterado por esta elaboração.

## 14. Ausência de GREEN

Não existe GREEN autorizado. Este relatório não autoriza implementação GREEN, não escolhe mecanismo físico e não autoriza qualquer correcção da lacuna.

A selecção de qualquer mecanismo GREEN exige instrumento documental posterior, independente e explicitamente ratificado. Até à publicação dessa autoridade própria, o teste RED deve permanecer preservado e a lacuna deve permanecer sem implementação correctiva.

## 15. Condições para futura abertura do GREEN

Uma futura abertura do GREEN depende cumulativamente de:

1. auditoria desta proposta de encerramento;
2. congelamento dos bytes deste relatório;
3. ratificação humana explícita deste encerramento;
4. registo e publicação dessa ratificação;
5. instrumento documental GREEN posterior e independente;
6. ratificação humana explícita desse instrumento posterior;
7. verificação do baseline e da integridade dos artefactos no momento futuro autorizado.

O cumprimento destas condições documentais não é presumido neste relatório.

## 16. Integridade documental e Git

As validações read-only posteriores à escrita devem confirmar que somente este REPORT-027 foi criado, que o teste congelado manteve tamanho e SHA-256, que nenhum ficheiro existente foi alterado além do RED já congelado, que nada está staged e que `git diff --check` passa.

Este documento é produzido em UTF-8 sem BOM, somente com finais de linha LF, exactamente uma newline final e zero trailing whitespace. Não contém auto-hash; o seu tamanho e SHA-256 devem ser calculados externamente após a fixação dos bytes.

## 17. Estado final

O RED diagnóstico da MISSION-011 demonstrou validamente a lacuna 9B2 no baseline publicado e fica documentalmente encerrado apenas quanto à sua fase diagnóstica. A proposta aguarda auditoria, congelamento, ratificação humana e publicação. A intenção 9B2 não está declarada tecnicamente encerrada em produção e nenhum GREEN está autorizado.

## 18. Veredicto

`REPORT_027_CRIADO_AGUARDA_AUDITORIA_E_RATIFICACAO`
