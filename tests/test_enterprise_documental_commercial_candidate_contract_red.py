"""P1-04B — contrato RED: oferta DOCUMENTAL especifica, sem autoridade de checkout.

Isolado, sem rede e sem base produtiva. Codigo/capability sao IDs de contrato
PROVISORIOS, NAO configuracoes de venda nem preco ratificado.
Executar: ALEMBIC_RUNNING=1 python -B tests/test_enterprise_documental_commercial_candidate_contract_red.py
"""
from __future__ import annotations

import ast
from copy import deepcopy
from decimal import Decimal
import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'app/services/enterprise_documental_commercial_candidate.py'
READINESS = ROOT / 'app/services/enterprise_diagnostic_readiness.py'
PREREQUISITE = ROOT / 'app/services/checkout_offer_prerequisite.py'
COMPOSER = ROOT / 'app/services/checkout_offer_order_composition.py'

# IDs tecnicos candidatos; este teste NAO publica oferta, nao escolhe preco.
OFFER_CODE = 'enterprise-documental-diagnostic-one-time-company'
CAPABILITY = 'enterprise.diagnostic.documental'
USER, EMPRESA, REPORT = 11, 21, 501
XML = b'<isolated-xml-placeholder-not-for-fiscal-processing/>'
READY = {
    'documental_suficiente': True,
    'empresarial_completo': False,
    'st_nao_destacado_observado': True,
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


def _offer(**changes):
    # Preco artificial de teste. NENHUM valor comercial real fica estabelecido.
    props = dict(
        id=101, codigo=OFFER_CODE, nome_publico='Diagnostico documental (fixture)',
        estado='published', checkout_mode='automatic', vertical='tax',
        commercial_model='one_time', subject_type='company',
        moeda='BRL', preco=Decimal('1.00'), usage_unit='diagnostic',
        usage_limit=1, billing_period=None, contract_version=1,
        capabilities=(CAPABILITY,),
    )
    props.update(changes)
    return SimpleNamespace(**props)


def _load():
    if not MODULE.is_file():
        raise AssertionError('P104B_COMMERCIAL_CANDIDATE_MODULE_MISSING')
    mod = importlib.import_module('app.services.enterprise_documental_commercial_candidate')
    f = getattr(mod, 'avaliar_candidatura_comercial_documental', None)
    if not callable(f):
        raise AssertionError('P104B_COMMERCIAL_CANDIDATE_API_MISSING')
    return mod, f


def _decision(mod, f, *, readiness=READY, offer=None, db=None,
              who=USER, empresa=EMPRESA, relatorio=REPORT, xml=XML):
    if offer is None:
        offer = _offer()
    if db is None:
        db = object()
    spy_path = 'app.services.enterprise_documental_commercial_candidate.avaliar_prontidao_diagnostico_enterprise'
    with patch(spy_path, return_value=deepcopy(readiness)) as spy:
        result = f(
            db, authenticated_user_id=who, empresa_id=empresa,
            relatorio_id=relatorio, xml_bytes=xml, oferta=offer,
        )
        assert type(result) is dict and set(result) == set(DENIED), 'P104B_SCHEMA_INVALID'
        assert all(type(v) is bool for v in result.values()), 'P104B_BOOLEAN_REQUIRED'
        assert result['checkout_autorizado'] is False, 'P104B_PAYMENT_AUTHORITY_ESCALATION'
        # Only valid identity/request data may reach the P1-04A verifier.
        if spy.called:
            spy.assert_called_once_with(db, authenticated_user_id=who, empresa_id=empresa,
                                        relatorio_id=relatorio, xml_bytes=xml)
        return result


class P104BDocumentalCommercialCandidateRED(TestCase):
    def test_01_fronteiras_existentes_e_checkout_legado_intactos(self):
        for path in (READINESS, PREREQUISITE, COMPOSER):
            self.assertTrue(path.is_file())
        readiness_ast = ast.parse(READINESS.read_text(encoding='utf-8-sig'))
        self.assertIn('checkout_autorizado', READINESS.read_text(encoding='utf-8-sig'))
        self.assertNotIn('CheckoutOfferPrerequisite', ast.dump(readiness_ast))
        previous = PREREQUISITE.read_text(encoding='utf-8-sig')
        self.assertIn('tax-report-one-time-company', previous)
        self.assertIn('TaxReportCheckoutIntent', previous)
        composer = COMPOSER.read_text(encoding='utf-8-sig')
        self.assertIn('CheckoutOfferPrerequisite(sessao).require(', composer)
        self.assertIn('MeiCompetenciaCheckoutPrerequisite(sessao).require(', composer)

    def test_02_sem_autorizacao_checkout_no_documental_p104a(self):
        source = READINESS.read_text(encoding='utf-8-sig')
        self.assertIn('"checkout_autorizado": False', source)
        self.assertIn('"empresarial_completo": False', source)
        self.assertFalse(READY['politica_diagnostico_elegivel'])
        self.assertTrue(READY['diagnostico_documental_apresentavel'])
        self.assertFalse(READY['checkout_autorizado'])

    def test_03_candidato_documental_valido_nao_inicia_checkout(self):
        mod, func = _load()
        db, oferta = object(), _offer()
        original = deepcopy(vars(oferta))
        self.assertEqual(_decision(mod, func, db=db, offer=oferta), CANDIDATE,
                         'P104B_DOCUMENTAL_VALID_CANDIDACY_BLOCKED')
        self.assertEqual(vars(oferta), original, 'P104B_OFFER_MUTATED')
        self.assertEqual(_decision(mod, func, readiness=dict(READY, politica_diagnostico_elegivel=True)),
                         CANDIDATE, 'P104B_LEGACY_ST_GATE_WRONGLY_REQUIRED')

    def test_04_ofertas_erradas_e_prontidao_incompleta_falham_fechado(self):
        mod, func = _load()
        edits = (
            {'codigo': 'tax-report-one-time-company'},
            {'codigo': 'mei-competencia-one-time-company'},
            {'capabilities': ('tax.report',)},
            {'capabilities': (CAPABILITY, 'tax.report')},
            {'capabilities': []},
            {'estado': 'draft'}, {'estado': 'revoked'},
            {'checkout_mode': 'proposal'}, {'vertical': 'document'},
            {'commercial_model': 'monthly'}, {'subject_type': 'cpf'},
            {'moeda': 'USD'}, {'preco': Decimal('0')},
            {'preco': Decimal('NaN')}, {'preco': True},
            {'billing_period': 'month'}, {'usage_limit': 0},
            {'usage_limit': 2}, {'usage_unit': 'month'},
            {'contract_version': 0}, {'id': True},
        )
        for edit in edits:
            with self.subTest(offer=edit):
                got = _decision(mod, func, offer=_offer(**edit))
                self.assertEqual(got, DENIED, 'P104B_INVALID_OFFER_ACCEPTED')
        bad_readiness = (
            dict(READY, documental_suficiente=False),
            dict(READY, diagnostico_documental_apresentavel=False),
            dict(READY, empresarial_completo=True),
            dict(READY, checkout_autorizado=True),
            dict(READY, documental_suficiente=1),
            dict(READY, politica_diagnostico_elegivel='true'),
            {**READY, 'outra_chave': True}, {}, None,
        )
        for state in bad_readiness:
            with self.subTest(state=state):
                self.assertEqual(_decision(mod, func, readiness=state), DENIED,
                                 'P104B_UNPROVEN_READINESS_ACCEPTED')
        for overrides in ({'who': True}, {'who': 0}, {'empresa': 0},
                          {'empresa': None}, {'relatorio': '501'},
                          {'xml': 'not-bytes'}, {'xml': b''}):
            with self.subTest(input=overrides):
                self.assertEqual(_decision(mod, func, **overrides), DENIED)

    def test_05_sem_escalada_checkout_nem_dependencias_mutantes(self):
        mod, func = _load()
        tree = ast.parse(MODULE.read_text(encoding='utf-8-sig'))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.add(node.module or '')
            elif isinstance(node, ast.Import):
                imports.update(n.name for n in node.names)
        forbidden = {
            'app.services.tax_report_checkout_intent',
            'app.services.tax_report_acquisition',
            'app.services.checkout_offer_order_composition',
            'app.services.checkout_offer_prerequisite',
            'app.services.mei_competencia_checkout_prerequisite',
            'app.services.mercado_pago_checkout_offer_one_time',
        }
        self.assertFalse(forbidden & imports, 'P104B_SHARED_CHECKOUT_IMPORTED')
        self.assertEqual(_decision(mod, func), CANDIDATE)
        self.assertFalse(_decision(mod, func)['checkout_autorizado'])
        # A candidatura e apenas informativa. P1-04C tera de impor
        # pre-condicao transacional no composer ANTES de publicar uma oferta.


if __name__ == '__main__':
    main(verbosity=2)
