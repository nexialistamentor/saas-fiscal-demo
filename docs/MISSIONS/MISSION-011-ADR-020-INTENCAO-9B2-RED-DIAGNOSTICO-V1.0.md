# MISSION-011 — ADR-020 — Intenção 9B2 — RED Diagnóstico da Coerência entre NormativeActivation e ActivationGeneration — Versão 1.0

## 1. Identificação

- Documento: `MISSION-011-ADR-020-INTENCAO-9B2-RED-DIAGNOSTICO-V1.0`
- Versão: `1.0`
- Data da proposta: `2026-08-04`
- Intenção: `ADR-020 9B2`
- Baseline publicada: `7e66fac40334720a99ad472d0aa6cd43a6171518`
- Diagnóstico de origem: `DIAGNOSTICO_9B2_CONCLUIDO_AGUARDA_INSTRUMENTO_DOCUMENTAL`

## 2. Estado

**PROPOSTA — NÃO RATIFICADA — NÃO EXECUTÁVEL**

Este documento não é autoridade executável. Depende cumulativamente de auditoria, congelamento, ratificação humana, registo da ratificação e publicação. Não autoriza qualquer alteração ou execução técnica enquanto permanecer neste estado.

A criação, a leitura, a auditoria ou o congelamento isolado desta proposta não concedem autoridade técnica. Este documento não inclui hash próprio; o seu SHA-256 deve ser calculado externamente após a fixação dos bytes.

## 3. Autoridade e baseline

No início da elaboração, `HEAD` e `origin/main` correspondiam exactamente à baseline publicada:

`7e66fac40334720a99ad472d0aa6cd43a6171518`

A árvore de trabalho estava limpa e nada estava staged.

A autoridade publicada para a ordenação documental é:

- Adenda: `docs/ADENDA-ADR-020-ORDENACAO-INTENCAO-9B2-ANTES-9B4-V1.0.md`;
- SHA-256 da Adenda: `26C67B4B74980A902BD96EFB8AABA6BFEB12E151DAA1BDF5A92B484921E026B1`;
- registo: `docs/REPORTS/REPORT-025-RATIFICACAO-ADENDA-ADR-020-ORDENACAO-9B2-9B4-V1.0.md`;
- SHA-256 do registo: `31E08E741BF7D2CFD3933BB2EC5DD0746296F479297AEBC81750B7D275196FA7`.

A ordem soberana publicada determina que 9B2 deve ser diagnosticada e formalizada antes de 9B4. Esta proposta subordina-se a essa ordem e não a amplia.

## 4. Contexto e diagnóstico

O diagnóstico read-only concluiu:

`DIAGNOSTICO_9B2_CONCLUIDO_AGUARDA_INSTRUMENTO_DOCUMENTAL`

Foi observada a ausência de mecanismo físico que imponha que a tripla declarada por `NormativeActivation`:

- `activation_generation_id`;
- `activation_decision_id`;
- `activation_decision_record_hash`;

corresponda à mesma tripla soberana persistida em `ActivationGeneration`.

O baseline permite construir relações individualmente válidas em que duas decisões exactas distintas `D1/H1` e `D2/H2` existem, `E1` pertence a `D1/H1`, `G1` pertence a `E1` e `D1/H1`, e uma `NormativeActivation` referencia `G1` e `E1`, mas declara `D2/H2`. Nesse cenário, subject e review permanecem válidos, o vínculo entre N e G é válido, o vínculo declarado entre N e `D2/H2` é válido, o vínculo entre N e E é válido, o trigger 0038 é satisfeito e a FK 0039 de G é satisfeita. A cadeia é individualmente válida e globalmente incoerente em 9B2.

Não existe actualmente RED específico para provar fisicamente essa falsidade.

## 5. Objectivo

Após esta proposta ser auditada, congelada, ratificada humanamente, ter a ratificação registada e ser publicada, o objectivo único da futura execução será criar e executar um único RED PostgreSQL que prove fisicamente que o baseline publicado aceita uma `NormativeActivation` cuja decisão exacta difere da decisão exacta da `ActivationGeneration` associada.

A futura missão termina após a prova RED e o respectivo encerramento documental. Não autoriza GREEN.

## 6. Invariável 9B2 a provar

A prova deverá isolar a seguinte coerência exacta:

```text
NormativeActivation.activation_decision_id
= ActivationGeneration.activation_decision_id

NormativeActivation.activation_decision_record_hash
= ActivationGeneration.activation_decision_record_hash
```

O par decisão ID/hash é cumulativo. A `NormativeActivation` associada a uma geração deve declarar exactamente a mesma decisão soberana dessa geração.

## 7. Cenário RED

O teste futuro deverá usar PostgreSQL na revision publicada:

`0039_adr020_gen_exec_decision_fk`

O caminho de escrita deverá ser SQLAlchemy Core. O cenário deverá construir:

1. duas decisões exactas, válidas e distintas, `D1/H1` e `D2/H2`;
2. uma execução `E1` pertencente a `D1/H1`;
3. uma geração `G1` pertencente a `E1` e `D1/H1`;
4. uma `NormativeActivation` coerente de controlo, `N_control`, com:
   - `activation_generation_id = G1`;
   - `activation_execution_id = E1`;
   - `activation_decision_id = D1`;
   - `activation_decision_record_hash = H1`;
   - subject válido;
   - review válida;
5. uma segunda cadeia física independente quando necessária para evitar colisões de cardinalidade, `UNIQUE` ou consumo do mesmo objecto;
6. uma `NormativeActivation` falsa, `N_false`, com:
   - `activation_generation_id` referenciando uma geração pertencente a `D1/H1`;
   - `activation_execution_id` referenciando exactamente a execução dessa geração;
   - `activation_decision_id = D2`;
   - `activation_decision_record_hash = H2`;
   - subject e review válidos;
   - todas as demais colunas e bindings válidos.

## 8. Falsidade única

A única falsidade soberana deverá ser:

`NormativeActivation` declara `D2/H2` enquanto a `ActivationGeneration` associada declara `D1/H1`.

Deverá permanecer verdadeiro que:

- a geração existe;
- a decisão `D2/H2` existe;
- a execução existe;
- `NormativeActivation` e `ActivationGeneration` apontam para a mesma execução;
- G e E pertencem à mesma decisão exacta `D1/H1`;
- subject e review são válidos;
- hashes, estados, cardinalidades e restantes contratos são válidos.

Identificadores, `record_hashes`, `idempotency_keys`, `scope_hashes`, `composition_hashes` e demais valores deverão ser distintos quando os contratos existentes o exigirem. Todos os identificadores deverão respeitar os limites físicos das colunas. Nenhum objecto poderá ser reutilizado quando isso provocar colisão alheia à falsidade 9B2.

## 9. Controlo positivo

Antes da tentativa de inserir `N_false`, o teste deverá persistir e confirmar `N_control` como uma `NormativeActivation` coerente. O controlo positivo é obrigatório e não poderá ser removido.

A persistência do controlo deverá demonstrar que fixture, baseline, decisões, execução, geração, subject, review e bindings válidos alcançaram correctamente o ponto exacto da prova.

## 10. Separação de 9B4

O teste não poderá introduzir divergência entre:

`NormativeActivation.activation_execution_id`

e:

`ActivationGeneration.activation_execution_id`.

Ambas deverão apontar para `E1`. O teste também não poderá depender de verificar a decisão directamente contra `ActivationExecution` como objecto autónomo da falsidade.

A intenção 9B4 permanece separada, posterior, fora do escopo e dependente de autoridade documental própria.

## 11. Escopo técnico futuro

O único ficheiro técnico que poderá ser modificado na futura execução RED é:

`tests/test_adr020_activation_postgresql.py`

O nome exacto do único teste futuro é:

`test_normative_activation_rejects_generation_from_different_exact_decision_via_core`

Nenhum segundo ficheiro técnico poderá ser alterado. Não estão autorizados:

- `app/models.py`;
- migration 0040;
- qualquer migration;
- código de aplicação;
- listener;
- trigger;
- constraint;
- função PostgreSQL;
- documentação adicional durante a execução técnica, salvo relatório separado posterior autorizado pelo fluxo institucional.

## 12. Fixture e baseline

A futura implementação deverá reutilizar a infraestrutura PostgreSQL existente com alvo final `0039_adr020_gen_exec_decision_fk`.

Será permitida somente a adaptação mínima da fixture ou constante necessária dentro de `tests/test_adr020_activation_postgresql.py`. Fixtures destinadas a revisions anteriores não poderão ser contaminadas. Não será criada migration 0040.

## 13. Comando exacto

O único comando futuro RED é:

```text
python -m pytest tests/test_adr020_activation_postgresql.py::test_normative_activation_rejects_generation_from_different_exact_decision_via_core -q
```

A inserção de `N_false` deverá ser envolvida por:

```python
with pytest.raises(DBAPIError):
    ...
```

No baseline 0039, a inserção deverá ser aceite e o teste deverá falhar exactamente por ausência da excepção esperada, de forma equivalente a:

```text
Failed: DID NOT RAISE <class 'sqlalchemy.exc.DBAPIError'>
```

## 14. Critérios de RED válido

A futura execução somente poderá declarar RED válido quando provar cumulativamente:

1. PostgreSQL iniciado correctamente;
2. revision final 0039 aplicada;
3. controlo positivo persistido;
4. `D1/H1` e `D2/H2` válidas;
5. E e G coerentes em `D1/H1`;
6. `N_false` aponta para a mesma G e E;
7. `N_false` declara `D2/H2`;
8. subject e review válidos;
9. inserção falsa aceite pelo banco;
10. teste falha somente por `DID NOT RAISE DBAPIError`;
11. nenhum ficheiro fora do escopo alterado;
12. nada staged;
13. nenhuma solução GREEN implementada.

## 15. Critérios de bloqueio

Não constitui RED válido qualquer resultado causado por:

- falha de fixture;
- erro de comprimento;
- colisão de `UNIQUE`;
- FK ausente;
- subject inválido;
- review inválida;
- execução divergente;
- erro de hash;
- erro de estado;
- erro de schema;
- erro de migration;
- erro de container;
- qualquer falha anterior à inserção falsa;
- qualquer rejeição produzida por mecanismo diferente da coerência 9B2 ainda inexistente.

Qualquer desses resultados bloqueia a declaração de RED válido e não autoriza reparação fora do escopo, ampliação da missão ou selecção de GREEN.

## 16. Preservação do RED

Após RED válido:

- não corrigir o teste;
- não implementar migration;
- não modificar models;
- não seleccionar automaticamente solução física;
- preservar os bytes do teste RED;
- manter nada staged;
- não implementar qualquer GREEN não autorizado.

O teste RED deverá permanecer como evidência física da lacuna até existir autoridade própria posterior.

## 17. Encerramento documental

Após a prova RED válida, deverá ser realizada auditoria read-only e criado relatório separado de encerramento do RED, mediante o fluxo institucional autorizado. O encerramento deverá ser congelado e publicado.

A futura missão termina após a prova RED e o respectivo encerramento documental. Somente depois poderá ser proposta missão GREEN própria. O relatório de ratificação e o relatório de encerramento não são criados nesta rodada.

## 18. Opções GREEN não ratificadas

O diagnóstico identificou, de forma não vinculante, possibilidades técnicas futuras:

- `UNIQUE` candidata em `ActivationGeneration` combinada com FK composta;
- FK composta directa quando já existir candidata adequada;
- trigger PostgreSQL;
- constraint trigger;
- listener ORM;
- validação de aplicação.

Nenhuma opção foi seleccionada. Nenhuma opção foi ratificada. A missão RED não poderá implementar qualquer delas. A escolha futura dependerá da evidência RED e de autoridade própria.

## 19. Divergências fora do escopo

Registam-se como observações não accionáveis nesta missão:

- `fk_normative_activations_activation_generation` existe fisicamente desde 0037, mas não está representada na metadata;
- `uq_activation_decisions_exact` existe fisicamente desde 0024, mas não está representada na metadata;
- `uq_activation_generations_exact` existe fisicamente desde 0024, mas não está representada na metadata.

Estas divergências não resolvem 9B2, não deverão ser corrigidas nesta missão, não autorizam ampliação do escopo e deverão permanecer preservadas para decisão própria futura.

## 20. Migrations preservadas

As seguintes migrations históricas deverão permanecer integralmente inalteradas:

- `0024_adr020_activation_foundation.py`;
- `0029_adr020_activation_execution_gate.py`;
- `0035_adr020_normative_activation_subject_gate.py`;
- `0036_adr020_normative_activation_review_gate.py`;
- `0037_adr020_activation_generation_fk.py`;
- `0038_adr020_normative_activation_generation_execution_gate.py`;
- `0039_adr020_activation_generation_decision_execution_fk.py`.

## 21. Proibições

Permanecem proibidos nesta rodada documental e não são autorizados pela futura execução RED:

- criação de REPORT nesta rodada;
- criação ou execução do teste nesta rodada;
- modificação de código ou models;
- criação ou modificação de migration;
- execução de pytest, Alembic ou containers nesta rodada;
- solução GREEN;
- alteração de listener, trigger, constraint ou função PostgreSQL;
- staging, commit ou push pelo executor;
- deploy, Railway ou produção;
- activação do motor ADR-020 ou abertura de gates;
- endpoints, workers, scheduler ou dispatcher;
- 9B4;
- 9C;
- 8B2;
- `MIGRATION-BOOTSTRAP-0000-0001`;
- `docs/ROADMAP_OPS_AGENTES.md`;
- qualquer melhoria oportunista ou ficheiro não expressamente autorizado.

## 22. Estado final

Esta MISSION-011 permanece uma proposta documental não ratificada e não executável. Não é autoridade executável, não autoriza alteração técnica enquanto permanecer neste estado e depende de auditoria, congelamento, ratificação humana, registo da ratificação e publicação.

Não existe autorização GREEN. A futura autoridade, se concedida pelo fluxo institucional completo, ficará limitada ao único teste RED, no único ficheiro técnico indicado, e ao encerramento documental posterior separado.

Este documento não inclui hash próprio.

## 23. Veredicto

`MISSION_011_PROPOSTA_RED_9B2_AGUARDA_AUDITORIA_E_RATIFICACAO`
