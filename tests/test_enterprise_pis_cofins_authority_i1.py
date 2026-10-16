"""I1: RED/GREEN - recusa ST como ICMS proprio e prova simulacao isolada.

Apenas snapshots/documentos ficticios. Sem base, SEFAZ, LLM, pagamentos ou deploy.
"""
import importlib
from copy import deepcopy
import unittest
from unittest.mock import patch

from app.services.resultado_empresarial_service import compor_resultado_empresarial
from app.services.enterprise_integral_projection import projetar_diagnostico_integral_i0


class EnterprisePisCofinsAuthorityI1Tests(unittest.TestCase):
    def _adapter(self):
        try:
            return importlib.import_module('app.services.enterprise_pis_cofins_authority_i1')
        except ModuleNotFoundError as e:
            if e.name == 'app.services.enterprise_pis_cofins_authority_i1':
                self.fail('I1_RED_CAUSAL_ADAPTER_NOT_PRESENT')
            raise

    def _resultado(self):
        fiscal = {'dados_fiscais': {'chave_nfe': '1' * 44}, 'insights': [],
                  'previsao_recuperacao': {}, 'context_flags': {}}
        inteligencia = {'empresa_id': 41, 'oportunidades': [], 'creditos_detectados': [],
                        'resultados_engines': {'pis_cofins': {
                            'tributos': {'pis': 700.0, 'cofins': 2000.0},
                            'creditos': {'pis': 400.0, 'cofins': 1000.0},
                            'bases_calculo': {'icms_excluido': 123.0}, 'regime': 'real'}},
                        'context_flags': {'dados_incompletos': True}}
        return compor_resultado_empresarial(41, fiscal, inteligencia)

    def _prova_declarada(self):
        return {'empresa_id': 41, 'regime': 'real', 'competencia': '2026-09',
                'documentos': [{
                    'empresa_id': 41, 'documento_id': 10, 'sha256': 'a' * 64,
                    'competencia': '2026-09', 'tipo_operacao': 'saida',
                    'papel_empresa': 'emitente', 'modalidade_icms': 'ICMS_PROPRIO',
                    'receita_documental': '1000.00', 'icms_proprio_documental': '80.00'}]}

    def _run(self, evidencia=None, resultado=None):
        return self._adapter().projetar_diagnostico_integral_i1(
            resultado=resultado or self._resultado(), empresa_id=41,
            evidencia_documental=evidencia)

    def _map(self, proj):
        return {x['id']: x for x in proj['cobertura']}

    def test_00_adapter_is_required(self):
        self.assertTrue(callable(self._adapter().projetar_diagnostico_integral_i1))

    def test_01_icms_st_legacy_does_not_publish_amounts(self):
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins') as calc:
            proj = self._run()
        calc.assert_not_called()
        rows = self._map(proj)
        for name in ('pis', 'cofins', 'credito_pis', 'credito_cofins'):
            self.assertIsNone(rows[name]['resultado_bruto_nao_validado'])
            self.assertIsNone(rows[name]['simulacao_condicional'])
            self.assertEqual(rows[name]['estado'], 'nao_apurado')
        self.assertEqual(rows['pis']['causa'], 'I1_EVIDENCIA_DOCUMENTAL_AUSENTE')
        self.assertFalse(proj['checkout_autorizado'])

    def test_02_documental_consistente_chama_motor_sem_st_nem_credito_manual(self):
        mock = {'tributos': {'pis': 15.18, 'cofins': 69.92}, 'creditos': {'pis': 0, 'cofins': 0}}
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins', return_value=mock) as calc:
            proj = self._run(self._prova_declarada())
        calc.assert_called_once()
        args, kwargs = calc.call_args
        self.assertEqual(kwargs, {'regime': 'real'})
        self.assertEqual(args[0]['faturamento'], 1000.0)
        self.assertEqual(args[0]['icms'], 80.0)
        self.assertNotIn('icms_pago', args[0])
        self.assertNotIn('icms_devido', args[0])
        self.assertNotIn('insumos_tributados', args[0])
        self.assertNotIn('creditos_pis_cofins', args[0])
        rows = self._map(proj)
        self.assertEqual(rows['pis']['simulacao_condicional'], 15.18)
        self.assertEqual(rows['cofins']['simulacao_condicional'], 69.92)
        self.assertEqual(rows['credito_pis']['estado'], 'nao_apurado')
        self.assertIsNone(rows['credito_pis']['simulacao_condicional'])
        self.assertFalse(rows['pis']['autoridade_fiscal'])
        self.assertFalse(proj['checkout_autorizado'])
        self.assertEqual(proj['pis_cofins_i1']['estado'], 'simulacao_sem_prova')

    def test_03_st_rotulado_como_proprio_recusado(self):
        ev = self._prova_declarada()
        ev['documentos'][0]['modalidade_icms'] = 'ICMS_ST'
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins') as calc:
            proj = self._run(ev)
        calc.assert_not_called()
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_ST_NAO_E_ICMS_PROPRIO')

    def test_04_falta_de_icms_nao_e_zero(self):
        ev = self._prova_declarada()
        del ev['documentos'][0]['icms_proprio_documental']
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['estado'], 'nao_apurado')
        self.assertIsNone(self._map(proj)['pis']['simulacao_condicional'])

    def test_05_documento_de_outra_empresa_recusado(self):
        ev = self._prova_declarada()
        ev['documentos'][0]['empresa_id'] = 42
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_IDENTIDADE_OPERACAO_INCOERENTE')

    def test_06_periodo_divergente_recusado(self):
        ev = self._prova_declarada()
        ev['documentos'][0]['competencia'] = '2026-08'
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_IDENTIDADE_OPERACAO_INCOERENTE')

    def test_07_hash_duplicado_recusado(self):
        ev = self._prova_declarada()
        second = deepcopy(ev['documentos'][0])
        second['documento_id'] = 20
        ev['documentos'].append(second)
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_HASH_AUSENTE_OU_DUPLICADO')

    def test_08_icms_maior_que_receita_recusado(self):
        ev = self._prova_declarada()
        ev['documentos'][0]['icms_proprio_documental'] = '1000.01'
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_ICMS_MAIOR_QUE_RECEITA_DOCUMENTAL')

    def test_09_valor_lixo_ou_negativo_recusado(self):
        for amount in (-1, '-1.00', 'nan', 'Inf', '1e6', '0.0001'):
            with self.subTest(amount=amount):
                ev = self._prova_declarada()
                ev['documentos'][0]['icms_proprio_documental'] = amount
                proj = self._run(ev)
                self.assertEqual(proj['pis_cofins_i1']['estado'], 'nao_apurado')

    def test_10_mei_nao_recebe_simulacao(self):
        ev = self._prova_declarada()
        ev['regime'] = 'mei'
        proj = self._run(ev)
        self.assertEqual(proj['pis_cofins_i1']['causa'], 'I1_REGIME_NAO_COMPROVADO')

    def test_11_falha_motor_legacy_e_explicita(self):
        result = self._resultado()
        result['resultados_engines']['pis_cofins'] = {
            'codigo': 'TEMPO_NORMATIVO_AUSENTE', 'erro': 'falta norma', 'estado_l3': 'bloqueado'}
        proj = self._run(self._prova_declarada(), result)
        self.assertEqual(self._map(proj)['cofins']['estado'], 'falha_motor')
        self.assertIsNone(self._map(proj)['cofins']['simulacao_condicional'])

    def test_12_resultado_de_outra_empresa_recusado(self):
        with self.assertRaisesRegex(ValueError, 'I0_EMPRESA_DIVERGENTE'):
            self._adapter().projetar_diagnostico_integral_i1(resultado=self._resultado(), empresa_id=42)

    def test_13_i0_intacto_e_catalogo_integral_preservado(self):
        original = self._resultado()
        old = projetar_diagnostico_integral_i0(resultado=original, empresa_id=41)
        new = self._run(resultado=original)
        self.assertEqual(len(old['cobertura']), len(new['cobertura']))
        self.assertEqual(self._map(new)['irpj']['estado'], self._map(old)['irpj']['estado'])
        self.assertEqual(original['resultados_engines']['pis_cofins']['tributos']['pis'], 700.0)

    def test_14_falha_calculo_nao_vira_zero(self):
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins', side_effect=RuntimeError('falhou')):
            proj = self._run(self._prova_declarada())
        self.assertEqual(proj['pis_cofins_i1']['estado'], 'falha_motor')
        self.assertIsNone(self._map(proj)['pis']['simulacao_condicional'])

    def test_15_dados_documentais_nao_sao_atestado(self):
        mock = {'tributos': {'pis': 6.5, 'cofins': 30.0}}
        with patch('app.services.tax_engines.pis_cofins_engine.calcular_pis_cofins', return_value=mock):
            p = self._run(self._prova_declarada())
        self.assertEqual(p['uso'], 'INTERNO_NAO_PUBLICAVEL')
        self.assertFalse(p['comprovacao_normativa'])
        self.assertFalse(p['diagnostico_empresarial_completo'])
        self.assertIsNone(self._map(p)['pis']['resultado_bruto_nao_validado'])
        self.assertEqual(self._map(p)['pis']['estado'], 'informativo_sem_prova')


if __name__ == '__main__':
    unittest.main()
