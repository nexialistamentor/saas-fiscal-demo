"""P1-04A: defesa do leitor comercial restrito (sem HTTP ou compras)."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from test_enterprise_diagnostic_readiness_contract_red import (
    CHAVE, DOCUMENTAL_LIMITADO, EMPRESA, NEGADO, RELATORIO, ROOT,
    UTILIZADOR, XML, _LeituraDB, _contexto_persistido,
)
from app.services import enterprise_diagnostic_readiness as readiness
from app.services.resultado_provenance_service import fingerprint_resultado_json


def _avaliar(db, *, user=UTILIZADOR, tenant=EMPRESA, rel_id=RELATORIO, raw=XML):
    return readiness.avaliar_prontidao_diagnostico_enterprise(
        db, authenticated_user_id=user, empresa_id=tenant,
        relatorio_id=rel_id, xml_bytes=raw,
    )


class P104ReadinessDefense(TestCase):
    def test_01_documental_limitado_preserva_estado_e_nao_escreve(self):
        rel, doc = _contexto_persistido()
        copy_before = deepcopy(rel.resultado_json)
        db = _LeituraDB(rel, doc)
        self.assertEqual(_avaliar(db), DOCUMENTAL_LIMITADO)
        self.assertEqual(db.requests, [('RelatorioAnalise', RELATORIO), ('DocumentoFiscal', doc.id)])
        self.assertEqual(db.writes, 0)
        self.assertEqual(rel.resultado_json, copy_before)

    def test_02_ids_bytes_e_db_invalidos_falham_sem_consulta(self):
        for args in (
            dict(user=True), dict(user='11'), dict(user=0), dict(tenant=-1),
            dict(tenant=True), dict(rel_id=0), dict(rel_id=False),
            dict(raw='not-bytes'), dict(raw=b''), dict(raw=b'x'* (2*1024*1024 + 1)),
        ):
            with self.subTest(args=list(args)):
                rel, doc = _contexto_persistido()
                db = _LeituraDB(rel, doc)
                self.assertEqual(_avaliar(db, **args), NEGADO)
                self.assertEqual(db.requests, [])
                self.assertEqual(db.writes, 0)
        self.assertEqual(_avaliar(None), NEGADO)

    def test_03_fingerprint_invalido_nao_pode_resolver_documento(self):
        rel, doc = _contexto_persistido()
        rel.fingerprint = '0'*64
        db = _LeituraDB(rel, doc)
        self.assertEqual(_avaliar(db), NEGADO)
        self.assertEqual(db.requests, [('RelatorioAnalise', RELATORIO)])

    def test_04_mesma_chave_outros_bytes_sao_rejeitados(self):
        rel, doc = _contexto_persistido()
        self.assertEqual(_avaliar(_LeituraDB(rel, doc), raw=XML.replace(b'1499.00', b'1499.01')), NEGADO)
        self.assertEqual(_avaliar(_LeituraDB(rel, doc), raw=XML.replace(CHAVE.encode(), b'2'*44)), NEGADO)

    def test_05_resultado_positivo_de_politica_nao_autoriza_checkout(self):
        rel, doc = _contexto_persistido()
        snapshot = deepcopy(rel.resultado_json)
        snapshot['context_flags']['documental']['dados_incompletos'] = False
        snapshot['context_flags']['empresarial']['dados_incompletos'] = False
        rel.resultado_json = snapshot
        rel.fingerprint = fingerprint_resultado_json(snapshot)
        received = _avaliar(_LeituraDB(rel, doc))
        self.assertTrue(received['politica_diagnostico_elegivel'])
        self.assertTrue(received['diagnostico_documental_apresentavel'])
        self.assertFalse(received['empresarial_completo'])
        self.assertFalse(received['checkout_autorizado'])

    def test_06_cobertura_empresarial_nao_comprovada_falha_fechado(self):
        rel, doc = _contexto_persistido()
        bogus = {'documental_suficiente': True, 'empresarial_completo': True,
                 'st_nao_destacado_observado': True}
        with patch.object(readiness, 'avaliar_cobertura_nfe_documental', return_value=bogus):
            self.assertEqual(_avaliar(_LeituraDB(rel, doc)), NEGADO)

    def test_07_erro_consulta_e_shape_da_cobertura_falham_fechado(self):
        class BrokenDB:
            def get(self, *_):
                raise RuntimeError('DB not available')
        self.assertEqual(_avaliar(BrokenDB()), NEGADO)
        rel, doc = _contexto_persistido()
        for invalid in (None, {}, {'documental_suficiente': True},
                        {'documental_suficiente': 1,
                         'empresarial_completo': False,
                         'st_nao_destacado_observado': True}):
            with self.subTest(invalid=invalid), patch.object(
                readiness, 'avaliar_cobertura_nfe_documental', return_value=invalid,
            ):
                self.assertEqual(_avaliar(_LeituraDB(rel, doc)), NEGADO)

    def test_08_nao_importa_gates_comerciais_nem_runtime(self):
        source = (ROOT / 'app/services/enterprise_diagnostic_readiness.py').read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports |= {alias.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                    for alias in n.names}
        forbidden = {'app.database', 'app.jobs.analysis_job',
            'app.services.tax_report_eligibility',
            'app.services.tax_report_checkout_intent',
            'app.services.tax_report_acquisition',
            'app.services.checkout_offer_prerequisite',
            'app.services.checkout_offer_catalog',
            'app.services.mercado_pago_gateway'}
        self.assertFalse(forbidden & imports)
        self.assertNotIn('checkout_autorizado": True', source)


if __name__ == '__main__':
    main(verbosity=2)
