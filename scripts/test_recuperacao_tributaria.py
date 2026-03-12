from app.services.tax_engines.tax_recovery_engine import TaxRecoveryEngine


dados = {
    "icms_pago": 25000,
    "icms_devido": 18000
}

engine = TaxRecoveryEngine()
resultado = engine.execute(dados)

print(resultado)
