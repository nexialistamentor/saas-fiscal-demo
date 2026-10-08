# Receitas informadas — prova PostgreSQL — 2026-10-08

Implementação: 47115a5e7a1e7932da075d1a4a4c35e99889a2c3.
Contrato congelado: c81f5d28c34b706ec706679e66b642c891ff1a28.

A prova foi executada antes do commit da implementação, sobre os arquivos
que foram registrados em 47115a5. O executor preservado foi fixado nesse
commit para permitir reprodução. Essa atualização não foi reexecutada.

Ambiente: PostgreSQL 17 local descartável; dados sintéticos.
Produção não acessada. Nenhum pagamento ou provedor externo chamado.

Resultados:
- Migrações Alembic online até 0059: PASS.
- Numeric(15,2), persistência e reenvio: PASS.
- Cinco corridas forçadas com dados iguais: mesmo ID e uma única linha.
- Cinco corridas forçadas com dados divergentes: um sucesso e uma recusa.
- Rollback PostgreSQL: PASS.
- Dados sintéticos anteriores preservados: PASS.
- Downgrade para 0058 e reaplicação de 0059: PASS.
- Container descartável removido: PASS.

O downgrade foi testado somente no banco descartável; remove a tabela nova.
A prova não demonstra integração HTTP ou interface, ainda não implementadas.
Não certifica receita, completude anual ou regularidade fiscal.

Execução local Windows:
C:\dev\saas-fiscal-demo-mei\venv311\Scripts\python.exe tests\support\mei_receita_informada_postgres\run.py

O executor exige o commit da implementação. Para reproduzir depois de
novos commits, usar uma worktree isolada nesse commit e fornecer nela
uma cópia do executor preservado.