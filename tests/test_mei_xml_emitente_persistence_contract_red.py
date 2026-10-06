"""Observed XML emitter persistence contract with disposable SQLite.

Run directly with Python. Does not import the production application lifecycle
or prove PostgreSQL migrations, providers or deployment.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCENARIO = r'''
from hashlib import sha256
from app.database import Base, engine, SessionLocal
from app import models
assert 'cnpj_emitente' in models.DocumentoFiscal.__table__.columns, 'MEI_XML_EMITENTE_NOT_PERSISTED'
from app.xml_service import ler_xml_unico, persistir_documento_fiscal, DuplicataFiscalError
Base.metadata.create_all(engine, tables=[models.Plano.__table__, models.User.__table__,
    models.Empresa.__table__, models.DocumentoFiscal.__table__])
with SessionLocal() as db:
    user = models.User(email='owner@example.invalid', hashed_password='unused')
    db.add(user); db.flush()
    company = models.Empresa(user_id=user.id, cnpj='12345678000195', regime_tributario='mei')
    db.add(company); db.commit()
    for number, emitter in [(1, '12345678000195'), (2, '11222333000181'), (3, None)]:
        emit = '<CNPJ>' + emitter + '</CNPJ>' if emitter else ''
        xml = ('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe>'
            '<emit>' + emit + '<xNome>FICTICIO</xNome></emit><ide><nNF>' + str(number) +
            '</nNF><tpNF>1</tpNF><dhEmi>2026-01-01T12:00:00-03:00</dhEmi></ide>'
            '<total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>'
            '</infNFe></NFe></nfeProc>').encode()
        digest = sha256(xml).hexdigest()
        data = ler_xml_unico(xml_bytes=xml)
        document = persistir_documento_fiscal(db, user, company, data, conteudo_sha256=digest)
        db.expire_all()
        persisted = db.get(models.DocumentoFiscal, document.id)
        assert persisted.cnpj_emitente == emitter
        assert persisted.conteudo_sha256 == digest and persisted.empresa_id == company.id
        assert company.cnpj == '12345678000195'
        try:
            persistir_documento_fiscal(db, user, company, data, conteudo_sha256=digest)
        except DuplicataFiscalError:
            pass
        else:
            raise AssertionError('XML_DUPLICATE_ACCEPTED')
    legacy = models.DocumentoFiscal(empresa_id=company.id, usuario_id=user.id)
    db.add(legacy); db.commit(); db.refresh(legacy)
    assert legacy.cnpj_emitente is None, 'LEGACY_EMITTER_MUST_REMAIN_UNKNOWN'
    assert db.query(models.DocumentoFiscal).count() == 4
engine.dispose()
print('MEI_XML_EMITENTE_PERSISTENCE=PASS')
'''


class XmlEmitterPersistenceContract(unittest.TestCase):
    def test_xml_parser_and_writer_preserve_observed_emitter_without_inference(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="mei-documental-contract-") as temporary:
            allowed = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PYTHONPATH")
            env = {key: os.environ[key] for key in allowed if key in os.environ}
            env.update(ENVIRONMENT="test", ALEMBIC_RUNNING="1", PYTHON_DOTENV_DISABLED="1",
                DATABASE_URL="sqlite:///" + (Path(temporary) / "test.db").as_posix(),
                SECRET_KEYS="test=disposable-contract-secret-not-for-production",
                MERCADO_PAGO_ENABLED="false", SERPRO_PGMEI_ENABLED="false")
            result = subprocess.run([sys.executable, "-c", SCENARIO], cwd=repo,
                env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("MEI_XML_EMITENTE_PERSISTENCE=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
