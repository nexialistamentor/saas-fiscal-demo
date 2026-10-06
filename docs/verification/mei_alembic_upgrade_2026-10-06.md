# Atualização Alembic com dados sintéticos — 2026-10-06

Commit testado: 159718986ef130d1aed3e525ee7503cabc485f8a.

POPULATED_UPGRADE_0056_0058=PASS
LEGACY_PRESERVED=PASS
NO_INFERENCE=PASS
DOWNGRADE_REUPGRADE=PASS
DISPOSABLE_CONTAINER_REMOVED=PASS
PRODUCTION=NOT_TESTED

PostgreSQL descartável criado pelas migrations até 0056.
Inseridos documentos e itens legados sintéticos.
Atualização até 0058 preservou os registros e manteve nulas
as novas observações, sem inferir dados legados.
Downgrade até 0056 e nova atualização também aprovados.

Não utiliza cópia de produção e não valida os dados reais.
Script: tests/support/mei_alembic_upgrade/run.py.
Resultado: resultado_2026-10-06.json.