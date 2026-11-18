# SOLVERIS Enterprise — STOP funcional G12 V4.1.1 (18/11/2026)

Branch isolado `recovery/enterprise-b00-b04-20261117`. Estado: **STOP; nao GREEN nem autorizado para global/deploy**.

## Evidência reportada por Miguel (Windows `.venv-release`)

- Gate versionado V4.1.1: **69/69 testes OK**, hash/manifesto sincronizados ate `ad8f03c94ccf30f71fbaadd8e952efcebc59bb08`.
- Suite funcional dirigida de 74 testes: **71 passed, 3 failed, 49 warnings**, exit não-zero; `STOP_V411_FUNCIONAIS_74` correto.
- Falhas observadas:
  1. `tests/test_solveris_b01_circuit.py::TestEnterpriseB01SyntheticIntegration::test_01_circuito_real_writer_i2_g12_g14_adr020_c3_c7`: `ABSTENCAO` em vez de `DOSSIER_INTERNO_NAO_PUBLICAVEL`.
  2. `tests/test_enterprise_g12_synthetic_observation_v4_gate.py::TestEnterpriseG12SyntheticObservationV4::test_b01_pr_sintetico_produz_dossie_sem_autoridade`: mesma divergência.
  3. `tests/test_enterprise_g12_xml_parser_v41_contract.py::TestEnterpriseG12XmlParserV41::test_01_segundo_cenario_rs_valores_novos_simula_sem_autoridade`: `itens_simulados` 0 em vez de 1.
- Diferentemente do STOP V4 anterior, o teste de falha da dependência C3 não aparece entre os RED atuais; nenhuma conclusão de causalidade deve ser inferida sem `motivo` G12 atual.

## Fronteira

A correção da portabilidade V4.1.1 foi test-only e não é causa comprovada das três recusas. O G12 V4.1 compara `vBCST/vICMSST` do XML com `base_st/valor_st` do parser, mas há outros filtros anteriores e posteriores (identidade, ICMS próprio, condição normativa, unicidade sintética in-memory, vigência, base ST, comparação de motores). **A identidade exata do primeiro filtro que recusa PR e RS ainda não está comprovada**.

Proibido editar B01 original, trocar PR por PA, alterar norma/resolvedor partilhado, afrouxar verificações fiscais, anunciar global GREEN, executar deploy ou fazer merge em main. Próximo ato: diagnóstico apenas de leitura, com `out['estado']`, `out['itens'][0]['motivo']`, verificação XML-parser e linha sintética para **PR e RS**, sem alterar código/testes/BD.
