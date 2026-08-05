# REPORT-030 — Fechamento Técnico da MISSION-012 — ADR-020 — Intenção 9B2 — Versão 1.0

## Estado

FECHAMENTO TÉCNICO PROPOSTO — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO

## 1. Identificação

- Documento: `REPORT-030-FECHAMENTO-TECNICO-MISSION-012-ADR-020-INTENCAO-9B2-V1.0`
- Versão: `1.0`
- Estado: `FECHAMENTO TÉCNICO PROPOSTO — AGUARDA AUDITORIA, CONGELAMENTO E PUBLICAÇÃO`
- Intenção: `ADR-020 9B2`
- Branch: `main`
- Commit/HEAD publicado e validado: `868d5abec642865c7839eb02ea53db5f895b1002`
- Mensagem do commit: `feat(adr020): enforce exact normative generation decision binding`

Este relatório documenta a implementação e a validação técnica da intenção 9B2. Não cria, altera, reinterpreta ou amplia autoridade, contratos canónicos, invariantes, política fiscal ou regras de negócio. Este relatório ainda não é canónico nem publicado.

## 2. Autoridade e cadeia documental preservada

A execução e o presente fechamento preservam, sem alteração retroactiva, os seguintes instrumentos:

1. MISSION-012:
   - caminho: `docs/MISSIONS/MISSION-012-ADR-020-INTENCAO-9B2-GREEN-NORMATIVE-GENERATION-V1.0.md`;
2. REPORT-029:
   - caminho: `docs/REPORTS/REPORT-029-RATIFICACAO-MISSION-012-ADR-020-INTENCAO-9B2-V1.0.md`.

A implementação validada limita-se aos dois ficheiros técnicos do commit:

1. `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
2. `tests/test_adr020_activation_postgresql.py`.

Este fechamento não modifica retroactivamente a MISSION-012, o REPORT-029 ou qualquer outro elemento da cadeia 9B2.

## 3. Identidade da implementação validada

A implementação foi publicada e validada na branch `main`, no commit/HEAD:

`868d5abec642865c7839eb02ea53db5f895b1002`

Mensagem exacta:

`feat(adr020): enforce exact normative generation decision binding`

Os ficheiros técnicos exactos desse commit são:

- `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
- `tests/test_adr020_activation_postgresql.py`.

## 4. Identidade da migration 0040

- Caminho: `migrations/versions/0040_adr020_norm_gen_decision_fk.py`;
- tamanho: `1493 bytes`;
- SHA-256: `FE1A8F23516A3B36FD3A26DAC93B0E7C546BD6846B97C2EBB2FE4E84D4ABCDFA`;
- revision: `0040_adr020_norm_gen_decision_fk`;
- down revision: `0039_adr020_gen_exec_decision_fk`;
- dialecto exclusivo: PostgreSQL;
- `UNIQUE`: `uq_activation_generations_generation_exact_decision`;
- FK composta: `fk_normative_activations_generation_exact_decision`.

A `UNIQUE`, as colunas locais da FK composta e as colunas referenciadas usam a mesma ordem exacta:

1. `activation_generation_id`;
2. `activation_decision_id`;
3. `activation_decision_record_hash`.

O contrato físico da FK composta é cumulativamente:

- `MATCH SIMPLE`;
- `ON UPDATE RESTRICT`;
- `ON DELETE RESTRICT`;
- `NOT DEFERRABLE`;
- `INITIALLY IMMEDIATE`;
- `NOT VALID`.

A FK simples preexistente `fk_normative_activations_activation_generation` foi preservada. O downgrade permanece explicitamente bloqueado por `RuntimeError`.

`activation_execution_id` não integra a `UNIQUE` nem a FK composta de 9B2. A sua garantia autónoma permanece separada e reservada à intenção 9B4.

## 5. Identidade e preservação do ficheiro de testes

- Caminho: `tests/test_adr020_activation_postgresql.py`;
- tamanho: `270649 bytes`;
- SHA-256: `2F8DD1DB5F2386865A8DE1D7152309D716DD9A74E848E04A4A923E24AA273E13`.

O RED congelado possui a identidade exacta seguinte:

- teste: `test_normative_activation_rejects_generation_from_different_exact_decision_via_core`;
- tamanho do bloco exacto: `7572 bytes`;
- SHA-256 do bloco exacto: `D038D8126AE1D41754284BF52C4C6CF606B914EE0469261A0E49A49969BFC2E8`.

O RED previamente congelado pela cadeia documental foi incorporado no commit `868d5abec642865c7839eb02ea53db5f895b1002` com identidade byte-for-byte coincidente com a linha de base congelada.

Foram acrescentados os dois testes GREEN seguintes:

1. `test_normative_generation_decision_fk_is_physical_and_not_valid`;
2. `test_normative_generation_decision_fk_is_prospective`.

Esses testes registam a prova física e prospectiva da nova garantia, incluindo a preservação da FK simples e a exclusão de `activation_execution_id` do mecanismo 9B2.

## 6. Gates executadas após resolução ambiental

As três gates foram executadas directamente no PowerShell, após a resolução do incidente ambiental descrito na secção 7.

### 6.1. Gate 1 — PostgreSQL de activação ADR-020

Comando exacto:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_adr020_activation_postgresql.py -q
```

Resultado exacto:

```text
178 passed, 29 warnings in 466.60s (0:07:46)
```

### 6.2. Gate 2 — suíte ADR-020

Comandos exactos:

```powershell
$files = Get-ChildItem .\tests -File -Filter "*adr020*.py" | Sort-Object FullName | ForEach-Object FullName
.\venv\Scripts\python.exe -m pytest @files -q
```

Escopo: `14 ficheiros ADR-020`.

Resultado exacto:

```text
357 passed, 7 skipped, 29 warnings in 470.03s (0:07:50)
```

### 6.3. Gate 3 — regressão global

Comando exacto:

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

Resultado exacto:

```text
2762 passed, 15 skipped, 966 warnings in 578.25s (0:09:38)
```

Após a recuperação ambiental, as três gates passaram integralmente.

### 6.4. Evidência independente capturada e congelada

Os resultados das secções 6.1–6.3 correspondem à execução directa anteriormente observada no PowerShell.

Para eliminar dependência de transcrição manual e evidência circular, as três gates foram posteriormente repetidas por capturador auditado, com:

- stdout bruto;
- stderr bruto;
- argv;
- exit code;
- timestamps UTC;
- duração monotónica;
- ambiente;
- inventários Git;
- tamanhos;
- SHA-256.

Identidade do capturador:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B2-REPORT-030-V1.0/CAPTURE.py`;
- tamanho: `32242 bytes`;
- SHA-256: `7DD5AE620041EFB3088BB3083E62EC186E3E0294760AC2F45833C9D6697F9EB1`.

Resultados exactos da captura independente:

Gate 1 — PostgreSQL:

- pytest: `178 passed, 29 warnings in 495.57s (0:08:15)`;
- skipped: `0`;
- duração monotónica: `500.0272683s`;
- exit code: `0`.

Gate 2 — ADR-020:

- pytest: `357 passed, 7 skipped, 29 warnings in 466.13s (0:07:46)`;
- duração monotónica: `470.4208446s`;
- exit code: `0`;
- lista materializada: exactamente 14 ficheiros `tests/*adr020*.py`, ordenados lexicalmente e idênticos ao argv executado.

Gate 3 — regressão global:

- pytest: `2762 passed, 15 skipped, 966 warnings in 557.49s (0:09:17)`;
- duração monotónica: `562.8887445s`;
- exit code: `0`.

Nenhuma das três capturas contém `failed` ou `error`. As durações pytest são distintas das durações monotónicas dos subprocessos. Os totais funcionais coincidem com as execuções directas anteriores, embora as durações sejam naturalmente diferentes.

Identidade do MANIFEST externo:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B2-REPORT-030-V1.0/MANIFEST.txt`;
- tamanho: `1507 bytes`;
- SHA-256: `E7C9DFB7777A01F8F6ED544C71B09BFF431AE6E8DA459CDDFA35D0D1BBD7A890`;
- contém 16 entradas;
- exclui o próprio MANIFEST;
- não contém hash do ZIP;
- não contém auto-hash.

Identidade do bundle ZIP:

- caminho: `docs/EVIDENCE/BUNDLE-EVIDENCIA-9B2-REPORT-030-V1.0.zip`;
- tamanho: `72064 bytes`;
- SHA-256: `96D11BFEAA5D475DB605976D5D4C8BCF4CAEFC018502F635206C8F59EEFE585E`;
- contém 17 membros;
- inclui o MANIFEST;
- não inclui a si próprio.

Resultado da auditoria:

- 17 ficheiros soltos canónicos;
- 16 entradas no MANIFEST;
- 17 membros no ZIP;
- nenhuma divergência bloqueante;
- nenhuma divergência não bloqueante;
- veredicto exacto: `BUNDLE_EVIDENCIA_9B2_APTO_PARA_VINCULACAO_DOCUMENTAL`.

Integridade observada:

- os 451 ficheiros rastreados protegidos de `app`, `migrations` e `tests` apresentaram caminhos, tamanhos e SHA-256 idênticos nas fotografias GIT-BEFORE e GIT-AFTER;
- nenhuma alteração rastreada ou staged foi observada;
- não se alega capacidade de detectar alterações transitórias posteriormente restauradas;
- CAPTURE.py permaneceu durante a execução com a identidade exacta registada no bundle: 32242 bytes e SHA-256 7DD5AE620041EFB3088BB3083E62EC186E3E0294760AC2F45833C9D6697F9EB1.
- O capturador calculou em memória uma fotografia hash do REPORT-030 antes das gates e verificou novamente, no fechamento, que os seus bytes não tinham mudado durante a execução.
- O tamanho e o SHA-256 exactos dessa versão do REPORT-030 não foram persistidos nos artefactos do bundle; por isso, o bundle prova invariância observada durante a execução, mas não materializa a identidade exacta do relatório naquele momento.

Após a captura, este REPORT-030 foi alterado documentalmente para vincular o bundle e para explicitar os limites temporais da evidência. A identidade exacta do estado final deste relatório será estabelecida externamente no acto de congelamento; o documento não contém nem reivindica auto-hash.

Proveniência ambiental:

- o ficheiro `INCIDENTE-AMBIENTAL-RETROSPECTIVO.txt` está explicitamente marcado como reconstrução retrospectiva;
- não é stdout bruto;
- não é usado como prova das novas gates.

Autoridade da evidência:

- para o fechamento documental final, o bundle congelado é a evidência independente vinculada;
- os resultados anteriores permanecem registo histórico válido da execução directa;
- o bundle não autoriza deploy, produção, Railway, motor, gates operacionais, endpoint, worker, scheduler ou dispatcher.

## 7. Incidente ambiental

A primeira repetição da Gate 1 foi interrompida por falta de espaço no disco do Windows/Docker. O erro ocorreu durante a criação de PostgreSQL isolado e não por falha funcional da migration 0040.

Para recuperar o ambiente, foram removidos containers PostgreSQL efémeros e volumes Docker anónimos órfãos. O Docker reportou `160.5 GB` recuperados internamente. O VHDX `docker_data.vhdx` foi compactado de `148.15 GB` para `11.70 GB`, e o disco `C:` ficou com `141.68 GB` livres.

Concluída a recuperação ambiental, as três gates foram repetidas ou executadas no ambiente recuperado e passaram integralmente. O incidente é ambiental e não é atribuído ao código ADR-020 nem à migration 0040.

## 8. Estado Git e não-alteração pelos testes

Antes e depois das gates, o estado da branch foi:

```text
## main...origin/main
```

A working tree permaneceu limpa. Nenhum ficheiro foi alterado pela execução dos testes.

Não foram executados staging, novo commit ou push durante o presente fechamento documental.

## 9. Prova técnica encerrada

A implementação demonstrou o vínculo físico prospectivo exacto entre a geração e a decisão declaradas por `NormativeActivation`:

```text
NormativeActivation(
    activation_generation_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

e a identidade correspondente de `ActivationGeneration`:

```text
ActivationGeneration(
    activation_generation_id,
    activation_decision_id,
    activation_decision_record_hash
)
```

A FK composta `NOT VALID` protege prospectivamente novas escritas sem declarar validado, reparar, remover ou validar retroactivamente o histórico. As regressões 9B3 e 9B4 e a FK simples foram preservadas.

## 10. Fronteira operacional

O GREEN aqui documentado é exclusivamente técnico e local/de teste. O motor ADR-020 e as gates operacionais permanecem desligados.

Este relatório não autoriza:

- deploy;
- Railway;
- produção;
- endpoint;
- worker;
- scheduler;
- dispatcher;
- publicação operacional;
- activação do motor ADR-020;
- abertura de gates operacionais;
- consulta, alteração ou migração de dados reais;
- validação retroactiva do histórico.

## 11. Fora de escopo e pendências preservadas

Permanecem expressamente separados e fora do escopo deste fechamento:

- `MIGRATION-BOOTSTRAP-0000-0001`;
- intenção 9B4;
- qualquer deploy ou operação em Railway ou produção;
- endpoint, worker, scheduler e dispatcher;
- motor ADR-020 e gates operacionais;
- substituição futura da ratificação humana repetitiva, que exige instrumento próprio.

A MISSION-012, o REPORT-029, a cadeia 9B2 e `docs/ROADMAP_OPS_AGENTES.md` permanecem inalterados.

## 12. Integridade documental

Este documento não contém auto-hash. O seu tamanho e SHA-256 devem ser calculados externamente após a fixação dos bytes.

A codificação exigida é UTF-8 sem BOM, somente com finais de linha LF, exactamente uma newline final e zero trailing whitespace.

## 13. Estado final

- GREEN técnico integral para a intenção 9B2;
- vínculo físico prospectivo exacto geração↔decisão provado;
- regressões 9B3/9B4 e FK simples preservadas;
- implementação apta para fechamento documental;
- bundle independente capturado, congelado, auditado e vinculado;
- motor ADR-020 e gates operacionais permanecem desligados;
- nenhuma autorização operacional ou de produção é concedida.

O bundle independente foi capturado, congelado, auditado e vinculado. O próximo acto admissível é a auditoria final, o congelamento e a publicação deste REPORT-030 pela autoridade competente. Até esses actos, o relatório permanece proposta documental não canónica e não publicada.

## Veredicto final do documento

`GREEN_TECNICO_9B2_INTEGRAL_IMPLEMENTACAO_APTA_PARA_FECHAMENTO_DOCUMENTAL_AGUARDA_PUBLICACAO`
