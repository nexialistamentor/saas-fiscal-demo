# Cadeia Alembic em PostgreSQL descartável — 2026-10-06

Commit testado: e759b9038a0d6c45bd9e38554650d184d71bbe66.

FULL_ALEMBIC_CHAIN=PASS
OBSERVED_COLUMNS=PASS
DISPOSABLE_CONTAINER_REMOVED=PASS
PRODUCTION=NOT_TESTED

Executado alembic upgrade head em PostgreSQL vazio e descartável.
Revisão final: 0058_documento_operacao_observada.
Verificadas as colunas cnpj_emitente, natureza_operacao_observada
e finalidade_emissao_observada.

Esta prova valida bootstrap completo; não valida atualização
de uma cópia do banco de produção nem compatibilidade dos dados existentes.

Script: tests/support/mei_alembic_chain/run.py.
Resultado: resultado_2026-10-06.json.