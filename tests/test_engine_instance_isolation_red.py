from app.services.engine_registry import ENGINE_REGISTRY
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_engine_registry_uses_a_fresh_mei_engine_instance_per_execution(monkeypatch):
    marker = "_engine_instance_isolation_test_marker"
    sentinel = object()
    observed_calls = []

    def execute_instrumented(self, context):
        observed_calls.append((self, context))
        if len(observed_calls) == 1:
            setattr(self, marker, True)
        else:
            assert not hasattr(self, marker), (
                "ENGINE_REGISTRY reused the MEITaxEngine instance from the first execution"
            )
        return sentinel

    monkeypatch.setattr(MEITaxEngine, "execute", execute_instrumented)
    execute_mei_tax = ENGINE_REGISTRY["mei_tax"]["v1"]
    context = {
        "faturamento": 1_000,
        "atividade": "servicos",
        "ano_referencia": 2025,
    }

    try:
        results = [execute_mei_tax(context), execute_mei_tax(context)]

        assert len(observed_calls) == 2
        first_instance, first_context = observed_calls[0]
        second_instance, second_context = observed_calls[1]
        assert first_instance is not second_instance
        assert hasattr(first_instance, marker)
        assert not hasattr(second_instance, marker)
        assert first_context is context
        assert second_context is context
        assert results == [sentinel, sentinel]
    finally:
        for instance, _context in observed_calls:
            if hasattr(instance, marker):
                delattr(instance, marker)
