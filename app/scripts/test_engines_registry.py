from app.services.engine_registry import ENGINES

context = {
    "faturamento": 100000,
    "custos": 60000,
    "lucro": 40000,
    "atividade": "comercio",
    "icms_pago": 25000,
    "icms_devido": 18000
}

print("\nTESTE DE EXECUÇÃO DAS ENGINES\n")

for nome, engine in ENGINES.items():
    try:
        resultado = engine.execute(context)
        print(f"{nome}: OK -> {resultado}")
    except Exception as e:
        print(f"{nome}: ERRO -> {e}")
