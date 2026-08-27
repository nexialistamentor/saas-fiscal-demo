from app.services.insights_engine import executar_engines
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_executar_engines_uses_a_fresh_mei_engine_instance_per_call(monkeypatch):
    marker = "_insights_engine_instance_isolation_test_marker"
    sentinel = object()
    observed_calls = []

    def execute_instrumented(self, context):
        observed_calls.append((self, context))
        if len(observed_calls) == 1:
            setattr(self, marker, True)
        else:
            assert not hasattr(self, marker), (
                "executar_engines reused the MEITaxEngine instance from the first call"
            )
        return sentinel

    monkeypatch.setattr(MEITaxEngine, "execute", execute_instrumented)
    context = {"regime": "mei"}

    try:
        first_results = executar_engines(dict(context))
        second_results = executar_engines(dict(context))

        assert len(observed_calls) == 2
        first_instance, _first_context = observed_calls[0]
        second_instance, _second_context = observed_calls[1]
        assert first_instance is not second_instance
        assert hasattr(first_instance, marker)
        assert not hasattr(second_instance, marker)
        assert first_results["mei_tax"] is sentinel
        assert second_results["mei_tax"] is sentinel
    finally:
        for instance, _context in observed_calls:
            if hasattr(instance, marker):
                delattr(instance, marker)
