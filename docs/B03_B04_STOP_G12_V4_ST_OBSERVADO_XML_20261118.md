# SOLVERIS — STOP funcional G12 V4: sinalizador ST ausente no parser legado

**Corte:** 18/11/2026. **Branch autorizado:** recovery/enterprise-b00-b04-20261117. **Estado:** STOP funcional; nao declarar GREEN.

## Evidencia Windows

- Testes da catraca V4: 54/54 OK, incluindo manifesto e hashes; comprovam estrutura, nao circuito funcional.
- Testes funcionais dirigidos: **64 passed, 3 failed**, em:
  1. B01 original test_01_circuito_real_writer_i2_g12_g14_adr020_c3_c7;
  2. B01 original test_05_dependencia_c3_falha_fecha_circuito;
  3. controlo novo V4 test_b01_pr_sintetico_produz_dossie_sem_autoridade.
- Diagnostico real em fixture B01 in-memory, sem modificar ficheiros:
  - G12_ESTADO = G12_SEM_SIMULACAO; G12_SIMULADOS = 0;
  - G12_ITEM_ESTADO = NAO_AVALIADO; G12_ITEM_MOTIVO = G12_ST_NAO_OBSERVADO_XML;
  - G12_L2_PRESENTE = False;
  - G14_ESTADO = LACUNA_CANDIDATO_NORMATIVO; G14_MOTIVO = G12_SEM_SIMULACAO_ITEM;
  - B01_ESTADO = ABSTENCAO; B01_MOTIVO = G14_SEM_CANDIDATO_ESTRUTURAL.

## Causa identificada por leitura direta

Em app/xml_service.py, ler_xml_unico utiliza _extrair_valor_icms_detalhe para extrair os campos NF-e vBCST e vICMSST, retornando em cada item base_st e valor_st. **Nao retorna st_observado_xml**. Em app/services/enterprise_g12_st_item_reconciliation.py, o G12 V4 exige item.get('st_observado_xml') is True antes de consultar o resolvedor e de validar o marcador sintetico. Esse predicado e insatisfazivel com a saida real do parser legado, mesmo quando o XML da fixture contem ICMS10, vBCST e vICMSST. Portanto, o erro ocorre **antes** da politica PA, da prova L2 e de C3.

## Invariantes preservados e decisao pendente

- B01 original permanece blob eb961ee500de8a3dee76c0a6e4c4b4be577367e5, com PR/12119090; nao substituir por PA.
- G12 V4 atual permanece blob 4a782490cf8fd6d6b9d2d6d7b801370cbe6e2ea0; nao alterar silenciosamente o manifesto V4.
- Nao modificar app/xml_service.py, o resolvedor partilhado, testes/fixtures originais, MEI, main, migrations ou deploy.
- A correcao causal V4.1 proposta e exclusivamente no G12 Enterprise: validar diretamente vBCST e vICMSST do XML ICMS10 contra base_st e valor_st extraidos pelo parser, com valores monetarios coerentes. A eventual ausencia do sinalizador so podera ser aceite no caminho **estritamente sintetico**, SQLite in-memory, registo unico, marcador B01_SYNTHETIC_FIXTURE, fonte sintetica declarada, autorizacao normativa ainda falsa e todas as flags de autoridade/credito/checkout/publicacao falsas.
- A catraca V4 e o manifesto V4 **devem continuar a rejeitar** o G12 V4.1. Exige extensao de escopo e gate V4.1 proprios, comprovacao de V3/V4 historicos e hashes, novos controlos positivos/negativos, teste B01 original imutavel, suite dirigida e depois suite global com a mesma baseline de 13 RED preexistentes.
- Nao executar suite global nem retomar B06 antes de nova validação dirigida. Esta nota documenta STOP e causa; **nao declara implementacao, ratificacao ou aprovacao funcional**.
