# SOLVERIS — STOP dirigido B01: contrato PR versus piloto canónico PA

**Corte:** 18/11/2026. **Resultado:** `CONTRACT_CONFLICT`, `B03_B04_DIRECTED_GREEN=false`, `GLOBAL_GREEN=false`.

## Custódia e evidência observada

- `main` imutável de referência: `a6a2da6cbf07c7b9922f8571bf2e6016376304d5`.
- Recuperação exclusiva: `recovery/enterprise-b00-b04-20261117`, base documental V3.1 `b968c7b017cc40ca0ff03f4df6d11469339c6ad0`.
- Resultado Windows reportado por Miguel no worktree `C:\dev\saas-fiscal-demo-b06-green-20261118`:
  - `python -m unittest discover -s tests -p 'test_enterprise_recovery*gate.py' -q`: **39 OK**.
  - Suite dirigida de seis ficheiros: **59 passed, 2 failed**, exit **1**, em 3,74 s; não equivale a GREEN dirigido.
- Os dois RED vêm do mesmo contrato histórico, `tests/test_solveris_b01_circuit.py`, Git blob original `eb961ee500de8a3dee76c0a6e4c4b4be577367e5`, idêntico ao de `1af67fe4`:
  1. `test_01_circuito_real_writer_i2_g12_g14_adr020_c3_c7`: `itens[0].estado` recebido **`ABSTENCAO`**; esperado **`DOSSIER_INTERNO_NAO_PUBLICAVEL`**.
  2. `test_05_dependencia_c3_falha_fecha_circuito`: a adulteração do PDF (`self.pdf + b'!'`) não provocou a exceção esperada.
- A suite global da candidata **não deve ser iniciada** enquanto o gate dirigido estiver RED.

## Conflito de origem verificado por leitura do código

1. O B01 histórico gera NF-e e regra `TabelaMVA` **sintéticas para `PR`** (`tests/test_solveris_b01_circuit.py`, `nfe()`, `setUp()`, `candidate()`).
2. O resolvedor compartilhado da `main`, `app/services/fiscal_utils.py`, Git blob `d625f12f68441f655cee06a6368b2ef7cfbf85b2`, contém `_UF_PILOTO = "PA"` e o guarda `if uf_norm != _UF_PILOTO: return _bloqueio(...)`, que devolve `calculo_autorizado=False` para `PR`.
3. `app/services/enterprise_g12_st_item_reconciliation.py` exige precisamente `rule['calculo_autorizado'] is True` e `rule['confianca'] == 'oficial'` para produzir simulação; caso contrário, classifica `G12_REGRA_NAO_AUTORIZADA_PELO_RESOLVEDOR` e permanece sem simulação.
4. `app/services/enterprise_g14_operational_normative_scope.py` exige `sim['comparacao_condicional'] is True` e `sim['estado'] == 'SIMULACAO_CONDICIONAL_MVA'` para admitir o candidato estrutural; sem isso, devolve `G12_SEM_SIMULACAO_ITEM`.
5. `executar_circuito_enterprise_01` em `app/services/registro_analise_service.py` só invoca C3 se G14 devolver `COERENCIA_ESTRUTURAL_CANDIDATA_SEM_TRUST`. Se não, devolve `ABSTENCAO`, sem ler o PDF; isso explica, **por inferência da trajetória do código**, os dois RED observados. O motivo G12/G14 interno ainda não foi capturado por instrumentação no Windows.
6. O commit histórico de B01 `b45ef539` e a fonte recuperada `c9a17fd1` usavam **outro contrato normativo** em `app/services/fiscal_utils.py`, Git blob `7eb7599cc25e8db3804405aeedfe794e097f0145`, com `_UFS_VALIDAS` incluindo `PR`. Este resolvedor histórico **não é** o resolvedor da `main`; portanto, restaurar B01/G12 sem essa distinção deixa a prova sintética antiga incompatível com a restrição PA.

**Conclusão:** a catraca V3.1 passou, mas a integração B01 ainda tem incompatibilidade real entre uma premissa histórica nacional e a autoridade canónica atual do piloto PA. Não há fundamento para atribuir o problema ao G1 privado nem para relaxar o bloqueio de UF. Dois RED não justificam reescrever testes ou ampliar autorização normativa.

## STOP e próximo ato requerido

- **Não alterar** `fiscal_utils.py`, `TaxConsistencyEngine` compartilhado, G1 privado, G12/G13, asserções/fixtures/contratos B01, a `main`, o MEI, o Railway, o Vercel ou migrações para obter GREEN artificial.
- Preservar o worktree Windows e o patch V3.1 aplicado. Não tentar `merge`, `deploy` ou B06 Fase 1; sem suite global até o fecho do RED dirigido.
- É necessária decisão arquitetural **específica e separadamente ratificada** para compatibilizar a prova sintética B01 com o escopo do piloto PA. Alternativas a avaliar, **nenhuma autorizada por este registo**:
  - recuperar em área privada Enterprise uma interpretação estritamente **sintética e sem autoridade** da proveniência histórica para testes, com catraca contra consumo de produção e sem duplicar silenciosamente o resolvedor fiscal; ou
  - criar um novo contrato de integração B01 representativo de PA, mantendo o testemunho original PR intacto e explicitamente inconciliado, com aprovação formal de uma nova baseline.

**Próxima verificação permitida sem mutação:** colher do circuito Windows a razão interna de G12/G14 (`G12_REGRA_NAO_AUTORIZADA_PELO_RESOLVEDOR` e `G12_SEM_SIMULACAO_ITEM` são resultados previstos por leitura), sem mexer nos ficheiros protegidos. Prosseguir apenas com a ratificação sobre o delta arquitetural exato.
