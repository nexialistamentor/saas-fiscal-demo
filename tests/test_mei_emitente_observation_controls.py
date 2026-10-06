import unittest
from app.services.mei_emitente_observation import comparar_emitente_observado


class EmitterObservationControls(unittest.TestCase):
    def test_noncanonical_identifiers_never_match_by_coercion(self):
        for emitter in (12345678000195, '１２３４５６７８０００１９５', '12.345.678/0001-95', '12345678000195 '):
            with self.subTest(emitter=emitter):
                result = comparar_emitente_observado(documento_id=1, cnpj_empresa='12345678000195', cnpj_emitente=emitter)
                self.assertEqual(result['estado'], 'invalido')
                self.assertEqual(result['cnpj_emitente_observado'], emitter)

    def test_equal_strings_do_not_produce_fiscal_or_revenue_authority(self):
        result = comparar_emitente_observado(documento_id=1, cnpj_empresa='12345678000195', cnpj_emitente='12345678000195')
        self.assertEqual(result, {'documento_id': 1, 'estado': 'coincidente', 'cnpj_emitente_observado': '12345678000195'})


if __name__ == '__main__':
    unittest.main()
