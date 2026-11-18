# Dívida técnica rastreada — reconciliar comparadores G1 Enterprise e compartilhado

**Identificador:** `SOLVERIS-DT-G1-COEXISTENCIA-20261118`  
**Estado:** ABERTA, não resolvida por esta missão; data 18/11/2026.  
**Autoridade de decisão:** Miguel. **Bloqueio de promoção à main:** permanece independente desta dívida.

## Contratos que coexistem deliberadamente

- `app/services/tax_consistency/tax_consistency_engine.py`: comparador compartilhado da `main@a6a2da6c`, Git blob `9f7a5ddf144293fe3591989c784c8ec6d875cd07`; consumidores reais em `app/xml_service.py`, `app/agents/consistency_audit_agent.py` e outros. **Não foi alterado**.
- `app/services/enterprise_tax_consistency/enterprise_tax_consistency_engine.py`: recuperação privada do G1 histórico de `ee1007562836378e2addb50f9af0a09b609aef88`, blob original `543f19b4b777ecaaa107d699dd13c002b378e8a2`. Mudança apenas de nome de classe e docstring; contrato por item fail-closed é a origem preservada.
- `tests/enterprise_g1_contract_origin.py`: teste original de 22 casos de `c9a17fd1`, Git blob `45a2080a8adead467aa4b00275e3a33616b0966c`; importado por adaptador isolado de testes, sem alterar as asserções originais.

## Motivo e regra temporal

G12 e B03 esperam `estado`, identidade documental e por item, `consistente=None` e garantias negativas de autoridade. O comparador compartilhado atual pode retornar `consistente=True` sem pares comprovados; o G13 recusa corretamente. O privado serve exclusivamente B03/G12/G13, evitando risco a MEI e consumidores legados.

A coexistência tem registo explícito (`comparador_consistencia_enterprise_g1` → `coexiste_com: [comparador_consistencia]`) e exceção estrita da catraca. **Não declara `substitui`** e não autoriza replicar o padrão noutros motores. Nenhum resultado privado pode ser apresentado como prova legal, crédito ou checkout.

## Condições objetivas para encerrar a dívida

1. Inventariar os consumidores efetivos do G1 compartilhado e dos contratos de entrada/saída de ambos, incluindo varrimentos de alcance MEI.
2. Conceber uma única interface tipada e versionada que suporte ambas as necessidades sem perder `consistente=None` para provas não verificadas.
3. Provar todos os contratos causais G1, os testes do circuito Enterprise e regressões dos consumidores compartilhados, mantendo os hashes dos contratos ratificados.
4. Obter decisão expressa de Miguel sobre eventual convergência e alteração da exceção; não apagar o legado por conveniência.

**Este item é rastreabilidade, não autorização para resolver já.** B06 Fase 0 permanece pendente da validação da recuperação B03/B04.
