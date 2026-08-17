from app.services.engine_registry import ENGINE_REGISTRY
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_engine_registry_uses_a_fresh_mei_engine_instance_per_execution(monkeypatch):
    marker = "_engine_instance_isolation_test_marker"
    original_execute = MEITaxEngine.execute
    observed_instances = []

    def execute_instrumented(self, context):
        observed_instances.append(self)
        if len(observed_instances) == 1:
            setattr(self, marker, True)
        else:
            assert not hasattr(self, marker), (
                "ENGINE_REGISTRY reused the MEITaxEngine instance from the first execution"
            )
        return original_execute(self, context)

    monkeypatch.setattr(MEITaxEngine, "execute", execute_instrumented)
    execute_mei_tax = ENGINE_REGISTRY["mei_tax"]["v1"]
    context = {
        "faturamento": 1_000,
        "atividade": "servicos",
        "ano_referencia": 2025,
    }

    try:
        execute_mei_tax(context)
        execute_mei_tax(context)
    finally:
        for instance in observed_instances:
            if hasattr(instance, marker):
                delattr(instance, marker)
