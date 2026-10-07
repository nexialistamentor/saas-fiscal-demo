"""Exercise the deployed route body with local stubs; never call external services."""
import ast
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class Blocked(Exception):
    def __init__(self, status, reason):
        self.status = status
        self.reason = reason


class RouteDiagnosticContract(unittest.TestCase):
    def setUp(self):
        source = (ROOT / 'app/routes/imposto_router.py').read_text(encoding='utf-8-sig')
        tree = ast.parse(source)
        route = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name == 'obter_das_mei_oficial')
        route.decorator_list = []
        route.returns = None
        route.args.defaults = []
        for arg in route.args.args:
            arg.annotation = None
        # Include diagnostic constants/helpers if present, preserving their real code.
        diagnostic = [node for node in tree.body
                      if (isinstance(node, ast.FunctionDef) and node.name == '_log_mei_das_failure')
                      or (isinstance(node, ast.Assign) and any(
                          isinstance(target, ast.Name) and target.id == '_MEI_DAS_FAILURE_REASONS'
                          for target in node.targets))]
        self.log = logging.getLogger('mei_das_route_contract')
        self.ns = dict(os=os, logging=logging, logger=self.log,
                       _SERVICOS_PGMEI={'pdf': 'GERARDASPDF21'},
                       _cnpj_canonico=lambda value: value,
                       _bloqueio=lambda status, reason: Blocked(status, reason),
                       _tem_autoridade_economica_mei_competencia=lambda **kwargs: True,
                       _motivo_nao_emissao=lambda messages: 'SEM_DAS_A_EMITIR',
                       _normalizar_documento_oficial=lambda *args: {'pdf_base64': 'safe-fixture'})
        exec(compile(ast.fix_missing_locations(ast.Module(body=diagnostic + [route],
             type_ignores=[])), '<actual-route-body>', 'exec'), self.ns)
        self.company = SimpleNamespace(id=80, status_empresa='ativa',
                                       regime_tributario='mei', cnpj='private-cnpj')
        self.body = SimpleNamespace(formato='pdf', periodo_apuracao='202609')
        self.client = SimpleNamespace(request=lambda *args: SimpleNamespace(data='[]', messages=[]))
        self.ns['_get_serpro_pgmei_client'] = lambda: self.client

    def call(self):
        with patch.dict(os.environ, {'SERPRO_PGMEI_ACCESS_MODE': 'tenant'}):
            return self.ns['obter_das_mei_oficial'](None, self.body, self.company)

    def failure(self, stage):
        with self.assertLogs(self.log, level='WARNING') as captured:
            with self.assertRaises(Blocked) as raised:
                self.call()
        self.assertEqual(raised.exception.status, 502)
        self.assertEqual(raised.exception.reason, 'AUTORIDADE_OFICIAL_MEI_FALHOU')
        output = '\n'.join(captured.output)
        self.assertIn('mei_das_route_failure stage=' + stage, output)
        for private in ('private-cnpj', 'private-token', 'private-response', '202609'):
            self.assertNotIn(private, output)
        return output

    def test_request_failure_is_sanitized(self):
        def fail(*args):
            raise RuntimeError('private-token private-response')
        self.client.request = fail
        self.failure('official_request')

    def test_invalid_data_type_has_response_stage(self):
        self.client.request = lambda *args: SimpleNamespace(data={'private-response': 1})
        self.failure('official_response')

    def test_non_emission_failure_has_separate_stage(self):
        self.client.request = lambda *args: SimpleNamespace(data='', messages=[])
        def fail(messages):
            raise ValueError('private-response')
        self.ns['_motivo_nao_emissao'] = fail
        self.failure('non_emission_reason')

    def test_normalization_failure_is_sanitized(self):
        def fail(*args):
            raise ValueError('cnpj oficial divergente')
        self.ns['_normalizar_documento_oficial'] = fail
        output = self.failure('document_normalization')
        self.assertIn('reason=cnpj_mismatch', output)

    def test_unrecognized_exception_text_is_not_logged(self):
        def fail(*args):
            raise ValueError('private-token private-response')
        self.ns['_normalizar_documento_oficial'] = fail
        output = self.failure('document_normalization')
        self.assertIn('reason=unclassified', output)

    def test_denied_purchase_never_calls_provider(self):
        self.ns['_tem_autoridade_economica_mei_competencia'] = lambda **kwargs: False
        self.client.request = lambda *args: self.fail('Provider must not be called')
        with self.assertRaises(Blocked) as raised:
            self.call()
        self.assertEqual(raised.exception.status, 403)

    def test_success_preserves_response_without_failure_log(self):
        with self.assertNoLogs(self.log, level='WARNING'):
            result = self.call()
        self.assertEqual(result['estado_oficial'], 'emitido')
        self.assertEqual(result['empresa_id'], 80)
        self.assertEqual(result['periodo_apuracao'], '202609')


if __name__ == '__main__':
    unittest.main()
