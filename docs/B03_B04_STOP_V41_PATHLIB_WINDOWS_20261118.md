# SOLVERIS Enterprise — STOP V4.1 por teste de portabilidade Windows

Corte: 18/11/2026. Branch: `recovery/enterprise-b00-b04-20261117`.

## Evidência reportada por Miguel

- `git fetch` e `git merge --ff-only` concluídos até `71dc389cc8897ebcc12a7347c653f9338f1d7973`.
- Manifesto G12 V4.1 Git blob `a26572484cfac26b614b2bc9e63c1a70fd1b68b1` confirmado (`V41_DOCUMENTOS_GIT_OK`).
- Após aplicar patches V4.1 no Windows, `python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q`: **66 testes, 1 falha**.
- Falha: `test_enterprise_recovery_v41_history_gate.TestRecoveryV41Historical.test_v41_manifesto_inexistente_rejeitado` esperava `V41_RATIFIED_MANIFEST_MISSING`, recebeu `V41_G12_SOURCE_NOT_RATIFIED`.
- O PowerShell lançou `STOP_V41_CATRACA_66`. O `Write-Host 'V41_CATRACA_66_OK'` isoladamente executado após o STOP **não representa aprovação**.

## Causa e limite do ajuste

O teste V4.1 novo em `tests/test_enterprise_recovery_v41_history_gate.py` simula a ausência do manifesto quando `str(file).endswith(V41_MANIFEST)`; o caminho no Windows usa `\\`, enquanto `V41_MANIFEST` é `docs/...` com `/`. A simulação não acontece; o manifesto real é encontrado e a função chega à validação de outro motivo. **É erro de portabilidade do próprio teste novo**, não prova de defeito no XML, G12, B01 ou autoridade normativa.

Correção candidata: no teste novo, substituir a comparação textual por `file == ROOT / V41_MANIFEST`, sem editar produto, testes B01/G1 antigos, parser, resolvedor, nem V3/V4. É necessário **novo escopo e manifesto versionados**, porque V4.1 já publicou hash imutável deste teste (`7b12c0f3efd6a4c5baded068a885cff1ec8ed2ff`). Não reescrever manifesto V4.1 nem declarar GREEN; publicar um delta V4.1.1 separado e sujeito a catraca própria antes de prosseguir para os 74 testes funcionais.
