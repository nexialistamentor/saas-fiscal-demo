# SOLVERIS Enterprise — STOP V4.3 dirigido / alcance MEI (18/11/2026)

**Estado: STOP_TESTES_DIRIGIDOS_V43 / NÃO GLOBAL GREEN.** Resultado Windows entregue por Miguel: **317 passed, 7 failed, 2 skipped, 181 warnings**, 2208,70 s (36m48s). A catraca histórica V4.3 já tinha 78/78 GREEN no ensaio isolado; a execução dirigida Windows falhou e, portanto, **não existe GREEN da V4.3**. Não repetir a suite global nem este conjunto largo antes de corrigir a causa.

## Sete falhas observadas

1. `tests/test_mei_publication_reachability_generic_persisted_report.py::test_generic_persisted_report_publication_has_no_canonical_mei_producer_red`: esperava `NO_CANONICAL_MEI_PRODUCER`, recebeu `UNRESOLVED_MEI`.
2. `tests/test_mei_publication_reachability_orm_flush.py`: dois contratos esperavam `persistir_documento_fiscal` sem o `flush` final; estado atual contém também `flush` para `commit=False`.
3. `tests/test_mei_publication_reachability_orm_persistence.py`: `criar_registro_analise` ganhou `flush` condicional.
4. `tests/test_mei_publication_reachability_orm_transitive.py`: sink transitive reflete `flush` extra da persistência de XML.
5. `tests/test_mei_publication_reachability_orm_write_semantics.py`: dois contratos esperavam apenas `add,commit` / `commit`; `criar_registro_analise` e `finalizar_registro_analise` agora suportam `flush` sem `commit`.

São **6 testes ORM** com listas de operações antigas + **1 teste de proveniência do relatório persistido**. Estas alterações de transação B01 são anteriores à correção da guarda V4.3; as falhas estavam encobertas pela falha de alcance MEI `empresa_guard`.

## Diagnóstico causal reproduzido no checkout candidato (leitura, sem editar scanner)

- `app/scripts/mei_publication_reachability_census.py`, blob `a0a8f48e9f4c1955a8cd325154db28f86a700ab2`, permanece **intocado**.
- `app/services/registro_analise_service.py`, V4.3 `381cd15087eee7f9aaa39ff9d5ddeb547fdf47a7`; `app/xml_service.py`, V2 `b56a5dd36cd70064bdf55db86e00c416d55f21fb`.
- Scanner ORM real:
  - XML `_orm_session_operations`: `['add','flush','rollback','add','commit','flush']`.
  - XML `_orm_persistence_operations`: `['add','flush','add','commit','flush']`.
  - `criar_registro_analise` session: `['add','commit','flush','refresh']`; persistência: `['add','commit','flush']`.
  - `finalizar_registro_analise` persistência: `['commit','flush']`.
  - sink transitive é completo, com `unresolved_app_callees=[]`, `scan_complete=True`, e reflete os `flush`.
- O relatório `/relatorio/{relatorio_id:int}` tem `blocker_code=PERSISTED_MEI_PROVENANCE_UNPROVEN`, `lineage_proven=False`, `producer_ids=[]`; mantém-se **fail-closed**, sem publicação de proveniência não provada.
- Instrumentação exclusivamente em memória da função `_generic_persisted_report_writer_closure` localizou o primeiro `return False` na linha **7107**: esperava precisamente **uma** chamada result-bearing de `finalizar_registro_analise` do XML e uma do CPF; o B01 possui **duas** chamadas do XML (opt-in + legado), além da do CPF. Ao saltar *apenas na instrumentação diagnóstica* esse primeiro predicado, a próxima recusa foi na linha **7169**, onde o scanner espera precisamente **uma** atribuição `rel = criar_registro_analise(...)` e o B01 possui **duas**. Não foram alterados nem scanner nem código do produto para essa prova.
- Mesmo reunificando chamadas, a derivação de `resultado_persistido` usa `producer_id` distinto para Enterprise e legado, que exige uma prova de proveniência própria; **não presumir** que um refactor sintático isolado resolverá o contrato.

## Linhas proibidas para um falso GREEN

- Não apagar `db.flush()` da transação Enterprise para reaver listas antigas: pode comprometer atomicidade.
- Não editar scanner MEI, asserções RED, fixtures ou `lineage_proven` para esverdear sem missão test-only e segregação expressamente ratificadas.
- Não tocar no G1 partilhado, G12 já validado, MEI operacional, `main`, deploy, `git.deploymentEnabled`, ou nos JUnit originais.
- Não executar novamente 37 minutos de testes dirigidos/globais até fechar cada uma das sete falhas em testes específicos.

## Decisão arquitetural pendente (escopo V4.4 separado)

1. **ORM:** confirmar como os seis contratos test-only devem evoluir para reconhecer `flush` condicional com `commit=False`, provando em negativos que o `flush` é operação de escrita e `rollback` não é escrita; preservar os contratos históricos e versões.
2. **Linhagem:** comparar, em leitura, duas vias — (a) reconstruir o B01 para conservar uma cadeia estática verificável de criador/finalizador/produtor em ambos os ramos, com semântica transacional; (b) ampliar o scanner MEI com prova estrutural rigorosa e testes negativos para os dois ramos. Não alterar scanner MEI ou código B01 até Miguel ratificar a via.
3. Preparar *testes exclusivos dos sete IDs* antes de qualquer suite larga. Se os invariantes se contradisserem, STOP/CONTRACT_CONFLICT.
4. O gate V2 possui a sentinela `MEI_SOURCE_OR_TEST_CHANGED` sobre nomes de caminhos MEI. A V4.3 tem o patch test-only `tests/test_solveris_mei_vercel_routing_contract_red.py` (nome contém `_mei_`), embora mais restritivo sobre auto-deploy. Um futuro gate derivado terá de declarar e provar esta exceção **apenas para o hash exato ratificado**, sem desativar a sentinela V2, ou manter STOP. A aprovação dos sete testes não elimina automaticamente esta restrição de escopo.

A V4.3 permanece aplicada apenas no checkout local Windows de Miguel (segundo a sua saída); o branch Git tem os patches documentais, **não** os ficheiros de produção alterados nem autorização de merge.
