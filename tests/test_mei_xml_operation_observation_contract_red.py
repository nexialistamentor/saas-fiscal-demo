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
for field in ('natureza_operacao_observada', 'finalidade_emissao_observada'):
    assert field in models.DocumentoFiscal.__table__.columns, 'MEI_XML_OPERATION_OBSERVATIONS_NOT_PERSISTED:' + field
from app.xml_service import ler_xml_unico, persistir_documento_fiscal
Base.metadata.create_all(engine, tables=[models.Plano.__table__, models.User.__table__,
    models.Empresa.__table__, models.DocumentoFiscal.__table__, models.ItemFiscal.__table__])
with SessionLocal() as db:
    user = models.User(email='owner@example.invalid', hashed_password='unused')
    db.add(user); db.flush()
    company = models.Empresa(user_id=user.id, cnpj='12345678000195', regime_tributario='mei')
    db.add(company); db.commit()
    for number, nature, purpose in [(1, 'VENDA INFORMADA', '1'), (2, 'OPERACAO INFORMADA', '4'), (3, None, None)]:
        observation_tags = ('<natOp>' + nature + '</natOp>' if nature else '') + ('<finNFe>' + purpose + '</finNFe>' if purpose else '')
        xml = ('<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe>'
            '<emit><CNPJ>12345678000195</CNPJ></emit><ide><nNF>' + str(number) +
            '</nNF><tpNF>1</tpNF>' + observation_tags + '</ide>'
            '<det nItem="1"><prod><CFOP>5102</CFOP><qCom>1</qCom><vProd>60.00</vProd></prod></det>'
            '<det nItem="2"><prod><CFOP>5910</CFOP><qCom>1</qCom><vProd>40.00</vProd></prod></det>'
            '<total><ICMSTot><vNF>100.00</vNF></ICMSTot></total>'
            '</infNFe></NFe></nfeProc>').encode()
        digest = sha256(xml).hexdigest()
        data = ler_xml_unico(xml_bytes=xml)
        assert data['natureza_operacao_observada'] == nature
        assert data['finalidade_emissao_observada'] == purpose
        document = persistir_documento_fiscal(db, user, company, data, conteudo_sha256=digest)
        db.expire_all()
        persisted = db.get(models.DocumentoFiscal, document.id)
        assert persisted.natureza_operacao_observada == nature
        assert persisted.finalidade_emissao_observada == purpose
        assert persisted.conteudo_sha256 == digest and persisted.empresa_id == company.id
        assert sorted(item.cfop for item in persisted.itens) == ['5102', '5910']
        assert 'receita_confirmada' not in data and 'categoria_receita' not in data
    legacy = models.DocumentoFiscal(empresa_id=company.id, usuario_id=user.id)
    db.add(legacy); db.commit(); db.refresh(legacy)
    assert legacy.natureza_operacao_observada is None
    assert legacy.finalidade_emissao_observada is None
    assert db.query(models.DocumentoFiscal).count() == 4
engine.dispose()
print('MEI_XML_OPERATION_OBSERVATIONS=PASS')
'''


class XmlOperationObservationContract(unittest.TestCase):
    def test_xml_operation_observations_preserve_items_and_unknown_legacy(self):
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
            self.assertIn("MEI_XML_OPERATION_OBSERVATIONS=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
