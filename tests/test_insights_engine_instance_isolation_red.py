from app.services.insights_engine import executar_engines
from app.services.tax_engines.mei_tax_engine import MEITaxEngine


def test_executar_engines_uses_a_fresh_mei_engine_instance_per_call(monkeypatch):
    marker = "_insights_engine_instance_isolation_test_marker"
    original_execute = MEITaxEngine.execute
    observed_instances = []

    def execute_instrumented(self, context):
        observed_instances.append(self)
        if len(observed_instances) == 1:
            setattr(self, marker, True)
        else:
            assert not hasattr(self, marker), (
                "executar_engines reused the MEITaxEngine instance from the first call"
            )
        return original_execute(self, context)

    monkeypatch.setattr(MEITaxEngine, "execute", execute_instrumented)
    context = {
        "regime": "mei",
        "faturamento": 1_000,
        "atividade": "servicos",
        "ano_referencia": 2025,
    }

    try:
        executar_engines(dict(context))
        second_results = executar_engines(dict(context))

        assert "erro" not in second_results["mei_tax"], second_results["mei_tax"][
            "erro"
        ]
    finally:
        for instance in observed_instances:
            if hasattr(instance, marker):
                delattr(instance, marker)
