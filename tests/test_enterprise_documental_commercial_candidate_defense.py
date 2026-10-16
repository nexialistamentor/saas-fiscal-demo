"""P1-04B — defesa da candidatura somente informativa; nenhuma transacao."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

from app.services import enterprise_documental_commercial_candidate as subject

CAPABILITY = 'enterprise.diagnostic.documental'
CODE = 'enterprise-documental-diagnostic-one-time-company'
READY = {
    'documental_suficiente': True,
    'empresarial_completo': False,
    'st_nao_destacado_observado': False,
    'politica_diagnostico_elegivel': False,
    'diagnostico_documental_apresentavel': True,
    'checkout_autorizado': False,
}
DENIED = {
    'oferta_documental_valida': False,
    'candidatura_comercial': False,
    'checkout_autorizado': False,
}
CANDIDATE = {
    'oferta_documental_valida': True,
    'candidatura_comercial': True,
    'checkout_autorizado': False,
}
XML = b'<synthetic-placeholder/>'


def _offer(**changes):
    props = dict(
        id=101, codigo=CODE, nome_publico='Diagnostico documental teste',
        estado='published', checkout_mode='automatic', vertical='tax',
        commercial_model='one_time', subject_type='company',
        moeda='BRL', preco=Decimal('1.00'), usage_unit='diagnostic',
        usage_limit=1, billing_period=None, contract_version=1,
        capabilities=(CAPABILITY,),
    )
    props.update(changes)
    return SimpleNamespace(**props)


def _evaluate(*, oferta=None, ready=None, **changes):
    kwargs = dict(authenticated_user_id=11, empresa_id=21, relatorio_id=501,
                  xml_bytes=XML, oferta=_offer() if oferta is None else oferta)
    kwargs.update(changes)
    with patch.object(subject, 'avaliar_prontidao_diagnostico_enterprise',
                      return_value=deepcopy(READY if ready is None else ready)) as spy:
        result = subject.avaliar_candidatura_comercial_documental(object(), **kwargs)
    return result, spy


class P104BCandidateDefense(TestCase):
    def test_01_valid_negative_diagnostic_without_st_never_checkout(self):
        oferta = _offer()
        before = deepcopy(vars(oferta))
        result, spy = _evaluate(oferta=oferta)
        self.assertEqual(result, CANDIDATE)
        self.assertEqual(vars(oferta), before)
        self.assertEqual(spy.call_count, 1)
        self.assertFalse(result['checkout_autorizado'])

    def test_02_validation_precedes_readiness_and_rejects_boolean_ids(self):
        for field, value in (('id', True), ('id', 0), ('id', '101'),
                             ('contract_version', True), ('contract_version', 0),
                             ('usage_limit', True), ('usage_limit', 1.0)):
            with self.subTest(field=field, value=value):
                result, spy = _evaluate(oferta=_offer(**{field: value}))
                self.assertEqual(result, DENIED)
                spy.assert_not_called()

    def test_03_malformed_money_cannot_be_accepted(self):
        for value in (None, True, 1.0, '1.00', Decimal('0'),
                      Decimal('-1'), Decimal('NaN'), Decimal('Infinity'),
                      Decimal('1.001'), Decimal('0E-2')):
            with self.subTest(value=str(value)):
                result, spy = _evaluate(oferta=_offer(preco=value))
                self.assertEqual(result, DENIED)
                spy.assert_not_called()

    def test_04_missing_offer_fields_and_extra_capabilities_fail_closed(self):
        for key, value in (
            ('capabilities', (CAPABILITY, 'tax.report')),
            ('capabilities', ['enterprise.diagnostic.documental']),
            ('capabilities', ('tax.report',)),
            ('codigo', 'tax-report-one-time-company'),
            ('estado', 'draft'), ('vertical', 'document'),
            ('checkout_mode', 'proposal'), ('nome_publico', ''),
            ('nome_publico', ' a '), ('nome_publico', 'bad\nname')
        ):
            with self.subTest(key=key):
                result, spy = _evaluate(oferta=_offer(**{key: value}))
                self.assertEqual(result, DENIED)
                spy.assert_not_called()
        empty = SimpleNamespace()
        self.assertEqual(_evaluate(oferta=empty)[0], DENIED)

    def test_05_prontidao_invalida_nunca_autoriza_compra(self):
        for change in (
            {'documental_suficiente': False},
            {'diagnostico_documental_apresentavel': False},
            {'empresarial_completo': True},
            {'checkout_autorizado': True},
            {'st_nao_destacado_observado': None},
            {'politica_diagnostico_elegivel': 1},
        ):
            with self.subTest(change=change):
                state = dict(READY, **change)
                result, spy = _evaluate(ready=state)
                self.assertEqual(result, DENIED)
                spy.assert_called_once()
        invalid = dict(READY, unauthorized=True)
        self.assertEqual(_evaluate(ready=invalid)[0], DENIED)

    def test_06_readiness_raises_or_returns_malformed_denies(self):
        with patch.object(subject, 'avaliar_prontidao_diagnostico_enterprise',
                          side_effect=RuntimeError('sensitive')):
            got = subject.avaliar_candidatura_comercial_documental(
                object(), authenticated_user_id=11, empresa_id=21,
                relatorio_id=501, xml_bytes=XML, oferta=_offer(),
            )
        self.assertEqual(got, DENIED)
        for state in ([], 'true', {}, {'documental_suficiente': True}):
            self.assertEqual(_evaluate(ready=state)[0], DENIED)

    def test_07_input_guard_prevents_readiness_execution(self):
        for changes in (
            {'authenticated_user_id': True}, {'empresa_id': '21'},
            {'relatorio_id': -1}, {'xml_bytes': None},
            {'xml_bytes': bytearray(XML)}, {'xml_bytes': b''},
            {'xml_bytes': b'x' * (2 * 1024 * 1024 + 1)},
        ):
            with self.subTest(change=str(changes)[:50]):
                result, spy = _evaluate(**changes)
                self.assertEqual(result, DENIED)
                spy.assert_not_called()

    def test_08_static_scope_no_checkout_imports_or_write_paths(self):
        source = Path(subject.__file__).read_text(encoding='utf-8-sig')
        for name in ('CheckoutOfferPrerequisite', 'OrdemCheckout',
                     'TaxReportCheckoutIntent', 'MeiCompetenciaCheckoutPrerequisite',
                     'mercado_pago', 'SessionLocal', 'db.commit(', 'db.add('):
            self.assertNotIn(name, source)
        self.assertIn('"checkout_autorizado": False', source)


if __name__ == '__main__':
    main(verbosity=2)
