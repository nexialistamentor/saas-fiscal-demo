"""Targeted migration check; does not certify the full Alembic chain."""
import importlib.util
from pathlib import Path
import unittest

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


class ObservedEmitterMigrationControls(unittest.TestCase):
    def test_upgrade_keeps_legacy_unknown_and_downgrade_preserves_document(self):
        path = Path(__file__).resolve().parents[1] / 'migrations/versions/0057_documento_fiscal_emitente_observado.py'
        spec = importlib.util.spec_from_file_location('emitter_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        self.assertEqual(migration.down_revision, '0056_mei_competencia_checkout_intent')
        engine = sa.create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.execute(sa.text('CREATE TABLE documentos_fiscais (id INTEGER PRIMARY KEY, conteudo_sha256 VARCHAR(64))'))
                connection.execute(sa.text('INSERT INTO documentos_fiscais VALUES (1, :hash)'), {'hash': 'a' * 64})
                context = MigrationContext.configure(connection)
                with Operations.context(context):
                    migration.upgrade()
                columns = {column['name']: column for column in sa.inspect(connection).get_columns('documentos_fiscais')}
                self.assertTrue(columns['cnpj_emitente']['nullable'])
                self.assertEqual(connection.execute(sa.text('SELECT conteudo_sha256, cnpj_emitente FROM documentos_fiscais')).one(), ('a' * 64, None))
                connection.execute(sa.text('UPDATE documentos_fiscais SET cnpj_emitente=:value'), {'value': '12345678000195'})
                with Operations.context(context):
                    migration.downgrade()
                self.assertNotIn('cnpj_emitente', {column['name'] for column in sa.inspect(connection).get_columns('documentos_fiscais')})
                self.assertEqual(connection.execute(sa.text('SELECT conteudo_sha256 FROM documentos_fiscais')).scalar_one(), 'a' * 64)
        finally:
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
