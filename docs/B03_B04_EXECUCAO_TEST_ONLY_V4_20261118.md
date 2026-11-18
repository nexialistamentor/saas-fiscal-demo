# SOLVERIS — aplicação da evolução test-only V3→V4 sem alterar produto

**Corte:** 18/11/2026. **Autoridade:** ratificação explícita de Miguel após handoff 781d9db4. **Estado:** pacote test-only preparado e validado em V3 Linux (47/47); **teste Windows ainda pendente**. Não confundir este pacote com autorização para aplicar G12 V4.

## Escopo e evidência

- Handoff: docs/HANDOFF_B03_B04_RECOVERY_V4_20261118.md.
- Único delta test-only: docs/B03_B04_PATCH_V4_TEST_ONLY_20261118.patch, Git blob **5f0bb12497d3f5923c74d04e383f07fddff3edd2**.
- O patch adiciona **snapshot original do G12 V3** em tests/fixtures/enterprise_g12_v3_frozen_source.py.txt, hash **7b70bd28af292dc8028d572336b80f22bac0a945**, igual à fonte V3 aprovada.
- Acrescenta tests/recovery_v3_snapshot_guard.py (hash **de2e72093b07ebb5575d85783361050ade5bcd09**) e 8 controlos, incluindo testes negativos, em tests/test_enterprise_recovery_scope_v4_history_gate.py (hash **c48c3548282b4746fea83cf58483fd74bb966293**).
- Atualiza somente o adaptador de teste tests/test_enterprise_recovery_scope_v3_gate.py, original pré-V4 **5d8acdfbffeda4e87852472a57d118746b8d1879**, candidato test-only **3191ebb16662b6eb08cce45c85ddcaf05a6a71ae**. Os nomes dos 10 testes V3 e as suas asserções de resultado foram preservados; só a avaliação histórica passou a usar a guarda test-only de fonte G12 congelada.
- Com G12 V3 original, o novo contexto usa diretamente a fonte atual, sem substituição. Com futura V4, exige manifesto V4 **já commitado no Git**, com parent V3 e hash exato do G12 atual; apenas os testes unitários históricos V3 poderão observar o snapshot verificado. O **gate CLI V3 nunca é alterado** e continua a reprovar candidatas V4. O futuro gate CLI V4 deverá verificar diretamente todos os hashes reais e a suite nova.
- Verificado em worktree Linux com G12 V3 original: python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q → **47/47 OK**; git apply -R --check do pacote → OK; py_compile das fontes test-only → OK. Não foram executados os testes de integração Windows ou a suite global.

## Único procedimento Windows agora permitido

Executar no worktree isolado **C:\dev\saas-fiscal-demo-b06-green-20261118**, branch recovery/enterprise-b00-b04-20261117, **com V3/V3.1 já aplicada e sem qualquer patch V4 de produto**:

~~~powershell
Set-Location 'C:\dev\saas-fiscal-demo-b06-green-20261118'
if ((git branch --show-current) -ne 'recovery/enterprise-b00-b04-20261117') { throw 'STOP_BRANCH' }
if ((git hash-object tests/test_solveris_b01_circuit.py) -ne 'eb961ee500de8a3dee76c0a6e4c4b4be577367e5') { throw 'STOP_B01_ORIGINAL' }
if ((git hash-object app/services/enterprise_g12_st_item_reconciliation.py) -ne '7b70bd28af292dc8028d572336b80f22bac0a945') { throw 'STOP_G12_V3_SOURCE' }
git fetch --no-tags origin 'refs/heads/recovery/enterprise-b00-b04-20261117'
if ($LASTEXITCODE -ne 0) { throw 'STOP_FETCH' }
git merge --ff-only origin/recovery/enterprise-b00-b04-20261117
if ($LASTEXITCODE -ne 0) { throw 'STOP_FF_ONLY' }
git apply --check docs/B03_B04_PATCH_V4_TEST_ONLY_20261118.patch
if ($LASTEXITCODE -ne 0) { throw 'STOP_TEST_ONLY_PATCH_CONTEXT' }
git apply docs/B03_B04_PATCH_V4_TEST_ONLY_20261118.patch
if ($LASTEXITCODE -ne 0) { throw 'STOP_TEST_ONLY_PATCH' }
if ((git hash-object tests/fixtures/enterprise_g12_v3_frozen_source.py.txt) -ne '7b70bd28af292dc8028d572336b80f22bac0a945') { throw 'STOP_SNAPSHOT_HASH' }
if ((git hash-object tests/test_enterprise_recovery_scope_v3_gate.py) -ne '3191ebb16662b6eb08cce45c85ddcaf05a6a71ae') { throw 'STOP_TEST_ONLY_HASH' }
python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q
if ($LASTEXITCODE -ne 0) { throw 'STOP_TEST_ONLY_V4' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'STOP_DIFF_CHECK' }
Write-Host 'V4_TEST_ONLY_47_OK_SEM_PRODUTO'
~~~

**Se algum comando falhar:** STOP; devolver apenas mensagem causal e hash observado. Não reaplicar um patch já aplicado, alterar testes B01/G1, editar permissões de UF ou executar suite global. O código experimental do G12 V4 **não faz parte deste pacote**.

## Próximo passo condicionado

Só depois do recibo Windows de 47 testes verdes, preparar em **outro patch/documento/commit** o G12 V4 e a catraca V4 ativa com manifesto explícito e controlos negativos. As 61 provas dirigidas B01/B03/B04/G1 continuam pendentes de GREEN; manter os 13 RED globais pré-existentes visíveis e GLOBAL_GREEN=false.
