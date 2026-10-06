"""Test-only loopback backend. Never deploy this file."""
import base64
import json
import os
import socket
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

repo = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(repo))
os.chdir(repo)
assert os.environ['ENVIRONMENT'] == 'test'
assert os.environ['DATABASE_URL'].startswith('postgresql+psycopg2://')
assert '@127.0.0.1:' in os.environ['DATABASE_URL']
assert os.environ['MERCADO_PAGO_ENABLED'] == 'false'
assert os.environ['SERPRO_PGMEI_ENABLED'] == 'false'

connect = socket.socket.connect
connect_ex = socket.socket.connect_ex
def guard(address):
    if not isinstance(address, tuple) or address[0] not in ('127.0.0.1', 'localhost', '::1'):
        raise RuntimeError('TEST_EXTERNAL_NETWORK_BLOCKED')
def local_connect(self, address):
    guard(address)
    return connect(self, address)
def local_connect_ex(self, address):
    guard(address)
    return connect_ex(self, address)
socket.socket.connect = local_connect
socket.socket.connect_ex = local_connect_ex

from app.database import Base, engine, SessionLocal
from app import models
TABLES = ['planos', 'usuarios', 'empresas', 'checkout_offers', 'checkout_offer_capabilities', 'checkout_offer_campaigns', 'ordens_checkout', 'ordem_checkout_capabilities', 'checkout_offer_campaign_reservations', 'tax_report_checkout_intents', 'mei_competencia_checkout_intents', 'mercado_pago_payment_observations', 'eventos_pagamento', 'relatorios_analise', 'pagamentos', 'checkout_offer_grants', 'checkout_offer_grant_capabilities', 'mei_competencia_authority_bindings', 'termos_aceitacao', 'consentimentos_lgpd', 'request_logs', 'alertas_fiscais', 'entitlements', 'checkout_offer_grant_consumptions', 'tax_report_acquisition_bindings']
TABLES.append('documentos_fiscais')
selected = [Base.metadata.tables[name] for name in TABLES]
Base.metadata.create_all(engine, tables=selected)
from app.main import app
from app.security import get_usuario_atual
from app.rate_limit import limiter
from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, StrictInt
from app.services.checkout_offer_order_composition import CheckoutOfferOrderComposer
from app.services.checkout_offer_one_time_dispatch import CheckoutOfferOneTimeDispatcher
from app.services.checkout_offer_one_time_application import CheckoutOfferOneTimeApplication
from app.services.checkout_offer_one_time_confirmation import CheckoutOfferOneTimeConfirmer
from app.routers.checkout_offer_one_time_router import criar_checkout_offer_one_time_router
import app.routes.imposto_router as imposto_router

with SessionLocal() as db:
    offer = models.CheckoutOffer(
        codigo='mei-das-one-time-company', nome_publico='SIMULACAO LOCAL - DAS',
        vertical='tax', commercial_model='one_time', subject_type='company',
        estado='published', moeda='BRL', preco=Decimal('39.90'),
        billing_period=None, usage_unit='competence', usage_limit=1,
        contract_version=1,
    )
    offer.capabilities = [models.CheckoutOfferCapability(codigo='mei.das')]
    db.add(offer)
    db.commit()

class Gateway:
    def __init__(self):
        self.calls = []
    def criar_cobranca(self, **data):
        self.calls.append(data)
        number = data['ordem_id']
        return {'provider_order_id': f'local-pref-{number}',
                'checkout_url': f'https://checkout.example.invalid/local/{number}'}
    def cancelar_cobranca(self, **data):
        raise RuntimeError('UNEXPECTED_COMPENSATION')

PDF = b'%PDF-1.7\n% SIMULACAO LOCAL - SEM VALIDADE FISCAL\n%%EOF\n'
BARCODE = ['858900000008', '860503282026', '608201234567', '890123456789']
class Serpro:
    def __init__(self):
        self.calls = []
    def request(self, servico, cnpj, competencia):
        assert cnpj == '12345678000195'
        assert servico in ('GERARDASPDF21', 'GERARDASCODBARRA22')
        self.calls.append((servico, cnpj, competencia))
        detail = {'periodoApuracao': competencia,
                  'numeroDocumento': '12345678901234567',
                  'dataVencimento': '20260820', 'dataLimiteAcolhimento': '20260820',
                  'valores': {'principal': 86.05, 'multa': 0.0, 'juros': 0.0, 'total': 86.05}}
        document = {'cnpjCompleto': cnpj}
        if servico == 'GERARDASPDF21':
            document.update(pdf=base64.b64encode(PDF).decode(), detalhamento=detail)
        else:
            detail['codigoDeBarras'] = BARCODE
            document['detalhamento'] = [detail]
        return SimpleNamespace(data=json.dumps([document]),
                               messages=[{'codigo': 'INFO', 'texto': 'SIMULACAO LOCAL'}])

gateway, serpro = Gateway(), Serpro()
application = CheckoutOfferOneTimeApplication(
    CheckoutOfferOrderComposer(SessionLocal),
    CheckoutOfferOneTimeDispatcher(SessionLocal, gateway),
)
app.include_router(criar_checkout_offer_one_time_router(
    application_service=application, current_user_dependency=get_usuario_atual))
# Provider composition is replaced only in this test process. Authority is untouched.
imposto_router._get_serpro_pgmei_client.cache_clear()
imposto_router._get_serpro_pgmei_client = lambda: serpro
app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:5175'],
                   allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

class Payment(BaseModel):
    ordem_id: StrictInt

@app.post('/__smoke__/reset-rate-limit')
def reset_rate_limit(user=Depends(get_usuario_atual)):
    # Independent viewport scenarios should not consume each other's DAS budget.
    # This package does not verify throttle/rate-limit behavior.
    limiter.reset()
    return {'reset': True}

@app.post('/__smoke__/confirm')
def confirm(body: Payment, user=Depends(get_usuario_atual)):
    with SessionLocal() as db:
        order = db.get(models.OrdemCheckout, body.ordem_id)
        if order is None or order.user_id != user.id:
            raise HTTPException(404)
        if order.offer_code != 'mei-das-one-time-company':
            raise HTTPException(409)
        assert any(call['ordem_id'] == order.id for call in gateway.calls)
    result = CheckoutOfferOneTimeConfirmer(SessionLocal).confirmar_pagamento_autorizado(
        body.ordem_id, str(800000000000 + body.ordem_id),
        str(900000000000 + body.ordem_id), Decimal('39.90'), 'BRL')
    return {'estado': result.estado}

@app.get('/__smoke__/stats')
def stats(user=Depends(get_usuario_atual)):
    with SessionLocal() as db:
        orders = db.query(models.OrdemCheckout).filter_by(user_id=user.id).all()
        ids = [order.id for order in orders]
        bindings = db.query(models.MeiCompetenciaAuthorityBinding).filter(
            models.MeiCompetenciaAuthorityBinding.ordem_id.in_(ids)).count()
        return {'orders': len(orders), 'bindings': bindings,
                'gateway_calls': len(gateway.calls), 'serpro_calls': len(serpro.calls)}

from datetime import date
@app.post('/__smoke__/documental-seed')
def seed_documents(user=Depends(get_usuario_atual)):
    with SessionLocal() as db:
        company = db.query(models.Empresa).filter_by(user_id=user.id).one()
        if db.query(models.DocumentoFiscal).filter_by(empresa_id=company.id).count():
            raise HTTPException(409)
        documents = []
        for emitted in [date(2026, 1, 1), date(2025, 12, 31), None]:
            document = models.DocumentoFiscal(empresa_id=company.id, usuario_id=user.id,
                data_emissao=emitted, tipo='saida', valor_total=100.0,
                cnpj_emitente='12345678000195' if emitted == date(2026, 1, 1)
                else '11222333000181' if emitted is not None else None)
            db.add(document)
            documents.append(document)
        db.flush()
        ids = [document.id for document in documents]
        db.commit()
        return {'year2026': ids[0], 'year2025': ids[1], 'undated': ids[2]}

print('TEST_ONLY_BACKEND: localhost; real providers OFF; synthetic fiscal identity', flush=True)
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=8766, log_level='info')
